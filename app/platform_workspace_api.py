"""Company-bound presentation, review and configuration APIs, using existing stores."""
import csv
from datetime import datetime
from io import StringIO
from typing import Literal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Query, File, UploadFile
from fastapi.responses import Response
from pydantic import Field
from persiantools.jdatetime import JalaliDate
from .platform_identity import principal
from .platform_sales_api import StrictInput
from .company_context import ReportAccess, personal_owner
from .forecast_views import SavedView
from .sales_demand import SCHEMAS, export_demand, StaleOrderRevision
from .actuals import export_actuals
from .units import STANDARD
from .forecast_orders import context
from .live_sources import SourceConfig, SourcePermission, SourceError


class SiteSettings(StrictInput):
    name: str = Field(min_length=2,max_length=120)
    province: str = Field(min_length=2,max_length=100)
    timezone: str = Field(min_length=2,max_length=80)


class TableSettings(StrictInput):
    sheet: str | None = None
    header_row: int = Field(default=1,ge=1,le=10000)


class ForecastSettings(StrictInput):
    horizon: int = Field(ge=1,le=24)
    month_basis: Literal['gregorian','jalali']
    calendar_country: str = Field(default='IR',max_length=2)
    request_id: str = Field(min_length=8,max_length=100)


def install_platform_workspace(api, workspaces, dispatcher=None):
    router=APIRouter()
    if dispatcher is None:
        from .company_jobs import dispatch
        dispatcher=dispatch

    def ws(request,*scopes):
        who=principal(request)
        for scope in scopes:principal(request,scope)
        if workspaces is None:raise HTTPException(503,'Company storage is not configured.')
        return workspaces.for_principal(who)

    def call(fn,missing=False):
        try:return fn()
        except SourceError as exc:raise HTTPException(400,str(exc)) from None
        except StaleOrderRevision as exc:raise HTTPException(409,str(exc)) from None
        except (ValueError,KeyError,TypeError) as exc:
            raise HTTPException(404 if missing else 400,str(exc)) from None

    def reports(request):
        return ReportAccess(ws(request,'reports:read'),principal(request))

    def file(request,key,write=False):
        w=ws(request)
        source,content=call(lambda:w.datasets.source(key),True)
        scope='orders' if source['role'].startswith('sales_') else 'factors' if source['role']=='factor_observations' else 'inputs'
        principal(request,scope+(':write' if write else ':read'))
        return w,source,content

    @router.get('/workspace',tags=['Workspace'])
    def workspace(request:Request):
        w=ws(request)
        today=datetime.now(ZoneInfo(w.site['timezone'])).date()
        return {'site':w.site,'today':str(today),'jalali_today':str(JalaliDate(today))}

    @router.put('/settings/site',tags=['Settings'])
    def site(body:SiteSettings,request:Request):
        return {'site':call(lambda:ws(request,'settings:manage').save_site(body.model_dump()))}

    @router.get('/units',tags=['Settings'])
    def units(request:Request):
        return {'versions':ws(request,'inputs:read').units.list(),'standard_labels':list(STANDARD)}

    @router.post('/units',status_code=201,tags=['Settings'])
    def save_units(body:dict,request:Request):
        return call(lambda:ws(request,'settings:manage').units.save(body))

    @router.post('/customers/imports/preview',tags=['Customers'])
    async def preview_customers(request:Request,file:UploadFile=File(...)):
        from .customers import parse_customers
        import io
        from pathlib import Path
        import pandas as pd
        ws(request,'customers:write')
        raw=await file.read(5*1024*1024+1)
        if not raw or len(raw)>5*1024*1024:raise HTTPException(413,'Use a non-empty customer file smaller than 5 MB.')
        def inspect():
            suffix=Path(file.filename or '').suffix.lower()
            if suffix=='.csv':rows=list(csv.DictReader(StringIO(raw.decode('utf-8-sig'))))
            elif suffix=='.xlsx':rows=pd.read_excel(io.BytesIO(raw),dtype=str,keep_default_na=False,nrows=20001).to_dict('records')
            else:raise ValueError('Choose a CSV or XLSX file.')
            if len(rows)>20000:raise ValueError('Use at most 20,000 product rows per file.')
            return parse_customers([{str(k).strip().lower():v for k,v in row.items()} for row in rows]).model_dump()
        return call(inspect)

    @router.post('/customers/imports',status_code=201,tags=['Customers'])
    def import_customers(body:dict,request:Request):
        from .customers import CustomerBatch
        w=ws(request,'customers:write')
        return call(lambda:w.customers.save(CustomerBatch.model_validate(body).customers))

    @router.get('/customers/{customer_id}/factor-profiles',tags=['Customer factors'])
    def profiles(customer_id:str,request:Request):
        from .factor_profiles import FactorProfiles
        w=ws(request,'customers:read','factors:read')
        return call(lambda:w.store('profiles',lambda:FactorProfiles(w.customers)).listing(customer_id),True)

    @router.put('/customers/{customer_id}/factor-profiles',tags=['Customer factors'])
    def save_profile(customer_id:str,body:dict,request:Request):
        from .factor_profiles import FactorProfiles,ProfileChange
        w=ws(request,'customers:write','factors:write')
        return call(lambda:w.store('profiles',lambda:FactorProfiles(w.customers)).save(customer_id,ProfileChange.model_validate(body).model_dump()))

    @router.post('/sources/{source_id}/preview',tags=['Sales inputs'])
    def preview_file(source_id:str,body:TableSettings,request:Request):
        from .inventory import inventory_preview
        _,source,content=file(request,source_id)
        return call(lambda:inventory_preview(source['name'],content,body.sheet,body.header_row))

    @router.post('/sources/{source_id}/sheet',status_code=201,tags=['Sales inputs'])
    def choose_sheet(source_id:str,body:TableSettings,request:Request):
        w,source,content=file(request,source_id,True)
        # A sheet selection is a new immutable source, not a change to old evidence.
        return call(lambda:w.datasets.upload(source['name'],content,source['role'],body.sheet))

    @router.post('/datasets/{dataset_id}/forecast-settings',status_code=201,tags=['Sales inputs'])
    def forecast_settings(dataset_id:str,body:ForecastSettings,request:Request):
        w=ws(request,'inputs:read','inputs:write')
        value=call(lambda:w.datasets.get(dataset_id),True)
        if value.get('scenario_provenance') or value['sources'].get('operations'):
            raise HTTPException(400,'Choose original sales inputs.')
        settings={**value['settings'],**body.model_dump(exclude={'request_id'})}
        if settings==value['settings']:return value
        return call(lambda:w.datasets.save(value['name'],value['sources'],settings,value['classification'],True,
            parent_dataset_id=value['id'],request_id=body.request_id))

    @router.get('/orders/schema',tags=['Orders'])
    def order_schema(request:Request):
        ws(request,'orders:read')
        return {key:{name:{'required':field.is_required()} for name,field in model.model_fields.items()} for key,model in SCHEMAS.items()}

    @router.get('/datasets/{dataset_id}/orders/template/{role}',tags=['Orders'])
    def template(dataset_id:str,role:Literal['customers','orders','commitments'],request:Request):
        from .sales_api import template_customers
        w=ws(request,'orders:read','inputs:read')
        run=call(lambda:context(w.datasets,dataset_id,site=w.site),True)
        output=StringIO();writer=csv.DictWriter(output,fieldnames=list(SCHEMAS[role].model_fields));writer.writeheader()
        if role=='customers':
            for row in template_customers(run):writer.writerow({k:"'"+v if v.lstrip().startswith(('=','+','-','@')) else v for k,v in row.items()})
        return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{role}.csv"'})

    @router.get('/runs',tags=['Forecast results'])
    def runs(request:Request,limit:int=Query(100,ge=1,le=1000),offset:int=Query(0,ge=0)):
        access=reports(request);values=[]
        for value in access.ws.list_runs():
            if not access.drafts:
                try:access.approved(value['run_id'])
                except HTTPException:continue
            values.append({'run_id':value['run_id'],'name':value.get('forecast_name') or value.get('dataset_name') or 'Forecast',
                'created_at':value.get('issued_at',''),**{k:value.get(k) for k in ('base_run_id','dataset_id','scenario_name',
                'summary','metrics','forecast_group_id','forecast_name','method_selection','forecast_order_inputs_id','sales_input_snapshot_id','unit')}})
        return {'runs':values[offset:offset+limit],'total':len(values),'offset':offset,'limit':limit}

    @router.get('/runs/{run_id}/orders/starter',tags=['Orders'])
    def order_starter(run_id:str,request:Request):
        from .sales_api import template_customers
        from .sales_demand import run_today
        access=reports(request);principal(request,'orders:write')
        run=access.run(run_id);today=str(run_today(run))
        return {'name':'Customer demand plan','run_id':run_id,'as_of':today,'valid_until':today,
                'classification':run.get('source_classification','user_provided'),
                'order_feed':'unknown','customers':template_customers(run),'orders':[],
                'commitments':[],'reviewed':False,'note':''}

    @router.get('/runs/{run_id}/orders/template/{role}',tags=['Orders'])
    def run_order_template(run_id:str,role:Literal['customers','orders','commitments'],request:Request):
        from .sales_api import template_customers
        principal(request,'orders:read');run=reports(request).run(run_id)
        output=StringIO();writer=csv.DictWriter(output,fieldnames=list(SCHEMAS[role].model_fields));writer.writeheader()
        if role=='customers':
            for row in template_customers(run):writer.writerow({k:"'"+v if v.lstrip().startswith(('=','+','-','@')) else v for k,v in row.items()})
        return Response(output.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{role}.csv"'})

    @router.get('/jobs',tags=['Forecast jobs'])
    def jobs(request:Request):
        w=ws(request,'drafts:read')
        return {'jobs':[{k:v for k,v in job.items() if k not in {'owner','heartbeat_at','request_id'}} for job in w.jobs.list()],
                'worker_available':w.jobs.worker_available()}

    @router.post('/jobs/{job_id}/retry',status_code=202,tags=['Forecast jobs'])
    def retry(job_id:str,body:dict,request:Request):
        w=ws(request,'forecasts:run','forecasts:write','inputs:read','orders:read','factors:read')
        old=call(lambda:w.jobs.get(job_id),True)
        if old['state'] not in {'failed','interrupted','cancelled'}:raise HTTPException(409,'Only stopped calculations can be retried.')
        from .forecast_orders import reviewed
        payload=old['payload']
        request_id=body.get('request_id')
        if not isinstance(request_id,str) or not 8<=len(request_id)<=100:raise HTTPException(400,'A retry identifier is required.')
        if not payload.get('sales_input_id'):
            for scope in ('inputs:write','factors:write'):principal(request,scope)
            from .company_workflows import submit_draft,schedule_authorized
            values=dict(payload);owner=values.pop('_schedule_owner',None)
            if owner:
                principal(request,'settings:manage')
                # Retry must not detach a scheduled job from its live owner grant.
                from .main import ACCESS
                if not schedule_authorized(ACCESS.identity_service,w,owner):raise HTTPException(403,'Schedule authorization is unavailable.')
            return call(lambda:submit_draft(w,dispatcher,values,old['name'],request_id,schedule_owner=owner,retry_of=job_id))
        call(lambda:reviewed(w.datasets,w.sales,payload['dataset_id'],payload['sales_input_id'],site=w.site))
        job=call(lambda:w.jobs.create(payload,old['name'],request_id,retry_of=job_id))
        dispatcher(w,job['id'])
        return {k:v for k,v in job.items() if k not in {'owner','heartbeat_at','request_id'}}

    @router.get('/runs/{run_id}/order-snapshots',tags=['Forecast results'])
    def snapshots(run_id:str,request:Request):
        access=reports(request);access.run(run_id)
        rows=access.ws.sales.list(run_id)
        if not access.drafts:rows=[r for r in rows if r['id']==access.approved(run_id)['snapshot_id']]
        return {'snapshots':[{'id':row['id'],'name':row['inputs']['name'],'as_of':row['inputs']['as_of'],
                             'created_at':row['created_at']} for row in rows]}

    @router.get('/order-snapshots/{snapshot_id}/demand',tags=['Forecast results'])
    def snapshot_demand(snapshot_id:str,request:Request):
        return reports(request).outlook(snapshot_id)

    def prepare_orders(run_id,body,request):
        from .sales_api import prepare_sales_inputs
        from .demand_comparison import digest
        w=ws(request,'orders:read','orders:write','drafts:read')
        if body.get('inputs',{}).get('run_id')!=run_id:raise HTTPException(400,'Choose matching forecast and orders.')
        values=call(lambda:prepare_sales_inputs(w.sales,w.datasets,w.load_run,body))
        token=digest({'inputs':values[0],'run':values[1],'evidence':values[2],'base':body.get('base_snapshot_id')})
        return w,values,token

    @router.post('/runs/{run_id}/order-snapshots/preview',tags=['Orders'])
    def preview_run_orders(run_id:str,body:dict,request:Request):
        _,values,token=prepare_orders(run_id,body,request)
        return {**values[3],'review_token':token}

    @router.post('/runs/{run_id}/order-snapshots',status_code=201,tags=['Orders'])
    def save_run_orders(run_id:str,body:dict,request:Request):
        w,values,token=prepare_orders(run_id,body,request)
        if body.get('review_token')!=token:raise HTTPException(409,'Inputs changed. Review the orders again.')
        from .demand_releases import identity
        result=call(lambda:w.sales.save(values[0],values[1],body.get('request_id'),
            identity(principal(request)),values[2],body.get('base_snapshot_id')))
        return result

    @router.get('/order-snapshots/{snapshot_id}/export',tags=['Forecast results'])
    def snapshot_export(snapshot_id:str,request:Request,mode:Literal['remaining_forecast','combined_demand'],kind:Literal['csv','xlsx','json']='xlsx',customer:str='',sku:str='',period:str=''):
        principal(request,'reports:export');access=reports(request)
        value=access.outlook(snapshot_id)
        if not access.drafts:
            record=access.approved(value['run_id'],snapshot_id)
            if mode!=record['contract']['mode']:raise HTTPException(403,'Use the approved report export policy.')
        value['rows']=[r for r in value['rows'] if (not customer or r['customer']==customer) and (not sku or r['sku']==sku) and (not period or r['period'][:7]==period[:7])]
        if not value['rows']:raise HTTPException(400,'No rows match these filters.')
        content,mime=call(lambda:export_demand(value,mode,kind))
        return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="demand-{snapshot_id}.{kind}"'})

    def view_check(request,body):
        access=reports(request);access.run(body.run_id)
        if access.snapshot(body.snapshot_id)['inputs']['run_id']!=body.run_id:raise HTTPException(400,'Choose matching forecast and orders.')
        principal(request,'views:own')
        return access.ws.views,personal_owner(principal(request))

    @router.get('/views',tags=['Personal views'])
    def views(run_id:str,request:Request):
        principal(request,'views:own');access=reports(request);access.run(run_id)
        rows=access.ws.views.list(personal_owner(principal(request)),run_id)
        visible=[]
        for row in rows:
            try:access.snapshot(row['snapshot_id'])
            except HTTPException:continue
            visible.append(row)
        return {'views':visible}

    @router.post('/views',status_code=201,tags=['Personal views'])
    def create_view(body:SavedView,request:Request):
        store,owner=view_check(request,body)
        return call(lambda:store.save(owner,body))

    @router.get('/views/{view_id}',tags=['Personal views'])
    def get_view(view_id:str,request:Request):
        principal(request,'views:own');w=ws(request);owner=personal_owner(principal(request))
        value=call(lambda:w.views.get(owner,view_id),True);view_check(request,SavedView(**{k:v for k,v in value.items() if k!='id'}))
        return value

    @router.put('/views/{view_id}',tags=['Personal views'])
    def update_view(view_id:str,body:SavedView,request:Request):
        store,owner=view_check(request,body)
        return call(lambda:store.update(owner,view_id,body),True)

    @router.delete('/views/{view_id}',tags=['Personal views'])
    def delete_view(view_id:str,request:Request):
        principal(request,'views:own')
        return call(lambda:ws(request).views.delete(personal_owner(principal(request)),view_id),True)

    @router.get('/runs/{run_id}/actuals',tags=['Actual results'])
    def actuals(run_id:str,request:Request):
        access=reports(request);access.run(run_id)
        return {'evaluations':access.ws.actuals.list(run_id)}

    def actual_input(run_id,body,request):
        w=ws(request,'inputs:read','inputs:write','drafts:read')
        if body.get('plan_id'):raise HTTPException(400,'Company comparisons use the saved forecast, not legacy plans.')
        run=call(lambda:w.load_run(run_id),True)
        _,source,_=file(request,body.get('source_id',''))
        if source['role']!='actuals':raise HTTPException(400,'Choose actual results.')
        return w,run

    @router.post('/runs/{run_id}/actuals/preview',tags=['Actual results'])
    def preview_actuals(run_id:str,body:dict,request:Request):
        w,run=actual_input(run_id,body,request);value=call(lambda:w.actuals.inspect(body,run))
        return {**value,'rows':value['rows'][:30]}

    @router.post('/runs/{run_id}/actuals',status_code=201,tags=['Actual results'])
    def save_actuals(run_id:str,body:dict,request:Request):
        w,run=actual_input(run_id,body,request)
        return call(lambda:w.actuals.save(body,run))

    @router.get('/actuals/{evaluation_id}',tags=['Actual results'])
    def actual_result(evaluation_id:str,request:Request):
        access=reports(request);value=call(lambda:access.ws.actuals.get(evaluation_id),True)
        access.run(value['run_id'])
        return value

    @router.get('/actuals/{evaluation_id}/export',tags=['Actual results'])
    def export_actual(evaluation_id:str,request:Request):
        principal(request,'reports:export');value=actual_result(evaluation_id,request)
        return Response(export_actuals(value),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="actual-results.csv"'})

    @router.get('/connections/external-sources',tags=['External data connections'])
    def live_sources(request:Request):
        return ws(request,'connections:read','factors:read').live_sources.listing()

    @router.put('/connections/external-sources/{key}',tags=['External data connections'])
    def configure_source(key:str,body:SourceConfig,request:Request):
        return call(lambda:ws(request,'connections:manage').live_sources.configure(key,body.enabled))

    @router.put('/connections/external-sources/{key}/permission',tags=['External data connections'])
    def permission(key:str,body:SourcePermission,request:Request):
        return call(lambda:ws(request,'connections:manage').live_sources.permission(key,body.confirmed,body.reference))

    @router.post('/connections/external-sources/{key}/refresh',tags=['External data connections'])
    def refresh_source(key:str,request:Request,background:BackgroundTasks):
        store=ws(request,'connections:sync','factors:write').live_sources
        if call(lambda:store.queue_refresh(key)):background.add_task(store.background_refresh,key)
        return store.state(key)

    @router.put('/connections/external-sources/servix/credential',tags=['External data connections'])
    async def source_credential(request:Request):
        # Bounded, private interactive setup; credentials never enter OpenAPI validation errors.
        import json
        from starlette.concurrency import run_in_threadpool
        principal(request,'connections:manage',interactive=True)
        store=ws(request).live_sources;raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>8192:raise HTTPException(413,'Credential request is too large.')
        try:
            value=json.loads(raw)
            if not isinstance(value,dict) or set(value)!={'key'} or not isinstance(value['key'],str):raise ValueError
        except (ValueError,UnicodeDecodeError):raise HTTPException(400,'Provide one private API key.') from None
        return await run_in_threadpool(lambda:call(lambda:store.setup_key(value['key'])))

    api.include_router(router)

    # The root application also installs these handlers: mounted apps do not
    # automatically receive startup/shutdown events from Starlette.
    @api.on_event('startup')
    def start_sources():
        if workspaces is None:return
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler=BackgroundScheduler()
        scheduler.add_job(workspaces.refresh_sources,'interval',minutes=15,max_instances=1,coalesce=True)
        scheduler.start()
        api.state.source_scheduler=scheduler

    @api.on_event('shutdown')
    def stop_sources():
        scheduler=getattr(api.state,'source_scheduler',None)
        if scheduler:scheduler.shutdown(wait=False)

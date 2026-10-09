"""Scoped workflow routes; reuse existing review gates and numerical engines."""
import json
from typing import Literal
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import Response
from pydantic import Field
from .platform_identity import principal
from .platform_sales_api import StrictInput
from .company_context import personal_owner
from .company_workflows import monthly,recurring,submit_draft
from .monthly_refresh import StartUpdate,UpdateStep
from .recurring_forecasts import RecurringConfig
from .sales_demand import export_demand,StaleOrderRevision


class ScenarioJob(StrictInput):
    dataset_id:str=Field(pattern=r'^[a-f0-9]{32}$')
    base_run_id:str|None=None
    method:None=None
    adjustment:Literal[0]=0
    scenario_name:None=None
    request_id:str=Field(min_length=8,max_length=100)


def install_platform_workflows(api,workspaces,dispatcher,service):
    router=APIRouter()
    if dispatcher is None:
        from .company_jobs import dispatch
        dispatcher=dispatch

    def ws(request,*scopes):
        who=principal(request)
        for scope in scopes:principal(request,scope)
        if workspaces is None:raise HTTPException(503,'Company storage is not configured.')
        return workspaces.for_principal(who)

    def safe(work,missing=False):
        try:return work()
        except StaleOrderRevision as exc:raise HTTPException(409,str(exc)) from None
        except (ValueError,KeyError,TypeError) as exc:raise HTTPException(404 if missing else 400,str(exc)) from None

    def draft(request,write=False):
        w=ws(request,'reports:read','drafts:read','inputs:read','factors:read')
        if write:
            for scope in ('inputs:write','factors:write','forecasts:run'):principal(request,scope)
        return w

    def refresh(request,write=False):
        w=draft(request,write)
        principal(request,'orders:read')
        return monthly(w,dispatcher),personal_owner(principal(request))

    def schedules(request):
        w=draft(request,True)
        principal(request,'settings:manage');principal(request,'orders:read')
        if principal(request)['role']!='admin':raise HTTPException(403,'Administrator access required.')
        return recurring(w,dispatcher,service),personal_owner(principal(request))

    @router.get('/runs/{run_id}/factor-links',tags=['Scenarios'])
    def links(run_id:str,request:Request):
        from .factor_links import choices
        w=draft(request)
        return safe(lambda:choices(w.load_run(run_id),w.datasets,w.factors),True)

    @router.post('/runs/{run_id}/factor-links/preview',tags=['Scenarios'])
    def preview_links(run_id:str,body:dict,request:Request):
        from .factor_links import preview_link
        w=draft(request)
        return safe(lambda:preview_link(w.load_run(run_id),w.datasets,w.factors,body,w.live_sources,w.profiles))

    @router.post('/runs/{run_id}/factor-links',status_code=201,tags=['Scenarios'])
    def save_links(run_id:str,body:dict,request:Request):
        from .factor_links import save_link
        w=draft(request,True)
        return safe(lambda:save_link(w.load_run(run_id),w.datasets,w.factors,body,w.live_sources,w.profiles))

    @router.post('/runs/{run_id}/factor-preparation',tags=['Scenarios'])
    def preparation(run_id:str,body:dict,request:Request):
        from .factor_preparation import preparation_report
        w=draft(request)
        return safe(lambda:preparation_report(w.load_run(run_id),w.datasets,w.factors,w.live_sources,body,w.profiles))

    @router.get('/runs/{run_id}/factor-profiles',tags=['Scenarios'])
    def profiles(run_id:str,request:Request):
        w=draft(request);principal(request,'customers:read')
        return safe(lambda:w.profiles.for_run(w.load_run(run_id)),True)

    @router.post('/runs/{run_id}/factor-batch/preview',tags=['Scenarios'])
    def preview_batch(run_id:str,body:dict,request:Request):
        from .factor_batch import preview_batch
        w=draft(request)
        return safe(lambda:preview_batch(w.load_run(run_id),w.datasets,w.factors,body,w.live_sources,w.profiles))

    @router.post('/runs/{run_id}/factor-batch',status_code=201,tags=['Scenarios'])
    def save_batch(run_id:str,body:dict,request:Request):
        from .factor_batch import save_batch
        w=draft(request,True)
        return safe(lambda:save_batch(w.load_run(run_id),w.datasets,w.factors,body,w.live_sources,w.profiles))

    @router.get('/runs/{run_id}/factors',tags=['Scenarios'])
    def factor_review(run_id:str,request:Request):
        from .factor_review import review_factors
        w=draft(request)
        return safe(lambda:review_factors(w.load_run(run_id),w.datasets),True)

    @router.post('/runs/{run_id}/factor-comparison',status_code=201,tags=['Scenarios'])
    def factor_comparison(run_id:str,body:dict,request:Request):
        from .factor_review import save_factor_comparison
        w=draft(request,True)
        return safe(lambda:save_factor_comparison(w.load_run(run_id),w.datasets,body))

    @router.post('/scenario-jobs',status_code=202,tags=['Scenarios'])
    def scenario_job(body:ScenarioJob,request:Request):
        w=draft(request,True)
        source=safe(lambda:w.datasets.get(body.dataset_id),True)
        proof=source.get('scenario_provenance')
        if not proof:raise HTTPException(400,'Use New forecast for a baseline; this route calculates reviewed factor comparisons only.')
        values=body.model_dump(exclude={'request_id'})
        values['base_run_id']=body.base_run_id or proof['base_run_id']
        return safe(lambda:submit_draft(w,dispatcher,values,source['name'],body.request_id))

    @router.get('/runs/{run_id}/order-reuse/choices',tags=['Order comparisons'])
    def reuse_choices(run_id:str,request:Request):
        from .ai_order_reuse import AssistantOrderReuse
        w=draft(request);principal(request,'orders:read')
        def choices():
            result=AssistantOrderReuse(w.sales,w.load_run,lambda:{'runs':[dict(r,name=r.get('dataset_name','Forecast')) for r in w.list_runs()]},w.load_run(run_id)).choices()
            # UI picker contract uses id; assistant tools retain snapshot_id.
            result['sources']=[dict(row,id=row['snapshot_id']) for row in result['sources']]
            return result
        return safe(choices,True)

    @router.post('/runs/{run_id}/order-reuse/preview',tags=['Order comparisons'])
    def reuse_preview(run_id:str,body:dict,request:Request):
        from .order_reuse import preview_reuse
        w=draft(request);principal(request,'orders:read')
        return safe(lambda:preview_reuse(w.sales,w.load_run,run_id,body.get('snapshot_id',''))[0])

    @router.post('/runs/{run_id}/order-reuse',status_code=201,tags=['Order comparisons'])
    def reuse_save(run_id:str,body:dict,request:Request):
        from .order_reuse import save_reuse
        w=draft(request);principal(request,'orders:write')
        return safe(lambda:save_reuse(w.sales,w.load_run,run_id,body,personal_owner(principal(request))))

    @router.post('/runs/{run_id}/order-comparison/preview',tags=['Order comparisons'])
    def compare_preview(run_id:str,body:dict,request:Request):
        from .demand_comparison import compare_orders
        w=draft(request);principal(request,'orders:read')
        return safe(lambda:compare_orders(w.sales,w.load_run,run_id,body.get('snapshot_id',''))[0])

    @router.post('/runs/{run_id}/order-comparison',status_code=201,tags=['Order comparisons'])
    def compare_save(run_id:str,body:dict,request:Request):
        from .demand_comparison import save_comparison
        w=draft(request);principal(request,'orders:write')
        return safe(lambda:save_comparison(w.sales,w.load_run,run_id,body,personal_owner(principal(request))))

    @router.get('/forecast-updates',tags=['Monthly updates'])
    def updates(request:Request):
        store,owner=refresh(request)
        return {'updates':store.listing(owner)}

    @router.post('/forecast-updates',status_code=201,tags=['Monthly updates'])
    def start_update(body:StartUpdate,request:Request):
        store,owner=refresh(request,True)
        return safe(lambda:store.view(store.start(owner,body)))

    @router.get('/forecast-updates/{key}',tags=['Monthly updates'])
    def get_update(key:str,request:Request):
        store,owner=refresh(request)
        return safe(lambda:store.view(store.get(key,owner)),True)

    @router.post('/forecast-updates/{key}/steps',tags=['Monthly updates'])
    def update_step(key:str,body:UpdateStep,request:Request):
        store,owner=refresh(request,True)
        if body.action=='orders':principal(request,'orders:write')
        return safe(lambda:store.view(store.step(key,owner,body)))

    @router.get('/forecast-updates/{key}/export',tags=['Monthly updates'])
    def update_export(key:str,request:Request,mode:Literal['remaining_forecast','combined_demand'],kind:Literal['csv','xlsx','json']='xlsx'):
        principal(request,'reports:export');store,owner=refresh(request)
        def download():
            value=store.get(key,owner);report=store.comparison(value)
            if value['stage']!='ready' or value.get('review_token')!=report['review_token']:
                raise ValueError('Review the current changes and orders before exporting this update.')
            return export_demand(store.fresh_orders(value),mode,kind)
        content,mime=safe(download)
        return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="draft-forecast-update-{mode}.{kind}"'})

    @router.get('/recurring-forecasts',tags=['Schedules'])
    def list_schedules(request:Request):
        store,owner=schedules(request)
        return {'schedules':store.listing(owner)}

    @router.post('/recurring-forecasts',status_code=201,tags=['Schedules'])
    def save_schedule(body:RecurringConfig,request:Request):
        store,owner=schedules(request)
        return safe(lambda:store.save(owner,body))

    @router.get('/recurring-forecasts/{key}',tags=['Schedules'])
    def get_schedule(key:str,request:Request):
        store,owner=schedules(request)
        return safe(lambda:store.config(key,owner)[1],True)

    @router.put('/recurring-forecasts/{key}',tags=['Schedules'])
    def edit_schedule(key:str,body:RecurringConfig,request:Request):
        store,owner=schedules(request);old=safe(lambda:store.config(key,owner)[1],True)
        if body.run_id!=old['run_id']:raise HTTPException(400,'Keep the original baseline when editing a schedule.')
        return safe(lambda:store.save(owner,body))

    @router.delete('/recurring-forecasts/{key}',tags=['Schedules'])
    def pause_schedule(key:str,request:Request):
        store,owner=schedules(request)
        safe(lambda:store.config(key,owner),True)
        # Preserve cycle evidence; deletion means stopping future drafts.
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current=json.loads(db.execute('SELECT payload FROM recurring_forecasts WHERE id=? AND actor=?',(key,owner)).fetchone()[0])
            current['enabled']=False
            db.execute('UPDATE recurring_forecasts SET payload=? WHERE id=? AND actor=?',(json.dumps(current),key,owner))
        return {'id':key,'paused':True}

    @router.post('/recurring-forecasts/{key}/check',tags=['Schedules'])
    def check_schedule(key:str,request:Request):
        store,owner=schedules(request)
        return safe(lambda:store.check(key,owner))

    api.include_router(router)
    if workspaces is not None and service is not None:
        from .platform_identity import COMPANY_ID
        def tick():
            if not workspaces.root.exists():return
            for path in workspaces.root.iterdir():
                if path.is_symlink() or not path.is_dir() or not COMPANY_ID.fullmatch(path.name):continue
                if not (path/'recurring.sqlite3').is_file():continue
                recurring(workspaces.for_principal({'company_id':path.name}),dispatcher,service).tick()
        def start():
            from apscheduler.schedulers.background import BackgroundScheduler
            scheduler=BackgroundScheduler(timezone='UTC')
            scheduler.add_job(tick,'interval',minutes=10,id='company-monthly-drafts',max_instances=1,coalesce=True)
            scheduler.start()
            api.state.workflow_scheduler=scheduler
        def stop():
            scheduler=getattr(api.state,'workflow_scheduler',None)
            if scheduler:scheduler.shutdown(wait=False)
        api.router.add_event_handler('startup',start)
        api.router.add_event_handler('shutdown',stop)

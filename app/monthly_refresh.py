"""Recoverable monthly journey. Existing stores own inputs, maths, orders and exports."""
from contextlib import closing
import json
import re
import sqlite3
import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from .ai_forecast import forecast_preflight
from .input_review import digest, input_report
from .sales_demand import month_basis, export_demand


class StartUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    run_id: str = Field(min_length=1, max_length=80)
    request_id: str = Field(min_length=8, max_length=100)
    workflow: Literal['legacy', 'grouped'] = 'legacy'


class UpdateStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: StrictInt = Field(ge=0)
    action: str = Field(min_length=1, max_length=40)
    request_id: str = Field(min_length=8, max_length=100)
    dataset_id: str | None = None
    snapshot_id: str | None = None
    job_id: str | None = None
    months: StrictInt | None = Field(default=None, ge=1, le=24)
    method: str = Field(default='recommended', max_length=100)
    reviewed: StrictBool = False
    review_token: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    methods: list[str] | None = Field(default=None, min_length=1, max_length=24)
    sales_input_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')


def principal_actor(request):
    principal = request.state.principal
    return json.dumps([principal.get('issuer'), principal.get('subject')]) if principal else 'Local session'


class MonthlyRefresh:
    def __init__(self, path, datasets, load_run, sales, outlook, jobs, submit, live=None, submit_for_actor=None, submit_group=None, site=None):
        self.path, self.datasets, self.load_run = path, datasets, load_run
        self.sales, self.outlook, self.jobs, self.submit, self.live = sales, outlook, jobs, submit, live
        self.submit_for_actor = submit_for_actor
        self.submit_group = submit_group
        self.site = site or {}
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS monthly_updates '
                       '(id TEXT PRIMARY KEY, actor TEXT, updated REAL, payload TEXT)')

    def db(self):
        return closing(sqlite3.connect(self.path, timeout=30))

    def read(self, db, key, actor):
        row = db.execute('SELECT actor,payload FROM monthly_updates WHERE id=?', (key,)).fetchone()
        if not row or row[0] != actor:
            raise ValueError('This forecast update is not available to this user.')
        return json.loads(row[1])

    def write(self, db, actor, value):
        db.execute('INSERT OR REPLACE INTO monthly_updates VALUES (?,?,?,?)',
                   (value['id'], actor, time.time(), json.dumps(value, allow_nan=False)))
        db.commit()

    def baseline(self, run_id):
        run = self.load_run(run_id)
        if run.get('scenario_name') or run.get('base_run_id') or run.get('scenario',{}).get('type'):
            raise ValueError('Start an update from the original sales forecast, not a comparison.')
        source = self.datasets.get(run.get('dataset_id', ''))
        if source.get('scenario_provenance') or source['sources'].get('operations'):
            raise ValueError('Choose original sales history, not a production or factor dataset.')
        if source['settings'].get('frequency') != 'monthly':
            raise ValueError('This guided update uses monthly sales history.')
        return run, source

    def start(self, actor, payload):
        key = uuid.uuid5(uuid.NAMESPACE_URL, 'monthly-update:'+actor+':'+payload.request_id).hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            found = db.execute('SELECT id FROM monthly_updates WHERE id=?', (key,)).fetchone()
            if found:
                value = self.read(db, key, actor)
                if value['base_run_id'] != payload.run_id or value.get('workflow','legacy') != payload.workflow:
                    raise ValueError('This retry identifier already started another update.')
                return value
            run, source = self.baseline(payload.run_id)
            versions = self.sales.list(run['run_id'])
            value = {'id':key, 'revision':0, 'stage':'history', 'base_run_id':run['run_id'],
                     'base_run_sha256':digest(run), 'base_dataset_id':source['id'],
                     'base_dataset_sha256':digest(source), 'name':source['name'],
                     'classification':source['classification'],
                     'previous_snapshot_id':versions[0]['id'] if versions else None,
                     'created_at':time.time()}
            if payload.workflow == 'grouped':
                from .sales_conventions import local_today
                previous_name=run.get('forecast_name') or source['name']
                version=re.search(r' · R(\d+)$',previous_name)
                number=int(version.group(1))+1 if version else 2
                stem=re.sub(r'(?: · \d{4}-\d{2}-\d{2})*(?: · R\d+)?$','',previous_name)
                date=str(local_today(self.site.get('timezone','Asia/Tehran')))
                parent=run.get('forecast_group_id')
                if parent:
                    try:self.jobs.get_group(parent)
                    except ValueError as exc:
                        if str(exc)!='Forecast not found.':raise
                        # Older local results grouped their rows without a durable
                        # group receipt. Keep the original run reference intact.
                        parent=None
                value.update(workflow='grouped', stage='prepared', dataset_id=source['id'],
                    dataset_sha256=digest(source), months=source['settings'].get('horizon',6),
                    methods=[run.get('method_selection') or 'recommended'],
                    parent_forecast_id=parent,
                    name=stem[:130]+' · '+date+' · R'+str(number))
            self.write(db, actor, value)
            return value

    def get(self, key, actor):
        with self.db() as db:
            return self.read(db, key, actor)

    def listing(self, actor):
        with self.db() as db:
            rows = db.execute('SELECT payload FROM monthly_updates WHERE actor=? ORDER BY updated DESC LIMIT 20', (actor,)).fetchall()
        result=[]
        for row in rows:
            value=json.loads(row[0])
            item={k:v for k,v in value.items() if k in
                 {'id','stage','name','base_run_id','created_at','classification','workflow','group_id'}}
            if value.get('group_id'):
                group=self.group_view(value)
                if all(j['state'] in {'succeeded','failed','interrupted','cancelled'} for j in group['jobs']):
                    item['stage']='grouped_complete'
            result.append(item)
        return result

    def grouped_history(self, value, identifier):
        _, base = self.check_base(value)
        source = self.datasets.get(identifier)
        ancestor, seen = source, set()
        while ancestor['id'] != base['id']:
            if ancestor['id'] in seen or not ancestor.get('parent_dataset_id'):
                raise ValueError('Choose the original history or a reviewed version of it.')
            seen.add(ancestor['id'])
            ancestor = self.datasets.get(ancestor['parent_dataset_id'])
        defaults={'unit':None,'frequency':'monthly','month_basis':'gregorian','sales_measure':'unspecified',
                  'history_grain':'transactions','history_calendar':'gregorian','returns_policy':'reject'}
        if source.get('scenario_provenance') or source['classification'] != base['classification'] or any(
                source['settings'].get(k,default) != base['settings'].get(k,default) for k,default in defaults.items()):
            raise ValueError('Calendar, quantity meaning, grain and units must stay comparable. Start separately for a different contract.')
        if source['sources'].get('operations') or input_report(self.datasets,source)['errors']:
            raise ValueError('Resolve the saved history problems first.')
        from .sales_groups import series_column
        if not series_column(source['settings']) or not all(source['settings'].get(k) for k in ('customer_col','sku_col')):
            raise ValueError('Map distinct customer/product series, customers and products before this update.')
        return source

    def group_view(self, value):
        group=self.jobs.get_group(value['group_id'])
        if digest([group['name'],[j['payload'] for j in group['jobs']]]) != value['group_sha256']:
            raise ValueError('The grouped forecast inputs changed. Review the saved revision.')
        return {k:v for k,v in group.items() if k not in {'request_id','job_ids','jobs'}} | {
            'jobs':[{k:v for k,v in job.items() if k not in {'owner','heartbeat_at','request_id'}} for job in group['jobs']]}

    def check_base(self, value):
        run, source = self.baseline(value['base_run_id'])
        if digest(run) != value['base_run_sha256'] or digest(source) != value['base_dataset_sha256']:
            raise ValueError('The original forecast or inputs changed. Start a new update.')
        for source_id in source['sources'].values():
            if source_id: self.datasets.source(source_id)
        return run, source

    def check_inputs(self, value, *, validate=False):
        source = self.datasets.get(value['dataset_id'])
        if digest(source) != value['dataset_sha256']:
            raise ValueError('These saved sales inputs changed. Review history again.')
        for source_id in source['sources'].values():
            if source_id: self.datasets.source(source_id)
        if validate:
            report = input_report(self.datasets, source)
            if report['errors']: raise ValueError('Resolve input problems before calculating.')
        return source

    def source_status(self):
        if self.live is None: return []
        # Status only. This never fetches or claims that a connected source is in a model.
        return [{k:r.get(k) for k in ('id','name','status','enabled','last_success','error',
                                      'data_behind','refresh_overdue','series')}
                for r in self.live.listing()['sources']]

    def fresh_orders(self, value):
        latest = self.sales.list(value['run_id'])
        if not latest or latest[0]['id'] != value.get('snapshot_id'):
            raise ValueError('Orders changed. Review the latest order version before continuing.')
        outlook = self.outlook(value['snapshot_id'])
        if outlook['run_id'] != value['run_id'] or not outlook['can_export']:
            raise ValueError('Orders are expired, incomplete or need attention. Review current orders again.')
        return outlook

    def comparison(self, value):
        old, _ = self.check_base(value)
        new = self.load_run(value['run_id'])
        if digest(new) != value['run_sha256']:
            raise ValueError('The new forecast changed. Start a new update.')
        current = self.fresh_orders(value)
        if old.get('unit') != new.get('unit') or month_basis(old) != month_basis(new):
            raise ValueError('Compare forecasts with the same units and planning calendar.')
        def forecasts(run):
            result = {}
            for series, meta in run.get('metadata', {}).items():
                for point in run.get('series', {}).get(series, {}).get('forecast', []):
                    key = (str(meta.get('customer', '')),str(meta.get('sku', '')),str(point['timestamp'])[:10])
                    if key in result: raise ValueError('Repeated customer/product/month forecast. Review series mapping.')
                    result[key] = float(point['mean'])
            return result
        previous, calculated = forecasts(old), forecasts(new)
        order_rows = {(r['customer'],r['sku'],r['period']):r for r in current['rows']}
        prior_rows, prior_note = {}, 'No earlier order review; comparing calculated forecasts only.'
        if value['previous_snapshot_id']:
            prior = self.outlook(value['previous_snapshot_id'])
            prior_rows = {(r['customer'],r['sku'],r['period']):r for r in prior['rows']}
            prior_note = 'Earlier orders are reference only.' + (' Their review has expired or is incomplete.' if not prior['can_export'] else '')
        rows = []
        for key in sorted(previous.keys() | calculated.keys() | order_rows.keys()):
            before, after = previous.get(key), calculated.get(key)
            before_order, after_order = prior_rows.get(key), order_rows.get(key)
            rows.append({'customer':key[0], 'sku':key[1], 'period':key[2],
                         'change':'added' if before is None else 'removed' if after is None else 'overlap',
                         'before_forecast':before,'after_forecast':after,
                         'forecast_difference':None if before is None or after is None else after-before,
                         'before_open_orders':before_order['booked'] if before_order else None,
                         'after_open_orders':after_order['booked'] if after_order else None,
                         'before_to_serve':before_order['still_to_serve'] if before_order else None,
                         'after_to_serve':after_order['still_to_serve'] if after_order else None})
        overlap = [r for r in rows if r['change']=='overlap']
        report = {'rows':rows, 'unit':new['unit'],'month_basis':month_basis(new),
                  'overlapping_rows':len(overlap), 'added_rows':sum(r['change']=='added' for r in rows),
                  'removed_rows':sum(r['change']=='removed' for r in rows),
                  'overlap_before':sum(r['before_forecast'] for r in overlap),
                  'overlap_after':sum(r['after_forecast'] for r in overlap),
                  'orders_note':prior_note, 'warnings':current['warnings'],
                  'snapshot_id':value['snapshot_id'], 'as_of':current['as_of'],
                  'valid_until':current['valid_until'], 'can_export':current['can_export']}
        report['review_token'] = digest({'report':report,'run':digest(new),'orders':current})
        return report

    def view(self, value):
        result = {k:v for k,v in value.items() if not k.startswith('last_request')}
        self.check_base(value)
        result['live_sources'] = self.source_status()
        if value.get('job_id'): result['job'] = self.jobs.get(value['job_id'])
        if value.get('dataset_id'): self.check_inputs(value)
        if value.get('workflow') == 'grouped':
            if value.get('group_id'):
                result['group']=self.group_view(value)
                if all(j['state'] in {'succeeded','failed','interrupted','cancelled'} for j in result['group']['jobs']):
                    result['stage']='grouped_complete'
            return result
        if value['stage'] in {'review','ready'}:
            try:
                result['comparison'] = self.comparison(value)
                result['ready'] = value['stage']=='ready' and value.get('review_token')==result['comparison']['review_token']
                if value['stage']=='ready' and not result['ready']:
                    result['attention'] = 'Demand readiness changed. Review the comparison again before export.'
            except ValueError as exc:
                result.update(ready=False, attention=str(exc))
        return result

    def step(self, key, actor, payload):
        request_sha = digest(payload.model_dump())
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            value = self.read(db, key, actor)
            if value.get('last_request_id') == payload.request_id:
                if value['last_request_sha256'] != request_sha: raise ValueError('Retry inputs changed.')
                return value
            if payload.revision != value['revision']:
                raise ValueError('This update changed in another tab. Reload to continue.')
            _, base_source = self.check_base(value)
            stage, action = value['stage'], payload.action
            def require(expected):
                if stage not in expected: raise ValueError('Finish the current step before continuing.')
            if value.get('workflow') == 'grouped':
                require({'prepared'})
                if action == 'prepare_group':
                    if payload.reviewed is not True:
                        raise ValueError('Review the history choice first.')
                    source=self.grouped_history(value,payload.dataset_id or '')
                    from .grouped_forecasts import check_methods
                    methods=payload.methods or value['methods']
                    check_methods(methods,{**source['settings'],'profile':'deep'})
                    value.update(dataset_id=source['id'],dataset_sha256=digest(source),
                        months=payload.months or value['months'],methods=methods)
                elif action == 'calculate_group':
                    if payload.reviewed is not True or not payload.sales_input_id or not payload.methods or not payload.name or not payload.name.strip():
                        raise ValueError('Review sales, factors, customers, orders and methods before calculating.')
                    source=self.grouped_history(value,payload.dataset_id or '')
                    if not self.submit_group:
                        raise ValueError('Grouped forecast calculation is unavailable.')
                    dispatch='monthly-group:'+value['id']+':'+str(value['revision'])
                    group=self.submit_group({'name':payload.name.strip(),'dataset_id':source['id'],
                        'sales_input_id':payload.sales_input_id,'methods':payload.methods,'request_id':dispatch,
                        'parent_forecast_id':value.get('parent_forecast_id')})
                    value.update(stage='grouped',dataset_id=source['id'],dataset_sha256=digest(source),
                        group_id=group['id'],name=group['name'],methods=payload.methods,
                        sales_input_id=payload.sales_input_id,months=source['settings']['horizon'],
                        group_sha256=digest([group['name'],[j['payload'] for j in group['jobs']]]))
                else:
                    raise ValueError('Use the grouped forecast workflow for this update.')
            elif action == 'history':
                require({'history','forecast'})
                if payload.reviewed is not True: raise ValueError('Review the history choice first.')
                source = self.datasets.get(payload.dataset_id or '')
                ancestor, seen = source, set()
                while ancestor['id'] != base_source['id']:
                    if ancestor['id'] in seen or not ancestor.get('parent_dataset_id'):
                        raise ValueError('Choose the original history or a reviewed version of it.')
                    seen.add(ancestor['id']); ancestor = self.datasets.get(ancestor['parent_dataset_id'])
                if source.get('scenario_provenance') or source['sources'].get('operations'):
                    raise ValueError('Choose original sales history, not a scenario.')
                defaults={'unit':None,'frequency':'monthly','month_basis':'gregorian','sales_measure':'unspecified',
                          'history_grain':'transactions','history_calendar':'gregorian','returns_policy':'reject'}
                if source['classification'] != base_source['classification'] or any(source['settings'].get(k,default) != base_source['settings'].get(k,default)
                    for k,default in defaults.items()):
                    raise ValueError('Calendar, quantity meaning, grain and units must stay comparable. Start separately for a different contract.')
                report = input_report(self.datasets,source)
                if report['errors']: raise ValueError('Resolve the saved history problems first.')
                from .sales_groups import series_column
                if not series_column(source['settings']) or not all(source['settings'].get(k) for k in ('customer_col','sku_col')):
                    raise ValueError('Map distinct customer/product series, customers and products before this update.')
                value.update(stage='forecast',dataset_id=source['id'],dataset_sha256=digest(source))
            elif action == 'history_back':
                require({'forecast'}); value.update(stage='history')
            elif action == 'calculate':
                require({'forecast'})
                if payload.reviewed is not True or payload.months is None:
                    raise ValueError('Review the horizon, method and factor checks before calculating.')
                source = self.check_inputs(value,validate=True)
                settings, sources = forecast_preflight(self.datasets,source,payload.months,payload.method)
                # Reuse the numerical engine's model catalog, not an AI-generated formula.
                from .forecast_engine import _model_specs
                allowed = {'recommended','seasonal','trend','intermittent','driver'} | {'model:'+s.name for s in _model_specs('deep')}
                if payload.method not in allowed: raise ValueError('Choose an available forecasting method.')
                dispatch = 'monthly-'+value['id']+'-'+str(value['revision'])
                saved = self.datasets.save(source['name']+' · Forecast update',sources,settings,
                    source['classification'],True,parent_dataset_id=source['id'],request_id=dispatch)
                submit = self.submit if self.submit_for_actor is None else lambda *args:self.submit_for_actor(actor,*args)
                job = submit({'dataset_id':saved['id'],'method':payload.method,'adjustment':0,
                              'scenario_name':None,'base_run_id':None},saved['name'],dispatch)
                value.update(stage='calculating',job_id=job['id'],calculation_dataset_id=saved['id'],
                             source_check=self.source_status(),months=payload.months,method=payload.method)
            elif action in {'calculated','factor_calculated'}:
                require({'calculating'} if action=='calculated' else {'factor_calculating'})
                job = self.jobs.get(value['job_id'])
                if job['state'] != 'succeeded' or not job.get('run_id'):
                    raise ValueError('Wait for the calculation to finish, or retry a stopped job.')
                run = self.load_run(job['run_id'])
                if run.get('dataset_id') != value['calculation_dataset_id']:
                    raise ValueError('The calculation does not match these reviewed inputs.')
                if action=='calculated': value['new_baseline_id']=run['run_id']
                else:
                    if run.get('base_run_id') != value['new_baseline_id'] or run.get('scenario',{}).get('type') not in {'factor_link','factor_batch'}:
                        raise ValueError('Choose a reviewed factor comparison of this new forecast.')
                value.update(run_id=run['run_id'],run_sha256=digest(run),stage='factors' if action=='calculated' else 'orders')
            elif action == 'retry_calculation':
                require({'calculating'})
                if self.jobs.get(value['job_id'])['state'] not in {'failed','cancelled','interrupted'}:
                    raise ValueError('Only stopped calculations can be retried.')
                value.update(stage='forecast'); value.pop('job_id',None)
            elif action == 'no_factors':
                require({'factors'})
                if payload.reviewed is not True: raise ValueError('Confirm you want the calculated baseline without adding a factor scenario.')
                value.update(stage='orders',factor_choice='baseline')
            elif action == 'factor_job':
                require({'factors'})
                job = self.jobs.get(payload.job_id or '')
                source = self.datasets.get(job['payload']['dataset_id'])
                provenance = source.get('scenario_provenance',{})
                if (job['payload'].get('base_run_id') != value['new_baseline_id']
                        or provenance.get('base_run_id') != value['new_baseline_id']
                        or provenance.get('type') not in {'factor_link','factor_batch'}):
                    raise ValueError('Choose a reviewed factor comparison of this new forecast.')
                value.update(stage='factor_calculating',job_id=job['id'],calculation_dataset_id=source['id'],factor_choice='reviewed_scenario')
            elif action == 'discard_factor_job':
                require({'factor_calculating'})
                if self.jobs.get(value['job_id'])['state'] not in {'failed','cancelled','interrupted'}:
                    raise ValueError('Wait or stop this comparison before returning to factor choices.')
                value.update(stage='factors'); value.pop('job_id',None)
            elif action == 'orders':
                require({'orders','review','ready'})
                value['snapshot_id']=payload.snapshot_id
                self.fresh_orders(value)
                value.update(stage='review'); value.pop('review_token',None)
            elif action == 'orders_back':
                require({'review','ready'}); value.update(stage='orders'); value.pop('review_token',None)
            elif action == 'review':
                require({'review','ready'})
                report = self.comparison(value)
                if payload.reviewed is not True or payload.review_token != report['review_token']:
                    raise ValueError('Review this exact change report before exporting.')
                value.update(stage='ready',review_token=report['review_token'])
            else: raise ValueError('Unknown forecast-update step.')
            value.update(revision=value['revision']+1,last_request_id=payload.request_id,last_request_sha256=request_sha)
            self.write(db, actor, value)
            return value


def install_monthly_refresh(app, service):
    router = APIRouter(prefix='/api/forecast-updates')
    def perform(work):
        try: return work()
        except (ValueError,KeyError,TypeError) as exc: raise HTTPException(400,str(exc)) from exc
    @router.get('')
    def listing(request:Request):
        return {'updates':service.listing(principal_actor(request))}
    @router.post('')
    def start(payload:StartUpdate, request:Request):
        return perform(lambda:service.view(service.start(principal_actor(request),payload)))
    @router.get('/{key}')
    def get(key:str, request:Request):
        return perform(lambda:service.view(service.get(key,principal_actor(request))))
    @router.post('/{key}/steps')
    def step(key:str,payload:UpdateStep,request:Request):
        return perform(lambda:service.view(service.step(key,principal_actor(request),payload)))
    @router.get('/{key}/export')
    def export(key:str,mode:str,request:Request,kind:str='xlsx'):
        def download():
            value=service.get(key,principal_actor(request))
            report=service.comparison(value)
            if value['stage']!='ready' or value.get('review_token')!=report['review_token']:
                raise ValueError('Review the current changes and orders before exporting this update.')
            content,mime=export_demand(service.fresh_orders(value),mode,kind)
            return Response(content,media_type=mime,headers={
                'Content-Disposition':f'attachment; filename="draft-forecast-update-{mode}.{kind}"'})
        return perform(download)
    app.include_router(router)

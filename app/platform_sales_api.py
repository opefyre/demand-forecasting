"""Company-scoped sales pipeline. Reuse reviewed inputs, maths and evidence stores."""
from typing import Literal
import uuid

from fastapi import APIRouter, Request, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .platform_identity import principal
from .forecast_orders import prepare, save, reviewed
from .order_books import BookRequest
from .sales_demand import DemandInputs, demand_outlook, export_demand, StaleOrderRevision
from .demand_releases import identity, ReleaseConflict

class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class DatasetInput(StrictInput):
    name: str = Field(min_length=1, max_length=120)
    sources: dict[Literal['history','future'], str] = Field(min_length=1, max_length=2)
    settings: dict
    classification: Literal['user_provided','synthetic_sample'] = 'user_provided'
    accept_warnings: bool = False
    parent_dataset_id: str | None = None
    request_id: str = Field(min_length=8, max_length=100)


class OrdersReview(StrictInput):
    inputs: DemandInputs
    request_id: str = Field(min_length=8, max_length=100)
    review_token: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    reuse_snapshot_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')


class ForecastCreate(StrictInput):
    name: str = Field(min_length=1, max_length=160)
    dataset_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    sales_input_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    methods: list[str] = Field(min_length=1, max_length=24)
    request_id: str = Field(min_length=8, max_length=100)


class FactorImport(StrictInput):
    source_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=200)
    geography: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=200)
    frequency: Literal['daily','monthly','annual']
    classification: Literal['user_provided','synthetic_sample'] = 'user_provided'
    mapping: dict[Literal['period','value','available_at'], str]
    calendar: Literal['gregorian','jalali'] = 'gregorian'
    publication_timezone: Literal['UTC','Asia/Tehran'] = 'UTC'
    factor_details: dict | None = None
    sheet: str | None = None
    header_row: int = Field(default=1, ge=1, le=10000)
    parent_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    review_token: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    reviewed: bool = False
    request_id: str = Field(min_length=8, max_length=100)


class ReleaseInput(StrictInput):
    snapshot_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    receiver: str = Field(min_length=1, max_length=120)
    mode: Literal['remaining_forecast','combined_demand']
    request_id: str = Field(min_length=8, max_length=100)
    review_token: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    reviewed: bool = False


class ReleaseApproval(StrictInput):
    review_token: str = Field(pattern=r'^[a-f0-9]{64}$')
    reviewed: bool


def install_platform_sales(api, workspaces, dispatcher=None):
    router = APIRouter()
    if dispatcher is None:
        from .company_jobs import dispatch
        dispatcher = dispatch

    def workspace(request, *scopes):
        who = principal(request)
        for scope in scopes:
            principal(request, scope)
        if workspaces is None:
            raise HTTPException(503, 'Company storage is not configured.')
        return workspaces.for_principal(who)

    def call(fn, *, missing=False):
        try:
            return fn()
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except (StaleOrderRevision, ReleaseConflict) as exc:
            raise HTTPException(409, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(404 if missing else 400, str(exc)) from exc

    def dataset(ws, key):
        return call(lambda: ws.datasets.get(key), missing=True)

    def check_sources(ws, body):
        for role, key in body.sources.items():
            source = call(lambda: ws.datasets.source(key)[0], missing=True)
            if source['role'] != role:
                raise HTTPException(400, 'Choose files saved for the selected input role.')
        if body.parent_dataset_id:
            dataset(ws, body.parent_dataset_id)

    def run(ws, key):
        return call(lambda: ws.load_run(key), missing=True)

    def safe_job(job):
        # Never return internal owner tokens, ledger paths or other people's actor IDs.
        return {k:v for k,v in job.items() if k not in {'owner','heartbeat_at','request_id'}}

    def safe_group(group):
        return {k:v for k,v in group.items() if k not in {'job_ids','request_id'}} | {
            'jobs':[safe_job(job) for job in group['jobs']]}

    @router.post('/sources', status_code=201, tags=['Sales inputs'])
    async def upload_source(request: Request, file: UploadFile = File(...),
            role: Literal['history','future','sales_orders','sales_commitments','factor_observations'] = Form('history'),
            sheet: str | None = Form(None)):
        scope = 'orders:write' if role.startswith('sales_') else 'factors:write' if role == 'factor_observations' else 'inputs:write'
        ws = workspace(request, scope)
        payload = await file.read(50 * 1024 * 1024 + 1)
        if not payload or len(payload) > 50 * 1024 * 1024:
            raise HTTPException(400, 'Upload a non-empty file smaller than 50 MB.')
        return call(lambda: ws.datasets.upload(file.filename or 'data.csv', payload, role, sheet))

    @router.get('/sources/{source_id}', tags=['Sales inputs'])
    def source(source_id: str, request: Request):
        # File roles determine access; callers never choose the permission themselves.
        ws = workspace(request)
        value = call(lambda: ws.datasets.source(source_id)[0], missing=True)
        scope = 'orders:read' if value['role'].startswith('sales_') else 'factors:read' if value['role'] == 'factor_observations' else 'inputs:read'
        principal(request, scope)
        return value

    @router.get('/sources', tags=['Sales inputs'])
    def sources(request: Request, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        ws = workspace(request)
        scopes = set(principal(request)['permissions'])
        if not scopes.intersection({'inputs:read','orders:read','factors:read'}):
            raise HTTPException(403, 'Sales input access is required.')
        rows = [row for row in ws.datasets.list_sources() if
            ('orders:read' if row['role'].startswith('sales_') else
             'factors:read' if row['role'] == 'factor_observations' else 'inputs:read') in scopes]
        return {'sources':rows[offset:offset+limit], 'total':len(rows), 'limit':limit, 'offset':offset}

    @router.get('/datasets', tags=['Sales inputs'])
    def list_datasets(request: Request, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        rows = workspace(request, 'inputs:read').datasets.list()
        return {'datasets':rows[offset:offset+limit], 'total':len(rows), 'limit':limit, 'offset':offset}

    @router.post('/datasets/preview', tags=['Sales inputs'])
    def preview_dataset(body: DatasetInput, request: Request):
        ws = workspace(request, 'inputs:write')
        check_sources(ws, body)
        from .input_review import validate_import
        return call(lambda: validate_import(ws.datasets, body.sources, body.settings, body.classification))

    @router.post('/datasets', status_code=201, tags=['Sales inputs'])
    def create_dataset(body: DatasetInput, request: Request):
        ws = workspace(request, 'inputs:write')
        check_sources(ws, body)
        return call(lambda: ws.datasets.save(body.name, body.sources, body.settings,
            body.classification, body.accept_warnings, parent_dataset_id=body.parent_dataset_id,
            request_id=body.request_id))

    @router.get('/datasets/{dataset_id}', tags=['Sales inputs'])
    def get_dataset(dataset_id: str, request: Request):
        return dataset(workspace(request, 'inputs:read'), dataset_id)

    @router.get('/datasets/{dataset_id}/orders', tags=['Orders'])
    def get_orders(dataset_id: str, request: Request):
        ws = workspace(request, 'orders:read','inputs:read')
        dataset(ws, dataset_id)
        return call(lambda: ws.order_books.get(dataset_id))

    @router.put('/datasets/{dataset_id}/orders', tags=['Orders'])
    def update_orders(dataset_id: str, body: BookRequest, request: Request):
        ws = workspace(request, 'orders:write','inputs:read')
        dataset(ws, dataset_id)
        return call(lambda: ws.order_books.save(dataset_id, body))

    @router.post('/datasets/{dataset_id}/orders/preview', tags=['Orders'])
    def preview_orders(dataset_id: str, body: OrdersReview, request: Request):
        ws = workspace(request, 'orders:write','inputs:read')
        dataset(ws, dataset_id)
        return call(lambda: prepare(ws.datasets, ws.sales, dataset_id,
            body.model_dump(mode='json'), ws.load_run, site=ws.site)[0])

    @router.post('/datasets/{dataset_id}/orders/snapshots', status_code=201, tags=['Orders'])
    def save_orders(dataset_id: str, body: OrdersReview, request: Request):
        ws = workspace(request, 'orders:write','inputs:read')
        dataset(ws, dataset_id)
        return call(lambda: save(ws.datasets, ws.sales, dataset_id,
            body.model_dump(mode='json'), ws.load_run, identity(principal(request)), site=ws.site))

    @router.get('/order-snapshots/{snapshot_id}', tags=['Orders'])
    def snapshot(snapshot_id: str, request: Request):
        return call(lambda: workspace(request, 'orders:read').sales.get(snapshot_id), missing=True)

    @router.get('/factors', tags=['Forecast factors'])
    def factors(request: Request):
        return {'snapshots':workspace(request, 'factors:read').factors.list()}

    @router.post('/factors/imports/preview', tags=['Forecast factors'])
    def preview_factor_import(body: FactorImport, request: Request):
        ws = workspace(request, 'factors:write')
        from .factor_imports import review_import
        return call(lambda: review_import(ws.datasets, body.model_dump(exclude_none=True)))

    @router.post('/factors/imports', status_code=201, tags=['Forecast factors'])
    def save_factor_import(body: FactorImport, request: Request):
        ws = workspace(request, 'factors:write')
        from .factor_imports import save_import
        return call(lambda: save_import(ws.datasets, ws.factors, body.model_dump(exclude_none=True)))

    @router.get('/factors/{snapshot_id}', tags=['Forecast factors'])
    def factor(snapshot_id: str, request: Request):
        return call(lambda: workspace(request, 'factors:read').factors.get(snapshot_id), missing=True)

    @router.get('/datasets/{dataset_id}/factors', tags=['Forecast factors'])
    def factor_options(dataset_id: str, request: Request):
        ws = workspace(request, 'factors:read','inputs:read')
        dataset(ws, dataset_id)
        from .forecast_inputs import factor_options as options
        return call(lambda: options(ws.datasets, ws.factors, dataset_id, ws.live_sources))

    @router.post('/datasets/{dataset_id}/factors/preview', tags=['Forecast factors'])
    def factor_preview(dataset_id: str, body: dict, request: Request):
        ws = workspace(request, 'factors:write','inputs:read')
        dataset(ws, dataset_id)
        from .forecast_inputs import preview_inputs
        return call(lambda: preview_inputs(ws.datasets, ws.factors, dataset_id, body, ws.live_sources))

    @router.post('/datasets/{dataset_id}/factors', status_code=201, tags=['Forecast factors'])
    def factor_save(dataset_id: str, body: dict, request: Request):
        ws = workspace(request, 'factors:write','inputs:write')
        dataset(ws, dataset_id)
        from .forecast_inputs import save_inputs
        # The factor service produces a reviewed, immutable derived sales dataset.
        return call(lambda: save_inputs(ws.datasets, ws.factors, dataset_id, body, ws.live_sources))

    @router.post('/forecasts', status_code=202, tags=['Forecasts'])
    def create_forecast(body: ForecastCreate, request: Request):
        ws = workspace(request, 'forecasts:run','inputs:read','orders:read')
        value = dataset(ws, body.dataset_id)
        if value.get('scenario_provenance') or set(value['sources']) - {'history','future'}:
            raise HTTPException(400, 'Choose reviewed sales inputs.')
        call(lambda: reviewed(ws.datasets, ws.sales, body.dataset_id, body.sales_input_id, site=ws.site))
        from .forecast_orders import context
        revisions = ws.sales.list(context(ws.datasets, body.dataset_id, site=ws.site)['run_id'])
        if not revisions or revisions[0]['id'] != body.sales_input_id:
            raise HTTPException(409, 'A newer order review exists. Use the latest reviewed inputs.')
        from .forecast_engine import _model_specs, _factor_specs, METHOD_GROUPS
        drivers = value['settings'].get('drivers',[])
        factor_specs = _factor_specs(value['settings'].get('profile','deep'), drivers) if 1 <= len(drivers) <= 8 else []
        choices = {'recommended', *METHOD_GROUPS} | {'model:'+spec.name for spec in
            _model_specs(value['settings'].get('profile','deep')) + factor_specs}
        if factor_specs:
            choices.add('factor_test')
        if len(set(body.methods)) != len(body.methods) or any(method not in choices for method in body.methods):
            raise HTTPException(400, 'Choose distinct supported forecasting methods.')
        group_id = uuid.uuid5(uuid.NAMESPACE_URL, 'demandlab-group:' + body.request_id).hex
        payloads = [{'dataset_id':body.dataset_id, 'sales_input_id':body.sales_input_id,
            'method':method, 'forecast_group_id':group_id, 'forecast_name':body.name} for method in body.methods]
        group = call(lambda: ws.jobs.create_group(payloads, body.name, body.request_id))
        # A dispatch failure leaves the durable group queued and safe to retry;
        # every method is recorded before any is sent to Huey.
        for job in group['jobs']:
            if job['state'] == 'queued':
                dispatcher(ws, job['id'])
        return safe_group(ws.jobs.get_group(group_id))

    @router.get('/forecast-methods', tags=['Forecasts'])
    def forecast_methods(request: Request, frequency: Literal['monthly','weekly','daily'] = 'monthly',
            profile: Literal['fast','deep'] = 'fast'):
        principal(request, 'drafts:read')
        from .forecast_engine import _model_specs, METHOD_GROUPS, _engine_versions
        return {'automatic':'recommended', 'families':sorted(METHOD_GROUPS),
            'methods':[{'id':'model:'+spec.name,'name':spec.name,'kind':spec.kind}
                for spec in _model_specs(profile) if frequency == 'daily' or spec.kind != 'mstl'],
            'engine':_engine_versions(), 'frequency':frequency,
            'note':'A method still needs enough history and matching factors to calculate.'}

    @router.get('/forecasts', tags=['Forecasts'])
    def forecasts(request: Request, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
        ws = workspace(request, 'drafts:read')
        return {'forecasts':[safe_group(group) for group in ws.jobs.list_groups(limit, offset)]}

    @router.get('/forecasts/{forecast_id}', tags=['Forecasts'])
    def forecast(forecast_id: str, request: Request):
        ws = workspace(request, 'drafts:read')
        return safe_group(call(lambda: ws.jobs.get_group(forecast_id), missing=True))

    @router.get('/jobs/{job_id}', tags=['Forecast jobs'])
    def job(job_id: str, request: Request):
        return safe_job(call(lambda: workspace(request, 'drafts:read').jobs.get(job_id), missing=True))

    @router.post('/jobs/{job_id}/cancel', tags=['Forecast jobs'])
    def cancel_job(job_id: str, request: Request):
        ws = workspace(request, 'forecasts:write')
        call(lambda: ws.jobs.get(job_id), missing=True)
        return safe_job(ws.jobs.cancel(job_id))

    @router.get('/runs/{run_id}', tags=['Forecast results'])
    def result(run_id: str, request: Request):
        value = dict(run(workspace(request, 'drafts:read'), run_id))
        value.pop('job_owner', None)
        return value

    @router.get('/runs/{run_id}/files/{kind}', tags=['Forecast results'])
    def model_file(run_id: str, kind: Literal['csv','xlsx','models','drivers'], request: Request):
        ws = workspace(request, 'drafts:read','reports:export')
        run(ws, run_id)
        filename = {'csv':'forecast.csv', 'xlsx':'forecast_package.xlsx',
                    'models':'model_leaderboard.csv', 'drivers':'driver_importance.csv'}[kind]
        path = ws.runs / run_id / filename
        if path.is_symlink() or not path.is_file():
            raise HTTPException(404, 'Forecast file not found.')
        return FileResponse(path, filename=f'{run_id}-{filename}')

    def outlook(ws, key):
        value = run(ws, key)
        saved = ws.sales.get(value['sales_input_snapshot_id'])
        return {**demand_outlook(saved['inputs'], value), 'snapshot_id':saved['id']}

    def filtered(value, customer, sku, period):
        return {**value, 'rows':[row for row in value['rows'] if
            (not customer or row['customer'] == customer) and (not sku or row['sku'] == sku)
            and (not period or row['period'][:7] == period[:7])]}

    @router.get('/runs/{run_id}/demand', tags=['Forecast results'])
    def demand(run_id: str, request: Request, customer: str = '', sku: str = '', period: str = ''):
        ws = workspace(request, 'drafts:read')
        value = call(lambda: outlook(ws, run_id))
        return filtered(value, customer, sku, period)

    @router.get('/runs/{run_id}/export', tags=['Forecast results'])
    def export(run_id: str, request: Request, mode: Literal['remaining_forecast','combined_demand'],
            kind: Literal['csv','xlsx','json'] = 'xlsx', customer: str = '', sku: str = '', period: str = ''):
        ws = workspace(request, 'drafts:read','reports:export')
        value = call(lambda: filtered(outlook(ws, run_id), customer, sku, period))
        if not value['rows']:
            raise HTTPException(400, 'No forecast rows match these filters.')
        content, mime = call(lambda: export_demand(value, mode, kind))
        return Response(content, media_type=mime, headers={
            'Content-Disposition':f'attachment; filename="demand-{run_id}.{kind}"'})

    def release(ws, key, who):
        record = call(lambda: ws.releases.get(key), missing=True)
        if 'drafts:read' not in who.get('permissions',[]) and record['state'] != 'approved':
            raise HTTPException(404, 'Approved report not found.')
        return call(lambda: ws.releases.detail(key, identity(who), who['role']))

    @router.get('/releases', tags=['Approved reports'])
    def releases(request: Request):
        ws = workspace(request, 'reports:read')
        who = principal(request)
        rows = ws.releases.list()
        return {'releases':[row for row in rows if row['state'] == 'approved' or 'drafts:read' in who['permissions']]}

    @router.post('/releases/preview', tags=['Approved reports'])
    def preview_release(body: ReleaseInput, request: Request):
        ws = workspace(request, 'forecasts:write')
        return call(lambda: ws.releases.preview(body.model_dump())[0])

    @router.post('/releases', status_code=201, tags=['Approved reports'])
    def create_release(body: ReleaseInput, request: Request):
        ws = workspace(request, 'forecasts:write')
        return call(lambda: ws.releases.request(body.model_dump(), identity(principal(request))))

    @router.get('/releases/{release_id}', tags=['Approved reports'])
    def get_release(release_id: str, request: Request):
        ws = workspace(request, 'reports:read')
        return release(ws, release_id, principal(request))

    @router.post('/releases/{release_id}/approve', tags=['Approved reports'])
    def approve_release(release_id: str, body: ReleaseApproval, request: Request):
        ws = workspace(request, 'releases:approve', 'drafts:read')
        who = principal(request)
        return call(lambda: ws.releases.approve(release_id, body.model_dump(), identity(who), who['role']))

    @router.get('/releases/{release_id}/export', tags=['Approved reports'])
    def export_release(release_id: str, request: Request, kind: Literal['csv','xlsx','json'] = 'xlsx'):
        ws = workspace(request, 'reports:export')
        release(ws, release_id, principal(request))
        content, mime, record = call(lambda: ws.releases.export(release_id, kind))
        return Response(content, media_type=mime, headers={
            'Content-Disposition':f'attachment; filename="demand-release-{release_id}-v{record["version"]}.{kind}"'})

    api.include_router(router)

"""Company-owned adapters for existing scenario, monthly and scheduled workflows."""
import asyncio
import json
from .monthly_refresh import MonthlyRefresh
from .recurring_forecasts import RecurringForecasts
from .sales_demand import demand_outlook

def review_scenario(source,datasets,factors,load_run,live=None,profiles=None):
    """Reuse authoritative comparison review before dispatch; never infer scope."""
    from .factor_links import preview_link
    from .factor_batch import check_saved_batch
    from .factor_imports import digest
    proof=source.get('scenario_provenance') or {}
    base=load_run(proof.get('base_run_id',''))
    if proof.get('type')=='factor_link':
        if proof.get('baseline_sha256')!=digest(base) or proof.get('derived_inputs_sha256')!=digest({'sources':source['sources'],'settings':source['settings']}):
            raise ValueError('Factor inputs changed. Review them again.')
        report=preview_link(base,datasets,factors,proof['reviewed_inputs'],live,profiles)
        if report['missing'] or report['review_token']!=proof['review_token']:
            raise ValueError('Factor inputs changed. Review them again.')
    elif proof.get('type')=='factor_batch':
        check_saved_batch(base,source,datasets,factors,live,profiles)
    elif proof.get('type') in {'factor_assumptions','factor_comparison'}:
        from .assumptions import scenario_inputs
        original,settings,_,_,_=scenario_inputs(base,datasets)
        if proof['type']=='factor_assumptions':
            if proof.get('baseline_sha256')!=digest(base) or proof.get('derived_inputs_sha256')!=digest({'sources':source['sources'],'settings':source['settings']}):
                raise ValueError('Factor inputs changed. Review them again.')
            # Recheck the bytes behind each immutable saved source, not just IDs.
            datasets.inspect(source['sources'],source['settings'],source['classification'])
        else:
            from .factor_review import review_factors
            if not review_factors(base,datasets)['can_compare']:
                raise ValueError('Recalculate this baseline first: older forecasts used a different factor-testing rule.')
            removed=list(settings['drivers'])
            settings.update(drivers=[],driver_roles={},method_selection=base.get('method_selection') or base['run_settings']['method_selection'])
            if source['sources']!=original['sources'] or source['settings']!=settings or proof.get('removed_factors')!=removed or source['classification']!=original['classification']:
                raise ValueError('Factor inputs changed. Review them again.')
    else:
        raise ValueError('Choose a reviewed factor comparison or batch.')
    return proof['base_run_id']


def outlook(workspace, key):
    saved=workspace.sales.get(key)
    return {**demand_outlook(saved['inputs'],workspace.load_run(saved['inputs']['run_id'])),
            'snapshot_id':key,'created_at':saved['created_at'],'evidence':saved['evidence']}


def submit_draft(workspace, dispatcher, payload, name, request_id, schedule_owner=None, retry_of=None):
    from .main import SavedRunConfig
    from .input_review import input_report
    values=SavedRunConfig(**payload).model_dump()
    source=workspace.datasets.get(values['dataset_id'])
    workspace.lifecycle.require_active('datasets',values['dataset_id'])
    for key in source['sources'].values():workspace.lifecycle.require_active('sources',key)
    if source['sources'].get('operations') or values['scenario_name'] or values['adjustment'] or values['sales_input_id']:
        raise ValueError('Use reviewed sales and factor inputs for this draft.')
    proof=source.get('scenario_provenance')
    if proof:
        if values['base_run_id']!=proof.get('base_run_id') or values['method']:
            raise ValueError('Use the comparison’s recorded baseline and method.')
        review_scenario(source,workspace.datasets,workspace.factors,workspace.load_run,workspace.live_sources,workspace.profiles)
    elif values['base_run_id'] or input_report(workspace.datasets,source)['errors']:
        raise ValueError('Review sales inputs before calculating.')
    if schedule_owner:values['_schedule_owner']=schedule_owner
    job=workspace.jobs.create(values,name,request_id,retry_of=retry_of)
    if job['state']=='queued':dispatcher(workspace,job['id'])
    return {k:v for k,v in job.items() if k not in {'owner','heartbeat_at','request_id'}}


def monthly(workspace, dispatcher, scheduled=False):
    from .grouped_forecasts import create_group
    return MonthlyRefresh(workspace.path('monthly-updates.sqlite3'),workspace.datasets,workspace.load_run,
        workspace.sales,lambda key:outlook(workspace,key),workspace.jobs,
        lambda *args:submit_draft(workspace,dispatcher,*args),workspace.live_sources,
        submit_for_actor=(lambda actor,*args:submit_draft(workspace,dispatcher,*args,schedule_owner=actor)) if scheduled else None,
        submit_group=lambda body:create_group(workspace.datasets,workspace.sales,workspace.jobs,body,
            lambda key:dispatcher(workspace,key),lifecycle=workspace.lifecycle,site=workspace.site),site=workspace.site)


def schedule_authorized(service, workspace, owner):
    try:
        company,issuer,subject=json.loads(owner)
        if company!=workspace.company_id or service is None:return False
        answer=asyncio.run(service.call('schedules/authorize',dict(company_id=company,issuer=issuer,subject=subject)))
        return answer.get('allowed') is True
    except Exception:
        # No cached grants, cookies or keys. Identity outages stop new work.
        return False


def recurring(workspace, dispatcher, service):
    return RecurringForecasts(workspace.path('recurring.sqlite3'),monthly(workspace,dispatcher,True),
        authorized=lambda owner:schedule_authorized(service,workspace,owner),
        timezone_name=lambda:workspace.site['timezone'])

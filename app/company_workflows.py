"""Company-owned adapters for existing scenario, monthly and scheduled workflows."""
import asyncio
import json
from .monthly_refresh import MonthlyRefresh
from .recurring_forecasts import RecurringForecasts
from .sales_demand import demand_outlook


def outlook(workspace, key):
    saved=workspace.sales.get(key)
    return {**demand_outlook(saved['inputs'],workspace.load_run(saved['inputs']['run_id'])),
            'snapshot_id':key,'created_at':saved['created_at'],'evidence':saved['evidence']}


def submit_draft(workspace, dispatcher, payload, name, request_id, schedule_owner=None, retry_of=None):
    from .main import SavedRunConfig
    from .factor_links import preview_link
    from .factor_batch import check_saved_batch
    from .input_review import input_report
    values=SavedRunConfig(**payload).model_dump()
    source=workspace.datasets.get(values['dataset_id'])
    if source['sources'].get('operations') or values['scenario_name'] or values['adjustment'] or values['sales_input_id']:
        raise ValueError('Use reviewed sales and factor inputs for this draft.')
    proof=source.get('scenario_provenance')
    if proof:
        if values['base_run_id']!=proof.get('base_run_id') or values['method']:
            raise ValueError('Use the comparison’s recorded baseline and method.')
        base=workspace.load_run(proof['base_run_id'])
        if proof['type']=='factor_link':
            report=preview_link(base,workspace.datasets,workspace.factors,proof['reviewed_inputs'],workspace.live_sources,workspace.profiles)
            if report['missing'] or report['review_token']!=proof['review_token']:
                raise ValueError('Factor inputs changed. Review them again.')
        elif proof['type']=='factor_batch':
            check_saved_batch(base,source,workspace.datasets,workspace.factors,workspace.live_sources,workspace.profiles)
        elif proof['type']!='factor_comparison':
            raise ValueError('Choose reviewed factor inputs.')
    elif values['base_run_id'] or input_report(workspace.datasets,source)['errors']:
        raise ValueError('Review sales inputs before calculating.')
    if schedule_owner:values['_schedule_owner']=schedule_owner
    job=workspace.jobs.create(values,name,request_id,retry_of=retry_of)
    if job['state']=='queued':dispatcher(workspace,job['id'])
    return {k:v for k,v in job.items() if k not in {'owner','heartbeat_at','request_id'}}


def monthly(workspace, dispatcher, scheduled=False):
    return MonthlyRefresh(workspace.path('monthly-updates.sqlite3'),workspace.datasets,workspace.load_run,
        workspace.sales,lambda key:outlook(workspace,key),workspace.jobs,
        lambda *args:submit_draft(workspace,dispatcher,*args),workspace.live_sources,
        submit_for_actor=(lambda actor,*args:submit_draft(workspace,dispatcher,*args,schedule_owner=actor)) if scheduled else None)


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

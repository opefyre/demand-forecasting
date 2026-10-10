"""One reviewed grouped calculation contract for new and monthly forecasts."""
import uuid

from .forecast_orders import context, reviewed
from .sales_demand import StaleOrderRevision


def method_choices(settings):
    from .forecast_engine import _model_specs, _factor_specs, METHOD_GROUPS
    drivers = settings.get('drivers', [])
    factors = _factor_specs(settings.get('profile', 'deep'), drivers) if 1 <= len(drivers) <= 8 else []
    result = {'recommended', *METHOD_GROUPS} | {'model:' + spec.name for spec in
        _model_specs(settings.get('profile', 'deep')) + factors}
    if factors:
        result.add('factor_test')
    return result


def check_methods(methods, settings):
    if not methods or len(methods) > 24 or len(set(methods)) != len(methods) or any(
            method not in method_choices(settings) for method in methods):
        raise ValueError('Choose distinct supported forecasting methods.')


def create_group(datasets, sales, jobs, body, dispatch, *, lifecycle=None, site=None):
    value = datasets.get(body['dataset_id'])
    if lifecycle:
        lifecycle.require_active('datasets', value['id'])
        for key in value['sources'].values():
            lifecycle.require_active('sources', key)
    parent_id = body.get('parent_forecast_id')
    if parent_id:
        jobs.get_group(parent_id)
        if lifecycle:
            lifecycle.require_active('forecasts', parent_id)
        if jobs.active_group_jobs(parent_id):
            raise ValueError('Wait for the previous forecast to finish before revising it.')
    if value.get('scenario_provenance') or set(value['sources']) - {'history', 'future'}:
        raise ValueError('Choose reviewed sales inputs.')
    reviewed(datasets, sales, value['id'], body['sales_input_id'], site=site)
    revisions = sales.list(context(datasets, value['id'], site=site)['run_id'])
    if not revisions or revisions[0]['id'] != body['sales_input_id']:
        raise StaleOrderRevision('A newer order review exists. Use the latest reviewed inputs.')
    check_methods(body['methods'], value['settings'])
    identifier = uuid.uuid5(uuid.NAMESPACE_URL, 'demandlab-group:' + body['request_id']).hex
    payloads = [{'dataset_id': value['id'], 'sales_input_id': body['sales_input_id'],
        'method': method, 'forecast_group_id': identifier, 'forecast_name': body['name']}
        for method in body['methods']]
    if parent_id:
        for payload in payloads:
            payload['parent_forecast_id'] = parent_id
    group = jobs.create_group(payloads, body['name'], body['request_id'])
    # All methods are durable before dispatch. An exact retry uses the same jobs.
    for job in group['jobs']:
        if job['state'] == 'queued':
            dispatch(job['id'])
    return jobs.get_group(identifier)

"""One forecast workflow: review orders before fitting, reconcile before publishing.

The input context has dates/identities only. No placeholder predictions are fitted
or stored. Existing customer-order validation and consumption mathematics are reused.
"""
from copy import deepcopy
import hashlib
from decimal import Decimal

from .forecast_inputs import input_context
from .sales_api import run_hash, template_customers
from .sales_demand import validate_inputs, demand_outlook, import_rows, run_today, StaleOrderRevision
from .order_reuse import compatible


def context(datasets, identifier, *, site=None):
    if site is None:
        from .main import SITE_PROFILE
        site = SITE_PROFILE
    value = input_context(datasets, identifier)
    settings = value['input_manifest']['settings']
    value.update(unit=settings.get('unit', 'units'),
                 run_settings={'frequency': 'monthly', 'calendar_profile': {
                     'month_basis': settings.get('month_basis', 'gregorian')}},
                 site=deepcopy(site))
    return value


def starter(datasets, identifier, *, site=None):
    value = context(datasets, identifier, site=site)
    today = str(run_today(value))
    return {'context': value, 'inputs': {'name': 'Forecast inputs', 'run_id': value['run_id'],
            'as_of': today, 'valid_until': today, 'classification': value['source_classification'],
            'order_feed': 'unknown', 'customers': template_customers(value),
            'orders': [], 'commitments': [], 'reviewed': False, 'note': ''}}


def prepare(datasets, sales, identifier, payload, load_run, *, site=None):
    value = context(datasets, identifier, site=site)
    inputs = deepcopy(payload.get('inputs', {}))
    evidence = []
    for role, config in payload.get('imports', {}).items():
        rows, proof = import_rows(datasets, role, config)
        inputs[role] = rows
        evidence.append(proof)
    source_id = payload.get('reuse_snapshot_id')
    if source_id:
        source = sales.get(source_id)
        base = load_run(source['inputs']['run_id'])
        if not compatible(base, value):
            raise ValueError('Saved orders must match these customers, products, units and calendar.')
        if sales.list(base['run_id'])[0]['id'] != source_id:
            raise StaleOrderRevision('A newer order version exists. Review current orders again.')
        if next((e.get('run_sha256') for e in source['evidence'] if 'run_sha256' in e), None) != run_hash(base):
            raise ValueError('The original forecast changed. Review its orders again.')
        # The UI may change freshness/coverage after a deliberate new review, but
        # cannot edit saved lines covertly while claiming that they were reused.
        for role in ('customers', 'orders', 'commitments'):
            if role not in payload.get('imports', {}) and inputs.get(role) != source['inputs'][role]:
                raise ValueError('Saved order lines changed. Import and review a replacement instead.')
        evidence.append({'type': 'wizard_order_reuse', 'source_snapshot_id': source_id,
                         'source_sha256': source['sha256']})
    inputs = validate_inputs(inputs, value).model_dump(mode='json')
    if any(c['unit'] != value['unit'] for c in inputs['customers']):
        raise ValueError('Customer quantities must use the forecast unit. Convert units explicitly before importing.')
    used = {c['series_id'] for c in inputs['customers'] if c['series_id']}
    unmapped = sorted(set(value['series']) - used - {'__all__'})
    if unmapped:
        raise ValueError('Include every historical customer/product series in the customer list.')
    periods = sorted({r['timestamp'] for s in value['series'].values() for r in s['forecast']})
    warnings = []
    if inputs['order_feed'] == 'unknown':
        warnings.append('Orders are missing or incomplete. Final demand totals and exports will be blocked.')
    if inputs['valid_until'] < str(run_today(value)):
        raise ValueError('Orders have expired. Refresh and review before calculating.')
    from .sales_demand import month, month_basis
    for order in inputs['orders']:
        if order['status'] == 'confirmed' and Decimal(order['ordered']) > Decimal(order['fulfilled']) + Decimal(order['cancelled']):
            if month(order['due_date'], month_basis(value)) not in periods:
                warnings.append('Some open orders are outside the selected forecast months. Review their delivery dates.')
                break
    evidence.append({'type': 'forecast_order_inputs', 'dataset_id': identifier,
                     'context_sha256': run_hash(value)})
    report = {'customer_count': len({c['customer'] for c in inputs['customers']}),
              'relationship_count': len(inputs['customers']), 'order_count': len(inputs['orders']),
              'periods': periods, 'warnings': warnings, 'inputs': inputs}
    report['review_token'] = run_hash({'inputs': inputs, 'evidence': evidence})
    return report, inputs, value, evidence


def save(datasets, sales, identifier, payload, load_run, actor, *, site=None):
    report, inputs, value, evidence = prepare(datasets, sales, identifier, payload, load_run, site=site)
    if payload.get('review_token') != report['review_token']:
        raise StaleOrderRevision('Inputs changed. Review them before continuing.')
    return sales.save(inputs, value, payload.get('request_id'), actor, evidence)


def reviewed(datasets, sales, identifier, snapshot_id, *, site=None):
    value = context(datasets, identifier, site=site)
    saved = sales.get(snapshot_id)
    proof = next((e for e in saved['evidence'] if e.get('type') == 'forecast_order_inputs'), {})
    if proof.get('dataset_id') != identifier or proof.get('context_sha256') != run_hash(value):
        raise ValueError('Sales data or factors changed. Review customers and orders again.')
    validate_inputs(saved['inputs'], value)
    if any(c['unit'] != value['unit'] for c in saved['inputs']['customers']):
        raise ValueError('Customer quantities must use the forecast unit. Convert units explicitly before importing.')
    if saved['inputs']['valid_until'] < str(run_today(value)):
        raise ValueError('Orders have expired. Refresh and review before calculating.')
    reuse = next((e for e in saved['evidence'] if e.get('type') == 'wizard_order_reuse'), None)
    if reuse:
        source = sales.get(reuse['source_snapshot_id'])
        if sales.list(source['inputs']['run_id'])[0]['id'] != source['id'] or source['sha256'] != reuse['source_sha256']:
            raise StaleOrderRevision('Saved orders changed. Review the current version before calculating.')
    return saved


def finalize(datasets, sales, result, snapshot_id, folder, *, site=None):
    saved = reviewed(datasets, sales, result['dataset_id'], snapshot_id, site=site)
    inputs = deepcopy(saved['inputs'])
    inputs['run_id'] = result['run_id']
    outlook = demand_outlook(inputs, result)
    request_id = 'forecast-orders:' + result['run_id']
    result['sales_input_snapshot_id'] = hashlib.sha256(request_id.encode()).hexdigest()[:32]
    result['forecast_order_inputs_id'] = snapshot_id
    result['demand_summary'] = {
        'total': sum(r['total'] for r in outlook['rows']) if outlook['can_export'] else None,
        'known_orders': sum(r['booked'] for r in outlook['rows']),
        'can_export': outlook['can_export'], 'warnings': outlook['warnings'], 'unit': result['unit']}
    evidence = [{'run_sha256': run_hash(result)}, {'type': 'forecast_workflow',
                 'inputs_snapshot_id': snapshot_id, 'inputs_sha256': saved['sha256'],
                 'source_evidence': saved['evidence']}]
    sales.save(inputs, result, request_id, saved['actor'], evidence)
    # The regular model workbook is still evidence; combined demand is an extra
    # sheet, not a silent replacement of the model's original numbers.
    package = folder / 'forecast_package.xlsx'
    if package.exists():
        import pandas as pd
        with pd.ExcelWriter(package, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            fields = ['customer', 'sku', 'period', 'unit', 'baseline', 'booked', 'fulfilled', 'remaining', 'total', 'issue']
            pd.DataFrame([{k: r[k] for k in fields} for r in outlook['rows']]).to_excel(writer, sheet_name='Combined demand', index=False)
            for row in writer.book['Combined demand']:
                for cell in row:
                    if cell.data_type == 'f':
                        cell.data_type = 's'
    return result

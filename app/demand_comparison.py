"""Reuse an exact reviewed order book for a separate scenario; never mutate orders."""
from copy import deepcopy
import hashlib
import json

from .sales_demand import demand_outlook, StaleOrderRevision


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def compare_orders(store, load_run, target_id, snapshot_id):
    target = load_run(target_id)
    if not target.get('base_run_id') or target.get('scenario', {}).get('type') != 'factor_link':
        raise ValueError('Choose a linked-factor scenario with a saved baseline.')
    base = load_run(target['base_run_id'])
    saved = store.get(snapshot_id)
    if saved['inputs']['run_id'] != base['run_id']:
        raise ValueError('Choose an order review from this scenario’s baseline.')
    latest = store.list(base['run_id'])
    if not latest or latest[0]['id'] != saved['id']:
        raise StaleOrderRevision('A newer order review is available. Select the latest version.')
    proof = next((e['run_sha256'] for e in saved['evidence'] if 'run_sha256' in e), None)
    if proof != digest(base):
        raise ValueError('The baseline changed since the order review. Review its orders again.')
    def scope(run):
        return {(key, str(p['timestamp'])[:10]) for key,s in run['series'].items()
                if key != '__all__' for p in s['forecast']}
    if (scope(base) != scope(target) or base.get('unit') != target.get('unit')
            or base.get('source_classification') != target.get('source_classification')):
        raise ValueError('Baseline and scenario must have matching series, periods, units and data type.')
    inputs = deepcopy(saved['inputs'])
    inputs.update(run_id=target_id, name=inputs['name'] + ' · scenario')
    before = demand_outlook(saved['inputs'], base)
    after = demand_outlook(inputs, target)
    key = lambda r: (r['customer'], r['sku'], r['unit'], r['period'])
    indexed = {key(r):r for r in after['rows']}
    if {key(r) for r in before['rows']} != set(indexed):
        raise ValueError('Customer and period coverage changed. Review the scenario inputs separately.')
    rows = []
    for old in before['rows']:
        new = indexed[key(old)]
        if old['booked'] != new['booked'] or old['fulfilled'] != new['fulfilled']:
            raise ValueError('Order quantities changed during the comparison.')
        rows.append({k:old[k] for k in ('customer','sku','unit','period','booked','fulfilled')} |
            {'before_remaining':old['remaining'], 'after_remaining':new['remaining'],
             'before_total':old['total'], 'after_total':new['total'],
             'difference':None if old['total'] is None or new['total'] is None else new['total']-old['total'],
             'issue':new['issue'] or old['issue']})
    targets=store.list(target_id)
    guard={'source_id':saved['id'],'source_sha256':saved['sha256'],
           'target_latest_id':targets[0]['id'] if targets else None}
    report={'source_snapshot_id':saved['id'],'source_name':saved['inputs']['name'],
            'base_run_id':base['run_id'],'target_run_id':target_id, 'unit':target['unit'],
            'as_of':before['as_of'],'valid_until':before['valid_until'],'rows':rows,
            'warnings':list(dict.fromkeys(before['warnings']+after['warnings'])),
            'can_save':before['can_export'] and after['can_export'], 'guard':guard,
            'classification':target['source_classification']}
    report['review_token']=digest({'report':report,'source':saved,'base':digest(base),'target':digest(target)})
    evidence=[{'run_sha256':digest(target)}, {'type':'scenario_order_reuse','source_snapshot_id':saved['id'],
        'source_sha256':saved['sha256'],'source_evidence':saved['evidence'],
        'base_run_sha256':digest(base),'review_token':report['review_token'],
        'orders_changed':False,'publication_approval_carried':False}]
    return report, inputs, target, evidence


def save_comparison(store, load_run, target_id, payload, actor):
    request_id=payload.get('request_id')
    if payload.get('reviewed') is not True or not isinstance(request_id,str) or not 8 <= len(request_id) <= 100:
        raise ValueError('Review the comparison and provide a retry identifier.')
    try:
        existing=store.get(hashlib.sha256(request_id.encode()).hexdigest()[:32])
    except ValueError:
        existing=None
    if existing:
        proof=next((e for e in existing['evidence'] if e.get('type')=='scenario_order_reuse'),{})
        if (existing['inputs']['run_id']!=target_id or proof.get('source_snapshot_id')!=payload.get('snapshot_id')
                or proof.get('review_token')!=payload.get('review_token')):
            raise ValueError('This retry identifier already saved different inputs.')
        return existing
    report, inputs, target, evidence=compare_orders(store,load_run,target_id,payload.get('snapshot_id',''))
    if payload.get('reviewed') is not True or payload.get('review_token') != report['review_token']:
        raise ValueError('Review this exact order-aware comparison before saving.')
    if not report['can_save']:
        raise ValueError('Resolve expired orders, missing customer coverage or unknown totals before saving.')
    return store.save(inputs,target,payload.get('request_id'),actor,evidence,
                      comparison_guard=report['guard'])

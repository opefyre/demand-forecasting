"""Explicit, coverage-reviewed reuse of orders across monthly forecast horizons."""
from copy import deepcopy
from .demand_comparison import digest
from .sales_demand import demand_outlook, StaleOrderRevision, month_basis


def compatible(base, target):
    def scope(run):
        return {key:(str(run.get('metadata',{}).get(key,{}).get('customer','')),
                     str(run.get('metadata',{}).get(key,{}).get('sku','')))
                for key in run['series'] if key != '__all__'}
    return (base['run_id'] != target['run_id'] and bool(scope(base))
            and all(customer and sku for customer,sku in scope(base).values())
            and scope(base) == scope(target)
            and base.get('unit') == target.get('unit')
            and base.get('source_classification') == target.get('source_classification')
            and month_basis(base) == month_basis(target)
            and all(r.get('run_settings',{}).get('frequency') == 'monthly' for r in (base,target)))


def preview_reuse(store, load_run, target_id, snapshot_id):
    target=load_run(target_id);source=store.get(snapshot_id);base=load_run(source['inputs']['run_id'])
    if not compatible(base,target):
        raise ValueError('Choose a monthly forecast with the same customer/SKU series, units, planning calendar and data type.')
    if store.list(base['run_id'])[0]['id'] != snapshot_id:
        raise StaleOrderRevision('A newer order version exists. Reopen the order review.')
    if next((e.get('run_sha256') for e in source['evidence'] if 'run_sha256' in e),None) != digest(base):
        raise ValueError('The original forecast changed. Review its orders again.')
    inputs=deepcopy(source['inputs']);inputs.update(run_id=target_id,name=inputs['name'][:140]+' · reused')
    outlook=demand_outlook(inputs,target)
    periods=lambda r:{str(p['timestamp'])[:10] for k,s in r['series'].items() if k!='__all__' for p in s['forecast']}
    old,new=periods(base),periods(target)
    months={}
    for row in outlook['rows']:
        item=months.setdefault(row['period'],{'period':row['period'],'added':row['period'] not in old,
                                               'booked':0,'remaining':0,'total':0})
        for field in ('booked','remaining','total'):
            item[field]=None if item[field] is None or row[field] is None else item[field]+row[field]
    excluded=[r for r in outlook['orders'] if r['reason']=='Outside forecast periods'
              and r['status']=='confirmed' and r['outstanding']>0]
    latest=store.list(target_id)
    report={'source_snapshot_id':snapshot_id,'source_name':source['inputs']['name'],'target_run_id':target_id,
            'month_basis':month_basis(target),
            'source_run_id':base['run_id'],'as_of':outlook['as_of'],'valid_until':outlook['valid_until'],
            'unit':target['unit'],'classification':target['source_classification'],
            'months':[months[k] for k in sorted(months)],'added_months':sorted(new-old),'removed_months':sorted(old-new),
            'outside_open_orders':[{'reference':r['reference'],'period':r['period'],'quantity':r['outstanding']} for r in excluded],
            'customer_count':len({c['customer'] for c in inputs['customers']}),'order_count':len(inputs['orders']),
            'warnings':outlook['warnings'],'can_save':outlook['can_export'],
            'guard':{'source_id':snapshot_id,'source_sha256':source['sha256'],'target_latest_id':latest[0]['id'] if latest else None}}
    report['review_token']=digest({'report':report,'source':source,'base':digest(base),'target':digest(target)})
    evidence=[{'run_sha256':digest(target)}, {'type':'horizon_order_reuse','source_snapshot_id':snapshot_id,
        'source_sha256':source['sha256'],'source_evidence':source['evidence'],'base_run_sha256':digest(base),
        'review_token':report['review_token'],'added_months':report['added_months'],'removed_months':report['removed_months'],
        'coverage_confirmed':True,'orders_changed':False,'publication_approval_carried':False}]
    return report,inputs,target,evidence


def save_reuse(store,load_run,target_id,payload,actor):
    request_id=payload.get('request_id')
    if (payload.get('reviewed') is not True or payload.get('coverage_confirmed') is not True
            or not isinstance(request_id,str) or not 8<=len(request_id)<=100):
        raise ValueError('Confirm the full order-book coverage for every displayed month before saving.')
    import hashlib
    try:existing=store.get(hashlib.sha256(request_id.encode()).hexdigest()[:32])
    except ValueError:existing=None
    if existing:
        proof=next((e for e in existing['evidence'] if e.get('type')=='horizon_order_reuse'),{})
        if (existing['inputs']['run_id']!=target_id or proof.get('source_snapshot_id')!=payload.get('snapshot_id')
                or proof.get('review_token')!=payload.get('review_token')):
            raise ValueError('This retry identifier was already used for different inputs.')
        return existing
    report,inputs,target,evidence=preview_reuse(store,load_run,target_id,payload.get('snapshot_id',''))
    if payload.get('review_token')!=report['review_token']:
        raise StaleOrderRevision('Inputs changed. Review the current order coverage before saving.')
    if not report['can_save']:
        raise ValueError('Refresh expired orders or resolve missing customer demand before reusing this order book.')
    return store.save(inputs,target,request_id,actor,evidence,comparison_guard=report['guard'])

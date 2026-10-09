"""Score a composed scenario on the same reserved observations as its baseline."""
import math
import numpy as np
from .forecast_engine import _metric_bundle


def scoped_accuracy(base, candidate, selected):
    def unavailable(reason):
        return {'available':False,'reason':reason,'rows':[]}
    bm,cm = base.get('metrics',{}),candidate.get('metrics',{})
    if (base.get('engine') != candidate.get('engine') or base.get('unit') != candidate.get('unit') or
            not bm.get('evaluation_signature') or
            bm.get('evaluation_signature') != cm.get('evaluation_signature')):
        return unavailable('Matching engine and historical test periods are required.')
    if not bm.get('independent_accuracy_verified') or not cm.get('independent_accuracy_verified'):
        return unavailable('Separate historical test evidence is incomplete.')
    keys = set(base['series']) - {'__all__'}
    if set(selected) - keys:
        return unavailable('Selected customer/product scope is unknown.')
    def index(metrics):
        indexed={}
        for row in metrics.get('range_check',{}).get('rows',[]):
            if row['item_id']=='__portfolio__':
                continue
            key=(row['item_id'],row['timestamp'],row['step'])
            if key in indexed or row['item_id'] not in keys:
                raise ValueError('Duplicate or unknown historical test observations.')
            if not all(isinstance(row.get(f),(int,float)) and not isinstance(row[f],bool)
                       and math.isfinite(row[f]) for f in ('actual','predicted')):
                raise ValueError('Historical test observations contain invalid quantities.')
            if row['timestamp'] not in metrics.get('confirmation_periods',[]):
                raise ValueError('Historical observations are outside the reserved test periods.')
            indexed[key]=row
        if (not indexed or len(indexed)!=metrics.get('validation_points') or
                {k[1] for k in indexed} != set(metrics.get('confirmation_periods',[]))):
            raise ValueError('Historical test observations are missing.')
        return indexed
    try:
        before,after=index(bm),index(cm)
    except (ValueError,KeyError,TypeError) as exc:
        return unavailable(str(exc))
    if set(before)!=set(after) or {k[0] for k in before}!=keys:
        return unavailable('Customer/product test coverage differs.')
    rows=[]
    for key,old in sorted(before.items()):
        new=after[key]
        if old['actual']!=new['actual']:
            return unavailable('Actual quantities differ between historical tests.')
        use_new=key[0] in selected
        rows.append({'item_id':key[0],'timestamp':key[1],'step':key[2],'actual':old['actual'],
                     'predicted':new['predicted'] if use_new else old['predicted'],
                     'baseline_predicted':old['predicted'],
                     'source':'factor_scenario' if use_new else 'saved_baseline'})
    def score(items):
        return _metric_bundle(np.array([r['actual'] for r in items]),np.array([r['predicted'] for r in items]))
    return {'available':True,'reason':'Matched reserved historical observations; not a guarantee of future accuracy.',
            'rows':rows,'metrics':score(rows),
            'horizon_metrics':[{'step':step,**score([r for r in rows if r['step']==step])}
                               for step in sorted({r['step'] for r in rows})]}

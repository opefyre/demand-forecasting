"""Local synthetic demo only; no client orders are created or changed."""
import argparse
import json
import math
import httpx
from io import BytesIO
import pandas as pd

URL='http://127.0.0.1:8010'
BASE='58df6ab41b1f'

def api(path,payload=None):
    response=httpx.get(URL+path,timeout=30) if payload is None else httpx.post(URL+path,json=payload,timeout=30)
    response.raise_for_status();return response.json()

def seed():
    existing=api(f'/api/sales/runs/{BASE}/inputs')['snapshots']
    if existing:
        print(json.dumps({'snapshot':existing[0]['id'],'existing':True}));return
    inputs=api(f'/api/sales/runs/{BASE}/sample')
    assert inputs['classification']=='synthetic_sample' and len(inputs['customers'])==6
    assert all(r['reference'].startswith('SAMPLE-') for r in inputs['orders'])
    inputs['reviewed']=True
    preview=api('/api/sales/validate',{'inputs':inputs})
    assert preview['can_export'] and len(preview['rows'])==36
    saved=api('/api/sales/inputs',{'inputs':inputs,'request_id':'order-comparison-demo-20260924'})
    print(json.dumps({'snapshot':saved['id'],'rows':len(preview['rows']),'orders':len(inputs['orders'])}))

def verify(key):
    saved=api('/api/sales/inputs/'+key)
    proof=next(e for e in saved['evidence'] if e.get('type')=='scenario_order_reuse')
    source=api('/api/sales/inputs/'+proof['source_snapshot_id'])
    assert proof['source_sha256']==source['sha256'] and not proof['publication_approval_carried']
    for field in ['customers','orders','commitments','as_of','valid_until','order_feed']:
        assert saved['inputs'][field]==source['inputs'][field]
    before=api('/api/sales/inputs/'+source['id']+'/outlook');after=api('/api/sales/inputs/'+key+'/outlook')
    assert before['can_export'] and after['can_export'] and len(after['rows'])==len(before['rows'])>0
    index=lambda r:(r['customer'],r['sku'],r['unit'],r['period'])
    old={index(r):r for r in before['rows']}
    for row in after['rows']:
        assert row['booked']==old[index(row)]['booked']
        assert math.isclose(row['total'],row['booked']+row['fulfilled']+row['remaining'],abs_tol=1e-8)
        assert row['total']>=row['booked']+row['fulfilled']
    for mode,field in [('combined_demand','still_to_serve'),('remaining_forecast','remaining')]:
        data=api(f'/api/sales/inputs/{key}/export?mode={mode}&kind=json')
        assert len(data)==len(after['rows']) and all(r['approval']=='draft' for r in data)
        assert math.isclose(sum(r['quantity'] for r in data),sum(r[field] for r in after['rows']),abs_tol=1e-8)
    for kind,mode,field in [('xlsx','combined_demand','still_to_serve'),('csv','remaining_forecast','remaining')]:
        response=httpx.get(f'{URL}/api/sales/inputs/{key}/export?mode={mode}&kind={kind}');response.raise_for_status()
        frame=pd.read_excel(BytesIO(response.content)) if kind=='xlsx' else pd.read_csv(BytesIO(response.content))
        assert len(frame)==len(after['rows']) and math.isclose(frame.quantity.sum(),sum(r[field] for r in after['rows']),abs_tol=1e-8)
    print(json.dumps({'source_snapshot':source['id'],'scenario_snapshot':key,'rows':len(after['rows']),
        'booked':sum(r['booked'] for r in after['rows']),
        'baseline_total':sum(r['total'] for r in before['rows']),
        'scenario_remaining':sum(r['remaining'] for r in after['rows']),
        'scenario_total':sum(r['total'] for r in after['rows']),
        'source_unchanged':True,'exports_reconciled':True,'approval':'draft'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--seed',action='store_true');group.add_argument('--verify')
    args=parser.parse_args();seed() if args.seed else verify(args.verify)

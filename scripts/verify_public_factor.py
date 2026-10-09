"""Create a separate labelled synthetic sales baseline, or verify its public-factor comparison.

Sales start Feb 2022 because the public vintage archive starts Jan 2022. This is
a new generated sample, not silent trimming of client or existing demo history.
"""
import argparse
from io import BytesIO
import json
import math
import uuid

import httpx
import pandas as pd

URL='http://127.0.0.1:8010'
NAME='Public factor comparison · synthetic sales'


def api(path, payload=None):
    response=httpx.get(URL+path,timeout=120) if payload is None else httpx.post(URL+path,json=payload,timeout=120)
    response.raise_for_status();return response.json()


def seed():
    existing=next((d for d in api('/api/datasets')['datasets'] if d['name']==NAME and d['classification']=='synthetic_sample'),None)
    if not existing:
        rows=[]
        for customer_no,customer in enumerate(['Demo A','Demo B','Demo C']):
            for sku_no,sku in enumerate(['Demo SKU 1','Demo SKU 2']):
                for i,period in enumerate(pd.date_range('2022-02-01','2026-08-01',freq='MS')):
                    quantity=40+customer_no*12+sku_no*7+i*.2+8*math.sin(i*math.pi/6)+2*math.cos(i*1.7)
                    rows.append({'date':period.date().isoformat(),'series':customer+' / '+sku,
                        'customer':customer,'sku':sku,'quantity':round(quantity,3)})
        response=httpx.post(URL+'/api/sources',files={'file':('public_factor_synthetic_sales.csv',pd.DataFrame(rows).to_csv(index=False).encode())},data={'role':'history'},timeout=30)
        response.raise_for_status()
        existing=api('/api/datasets',{'name':NAME,'sources':{'history':response.json()['id']},
            'settings':{'date_col':'date','target_col':'quantity','item_col':'series','customer_col':'customer','sku_col':'sku',
                'drivers':[],'frequency':'monthly','horizon':6,'unit':'tonnes','profile':'fast','future_driver_policy':'require',
                'method_selection':'model:Ridge + drivers','missing_strategy':'auto','outlier_strategy':'none'},
            'classification':'synthetic_sample','accept_warnings':True})
    run=api('/api/run-saved',{'dataset_id':existing['id']})
    snapshots=api('/api/runs/'+run['run_id']+'/factor-links')['snapshots']
    factor=next(s for s in snapshots if s.get('public_vintage'))
    print(json.dumps({'baseline':run['run_id'],'dataset':existing['id'],'public_snapshot':factor['id'],
        'baseline_error_pct':run['metrics']['wape_pct'],'series':len(run['items'])}))


def verify(key):
    result=api('/api/runs/'+key);base=api('/api/runs/'+result['base_run_id'])
    assert result['source_classification']==base['source_classification']=='synthetic_sample'
    assert result['scenario']['alignment']['availability_policy']=='vintage_month_end'
    assert result['metrics']['evaluation_signature']==base['metrics']['evaluation_signature']
    assert not result['scenario']['orders_changed'] and not result['scenario']['release_dates_verified']
    assert result['items']==base['items']
    for item in base['items']:
        assert base['series'][item]['history']==result['series'][item]['history']
    for row in result['series']['__all__']['forecast']:
        total=math.fsum(p['mean'] for key in result['items'] for p in result['series'][key]['forecast'] if p['timestamp']==row['timestamp'])
        assert math.isclose(row['mean'],total,abs_tol=1e-6)
    rows=result['scenario']['alignment']['rows']
    for row in rows:
        if row['treatment']=='archived_vintage':
            assert row['publication_date'] is None and row['availability_date']<row['available_before']
    response=httpx.get(URL+'/api/export/'+key+'/xlsx',timeout=30);response.raise_for_status()
    with pd.ExcelFile(BytesIO(response.content)) as book:
        assert 'vintage_month' in pd.read_excel(book,sheet_name='Factor alignment')
        assert 'attribution' in pd.read_excel(book,sheet_name='Factor sources')
    print(json.dumps({'run':key,'baseline':base['run_id'],'series':len(base['items']),
        'baseline_error_pct':base['metrics']['wape_pct'],'linked_error_pct':result['metrics']['wape_pct'],
        'baseline_total':sum(r['mean'] for r in base['series']['__all__']['forecast']),
        'linked_total':sum(r['mean'] for r in result['series']['__all__']['forecast']),
        'history_unchanged':True,'totals_reconciled':True,'export_verified':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--seed',action='store_true');group.add_argument('--verify')
    args=parser.parse_args();seed() if args.seed else verify(args.verify)

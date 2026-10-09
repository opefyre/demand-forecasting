"""Local synthetic Persian-month demo. No client data or external AI calls."""
import argparse
import csv
from datetime import date
from io import StringIO, BytesIO
import json
import math
import uuid

import httpx
import pandas as pd
from persiantools.jdatetime import JalaliDate

URL='http://127.0.0.1:8010'


def api(path,payload=None,**kwargs):
    response=httpx.post(URL+path,json=payload,timeout=60,**kwargs) if payload is not None or kwargs else httpx.get(URL+path,timeout=20)
    response.raise_for_status()
    return response.json()


def prepare():
    stream=StringIO();writer=csv.writer(stream)
    writer.writerow(['period','quantity','series_id','customer','sku'])
    for step in range(36):
        year,month=divmod(1402*12+6+step,12)
        for customer,offset in [('Demo Tehran A',0),('Demo Tehran B',20)]:
            writer.writerow([f'{year:04d}-{month+1:02d}-01',round(90+offset+step*.7+10*math.sin(step*math.pi/6),3),customer+' / SKU-01',customer,'SKU-01'])
    source=api('/api/sources',files={'file':('synthetic_persian_sales.csv',stream.getvalue().encode(),'text/csv')},data={'role':'history'})
    settings={'date_col':'period','target_col':'quantity','item_col':'series_id','customer_col':'customer','sku_col':'sku',
        'unit':'tonnes','frequency':'monthly','horizon':10,'profile':'fast','drivers':[],
        'history_calendar':'jalali','history_grain':'monthly_totals','month_basis':'jalali',
        'sales_measure':'customer_demand','returns_policy':'reject','calendar_country':'IR','weekend_days':[4],
        'method_selection':'model:Weighted recent average','missing_strategy':'auto','outlier_strategy':'none'}
    dataset=api('/api/datasets',{'name':'Demo · Persian months · sales and orders','sources':{'history':source['id']},
        'settings':settings,'classification':'synthetic_sample','accept_warnings':True,'request_id':str(uuid.uuid4())})
    job=api('/api/jobs',{'dataset_id':dataset['id'],'request_id':str(uuid.uuid4())})
    print(json.dumps({'job_id':job['id'],'dataset_id':dataset['id'],'synthetic_only':True}))


def verify(job_id):
    job=api('/api/jobs/'+job_id)
    if job['state']!='succeeded':
        print(json.dumps({'state':job['state'],'error':job.get('error')}));return
    run_id=job['run_id'];run=api('/api/runs/'+run_id)
    basis=run['run_settings']['calendar_profile']['month_basis']
    assert basis=='jalali'
    starter=api(f'/api/sales/runs/{run_id}/starter')
    first=starter['customers'][0]
    start=run['series'][first['series_id']]['forecast'][0]['timestamp'][:10]
    starter.update(name='Demo · Persian months · mixed orders',order_feed='complete_snapshot',
        valid_until='2026-12-31',reviewed=True,note='Synthetic monthly sales and one customer order; not client accuracy evidence.',
        orders=[{'reference':'DEMO-ORDER-001','customer':first['customer'],'sku':first['sku'],'unit':'tonnes',
            'due_date':start,'ordered':160,'fulfilled':20,'cancelled':0,'status':'confirmed'}])
    snapshots=api(f'/api/sales/runs/{run_id}/inputs')['snapshots']
    if snapshots:
        saved=api('/api/sales/inputs/'+snapshots[0]['id'])
    else:
        saved=api('/api/sales/inputs',{'inputs':starter,'imports':{},'request_id':str(uuid.uuid4())})
    outlook=api('/api/sales/inputs/'+saved['id']+'/outlook')
    assert len(outlook['rows'])==20 and outlook['can_export']
    assert len({r['period_label'] for r in outlook['rows']})==10
    for row in outlook['rows']:
        j=JalaliDate(date.fromisoformat(row['period']))
        assert j.day==1 and row['period_label']==f'{j.year:04d}-{j.month:02d}'
        assert math.isclose(row['remaining'],max(0,row['baseline']-row['fulfilled']-row['booked']),abs_tol=1e-8)
    for kind in ('csv','xlsx','json'):
        response=httpx.get(URL+f'/api/sales/inputs/{saved["id"]}/export',params={'mode':'combined_demand','kind':kind},timeout=30)
        response.raise_for_status()
        frame=pd.DataFrame(response.json()) if kind=='json' else pd.read_csv(BytesIO(response.content)) if kind=='csv' else pd.read_excel(BytesIO(response.content))
        assert set(frame.planning_calendar)=={'jalali'}
        assert len(frame)==20
        assert math.isclose(frame.quantity.sum(),sum(r['still_to_serve'] for r in outlook['rows']),abs_tol=1e-8)
    print(json.dumps({'run_id':run_id,'orders_id':saved['id'],'rows':20,'months':10,'calendar':basis,
        'first_month':outlook['rows'][0]['period_label'],'three_exports_reconciled':True,'synthetic_only':True}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','verify']);parser.add_argument('job_id',nargs='?');args=parser.parse_args()
    prepare() if args.action=='prepare' else verify(args.job_id)

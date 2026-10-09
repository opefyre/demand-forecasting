"""Seed an explicitly synthetic dated factor, or verify a completed linked run."""
import argparse
from datetime import timedelta
from io import BytesIO
import json
import math
import uuid

import httpx
import pandas as pd
import openpyxl

URL='http://127.0.0.1:8010'
BASELINE='9c4db36b5af8'
NAME='Synthetic monthly context · linking demo'

def api(path, payload=None):
    r=httpx.get(URL+path,timeout=60) if payload is None else httpx.post(URL+path,json=payload,timeout=60)
    r.raise_for_status();return r.json()

def seed():
    base=api('/api/runs/'+BASELINE)
    assert base['source_classification']=='synthetic_sample' and not base.get('scenario_name')
    existing=next((s for s in api('/api/factors')['snapshots'] if s.get('name')==NAME and s.get('classification')=='synthetic_sample'),None)
    start=pd.Timestamp(base['summary']['start']).to_period('M')-2
    end=pd.Timestamp(base['summary']['end']).to_period('M')
    if existing and existing['summary']['first_period']==start.end_time.date().isoformat():
        print(json.dumps({'baseline':BASELINE,'snapshot':existing['id'],'existing':True}));return
    rows=[]
    for i,period in enumerate(pd.period_range(start,end,freq='M')):
        day=period.end_time.date()
        rows.append({'period':day.isoformat(),'value':round(100+i*.5+3*math.sin(i),3),'published':(day+timedelta(days=5)).isoformat()})
    # A later revision to the first observation must never reach the first sales month.
    rows.append({**rows[0],'value':999,'published':(start+5).start_time.date().isoformat()})
    data=pd.DataFrame(rows).to_csv(index=False).encode()
    response=httpx.post(URL+'/api/sources',files={'file':('synthetic_monthly_factor.csv',data)},data={'role':'factor_observations'},timeout=30)
    response.raise_for_status(); source=response.json()
    config={'source_id':source['id'],'name':NAME,'unit':'Index points (synthetic)','geography':'Iran · synthetic national example',
        'provider':'Generated demo, not actual inflation or exchange rates','frequency':'monthly','classification':'synthetic_sample',
        'mapping':{'period':'A','value':'B','available_at':'C'},'parent_id':existing['id'] if existing else None}
    review=api('/api/factor-imports/preview',config)
    saved=api('/api/factor-imports',{**config,'review_token':review['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())})
    print(json.dumps({'baseline':BASELINE,'snapshot':saved['id'],'observations':review['summary']['observations']}))

def verify(key):
    result=api('/api/runs/'+key);base=api('/api/runs/'+result['base_run_id'])
    assert result['scenario']['type']=='factor_link'
    assert result['source_classification']==base['source_classification']=='synthetic_sample'
    assert result['engine']==base['engine']
    assert result['metrics']['evaluation_signature']==base['metrics']['evaluation_signature']
    for item in base['items']:
        assert base['series'][item]['history']==result['series'][item]['history']
    for row in result['series']['__all__']['forecast']:
        expected=math.fsum(point['mean'] for item in result['items'] for point in result['series'][item]['forecast'] if point['timestamp']==row['timestamp'])
        assert math.isclose(row['mean'],expected,abs_tol=1e-6)
    alignment=result['scenario']['alignment'];assert not alignment['missing']
    assert alignment['rows'][0]['value']==100  # Not the later 999 revision.
    response=httpx.get(URL+'/api/export/'+key+'/xlsx',timeout=30);response.raise_for_status()
    book=openpyxl.load_workbook(BytesIO(response.content),data_only=True)
    assert book['Factor alignment'].max_row==len(alignment['rows'])+1
    book.close()
    print(json.dumps({'run':key,'baseline':base['run_id'],'series':len(result['items']),
        'baseline_error_pct':base['metrics']['wape_pct'],'linked_error_pct':result['metrics']['wape_pct'],
        'forecast_total':sum(r['mean'] for r in result['series']['__all__']['forecast']),
        'history_unchanged':True,'aggregate_reconciled':True,'export_verified':True}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--seed',action='store_true');group.add_argument('--verify')
    args=parser.parse_args();seed() if args.seed else verify(args.verify)

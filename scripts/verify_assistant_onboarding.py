"""Read-only verification of a synthetic assistant forecast/order journey. No AI calls."""
import argparse
from contextlib import closing
from io import BytesIO
import json
import math
from pathlib import Path
import sqlite3

import pandas as pd
import requests


def verify(run_id):
    base='http://127.0.0.1:8010'
    def api(path):
        response=requests.get(base+path,timeout=30);response.raise_for_status();return response.json()
    run=api('/api/runs/'+run_id)
    assert run['source_classification']=='synthetic_sample'
    snapshots=api(f'/api/sales/runs/{run_id}/inputs')['snapshots']
    assert snapshots
    key=snapshots[0]['id']; saved=api('/api/sales/inputs/'+key)
    proof=next(e for e in saved['evidence'] if e.get('type')=='horizon_order_reuse')
    source=api('/api/sales/inputs/'+proof['source_snapshot_id'])
    assert proof['source_sha256']==source['sha256']
    assert proof['coverage_confirmed'] and not proof['publication_approval_carried']
    for field in ('orders','customers','commitments','as_of','valid_until','order_feed'):
        assert saved['inputs'][field]==source['inputs'][field]
    outlook=api(f'/api/sales/inputs/{key}/outlook')
    assert outlook['can_export']
    rows=outlook['rows']; assert len({r['period'] for r in rows})==10
    assert len({r['customer'] for r in rows})==2
    assert len(rows)==20
    for row in rows:
        assert math.isclose(row['total'],row['fulfilled']+row['booked']+row['remaining'],abs_tol=1e-8)
        assert math.isclose(row['still_to_serve'],row['booked']+row['remaining'],abs_tol=1e-8)
        if row['booked']==0 and row['fulfilled']==0:
            assert row['remaining']>0
    for kind in ('csv','xlsx','json'):
        for mode,field in (('combined_demand','still_to_serve'),('remaining_forecast','remaining')):
            response=requests.get(base+f'/api/sales/inputs/{key}/export',params={'kind':kind,'mode':mode},timeout=30)
            response.raise_for_status()
            frame=pd.DataFrame(response.json()) if kind=='json' else (
                pd.read_csv(BytesIO(response.content)) if kind=='csv' else pd.read_excel(BytesIO(response.content)))
            assert len(frame)==20 and set(frame.approval)=={'draft'}
            assert set(frame.planning_calendar)=={'jalali'}
            assert math.isclose(frame.quantity.sum(),sum(row[field] for row in rows),abs_tol=1e-8)
    with closing(sqlite3.connect('data/ai-workspace.sqlite3')) as con:
        turns=[{**json.loads(row[1]),'id':row[0]} for row in con.execute('SELECT id,payload FROM ai_turns ORDER BY created DESC')]
    reuse=next(t for t in turns if any(r.get('snapshot_id')==key for r in t.get('results',{}).values()))
    job_id=next(j['id'] for j in api('/api/jobs')['jobs'] if j.get('run_id')==run_id)
    forecast=next(t for t in turns if any(r.get('job',{}).get('run_id')==run_id or
        r.get('job',{}).get('id')==job_id
        for r in t.get('results',{}).values()))
    assert forecast.get('run_id') is None and forecast.get('dataset_id')
    assert {'inspect_inputs','prepare_forecast'}.issubset(forecast['tools_used'])
    assert {'inspect_saved_orders','preview_saved_orders','prepare_saved_orders'}.issubset(reuse['tools_used'])
    return {'run_id':run_id,'snapshot_id':key,'months':10,'customer_sku_rows':20,
        'original_orders_unchanged':True,'six_exports_reconciled':True,
        'open_orders':sum(r['booked'] for r in rows),'fulfilled':sum(r['fulfilled'] for r in rows),
        'expected_not_ordered':sum(r['remaining'] for r in rows),'still_to_serve':sum(r['still_to_serve'] for r in rows),
        'live_turns':[{'id':t.get('id'),'context_run':t.get('run_id'),'tools':t['tools_used'],
                       'role':t['role'],'model':t['model'],'usage':t['usage']} for t in (forecast,reuse)],
        'total_reported_usage':{k:sum(t['usage'][k] for t in (forecast,reuse)) for k in ('requests','input_tokens','output_tokens')}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run_id');args=parser.parse_args()
    print(json.dumps(verify(args.run_id),indent=2))

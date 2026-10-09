"""Separate, clearly artificial demo. No provider/AI calls or client-data changes."""
import argparse
import asyncio
import csv
from datetime import date, timedelta
from io import BytesIO
import json
import math
from pathlib import Path
import sys
import uuid

import openpyxl
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.generate_factor_test_samples import generate
from app import main
from app.factor_imports import review_import, save_import
from app.order_reuse import preview_reuse, save_reuse
from app.sales_api import run_hash
from app.sales_demand import export_demand

OUTPUT = main.BASE_DIR / 'outputs'
PREPARED = OUTPUT / 'factor-batch-demo-prepared.json'


async def prepare():
    history, _, _, _ = generate('mixed_customers', seed=7319)
    observations = history.drop_duplicates('date').sort_values('date')
    sales = history[history.date >= '2022-10-01'].drop(columns=['exchange_rate', 'unrelated_index'])
    source = main.DATASET_STORE.upload('synthetic-batch-sales.csv', sales.to_csv(index=False).encode(), 'history')
    settings = dict(date_col='date', target_col='quantity', item_col='series', customer_col='customer', sku_col='sku',
        drivers=[], frequency='monthly', horizon=6, profile='fast', unit='tonnes', method_selection='model:Ridge + drivers',
        future_driver_policy='require', missing_strategy='auto', outlier_strategy='none', history_calendar='gregorian',
        month_basis='gregorian', history_grain='monthly_totals', sales_measure='customer_demand', returns_policy='reject')
    dataset = main.DATASET_STORE.save('Demo · customer/product batch baseline', {'history':source['id']}, settings, 'synthetic_sample', True)
    run = await main.run_saved(main.SavedRunConfig(dataset_id=dataset['id']))
    factors = []
    for column, name, unit in [('exchange_rate', 'Demo batch · synthetic exchange rate', 'IRR per USD (synthetic)'),
                                ('unrelated_index', 'Demo batch · synthetic supply index', 'Index points (synthetic)')]:
        rows = []
        for record in observations.to_dict('records'):
            day = pd.Timestamp(record['date']).to_period('M').end_time.date()
            value = record[column] if column == 'exchange_rate' else 100 + record[column] * 3
            rows.append({'period':str(day), 'value':value, 'published':str(day+timedelta(days=5))})
        uploaded = main.DATASET_STORE.upload('synthetic-batch-'+column+'.csv', pd.DataFrame(rows).to_csv(index=False).encode(), 'factor_observations')
        config = dict(source_id=uploaded['id'], name=name, unit=unit, geography='Artificial Tehran-inspired example',
            provider='Generated demo, not a live market observation', frequency='monthly', classification='synthetic_sample',
            mapping={'period':'A', 'value':'B', 'available_at':'C'})
        review = review_import(main.DATASET_STORE, config)
        saved = save_import(main.DATASET_STORE, main.FACTOR_STORE, {**config, 'review_token':review['review_token'],
            'reviewed':True, 'request_id':str(uuid.uuid4())})
        factors.append({'snapshot_id':saved['id'], 'name':name, 'future_assumption':1800000 if column=='exchange_rate' else 105})
    evidence = {'baseline':run['run_id'], 'dataset_id':dataset['id'], 'classification':'synthetic_sample',
        'history_months':48, 'forecast_months':6, 'series':run['items'], 'factors':factors,
        'warning':'Artificial demand and factors. Not client accuracy, actual Iran data or a provider refresh.'}
    OUTPUT.mkdir(exist_ok=True)
    PREPARED.write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))


def verify(run_id):
    prepared = json.loads(PREPARED.read_text())
    base = main._load_run(prepared['baseline'])
    before = (main.RUNS_DIR/base['run_id']/'result.json').read_bytes()
    run = main._load_run(run_id)
    assert run['source_classification'] == 'synthetic_sample'
    assert run['scenario']['type'] == 'factor_batch' and run['base_run_id'] == base['run_id']
    alignment = run['scenario']['alignment']
    assert len(alignment['groups']) == 2
    assert set(alignment['unchanged_series_ids']) == {'Demo Tehran B/0001','Demo Tehran C/0003'}
    for key in alignment['unchanged_series_ids']:
        assert run['series'][key] == base['series'][key]
    assert run['metrics']['wape_pct'] is None
    for point in run['series']['__all__']['forecast']:
        assert point['p10'] is None and point['p90'] is None
        assert math.isclose(point['mean'], math.fsum(next(p['mean'] for p in run['series'][key]['forecast'] if p['timestamp']==point['timestamp']) for key in run['items']), abs_tol=1e-7)
    today = date.today()
    inputs = dict(name='Demo batch · complete book, partial customer orders', classification='synthetic_sample', run_id=base['run_id'],
        as_of=str(today), valid_until=str(today+timedelta(days=14)), order_feed='complete_snapshot',
        customers=[dict(customer=m['customer'],sku=m['sku'],unit='tonnes',series_id=key) for key,m in base['metadata'].items()],
        orders=[dict(reference='BATCH-DEMO-A',customer='Demo Tehran A',sku='0001',unit='tonnes',due_date='2026-10-15',ordered=300,fulfilled=20,cancelled=0,status='confirmed'),
                dict(reference='BATCH-DEMO-B',customer='Demo Tehran B',sku='0001',unit='tonnes',due_date='2026-11-15',ordered=90,fulfilled=0,cancelled=0,status='confirmed')],
        commitments=[],reviewed=True,note='Artificial complete order book. Other customers/products have no confirmed orders.')
    old = main.SALES_STORE.list(base['run_id'])
    original = main.SALES_STORE.get(old[0]['id']) if old else main.SALES_STORE.save(inputs,base,'batch-demo-orders-'+base['run_id'],'Local session',[{'run_sha256':run_hash(base)}])
    old_hash = original['sha256']
    prior = main.SALES_STORE.list(run_id)
    if prior:
        snapshot = main.SALES_STORE.get(prior[0]['id'])
    else:
        review, _, _, _ = preview_reuse(main.SALES_STORE,main._load_run,run_id,original['id'])
        snapshot = save_reuse(main.SALES_STORE,main._load_run,run_id,dict(snapshot_id=original['id'],review_token=review['review_token'],
            reviewed=True,coverage_confirmed=True,request_id='batch-demo-reuse-'+run_id),'Local session')
    outlook = main.sales_outlook(snapshot['id'])
    assert outlook['can_export']
    totals = {}; files = []
    for mode in ('combined_demand','remaining_forecast'):
        values = []
        for kind in ('csv','xlsx','json'):
            content, _ = export_demand(outlook,mode,kind)
            if kind=='csv': rows = list(csv.DictReader(content.decode('utf-8-sig').splitlines()))
            elif kind=='json': rows=json.loads(content)
            else:
                book=openpyxl.load_workbook(BytesIO(content),read_only=True,data_only=True)
                table=list(book.worksheets[0].values);rows=[dict(zip(table[0],r)) for r in table[1:]];book.close()
            assert len(rows)==24
            total=math.fsum(float(r['quantity']) for r in rows)
            expected=math.fsum(max(r['baseline'],r['booked']+r['fulfilled'])-r['fulfilled'] if mode=='combined_demand'
                else max(r['baseline']-r['booked']-r['fulfilled'],0) for r in outlook['rows'])
            assert math.isclose(total,expected,abs_tol=1e-7)
            path=OUTPUT/('factor-batch-demo-'+mode+'.'+kind);path.write_bytes(content);files.append(str(path));values.append(total)
        assert max(values)-min(values)<1e-7
        totals[mode]=values[0]
    assert math.isclose(totals['combined_demand']-totals['remaining_forecast'],370,abs_tol=1e-7)
    assert main.SALES_STORE.get(original['id'])['sha256']==old_hash
    assert (main.RUNS_DIR/base['run_id']/'result.json').read_bytes()==before
    evidence={'run_id':run_id,'baseline':base['run_id'],'snapshot_id':snapshot['id'],'classification':'synthetic_sample',
        'groups':2,'unchanged_products':2,'export_rows':24,'open_orders':370,'fulfilled':20,'totals':totals,'files':files,
        'originals_unchanged':True,'note':'Synthetic workflow and arithmetic check, not real client accuracy. No OpenAI or provider calls.'}
    (OUTPUT/'factor-batch-demo-evidence.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare',action='store_true');group.add_argument('--verify-run');args=parser.parse_args()
    asyncio.run(prepare()) if args.prepare else verify(args.verify_run)

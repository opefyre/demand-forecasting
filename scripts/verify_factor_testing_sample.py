"""Save a separate synthetic factor-test demo using the existing engine/orders."""
import asyncio
from datetime import date,timedelta
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.generate_factor_test_samples import write_samples,ROOT
from app import main
from app.sales_api import run_hash
from app.sales_demand import export_demand


async def verify(reuse=None):
    write_samples()
    settings={'date_col':'date','target_col':'quantity','item_col':'series','customer_col':'customer','sku_col':'sku',
        'drivers':['exchange_rate','unrelated_index'],'frequency':'monthly','horizon':6,'profile':'deep','unit':'tonnes',
        'method_selection':'factor_test','future_date_col':'date','future_item_col':'series','future_driver_policy':'require',
        'missing_strategy':'auto','outlier_strategy':'none','history_calendar':'gregorian','future_calendar':'gregorian',
        'month_basis':'gregorian','history_grain':'monthly_totals','sales_measure':'customer_demand','returns_policy':'reject'}
    if reuse:
        run=main._load_run(reuse)
    else:
        history=main.DATASET_STORE.upload('mixed_customers-history.csv',(ROOT/'mixed_customers-history.csv').read_bytes(),'history')
        future=main.DATASET_STORE.upload('mixed_customers-assumptions.csv',(ROOT/'mixed_customers-assumptions.csv').read_bytes(),'future')
        saved=main.DATASET_STORE.save('Demo · automatic factor tests',{'history':history['id'],'future':future['id']},settings,'synthetic_sample',True)
        run=await main.run_saved(main.SavedRunConfig(dataset_id=saved['id']))
    if reuse and run.get('dataset_name')!='Demo · automatic factor tests':raise ValueError('Reuse only this script’s synthetic demo.')
    today=date.today()
    inputs={'name':'Demo · partial confirmed orders','classification':'synthetic_sample','run_id':run['run_id'],
        'as_of':str(today),'valid_until':str(today+timedelta(days=14)),'order_feed':'complete_snapshot',
        'customers':[{'customer':m['customer'],'sku':m['sku'],'unit':'tonnes','series_id':key} for key,m in run['metadata'].items()],
        'orders':[{'reference':'DEMO-FACTOR-1','customer':'Demo Tehran A','sku':'0001','unit':'tonnes','due_date':'2026-10-15',
            'ordered':240,'fulfilled':20,'cancelled':0,'status':'confirmed'}],
        'commitments':[],'reviewed':True,'note':'Synthetic complete book; other customers/products have no confirmed orders.'}
    prior=main.SALES_STORE.list(run['run_id']) if reuse else []
    snapshot=main.SALES_STORE.get(prior[0]['id']) if prior else main.SALES_STORE.save(inputs,run,'factor-test-demo-'+run['run_id'],'Local session',[{'run_sha256':run_hash(run)}])
    outlook=main.sales_outlook(snapshot['id'])
    exports=[]
    for mode in ('combined_demand','remaining_forecast'):
        for kind in ('csv','xlsx','json'):
            content,_=export_demand(outlook,mode,kind)
            target=main.BASE_DIR/'outputs'/('factor-test-demo-'+mode+'.'+kind)
            target.write_bytes(content)
            exports.append(str(target))
    evidence={'run_id':run['run_id'],'dataset_id':run['dataset_id'],'snapshot_id':snapshot['id'],
        'classification':'synthetic_sample','source':str(ROOT),'history_months':84,'forecast_months':6,
        'choices':run['factor_evaluation']['rows'],'calculated_total':sum(row['mean'] for row in run['forecast_rows']),
        'open_orders':sum(r['booked'] for r in outlook['rows']),'still_expected':sum(r['remaining'] for r in outlook['rows']),
        'still_to_serve':sum(r['still_to_serve'] for r in outlook['rows']),'files':exports,
        'note':'Generated factors and sales; no live/AI calls, no client accuracy claim. Withheld synthetic actuals were not used.'}
    (main.BASE_DIR/'outputs'/'factor-test-demo-evidence.json').write_text(json.dumps(evidence,indent=2))
    print(json.dumps(evidence,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--reuse-run');args=parser.parse_args()
    asyncio.run(verify(args.reuse_run))

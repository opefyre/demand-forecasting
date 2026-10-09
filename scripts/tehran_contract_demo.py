"""One confirmed full-month customer contract, alongside partial and absent orders."""
import asyncio
import json
import uuid
from scripts.prepare_tehran_demo import MANIFEST, OUT, write


async def populate():
    from app import main
    from app.forecast_orders import starter, prepare, save
    from app.sales_demand import demand_outlook, export_demand
    from app.forecast_views import ViewStore, SavedView
    manifest = json.loads(MANIFEST.read_text())
    key = 'monthly_contract'
    if key not in manifest['runs']:
        dataset_id = manifest['datasets']['gregorian']
        base = main._load_run(manifest['runs']['gregorian:recommended'])
        inputs = main.SALES_STORE.get(main.SALES_STORE.list(base['run_id'])[0]['id'])['inputs']
        draft = starter(main.DATASET_STORE, dataset_id)
        first = base['series']['__all__']['forecast'][0]['timestamp']
        commitments = [dict(customer=row['customer'], sku=row['sku'], unit=row['unit'], period=first,
            quantity=row['ordered'], owner='Demo sales planner', reason='Fictional customer confirms this is the entire October monthly contract, not an additional order.',
            valid_until=inputs['valid_until']) for row in inputs['orders']
            if row['customer']=='Caspian Export' and row['status']=='confirmed' and row['due_date'].startswith(first[:7])]
        assert len(commitments)==4
        revised = {**inputs, 'run_id':draft['context']['run_id'], 'name':'Caspian full-month contract',
            'commitments':commitments, 'note':'Full-month contract is confirmed for Caspian October only. Other customers/months still combine orders with forecast.'}
        payload = dict(inputs=revised, request_id='tehran-confirmed-monthly-contract')
        review = prepare(main.DATASET_STORE, main.SALES_STORE, dataset_id, payload, main._load_run)[0]
        saved = save(main.DATASET_STORE, main.SALES_STORE, dataset_id, {**payload,'review_token':review['review_token']}, main._load_run, 'Local session')
        result = await main.run_saved(main.SavedRunConfig(dataset_id=dataset_id, method='recommended',
            sales_input_id=saved['id'], forecast_group_id=uuid.uuid4().hex, forecast_name='Tehran · confirmed monthly contract'))
        manifest = json.loads(MANIFEST.read_text())
        manifest['runs'][key] = result['run_id']; write(MANIFEST, manifest)
    run = main._load_run(manifest['runs'][key])
    snap = main.SALES_STORE.get(main.SALES_STORE.list(run['run_id'])[0]['id'])
    outlook = demand_outlook(snap['inputs'], run)
    assert outlook['can_export']
    period = run['series']['__all__']['forecast'][0]['timestamp']
    covered = [r for r in outlook['rows'] if r['customer']=='Caspian Export' and r['period']==period]
    assert len(covered)==4 and all(r['remaining']==0 for r in covered)
    for mode in ('combined_demand','remaining_forecast'):
        for kind in ('csv','json','xlsx'):
            content, _ = export_demand(outlook, mode, kind)
            path = OUT/'exports'/run['run_id']/(mode+'.'+kind)
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(content)
            if not any(e['path']==str(path) for e in manifest['exports']):
                manifest['exports'].append(dict(run_id=run['run_id'],mode=mode,kind=kind,path=str(path)))
    views = ViewStore(main.SALES_STORE.path)
    if not views.list('local',run['run_id']):
        for name, display, view, measure in [('Monthly demand','chart','month','total'),('Customer overview','chart','customer','total'),
                ('Product overview','pivot','sku','total'),('Orders and remaining demand','coverage','detail','booked')]:
            views.save('local',SavedView(name=name,run_id=run['run_id'],snapshot_id=snap['id'],
                settings=dict(unit='tonnes',display=display,view=view,measure=measure,sort='largest')))
    manifest['checks']['confirmed_monthly_contract'] = dict(rows=4,customer='Caspian Export',period=period)
    write(MANIFEST,manifest)
    print(json.dumps(manifest['checks']['confirmed_monthly_contract']),flush=True)


if __name__=='__main__':
    asyncio.run(populate())

"""Compare seasonal models only on buyers with sufficient genuine demo history."""
import asyncio
from io import BytesIO
import json
import uuid
import pandas as pd
from scripts.prepare_tehran_demo import ROOT, MANIFEST, OUT, order_inputs, write


async def populate():
    from app import main
    from app.sales_demand import demand_outlook, export_demand
    from app.forecast_views import ViewStore, SavedView
    manifest = json.loads(MANIFEST.read_text())
    def remember(): write(MANIFEST, manifest)
    if 'seasonal' not in manifest['datasets']:
        base = main.DATASET_STORE.get(manifest['datasets']['gregorian'])
        sources = {}
        for role in ('history', 'future'):
            frame = pd.read_csv(BytesIO(main.DATASET_STORE.source(base['sources'][role])[1]))
            frame = frame[frame.customer.ne('Negin Retail')]
            sources[role] = main.DATASET_STORE.upload('established-' + role + '.csv', frame.to_csv(index=False).encode(), role)['id']
        row = main.DATASET_STORE.save('Tehran · established-customer seasonal comparison', sources,
            base['settings'], 'synthetic_sample', True)
        manifest['datasets']['seasonal'] = row['id']; remember()
    dataset = main.DATASET_STORE.get(manifest['datasets']['seasonal'])
    if 'seasonal_group' not in manifest:
        orders = order_inputs(main, dataset)
        manifest['seasonal_group'] = dict(id=uuid.uuid4().hex, orders=orders['id']); remember()
    group = manifest['seasonal_group']
    views = ViewStore(main.SALES_STORE.path)
    for method in ('Seasonal naive', 'Holt-Winters seasonal', 'AutoETS', 'factor_test'):
        selected = method if method == 'factor_test' else 'model:' + method
        key = 'seasonal:' + selected
        if key not in manifest['runs']:
            print('Calculating established-customer seasonal comparison · ' + method, flush=True)
            result = await main.run_saved(main.SavedRunConfig(dataset_id=dataset['id'], method=selected,
                sales_input_id=group['orders'], forecast_group_id=group['id'],
                forecast_name='Tehran · established-customer seasonal comparison'))
            manifest['runs'][key] = result['run_id']; remember()
        run = main._load_run(manifest['runs'][key])
        snap = main.SALES_STORE.get(main.SALES_STORE.list(run['run_id'])[0]['id'])
        outlook = demand_outlook(snap['inputs'], run)
        assert outlook['can_export'] and len(outlook['rows']) == 192
        for mode in ('combined_demand', 'remaining_forecast'):
            for kind in ('csv', 'json', 'xlsx'):
                content, _ = export_demand(outlook, mode, kind)
                path = OUT / 'exports' / run['run_id'] / (mode + '.' + kind)
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
                if not any(e['path']==str(path) for e in manifest['exports']):
                    manifest['exports'].append(dict(run_id=run['run_id'], mode=mode, kind=kind, path=str(path)))
        if not views.list('local', run['run_id']):
            for name, display, view, measure in [('Monthly demand', 'chart', 'month', 'total'),
                    ('Customer overview', 'chart', 'customer', 'total'), ('Product overview', 'pivot', 'sku', 'total'),
                    ('Orders and remaining demand', 'coverage', 'detail', 'booked')]:
                views.save('local', SavedView(name=name, run_id=run['run_id'], snapshot_id=snap['id'],
                    settings=dict(unit='tonnes', display=display, view=view, measure=measure, sort='largest')))
        remember()
    print(json.dumps({'seasonal_methods':3, 'factor_test_methods':1, 'customers':4, 'rows_per_method':192}), flush=True)


if __name__ == '__main__':
    asyncio.run(populate())

"""Populate remaining sales-demo outputs using normal reviewed application services."""
import asyncio
from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
import sys
import uuid

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_tehran_demo import OUT, INPUT, MANIFEST, DEFINITIONS, write


async def complete():
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'secrets/.env.local', override=False)
    from app import main
    from app.sales_demand import demand_outlook, export_demand
    from app.sales_conventions import local_today
    from app.actuals import export_actuals
    from app.factor_imports import review_import, save_import
    from app.demand_releases import identity
    manifest = json.loads(MANIFEST.read_text())
    def remember(): write(MANIFEST, manifest)
    primary = main._load_run(manifest['runs']['gregorian:recommended'])
    dataset = main.DATASET_STORE.get(primary['dataset_id'])
    history = pd.read_csv(BytesIO(main.DATASET_STORE.source(dataset['sources']['history'])[1]))
    if 'factor_examples' not in manifest:
        saved = []
        observations = history.drop_duplicates('date').sort_values('date')
        for factor in ('scenario_cpi_yoy', 'scenario_usd_irr', 'disruption_index', 'import_delay_days'):
            rows = [dict(period=str(pd.Timestamp(r.date).to_period('M').end_time.date()), value=getattr(r,factor),
                available_at=str(pd.Timestamp(r.date).to_period('M').end_time.date()+timedelta(days=5)))
                for r in observations.itertuples() if pd.Timestamp(r.date).month != local_today().month or pd.Timestamp(r.date).year != local_today().year]
            # The latest complete source month may have published this month.
            rows = [r for r in rows if r['available_at'] <= str(local_today())]
            source = main.DATASET_STORE.upload(factor + '.csv', pd.DataFrame(rows).to_csv(index=False).encode(), 'factor_observations')
            definition = DEFINITIONS[factor]
            config = dict(source_id=source['id'], name=definition[0], unit=definition[1], geography=definition[2],
                provider='Fictional scenario generator', frequency='monthly', classification='synthetic_sample',
                mapping=dict(period='A', value='B', available_at='C'))
            review = review_import(main.DATASET_STORE, config)
            row = save_import(main.DATASET_STORE, main.FACTOR_STORE, {**config, 'review_token': review['review_token'],
                'reviewed': True, 'request_id': str(uuid.uuid4())})
            saved.append(row['id'])
        manifest['factor_examples'] = saved; remember()
    if 'folder_connection' not in manifest:
        folder = main.FOLDER_INPUTS.create(dict(name='Tehran sales export', path=str(INPUT), dataset_id=dataset['id'],
            minutes=60, files=dict(history='sales-gregorian.csv', future='assumptions-gregorian.csv'),
            classification='synthetic_sample', confirmed_local_access=True), 'Local session')
        check = main.FOLDER_INPUTS.check(folder['id'])
        assert check['state']=='ready', check
        # These are the identical already-reviewed bytes; pin acceptance to that
        # version rather than adding another duplicate input to the Files table.
        assert all(main.DATASET_STORE.source(check['sources'][role])[0]['sha256'] ==
                   main.DATASET_STORE.source(dataset['sources'][role])[0]['sha256'] for role in check['sources'])
        main.FOLDER_INPUTS.mark_saved(check['id'], dataset['id'])
        manifest['folder_connection'] = dict(id=folder['id'], candidate=check['id'], checked=True,
            note='Local generated business-input feed, not a real ERP integration.'); remember()
    if 'weather' not in manifest or manifest['weather'].get('unavailable'):
        try:
            snapshot = main.WEATHER_STORE.refresh(dict(location_name='Tehran city reference · not factory coordinates',
                latitude=35.689, longitude=51.389, start='2026-06-01', end='2026-09-30', share_coordinates=True))
            manifest['weather'] = dict(id=snapshot['id'], months=len(snapshot['monthly']),
                use='Regional context only; no unsupported weather-to-paper-demand multiplier.'); remember()
        except Exception as exc:
            manifest['weather'] = dict(unavailable=type(exc).__name__, use='No invented weather readings.'); remember()
    if 'releases' not in manifest:
        releases = []
        for key, mode, approve in [('gregorian:recommended', 'remaining_forecast', True),
                ('gregorian:model:Ridge + drivers', 'combined_demand', False), ('jalali:recommended', 'combined_demand', True)]:
            run_id = manifest['runs'][key]
            snapshot = main.SALES_STORE.list(run_id)[0]['id']
            payload = dict(snapshot_id=snapshot, receiver='Planning-system demo', mode=mode)
            report = main.DEMAND_RELEASES.preview(payload)[0]
            row = main.DEMAND_RELEASES.request({**payload, 'review_token': report['review_token'],
                'reviewed': True, 'request_id': 'tehran-release-' + run_id}, identity(None))
            if approve:
                row = main.DEMAND_RELEASES.approve(row['id'], dict(reviewed=True, demo_confirmed=True,
                    review_token=report['review_token']), identity(None), 'local')
                for kind in ('csv','json','xlsx'):
                    content, _, _ = main.DEMAND_RELEASES.export(row['id'], kind)
                    (OUT / ('approved-' + run_id + '.' + kind)).write_bytes(content)
            releases.append(dict(id=row['id'], run_id=run_id, state=row['state'], mode=mode, demo_only=True))
        manifest['releases'] = releases; remember()
    if 'actual_results' not in manifest:
        train = history[history.date < '2026-07-01'].copy()
        actual = history[(history.date >= '2026-07-01') & (history.date <= '2026-09-01')].copy()
        s = {**dataset['settings'], 'horizon':3, 'drivers':[], 'method_selection':'model:Weighted recent average'}
        source = main.DATASET_STORE.upload('sales-through-june.csv', train.to_csv(index=False).encode(), 'history')
        historical = main.DATASET_STORE.save('Tehran · July–September retrospective check', {'history': source['id']}, s, 'synthetic_sample', True)
        run = await main.run_saved(main.SavedRunConfig(dataset_id=historical['id']))
        rows = actual[['series','date','quantity']].rename(columns={'series':'item_id','date':'timestamp','quantity':'actual'})
        src = main.DATASET_STORE.upload('closed-sales-july-september.csv', rows.to_csv(index=False).encode(), 'actuals')
        config = dict(source_id=src['id'], mapping=dict(item_id='A', timestamp='B', actual='C'),
            unit='tonnes', classification='synthetic_sample', closed_through='2026-09-30',
            reviewed=True, owner='Demo planner', request_id=str(uuid.uuid4()), calendar='gregorian')
        report = main.ACTUALS_STORE.save(config, run)
        assert report['coverage']['matched']==54 and not any(r['prospective'] for r in report['rows'])
        content = export_actuals(report)
        (OUT / 'retrospective-actual-results.csv').write_bytes(content if isinstance(content,bytes) else content.encode())
        manifest['actual_results'] = dict(run_id=run['run_id'], evaluation_id=report['id'], rows=54,
            use='Retrospective diagnostic, not prospective accuracy.'); remember()
    # Test unavailable/expired coverage without polluting the visible demo list.
    latest = main.SALES_STORE.get(main.SALES_STORE.list(primary['run_id'])[0]['id'])
    inputs = latest['inputs']
    unknown = demand_outlook({**inputs, 'order_feed':'unknown'}, primary)
    expired = demand_outlook({**inputs, 'as_of':str(local_today()-timedelta(days=3)),
        'valid_until':str(local_today()-timedelta(days=1))}, primary)
    assert not unknown['can_export'] and not expired['can_export']
    for blocked in (unknown, expired):
        try: export_demand(blocked, 'combined_demand', 'csv')
        except ValueError: pass
        else: raise AssertionError('Unsafe demo input exported.')
    manifest['checks']['missing_and_expired_orders_block_export'] = True
    manifest['state'] = 'outputs_populated'; remember()
    print(json.dumps({'releases':manifest['releases'], 'actual_results':manifest['actual_results'],
        'weather':manifest['weather'], 'input_feed':manifest['folder_connection']}), flush=True)


if __name__ == '__main__':
    asyncio.run(complete())

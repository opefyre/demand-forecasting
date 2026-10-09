"""Use a genuine current Iranian FX quote as an explicit future what-if assumption."""
import asyncio
from datetime import datetime, timezone
import json
import uuid
from scripts.prepare_tehran_demo import ROOT, MANIFEST, OUT, write


async def populate():
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'secrets/.env.local', override=False)
    from app import main
    from app.assumptions import preview_assumptions, save_assumptions
    from app.order_reuse import preview_reuse, save_reuse
    from app.sales_demand import demand_outlook, export_demand
    from app.forecast_views import ViewStore, SavedView
    manifest = json.loads(MANIFEST.read_text())
    key = 'live_currency'
    if key not in manifest['runs']:
        feed = next(s for s in main.LIVE_SOURCES.listing()['sources'] if s['id']=='servix')
        assert feed['status']=='healthy' and not feed['data_behind'] and not feed['refresh_overdue']
        snapshot = main.FACTOR_STORE.get(feed['snapshot_ids'][0])
        assert snapshot['factor_id']=='servix_usd_rls' and snapshot['unit']=='IRR per USD'
        point = snapshot['points'][-1]
        quoted = datetime.fromisoformat(point['quote_time'])
        assert 0 <= (datetime.now(timezone.utc)-quoted).total_seconds() <= 3600
        base = main._load_run(manifest['runs']['live:model:Ridge + drivers'])
        changes = [dict(item_id=r['item_id'], period=r['timestamp'], factor='scenario_usd_irr', value=point['value'])
                   for r in preview_assumptions(base, main.DATASET_STORE)['rows']]
        scenario = save_assumptions(base, main.DATASET_STORE, dict(name='Tehran · current FX sensitivity',
            owner='Demo planner', reason='Hold the latest Servix reference quote as an explicit future assumption. Not a settlement quote, not predicted future FX, and not backfilled into synthetic sales history.',
            reviewed=True, request_id=str(uuid.uuid4()), changes=changes,
            definitions=[dict(factor='scenario_usd_irr', unit='IRR per USD', geography='Iran · provider reference quote',
                source=f"Servix snapshot {snapshot['id']}; quoted {point['quote_time']}; captured {snapshot['captured_at']}; future hold assumption, not future observation")]))
        result = await main.run_saved(main.SavedRunConfig(dataset_id=scenario['id']))
        source = main.SALES_STORE.list(base['run_id'])[0]['id']
        report = preview_reuse(main.SALES_STORE, main._load_run, result['run_id'], source)[0]
        save_reuse(main.SALES_STORE, main._load_run, result['run_id'], dict(snapshot_id=source,
            review_token=report['review_token'], reviewed=True, coverage_confirmed=True,
            request_id='tehran-live-fx-order-reuse'), 'Local session')
        manifest = json.loads(MANIFEST.read_text())
        manifest['runs'][key] = result['run_id']
        manifest['live_currency'] = dict(snapshot_id=snapshot['id'], quote_time=point['quote_time'],
            captured_at=snapshot['captured_at'], value=point['value'], unit=snapshot['unit'],
            use='Explicit future hold assumption in live what-if model; no historical FX gaps filled.')
        write(MANIFEST, manifest)
    run = main._load_run(manifest['runs'][key])
    assert run['evidence_policy']=='reviewed_what_if'
    assert all(p['p10'] is None and p['p90'] is None for p in run['series']['__all__']['forecast'])
    snap = main.SALES_STORE.get(main.SALES_STORE.list(run['run_id'])[0]['id'])
    outlook = demand_outlook(snap['inputs'], run)
    assert outlook['can_export'] and len(outlook['rows'])==216
    for mode in ('combined_demand', 'remaining_forecast'):
        for kind in ('csv', 'json', 'xlsx'):
            content, _ = export_demand(outlook, mode, kind)
            path = OUT / 'exports' / run['run_id'] / (mode+'.'+kind)
            path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
            if not any(e['path']==str(path) for e in manifest['exports']):
                manifest['exports'].append(dict(run_id=run['run_id'], mode=mode, kind=kind, path=str(path)))
    views = ViewStore(main.SALES_STORE.path)
    if not views.list('local', run['run_id']):
        for name, display, view, measure in [('Monthly demand', 'chart', 'month', 'total'),
                ('Customer overview', 'chart', 'customer', 'total'), ('Product overview', 'pivot', 'sku', 'total'),
                ('Orders and remaining demand', 'coverage', 'detail', 'booked')]:
            views.save('local', SavedView(name=name, run_id=run['run_id'], snapshot_id=snap['id'],
                settings=dict(unit='tonnes', display=display, view=view, measure=measure, sort='largest')))
    write(MANIFEST, manifest)
    print(json.dumps(manifest['live_currency']), flush=True)


if __name__ == '__main__':
    asyncio.run(populate())

"""Reproducible sales-only demo. Business inputs are fictional; live feeds are not.

Run --reset only with the app/worker stopped. Existing business records are moved
to a checksummed backup, never destroyed. Credentials, live feeds and units stay.
The seed command resumes from its manifest, avoiding duplicate demo forecasts.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import uuid
import zipfile

import numpy as np
import pandas as pd
from persiantools.jdatetime import JalaliDate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'outputs' / 'tehran-sales-demo'
INPUT = ROOT / 'sample_data' / 'tehran-sales-demo'
MANIFEST = OUT / 'manifest.json'
CUSTOMERS = [
    ('Mehr Packaging', 'بسته‌بندی مهر', 'C-1001', ['KRAFT-120', 'BOARD-300', 'FOOD-110', 'SPECIAL-090']),
    ('Simin Foods', 'صنایع غذایی سیمین', 'C-1002', ['KRAFT-120', 'BOARD-300', 'FOOD-110', 'SPECIAL-090']),
    ('Aftab Printing', 'چاپ آفتاب', 'C-1003', ['KRAFT-120', 'BOARD-300', 'FOOD-110', 'SPECIAL-090']),
    ('Caspian Export', 'بازرگانی کاسپین', 'C-1004', ['KRAFT-120', 'BOARD-300', 'FOOD-110', 'SPECIAL-090']),
    ('Negin Retail', 'توزیع نگین', 'C-1005', ['BOARD-300', 'FOOD-110']),
]
PRODUCTS = {'KRAFT-120': ('Kraft liner 120 gsm', 56), 'BOARD-300': ('Folding board 300 gsm', 40),
            'FOOD-110': ('Food packaging paper 110 gsm', 30), 'SPECIAL-090': ('Specialty label paper 90 gsm', 12)}
DEFINITIONS = {
    'scenario_usd_irr': ('Exchange-rate assumption', 'IRR per USD', 'Iran · assumed customer pricing exposure'),
    'scenario_cpi_yoy': ('Inflation assumption', '% year-on-year', 'Iran · fictional monthly scenario'),
    'selling_price_index': ('Selling-price index', 'Index, first month = 100', 'Tehran · fictional factory'),
    'promotion_index': ('Customer promotion', 'Index, 0–1', 'Fictional customer plan'),
    'payment_days': ('Customer payment terms', 'Days', 'Fictional customer contracts'),
    'import_delay_days': ('Import delay assumption', 'Days', 'Iran · fictional import route'),
    'disruption_index': ('Disruption assumption', 'Index, 0–1', 'Iran/regional · fictional stress, not a war prediction'),
}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False, default=str))
    temporary.replace(path)


def reset():
    from app.recovery import backup, verified_archive
    from app.workspace_lock import WorkspaceLease
    if MANIFEST.exists():
        raise ValueError('A prepared demo already exists. Reset is deliberately one-shot.')
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    archive_root = OUT / ('previous-state-' + stamp)
    archive_root.mkdir(mode=0o700)
    receipt = backup(ROOT, archive_root / 'workspace.zip')
    with zipfile.ZipFile(receipt['path']) as archive:
        verified_archive(archive)
        if archive.testzip() is not None:
            raise ValueError('Backup ZIP verification failed.')
    paths = ['runs', 'data/datasets', 'data/weather', 'data/customers.sqlite3',
             'data/orders.sqlite3', 'data/sales-demand.sqlite3', 'data/actuals.sqlite3',
             'data/inventory.sqlite3', 'data/decisions.sqlite3', 'data/plans.json',
             'data/plans.sqlite3', 'data/plans-post-migration-20260921.sqlite3',
             'data/folder-inputs.sqlite3', 'data/order-folders.sqlite3', 'data/factor-folders.sqlite3',
             'data/monthly-updates.sqlite3', 'data/recurring-forecasts.sqlite3',
             'data/jobs.sqlite3', 'data/queue.sqlite3']
    moved = []
    with WorkspaceLease(ROOT, exclusive=True):
        for relative in paths:
            path = ROOT / relative
            if not path.exists():
                continue
            if path.is_symlink():
                raise ValueError('Refusing to move a linked state path.')
            target = archive_root / 'originals' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            moved.append(relative)
            for suffix in ('-wal', '-shm', '-journal'):
                sidecar = Path(str(path) + suffix)
                if sidecar.exists():
                    shutil.move(str(sidecar), str(target) + suffix)
        # Keep provider quotas and AI consent/configuration, archive only old chats.
        journal = ROOT / 'data/ai-workspace.sqlite3'
        if journal.exists():
            with sqlite3.connect(journal) as db:
                db.execute("INSERT OR REPLACE INTO ai_chat_state(chat_id,actor,status,pinned) SELECT DISTINCT chat_id,actor,'archived',0 FROM ai_turns WHERE chat_id IS NOT NULL")
        for path in (ROOT / 'data/factors').glob('*.json'):
            row = json.loads(path.read_text())
            if row.get('classification') == 'synthetic_sample':
                target = archive_root / 'originals/data/factors' / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(target))
                moved.append('data/factors/' + path.name)
    write(MANIFEST, {'classification': 'synthetic_sample', 'seed': 14051009,
        'backup': receipt, 'archived_paths': moved, 'created_at': datetime.now(timezone.utc).isoformat(),
        'datasets': {}, 'runs': {}, 'exports': [], 'checks': {}, 'limitations': []})
    print(json.dumps({'backup': receipt, 'archived_records': len(moved), 'credentials_preserved': True}), flush=True)


def generate(basis='gregorian', end=None, horizon=12):
    from app.sales_conventions import local_today, period_start, shift_month
    rng = np.random.default_rng(14051009 + (basis == 'jalali'))
    end = end or shift_month(period_start(local_today(), basis), -1, basis)
    dates = [shift_month(end, i - 47, basis) for i in range(48 + horizon)]
    rows, future = [], []
    for ci, (customer, _, _, skus) in enumerate(CUSTOMERS):
        for sku in skus:
            pi = list(PRODUCTS).index(sku)
            base = PRODUCTS[sku][1] * [1.2, .85, .65, .9, .35][ci]
            for i, day in enumerate(dates):
                if ci == 4 and i < 30:
                    continue  # Genuine short-history case; do not invent prior zero sales.
                planning_month = JalaliDate(day.date()).month if basis == 'jalali' else day.month
                spring = planning_month == (1 if basis == 'jalali' else 3)
                autumn = planning_month in ((6, 7, 8) if basis == 'jalali' else (9, 10, 11))
                fx = round(410000 * 1.022 ** i * (1 + .025 * math.sin(i / 4)))
                inflation = round(34 + 6 * math.sin(i / 5) + .08 * i, 2)
                promo = .35 if (i + ci + pi) % 8 == 0 else .04
                delay = 8 + (20 if i in (21, 35, 43) else 0) + 3 * math.sin(i / 3)
                disruption = .6 if i in (35, 43) else .06
                price = round(100 * 1.018 ** i * (1 + pi * .04), 3)
                payment = 30 + ci * 10 + (15 if i in (35, 43) else 0)
                common = dict(date=str(JalaliDate(day.date())) if basis == 'jalali' else str(day.date()),
                    series=customer + '/' + sku, customer=customer, sku=sku,
                    product_name=PRODUCTS[sku][0], category='Packaging paper', unit='tonnes',
                    scenario_usd_irr=fx, scenario_cpi_yoy=inflation, selling_price_index=price,
                    promotion_index=promo, payment_days=payment,
                    import_delay_days=round(delay, 2), disruption_index=disruption)
                if i >= 48:
                    future.append(common)
                    continue
                season = (0.7 if spring else 1.14 if autumn else 1) * (1 + .08 * math.sin(2 * math.pi * i / 12 + ci))
                volume = base * season * (1 + .004 * i) * (1 + .25 * promo)
                volume *= (1 - .15 * disruption) * (1 - .0015 * max(payment - 30, 0))
                if ci == 3: volume *= 1 + .0017 * i  # Export buyer has a different trend.
                if ci == 2 and pi == 3 and i % 4 != 0: volume = 0  # Irregular buying.
                if ci == 4: volume *= .7 + .035 * (i - 30)  # New buyer ramps up.
                if volume: volume += rng.normal(0, base * (.14 if pi == 3 else .065))
                if i == 40 and ci == 0 and pi == 0: volume *= 1.65  # One legitimate bulk purchase.
                rows.append({'quantity': round(max(0, volume), 3), **common})
    history, assumptions = pd.DataFrame(rows), pd.DataFrame(future)
    assert not history.duplicated(['customer', 'sku', 'date']).any()
    assert history.quantity.ge(0).all() and not history.isna().any().any()
    return history, assumptions


def settings(basis='gregorian', horizon=12):
    return dict(date_col='date', target_col='quantity', item_col='series', sku_col='sku',
        customer_col='customer', category_col='category', unit='tonnes', frequency='monthly', horizon=horizon,
        drivers=list(DEFINITIONS), future_date_col='date', future_item_col='series',
        profile='fast', method_selection='recommended', future_driver_policy='require',
        history_calendar=basis, future_calendar=basis, month_basis=basis, history_grain='monthly_totals',
        sales_measure='customer_demand', returns_policy='reject', missing_strategy='auto', outlier_strategy='none',
        calendar_country='IR', weekend_days=[4],
        driver_roles={k: 'external' if k in ('scenario_usd_irr', 'scenario_cpi_yoy', 'import_delay_days', 'disruption_index') else 'internal' for k in DEFINITIONS},
        factor_definitions={k: dict(name=v[0], unit=v[1], geography=v[2], source='Generated fictional business scenario') for k, v in DEFINITIONS.items()})


def order_inputs(main, dataset, basis='gregorian', unknown=False):
    from app.forecast_orders import starter, prepare, save
    from app.order_books import BookRequest
    from app.sales_conventions import local_today
    draft = starter(main.DATASET_STORE, dataset['id'])
    today = local_today()
    future = pd.read_csv(BytesIO(main.DATASET_STORE.source(dataset['sources']['future'])[1]))
    history = pd.read_csv(BytesIO(main.DATASET_STORE.source(dataset['sources']['history'])[1]))
    future = future.rename(columns={dataset['settings']['future_item_col']: 'series',
                                    dataset['settings']['future_date_col']: 'date'})
    recent = history.groupby('series').quantity.last().to_dict()
    orders = []
    for ci, (customer, _, _, skus) in enumerate(CUSTOMERS):
        if ci == 2: continue  # No orders yet, NOT zero expected demand.
        for sku in skus:
            key = customer + '/' + sku
            if key not in recent:
                continue
            for fi, label in enumerate(future[future.series.eq(key)].date[:6]):
                if ci == 4 and fi > 1 or ci == 1 and fi % 2: continue
                day = JalaliDate.fromisoformat(label).to_gregorian() if basis == 'jalali' else pd.Timestamp(label).date()
                due = day + timedelta(days=14)
                qty = max(3, recent[key]) * (1.7 if ci == 0 and fi == 1 else .45 if ci == 1 else .7)
                orders.append(dict(reference=f'{basis[:1].upper()}-{ci+1}-{sku}-{fi+1}', customer=customer,
                    sku=sku, unit='tonnes', due_date=str(due), ordered=round(qty, 3),
                    fulfilled=round(qty * .12, 3) if fi == 0 else 0,
                    cancelled=round(qty * .08, 3) if ci == 3 and fi == 2 else 0, status='confirmed'))
            first = next(p['timestamp'] for p in draft['context']['series'][key]['forecast'])
            orders.append(dict(reference=f'{basis[:1].upper()}-QUOTE-{ci+1}-{sku}', customer=customer,
                sku=sku, unit='tonnes', due_date=str(pd.Timestamp(first).date() + timedelta(days=20)),
                ordered=12, fulfilled=0, cancelled=0, status='unconfirmed'))
    orders.append(dict(reference=basis[:1].upper() + '-CANCELLED', customer=CUSTOMERS[0][0], sku='KRAFT-120',
        unit='tonnes', due_date=str(today+timedelta(days=3)), ordered=18, fulfilled=0, cancelled=18, status='cancelled'))
    valid = str(today + timedelta(days=30))
    main.ORDER_BOOKS.save(dataset['id'], BookRequest(version=main.ORDER_BOOKS.get(dataset['id'])['version'],
        as_of=str(today), valid_until=valid, order_feed='unknown' if unknown else 'complete_snapshot', orders=orders))
    inputs = {**draft['inputs'], 'name': 'Tehran customer orders', 'as_of': str(today), 'valid_until': valid,
        'order_feed': 'unknown' if unknown else 'complete_snapshot', 'orders': orders,
        'reviewed': True, 'note': 'Fictional complete order snapshot. Customers without orders retain calculated demand.'}
    payload = {'inputs': inputs, 'request_id': 'tehran-orders-' + dataset['id'] + '-' + draft['context']['engine']['revision']}
    report = prepare(main.DATASET_STORE, main.SALES_STORE, dataset['id'], payload, main._load_run)[0]
    saved = save(main.DATASET_STORE, main.SALES_STORE, dataset['id'], {**payload, 'review_token': report['review_token']}, main._load_run, 'Local session')
    return saved


async def seed(refresh=False):
    from dotenv import load_dotenv
    load_dotenv(ROOT / 'secrets/.env.local', override=False)
    from app import main
    from app.customers import Customer
    from app.forecast_inputs import preview_inputs, save_inputs
    from app.forecast_views import ViewStore, SavedView
    from app.sales_demand import demand_outlook, export_demand
    manifest = json.loads(MANIFEST.read_text())
    def remember(): write(MANIFEST, manifest)
    if refresh:
        source_receipts = []
        for source in main.LIVE_SOURCES.listing()['sources']:
            if not source['enabled']: continue
            try:
                state = main.LIVE_SOURCES.refresh(source['id'])
                source_receipts.append(dict(id=source['id'], status=state['status'], last_success=state.get('last_success')))
            except ValueError as exc:
                source_receipts.append(dict(id=source['id'], error=str(exc)))
        manifest['source_refresh'] = source_receipts
        remember()
        print(json.dumps({'source_refresh': source_receipts}), flush=True)
    if not main.CUSTOMER_STORE.list():
        main.CUSTOMER_STORE.save([Customer(customer=name, external_id=code, aliases=[fa],
            products=[dict(sku=s, unit='tonnes') for s in skus]) for name, fa, code, skus in CUSTOMERS])
        for customer in main.CUSTOMER_STORE.list():
            main.FACTOR_PROFILES.save(customer['id'], dict(sku='', unit='', expected_revision=0,
                context=dict(currency_exposure=True, global_supply=True,
                    hormuz_route=customer['customer']=='Caspian Export', materials=['brent'])))
    for basis, title in [('gregorian', 'Tehran · sales plan'), ('jalali', 'Tehran · Persian-month plan')]:
        if basis not in manifest['datasets']:
            history, future = generate(basis)
            INPUT.mkdir(parents=True, exist_ok=True)
            history.to_csv(INPUT / f'sales-{basis}.csv', index=False)
            future.to_csv(INPUT / f'assumptions-{basis}.csv', index=False)
            sources = {role: main.DATASET_STORE.upload(name, frame.to_csv(index=False).encode(), role)['id']
                for role, name, frame in [('history', f'sales-{basis}.csv', history), ('future', f'assumptions-{basis}.csv', future)]}
            dataset = main.DATASET_STORE.save(title, sources, settings(basis), 'synthetic_sample', True)
            manifest['datasets'][basis] = dataset['id']; remember()
        dataset = main.DATASET_STORE.get(manifest['datasets'][basis])
        # Seasonal-only models cannot cover a new buyer with no full seasonal
        # training cycle at the reserved test cutoff. Do not invent that history.
        methods = ['recommended', 'model:Weighted recent average', 'model:Ridge + drivers', 'model:Histogram gradient boosting'] if basis=='gregorian' else ['recommended', 'model:Weighted recent average', 'model:Croston SBA']
        group_key = basis + '_group'
        if group_key not in manifest:
            saved = order_inputs(main, dataset, basis)
            manifest[group_key] = dict(id=uuid.uuid4().hex, orders=saved['id']); remember()
        group = manifest[group_key]
        for method in methods:
            key = basis + ':' + method
            if key in manifest['runs']: continue
            print('Calculating ' + title + ' · ' + method, flush=True)
            result = await main.run_saved(main.SavedRunConfig(dataset_id=dataset['id'], method=method,
                sales_input_id=group['orders'], forecast_group_id=group['id'], forecast_name=title))
            manifest['runs'][key] = result['run_id']; remember()
    # Fresh downloaded market data really enters the numerical input columns.
    # Revised commodity history cannot be presented as a point-in-time backtest.
    if 'live' not in manifest['datasets']:
        dataset_id = manifest['datasets']['gregorian']
        snapshots = main.FACTOR_STORE.list()
        links = []
        for factor, policy, lag in [('worldbank_brent', 'reviewed_what_if', 1), ('global_supply_pressure', 'vintage_month_end', 2)]:
            snapshot = next(s for s in snapshots if s['factor_id']==factor)
            points = snapshot['points']
            latest = points[-1]['value']
            links.append(dict(snapshot_id=snapshot['id'], lag_months=lag, future_value=latest, availability_policy=policy))
        payload = dict(links=links, method='model:Ridge + drivers')
        review = preview_inputs(main.DATASET_STORE, main.FACTOR_STORE, dataset_id, payload, main.LIVE_SOURCES)
        if review['missing']: raise ValueError(f"Live factors have {review['missing']} unmatched periods; no invented fills.")
        saved = save_inputs(main.DATASET_STORE, main.FACTOR_STORE, dataset_id,
            {**payload, 'review_token': review['review_token'], 'reviewed': True, 'request_id': str(uuid.uuid4())}, main.LIVE_SOURCES)
        manifest['datasets']['live'] = saved['id']
        manifest['live_factor_alignment'] = {'factors': review['factors'], 'factor_count': review['factor_count'], 'missing': 0}
        remember()
    live = main.DATASET_STORE.get(manifest['datasets']['live'])
    if 'live_group' not in manifest:
        book = order_inputs(main, live)
        manifest['live_group'] = dict(id=uuid.uuid4().hex, orders=book['id']); remember()
    for method in ['model:Ridge + drivers', 'model:Elastic Net + drivers']:
        key = 'live:' + method
        if key not in manifest['runs']:
            print('Calculating live market sensitivity · ' + method, flush=True)
            result = await main.run_saved(main.SavedRunConfig(dataset_id=live['id'], method=method,
                sales_input_id=manifest['live_group']['orders'], forecast_group_id=manifest['live_group']['id'],
                forecast_name='Tehran · live market sensitivity'))
            manifest['runs'][key] = result['run_id']; remember()
    # A separate, explicitly assumed FX/inflation/logistics shock, not real market news.
    if 'stress' not in manifest['runs']:
        from app.assumptions import preview_assumptions, save_assumptions
        from app.order_reuse import preview_reuse, save_reuse
        base = main._load_run(manifest['runs']['gregorian:model:Ridge + drivers'])
        changes = []
        multipliers = {'scenario_usd_irr': 1.2, 'scenario_cpi_yoy': 1.18, 'import_delay_days': 1.8, 'selling_price_index': 1.12}
        for row in preview_assumptions(base, main.DATASET_STORE)['rows']:
            for factor, multiplier in multipliers.items():
                changes.append(dict(item_id=row['item_id'], period=row['timestamp'], factor=factor, value=row[factor]*multiplier))
        scenario = save_assumptions(base, main.DATASET_STORE, dict(name='Tehran · currency and freight stress',
            owner='Demo planner', reason='Assumed currency, pricing and import-delay stress; not a prediction of actual events.',
            reviewed=True, request_id=str(uuid.uuid4()), changes=changes,
            definitions=[dict(factor=k, unit=DEFINITIONS[k][1], geography=DEFINITIONS[k][2], source='Fictional future stress assumption') for k in multipliers]))
        result = await main.run_saved(main.SavedRunConfig(dataset_id=scenario['id']))
        source = main.SALES_STORE.list(base['run_id'])[0]['id']
        review = preview_reuse(main.SALES_STORE, main._load_run, result['run_id'], source)[0]
        save_reuse(main.SALES_STORE, main._load_run, result['run_id'], dict(snapshot_id=source,
            review_token=review['review_token'], reviewed=True, coverage_confirmed=True,
            request_id='tehran-stress-order-reuse'), 'Local session')
        manifest['runs']['stress'] = result['run_id']; remember()
    manifest['live_sources'] = main.LIVE_SOURCES.listing()['sources']
    manifest['business_summary'] = dict(customers=5, products=4, customer_product_pairs=18,
        established_history_months=48, new_customer_history_months=18, history_rows_per_calendar=804, horizon_months=12)
    manifest['limitations'] = ['All customer sales, orders and internal factors are fictional.',
        'Live Brent prices and NY Fed supply pressure are used in the live sensitivity forecasts.',
        'Live commodity history is revised: live sensitivity has no claimed historical accuracy or calibrated intervals.',
        'Monthly CPI is not connected: IMF reuse permission has not been provided. Demo inflation is an explicit assumption.',
        'Servix quote freshness and incomplete monthly coverage prevent indiscriminate historical use.',
        'Hormuz history is too short for the four-year model; retained as regional context, not filled backwards.',
        'Future market values are explicit assumptions, not live future observations.']
    views = ViewStore(main.SALES_STORE.path)
    exports = []
    for key, run_id in manifest['runs'].items():
        run = main._load_run(run_id)
        saved = main.SALES_STORE.get(main.SALES_STORE.list(run_id)[0]['id'])
        outlook = demand_outlook(saved['inputs'], run)
        assert outlook['can_export'], outlook['warnings']
        assert len(outlook['rows']) == len(run['items']) * run['run_settings']['horizon']
        for mode in ('combined_demand', 'remaining_forecast'):
            for kind in ('csv', 'json', 'xlsx'):
                content, _ = export_demand(outlook, mode, kind)
                path = OUT / 'exports' / run_id / (mode + '.' + kind)
                path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
                exports.append(dict(run_id=run_id, mode=mode, kind=kind, path=str(path)))
        if not views.list('local', run_id):
            for name, display, view, measure in [('Monthly demand', 'chart', 'month', 'total'),
                    ('Customer overview', 'chart', 'customer', 'total'), ('Product overview', 'pivot', 'sku', 'total'),
                    ('Orders and remaining demand', 'coverage', 'detail', 'booked')]:
                views.save('local', SavedView(name=name, run_id=run_id, snapshot_id=saved['id'],
                    settings=dict(unit='tonnes', display=display, view=view, measure=measure, sort='largest')))
    manifest['exports'] = exports
    manifest['state'] = 'forecasts_populated'; remember()
    print(json.dumps({'runs': len(manifest['runs']), 'exports': len(exports), 'manifest': str(MANIFEST)}), flush=True)


def verify():
    from app import main
    from app.sales_demand import demand_outlook
    manifest = json.loads(MANIFEST.read_text())
    findings = []
    for key, run_id in manifest['runs'].items():
        run = main._load_run(run_id)
        snap = main.SALES_STORE.get(main.SALES_STORE.list(run_id)[0]['id'])
        outlook = demand_outlook(snap['inputs'], run)
        booked, fulfilled = defaultdict(Decimal), defaultdict(Decimal)
        from app.sales_demand import month
        basis = run['run_settings']['calendar_profile']['month_basis']
        for row in snap['inputs']['orders']:
            if row['status'] != 'confirmed': continue
            identity = (row['customer'], row['sku'], month(row['due_date'], basis))
            booked[identity] += Decimal(str(row['ordered'])) - Decimal(str(row['fulfilled'])) - Decimal(str(row['cancelled']))
            fulfilled[identity] += Decimal(str(row['fulfilled']))
        commitments = {(c['customer'],c['sku'],c['period']): Decimal(str(c['quantity']))
                       for c in snap['inputs'].get('commitments', [])}
        for row in outlook['rows']:
            identity = (row['customer'], row['sku'], row['period'])
            expected_month = commitments.get(identity, Decimal(str(row['baseline'])))
            remain = max(Decimal(0), expected_month-booked[identity]-fulfilled[identity])
            for actual, expected in [(row['booked'], booked[identity]), (row['fulfilled'], fulfilled[identity]),
                                     (row['remaining'], remain), (row['total'], booked[identity]+fulfilled[identity]+remain)]:
                assert math.isclose(float(actual), float(expected), abs_tol=1e-7)
        for point in run['series']['__all__']['forecast']:
            total = math.fsum(next(p['mean'] for p in run['series'][item]['forecast'] if p['timestamp']==point['timestamp']) for item in run['items'])
            assert math.isclose(total, point['mean'], abs_tol=1e-7)
        for export in [e for e in manifest['exports'] if e['run_id']==run_id]:
            path = Path(export['path'])
            frame = pd.read_csv(path) if export['kind']=='csv' else pd.read_excel(path) if export['kind']=='xlsx' else pd.DataFrame(json.loads(path.read_text()))
            assert len(frame)==len(outlook['rows']) and not frame.duplicated(['customer','sku','period']).any()
            expected = sum(r['still_to_serve'] if export['mode']=='combined_demand' else r['remaining'] for r in outlook['rows'])
            assert math.isclose(frame.quantity.sum(), expected, abs_tol=1e-7)
        findings.append(dict(run_id=run_id, rows=len(outlook['rows']),
            customers=len({r['customer'] for r in outlook['rows']}), products=len({r['sku'] for r in outlook['rows']}),
            booked=round(sum(r['booked'] for r in outlook['rows']),3),
            remaining=round(sum(r['remaining'] for r in outlook['rows']),3),
            no_orders_rows=sum(r['booked']==0 for r in outlook['rows']),
            above_baseline_rows=sum(r['booked']>r['baseline'] for r in outlook['rows']),
            all_six_exports_reconciled=True, aggregate_reconciled=True))
    manifest['checks']['independent_order_accounting'] = findings
    write(MANIFEST, manifest)
    print(json.dumps({'verified_runs': len(findings), 'verified_demand_rows':sum(f['rows'] for f in findings),
        'exports_reconciled':len(findings)*6}), flush=True)


def retry_calculations():
    """Archive this script's incomplete calculation attempt, not original records."""
    manifest = json.loads(MANIFEST.read_text())
    stage = OUT / ('calculation-attempt-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    stage.mkdir()
    # Resolve and move only successful result IDs recorded by this demo script.
    # Shared databases and all unrelated/unknown forecast folders stay untouched.
    for identifier in manifest['runs'].values():
        source = ROOT / 'runs' / identifier
        row = json.loads((source / 'result.json').read_text())
        if row.get('dataset_id') not in manifest['datasets'].values() or row.get('source_classification') != 'synthetic_sample':
            raise ValueError('Refusing to archive a result outside this demo.')
        shutil.move(str(source), str(stage / identifier))
    manifest['runs'] = {}
    for key in ('gregorian_group', 'jalali_group', 'live_group'):
        manifest.pop(key, None)
    write(MANIFEST, manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['reset','seed','verify','retry-calculations'])
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if args.action == 'reset': reset()
    elif args.action == 'retry-calculations': retry_calculations()
    elif args.action == 'seed': asyncio.run(seed(args.refresh))
    else: verify()

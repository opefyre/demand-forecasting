"""Isolated synthetic sales pilot: real imports, jobs, models, orders and recovery.

No OpenAI/provider requests, client-data edits, or live automation are performed.
Measurements describe this machine and sample only, not a performance SLA.
"""
import argparse
import asyncio
from collections import defaultdict
from contextlib import ExitStack
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
import csv
import json
import math
from pathlib import Path
import resource
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

import numpy as np
import openpyxl
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.datasets import DatasetStore
from app.jobs import JobStore, execute_job
from app.recovery import backup, restore, digest
from app.sales_demand import DemandStore, demand_outlook, export_demand, import_rows
from app.sales_conventions import local_today, period_start, shift_month, month_label
from app.forecast_views import ViewStore, SavedView


def generate(customers, skus, months, calendar, seed=7419):
    """Tonnes at customer/SKU/month grain, not actual Iranian market data."""
    rng = np.random.default_rng(seed)
    end = shift_month(period_start(local_today(), calendar), -1, calendar)
    dates = [shift_month(end, i - months + 1, calendar) for i in range(months)]
    rows, expected = [], {}
    for customer in range(customers):
        for sku in range(skus):
            name, product = f'Demo customer {customer + 1:03d}', f'{sku + 1:04d}'
            key = name + '/' + product
            values = []
            level = 8 + rng.uniform(2, 100)
            for i, day in enumerate(dates):
                seasonal = 1 + .2 * math.sin(2 * math.pi * i / 12)
                # A disclosed synthetic spring dip, trend, demand shock and noise.
                seasonal *= .82 if int(month_label(day, calendar)[5:]) == (1 if calendar == 'jalali' else 3) else 1
                quantity = level * seasonal * (1 + i * .002) + rng.normal(0, level * .07)
                if (customer + sku) % 7 == 0 and rng.random() < .65: quantity = 0
                if (customer + sku) % 11 == 0 and i >= months - 5: quantity *= .7
                values.append(round(max(0, quantity), 3))
                rows.append(dict(date=str(day.date()), item=key, customer=name, sku=product, qty=values[-1]))
            expected[key] = float(sum(Decimal(str(v)) * w for v, w in zip(values[-3:], (1, 2, 3))) / 6)
    return pd.DataFrame(rows), expected


def read_export(content, kind):
    if kind == 'json': return json.loads(content)
    if kind == 'csv': return list(csv.DictReader(content.decode('utf-8-sig').splitlines()))
    book = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    try:
        table = list(book.active.values)
        return [dict(zip(table[0], row)) for row in table[1:]]
    finally: book.close()


def close_enough(actual, expected):
    if not math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-7):
        raise AssertionError(f'Quantity mismatch: {actual} != {expected}')


def pilot(destination, *, customers=40, skus=3, orders_per_series=200, months=60,
          horizon=12, calendar='gregorian', method='model:Weighted recent average'):
    # Bound the test itself. These are not certified application capacity limits.
    if not (1 <= customers <= 200 and 1 <= skus <= 10 and customers * skus <= 1000
            and 24 <= months <= 120 and 1 <= horizon <= 24 and 0 <= orders_per_series <= 500
            and customers * skus * orders_per_series <= 50000):
        raise ValueError('Pilot dimensions exceed the bounded synthetic test size.')
    destination = Path(destination).absolute()
    if destination.exists(): raise ValueError('Choose a new pilot output directory; existing results are never overwritten.')
    destination.mkdir(mode=0o700, parents=True)
    # Unlike an application archive, this directory contains synthetic inputs only.
    (destination / 'PILOT_INCOMPLETE').write_text('Synthetic acceptance run has not finished.\n')
    timings = {}
    def timed(name, fn):
        started = time.perf_counter(); result = fn()
        timings[name] = round(time.perf_counter() - started, 3)
        return result

    history, expected_baselines = generate(customers, skus, months, calendar)
    raw_history = history.to_csv(index=False).encode()
    (destination / 'synthetic-sales.csv').write_bytes(raw_history)
    with TemporaryDirectory(prefix='demandlab-pilot-') as temporary, ExitStack() as stack:
        root = Path(temporary) / 'workspace'; root.mkdir(); runs = root / 'runs'; runs.mkdir()
        (root / 'requirements.txt').write_bytes((ROOT / 'requirements.txt').read_bytes())
        datasets = DatasetStore(root / 'data/datasets')
        source = timed('history_import', lambda: datasets.upload('synthetic-sales.csv', raw_history, 'history'))
        settings = dict(date_col='date', target_col='qty', item_col='item', customer_col='customer',
            sku_col='sku', frequency='monthly', horizon=horizon, unit='tonnes', profile='fast',
            method_selection=method, missing_strategy='auto', outlier_strategy='none', history_calendar='gregorian',
            month_basis=calendar, history_grain='monthly_totals', sales_measure='customer_demand', returns_policy='reject')
        # Persian totals use Persian source dates, not rebucketed Gregorian totals.
        if calendar == 'jalali':
            from persiantools.jdatetime import JalaliDate
            history['date'] = history.date.map(lambda d: str(JalaliDate(pd.Timestamp(d).date())))
            raw_history = history.to_csv(index=False).encode()
            (destination / 'synthetic-sales.csv').write_bytes(raw_history)
            source = datasets.upload('synthetic-sales.csv', raw_history, 'history')
            settings['history_calendar'] = 'jalali'
        dataset = timed('history_review_save', lambda: datasets.save('Synthetic release pilot',
            {'history': source['id']}, settings, 'synthetic_sample', True))
        original = digest(datasets._path('dataset', dataset['id']))
        from app import main
        stack.enter_context(patch.object(main, 'DATASET_STORE', datasets))
        stack.enter_context(patch.object(main, 'RUNS_DIR', runs))
        jobs = JobStore(root / 'data/jobs.sqlite3', runs); stack.callback(jobs.close)
        job = jobs.create({'dataset_id': dataset['id']}, 'Synthetic release pilot', 'pilot-calculation-request')
        timed('queued_calculation', lambda: execute_job(job['id'], jobs,
            lambda payload: asyncio.run(main.run_saved(main.SavedRunConfig(**payload)))))
        completed = jobs.get(job['id'])
        if completed['state'] != 'succeeded': raise AssertionError(completed.get('error') or completed['state'])
        run = json.loads((runs / completed['run_id'] / 'result.json').read_text())
        for key in run['items']:
            points = run['series'][key]['forecast']
            if len(points) != horizon: raise AssertionError('Wrong forecast horizon.')
            for point in points:
                if not math.isfinite(point['mean']) or point['mean'] < 0: raise AssertionError('Invalid forecast.')
                if method == 'model:Weighted recent average': close_enough(point['mean'], expected_baselines[key])
        for point in run['series']['__all__']['forecast']:
            close_enough(point['mean'], math.fsum(next(p['mean'] for p in run['series'][key]['forecast']
                if p['timestamp'] == point['timestamp']) for key in run['items']))
        # Reopen the durable ledger and redeliver; no second calculation may execute.
        reopened = JobStore(root / 'data/jobs.sqlite3', runs); stack.callback(reopened.close)
        timed('duplicate_delivery', lambda: execute_job(job['id'], reopened,
            lambda _: (_ for _ in ()).throw(AssertionError('Duplicate job executed.'))))
        if len(list(runs.iterdir())) != 1: raise AssertionError('Duplicate result published.')
        now = local_today(); orders, directory = [], []
        for index, key in enumerate(run['items']):
            meta = run['metadata'][key]
            directory.append(dict(customer=meta['customer'], sku=meta['sku'], unit='tonnes', series_id=key))
            for line in range(orders_per_series):
                point = run['series'][key]['forecast'][line % horizon]
                case = index % 5
                quantity = round(max(1, point['mean']) * (1.5 if case == 2 else .5) * horizon / max(orders_per_series, 1), 6)
                current = point['timestamp'][:10] == str(period_start(now, calendar).date())
                status = 'unconfirmed' if case == 0 else 'cancelled' if case == 4 and line % 2 == 0 else 'confirmed'
                orders.append(dict(reference=f'PILOT-{index}-{line}', customer=meta['customer'], sku=meta['sku'],
                    unit='tonnes', due_date=point['timestamp'][:10], ordered=quantity,
                    fulfilled=round(quantity * .1, 6) if case == 3 and current else 0,
                    cancelled=quantity if status == 'cancelled' else 0, status=status))
        raw_orders = pd.DataFrame(orders, columns=['reference','customer','sku','unit','due_date','ordered','fulfilled','cancelled','status']).to_csv(index=False).encode()
        (destination / 'synthetic-orders.csv').write_bytes(raw_orders)
        uploaded = timed('order_import', lambda: datasets.upload('synthetic-orders.csv', raw_orders, 'sales_orders'))
        fields = ['reference','customer','sku','unit','due_date','ordered','fulfilled','cancelled','status']
        config = dict(source_id=uploaded['id'], mapping={field:chr(65+i) for i,field in enumerate(fields)}, calendar='gregorian')
        reviewed_orders, proof = timed('order_mapping_validation', lambda: import_rows(datasets, 'orders', config))
        inputs = dict(name='Synthetic full order book', run_id=run['run_id'], classification='synthetic_sample',
            as_of=str(now), valid_until=str(now + timedelta(days=7)), order_feed='complete_snapshot',
            customers=directory, orders=reviewed_orders, commitments=[], reviewed=True,
            note='Generated artificial customer demand and orders; not client or Iranian market facts.')
        sales = DemandStore(root / 'data/sales-demand.sqlite3')
        snapshot = timed('order_review_save', lambda: sales.save(inputs, run, 'pilot-order-snapshot', 'Pilot'))
        outlook = timed('demand_calculation', lambda: demand_outlook(snapshot['inputs'], run))
        outlook['snapshot_id'] = snapshot['id']
        if not outlook['can_export'] or len(outlook['rows']) != customers * skus * horizon:
            raise AssertionError('Incomplete demand coverage.')
        # Independent order accounting from generated inputs, not the demand helper.
        buckets = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for order in orders:
            if order['status'] != 'confirmed': continue
            bucket = buckets[(order['customer'],order['sku'],order['due_date'])]
            bucket[0] += Decimal(str(order['ordered'])) - Decimal(str(order['cancelled'])) - Decimal(str(order['fulfilled']))
            bucket[1] += Decimal(str(order['fulfilled']))
        expected = {}
        for key in run['items']:
            meta = run['metadata'][key]
            for point in run['series'][key]['forecast']:
                identity = (meta['customer'],meta['sku'],point['timestamp'][:10])
                booked, fulfilled = buckets[identity]
                baseline = Decimal(str(expected_baselines[key] if method == 'model:Weighted recent average' else point['mean']))
                remainder = max(Decimal(0), baseline - booked - fulfilled)
                expected[identity] = dict(booked=booked, fulfilled=fulfilled, remaining=remainder,
                    combined_demand=booked + remainder, remaining_forecast=remainder)
        for row in outlook['rows']:
            values = expected[(row['customer'],row['sku'],row['period'])]
            for field in ('booked','fulfilled','remaining'): close_enough(row[field], values[field])
        totals = {}
        for mode in ('combined_demand','remaining_forecast'):
            for kind in ('csv','xlsx','json'):
                content, _ = timed('export_' + mode + '_' + kind, lambda: export_demand(outlook, mode, kind))
                rows = read_export(content, kind)
                if len(rows) != len(expected): raise AssertionError('Export row count mismatch.')
                identities = [(r['customer'],r['sku'],r['period']) for r in rows]
                if len(set(identities)) != len(expected): raise AssertionError('Duplicate or missing export row.')
                for row, identity in zip(rows, identities):
                    close_enough(row['quantity'], expected[identity][mode])
                    if row['approval'] != 'draft': raise AssertionError('Unapproved result was labelled approved.')
                totals[mode] = math.fsum(float(row['quantity']) for row in rows)
                (destination / f'{mode}.{kind}').write_bytes(content)
        # Unknown, expired and overdue orders may not leak into planning exports.
        blocked = []
        for case, changes in [('unknown_book', {'order_feed':'unknown'}),
                              ('expired_book', {'valid_until':str(now-timedelta(days=1)), 'as_of':str(now-timedelta(days=2))})]:
            result = demand_outlook({**inputs, **changes}, run)
            if result['can_export']: raise AssertionError('Unsafe order book exported.')
            try: export_demand(result, 'combined_demand', 'csv')
            except ValueError: blocked.append(case)
            else: raise AssertionError('Export gate bypassed.')
        for case, changes in [('new_customer_without_history', {'customers':directory + [
                dict(customer='Demo new customer',sku='NEW',unit='tonnes')]}),
                ('overdue_order', {'orders':reviewed_orders + [dict(reference='PILOT-OVERDUE',
                    customer=directory[0]['customer'],sku=directory[0]['sku'],unit='tonnes',
                    due_date=str(period_start(now,calendar).date()-timedelta(days=1)),
                    ordered=10,fulfilled=0,cancelled=0,status='confirmed')]})]:
            result = demand_outlook({**inputs, **changes}, run)
            if result['can_export']: raise AssertionError('Unresolved demand exported.')
            try: export_demand(result,'combined_demand','json')
            except ValueError: blocked.append(case)
            else: raise AssertionError('Export gate bypassed.')
        # Persist a view and incomplete worker job, then recover only in staging.
        views = ViewStore(sales.path)
        saved_view = views.save('Pilot', SavedView(name='Pilot customer view', run_id=run['run_id'],
            snapshot_id=snapshot['id'], settings={'customer':directory[0]['customer'], 'unit':'tonnes', 'display':'pivot'}))
        unfinished = jobs.create({'dataset_id':dataset['id']}, 'Interrupted pilot job', 'pilot-interrupted-request')
        jobs.claim(unfinished['id'])
        archive = destination / 'synthetic-state.zip'
        timed('backup', lambda: backup(root, archive))
        restored = Path(temporary) / 'restored'
        report = timed('restore', lambda: restore(archive, restored))
        copied = JobStore(restored / 'data/jobs.sqlite3', restored / 'runs'); stack.callback(copied.close)
        if copied.get(unfinished['id'])['state'] != 'interrupted': raise AssertionError('Active job replayed after restore.')
        if copied.get(job['id'])['state'] != 'succeeded': raise AssertionError('Completed job lost after restore.')
        if DemandStore(restored / 'data/sales-demand.sqlite3').get(snapshot['id']) != snapshot:
            raise AssertionError('Order snapshot changed during restore.')
        if ViewStore(restored / 'data/sales-demand.sqlite3').list('Pilot',run['run_id']) != [saved_view]:
            raise AssertionError('Saved view lost during restore.')
        for path in (root / 'runs').rglob('*'):
            if path.is_file() and digest(path) != digest(restored / path.relative_to(root)):
                raise AssertionError('Restored forecast/export bytes changed.')
        if digest(datasets._path('dataset',dataset['id'])) != original: raise AssertionError('Original input changed.')
        if jobs.get(unfinished['id'])['state'] != 'running': raise AssertionError('Live job was modified by restore.')
        result = dict(classification='synthetic_sample', seed=7419, calendar=calendar, method=method,
            customers=customers, skus=skus, series=customers*skus, history_months=months, history_rows=len(history),
            forecast_months=horizon, forecast_rows=len(expected), order_lines=len(orders), totals=totals,
            timings_seconds=timings, peak_process_memory_mb=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss /
                (1024**2 if sys.platform == 'darwin' else 1024), 1),
            backup_verified_files=report['verified_files'], blocked_cases=blocked,
            checks=['independent weighted baseline' if method == 'model:Weighted recent average' else 'finite nonnegative baseline',
                'portfolio reconciliation','independent customer/order accounting','all six export formats',
                'no duplicate job execution','restored business bytes unchanged','active restored job interrupted',
                'original input and job unchanged'],
            limitation='Synthetic correctness/load sample, not real-client accuracy, live-factor coverage, multi-user load or certified capacity.')
    (destination / 'evidence.json').write_text(json.dumps(result, indent=2))
    (destination / 'PILOT_INCOMPLETE').unlink()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--customers', type=int, default=40)
    parser.add_argument('--skus', type=int, default=3)
    parser.add_argument('--orders-per-series', type=int, default=200)
    parser.add_argument('--months', type=int, default=60)
    parser.add_argument('--horizon', type=int, default=12)
    parser.add_argument('--calendar', choices=['gregorian','jalali'], default='gregorian')
    parser.add_argument('--method', default='model:Weighted recent average')
    print(json.dumps(pilot(**vars(parser.parse_args())), indent=2))

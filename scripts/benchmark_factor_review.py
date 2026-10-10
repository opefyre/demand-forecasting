"""Offline review/save timings; disposable fictional Tehran data, no providers."""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import sys
from tempfile import TemporaryDirectory
import time
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    import pandas as pd
    from app.datasets import DatasetStore
    from app.factors import FactorStore
    from app.factor_imports import review_import, save_import
    from app import forecast_inputs
    from scripts.prepare_tehran_demo import generate

    raw, _ = generate(end=pd.Timestamp('2026-09-01'), horizon=6)
    receipt = {'synthetic': True, 'history_rows': len(raw),
               'series': raw.series.nunique(), 'operations': {}}
    profiler = cProfile.Profile()
    with TemporaryDirectory(prefix='factor-review-benchmark-') as folder:
        store = DatasetStore(Path(folder) / 'datasets')
        factors = FactorStore(Path(folder) / 'factors')
        source = store.upload('sales.csv', raw.to_csv(index=False).encode(), 'history')
        settings = dict(date_col='date', target_col='quantity', customer_col='customer',
            sku_col='sku', series_mode='customer_product', drivers=[], frequency='monthly',
            horizon=6, unit='tonnes', profile='fast', method_selection='model:Ridge + drivers',
            calendar_country='IR', sales_measure='customer_demand', history_grain='monthly_totals')
        dataset = store.save('Tehran benchmark', {'history': source['id']}, settings, 'synthetic_sample', True)
        points = pd.DataFrame([dict(period=day.date().isoformat(), value=100+i,
            published=(day+pd.Timedelta(days=5)).date().isoformat())
            for i, day in enumerate(pd.date_range('2022-08-31', periods=50, freq='ME'))])
        source = store.upload('index.csv', points.to_csv(index=False).encode(), 'factor_observations')
        config = dict(source_id=source['id'], name='Fictional index', unit='index',
            geography='Iran · fictional', provider='Offline test', frequency='monthly',
            classification='synthetic_sample', mapping={'period':'A','value':'B','available_at':'C'})
        report = review_import(store, config)
        snapshot = save_import(store, factors, {**config, 'reviewed':True,
            'review_token':report['review_token'], 'request_id':str(uuid.uuid4())})
        payload = dict(snapshot_id=snapshot['id'], lag_months=2, future_value=160,
                       method='model:Ridge + drivers')
        # Warm package/calendar imports before comparing operation work.
        forecast_inputs.factor_options(store, factors, dataset['id'])
        review = forecast_inputs.preview_inputs(store, factors, dataset['id'], payload)
        approved = {**payload, 'reviewed':True, 'review_token':review['review_token']}
        calls = [
            ('options', lambda: forecast_inputs.factor_options(store, factors, dataset['id'])),
            ('preview', lambda: forecast_inputs.preview_inputs(store, factors, dataset['id'], payload)),
            ('save', lambda: forecast_inputs.save_inputs(store, factors, dataset['id'],
                {**approved, 'request_id':str(uuid.uuid4())})),
        ]
        for name, call in calls:
            with patch.object(forecast_inputs, 'input_context', wraps=forecast_inputs.input_context) as contexts:
                started = time.perf_counter()
                profiler.enable()
                result = call()
                profiler.disable()
                receipt['operations'][name] = {'seconds':round(time.perf_counter()-started, 4),
                    'context_preparations':contexts.call_count,
                    'missing':result.get('missing')}
        assert store.get(dataset['id']) == dataset, 'Original sales inputs changed.'
    if args.output:
        args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False))
    print(json.dumps(receipt), flush=True)
    if args.profile:
        profiler.dump_stats(str(args.profile))
        pstats.Stats(profiler).sort_stats('cumulative').print_stats(12)


if __name__ == '__main__':
    main()

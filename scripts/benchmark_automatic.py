"""Offline Automatic benchmark; fictional Tehran inputs, no saved app mutations."""
import argparse
import cProfile
import json
import os
from pathlib import Path
import pstats
import sys
from tempfile import TemporaryDirectory
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    from scripts.prepare_tehran_demo import generate
    from app.data import prepare_history, build_future_covariates
    from app.forecast_engine import run_forecast, _model_specs
    raw, _ = generate(end=__import__('pandas').Timestamp('2026-09-01'), horizon=6)
    history, _ = prepare_history(raw, date_col='date', target_col='quantity', item_col='series',
        driver_cols=[], frequency='monthly', outlier_strategy='none', history_grain='monthly_totals',
        sales_measure='customer_demand', calendar_country='IR')
    future, _ = build_future_covariates(history, None, future_date_col=None, future_item_col=None,
        known_driver_cols=[], frequency='monthly', horizon=6)
    profiler = cProfile.Profile()
    started = time.perf_counter()
    with TemporaryDirectory(prefix='forecast-benchmark-') as temp:
        profiler.enable()
        result = run_forecast(history=history, future_covariates=future, known_driver_cols=[],
            horizon=6, frequency='monthly', profile='fast', runs_dir=Path(temp))
        profiler.disable()
        receipt = {'synthetic': True, 'history_rows': len(raw), 'series': raw.series.nunique(),
            'seconds': round(time.perf_counter() - started, 3), 'cloud': os.getenv('DEMANDLAB_CLOUD_RUNTIME') == 'true',
            'models': len(_model_specs('fast')), 'metrics': result.get('metrics'),
            'threads': {spec.name: spec.estimator.get_params().get('n_jobs') for spec in _model_specs('fast')
                        if spec.estimator is not None and 'n_jobs' in spec.estimator.get_params()}}
        # Avoid paths, business inputs and generated per-customer outputs in stdout.
        if args.output:
            args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False, default=str))
        print(json.dumps({key: value for key, value in receipt.items() if key != 'metrics'}), flush=True)
    if args.profile:
        profiler.dump_stats(str(args.profile))
        pstats.Stats(profiler).sort_stats('cumulative').print_stats(15)


if __name__ == '__main__':
    main()

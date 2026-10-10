"""Offline Automatic benchmark; fictional Tehran inputs, no saved app mutations."""
import argparse
import ast
import cProfile
from contextlib import ExitStack
import json
import os
from pathlib import Path
import pstats
import sys
import subprocess
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--reference-ref', help='Compare preparation with four functions from this local Git commit.')
    args = parser.parse_args()
    from scripts.prepare_tehran_demo import generate
    from app.data import prepare_history, build_future_covariates
    from app import forecast_engine as engine
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
        reference = None
        reference_seconds = None
        reference_csv = None
        reference_profiler = cProfile.Profile()
        if args.reference_ref:
            # Read only the explicit local commit; do not execute a module or
            # access its files/network. Reuse current packages and unchanged math.
            commit = subprocess.run(['git', 'rev-parse', '--verify', args.reference_ref + '^{commit}'],
                cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
            source = subprocess.run(['git', 'show', commit + ':app/forecast_engine.py'],
                cwd=ROOT, capture_output=True, text=True, check=True).stdout
            names = {'_feature_row', '_direct_supervised_frame', '_direct_predict', '_fit_full_models_and_predict'}
            tree = ast.Module(body=[node for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef) and node.name in names], type_ignores=[])
            if {node.name for node in tree.body} != names:
                raise ValueError('Reference commit does not contain the expected preparation functions.')
            namespace = engine.__dict__.copy()
            exec(compile(tree, '<local-reference-preparation>', 'exec'), namespace)
            with ExitStack() as stack:
                for name in names:
                    stack.enter_context(patch.object(engine, name, namespace[name]))
                before = time.perf_counter()
                reference_profiler.enable()
                reference = run_forecast(history=history, future_covariates=future, known_driver_cols=[],
                    horizon=6, frequency='monthly', profile='fast', runs_dir=Path(temp))
                reference_profiler.disable()
                reference_seconds = time.perf_counter() - before
            reference_csv = (Path(temp)/reference['run_id']/'forecast.csv').read_bytes()
        started = time.perf_counter()
        profiler.enable()
        result = run_forecast(history=history, future_covariates=future, known_driver_cols=[],
            horizon=6, frequency='monthly', profile='fast', runs_dir=Path(temp))
        profiler.disable()
        receipt = {'synthetic': True, 'history_rows': len(raw), 'series': raw.series.nunique(),
            'seconds': round(time.perf_counter() - started, 3), 'cloud': os.getenv('DEMANDLAB_CLOUD_RUNTIME') == 'true',
            'models': len(_model_specs('fast')), 'metrics': result.get('metrics'),
            'threads': {spec.name: spec.estimator.get_params().get('n_jobs') for spec in _model_specs('fast')
                        if spec.estimator is not None and 'n_jobs' in spec.estimator.get_params()}}
        if reference is not None:
            def evidence(value):
                if isinstance(value, dict):
                    return {key: evidence(item) for key, item in value.items() if key not in {'run_id', 'fit_time'}}
                if isinstance(value, list):
                    return [evidence(item) for item in value]
                return value
            equal = evidence(reference) == evidence(result)
            csv_equal = reference_csv == (Path(temp)/result['run_id']/'forecast.csv').read_bytes()
            receipt.update(reference_commit=commit, reference_seconds=round(reference_seconds, 3),
                exact_result_except_ids_and_timings=equal, exact_forecast_csv=csv_equal)
            def preparation_seconds(profile):
                return round(sum(value[3] for key, value in pstats.Stats(profile).stats.items()
                    if key[2] == '_global_direct_supervised_frame'), 4)
            receipt.update(reference_training_preparation_seconds=preparation_seconds(reference_profiler),
                training_preparation_seconds=preparation_seconds(profiler))
            if not equal or not csv_equal:
                raise AssertionError('Preparation change altered quantities or evidence.')
        # Avoid paths, business inputs and generated per-customer outputs in stdout.
        if args.output:
            args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False, default=str))
        print(json.dumps({key: value for key, value in receipt.items() if key != 'metrics'}), flush=True)
    if args.profile:
        profiler.dump_stats(str(args.profile))
        pstats.Stats(profiler).sort_stats('cumulative').print_stats(15)


if __name__ == '__main__':
    main()

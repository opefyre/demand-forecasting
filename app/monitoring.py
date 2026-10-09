"""Comparable historical evidence; never infer live drift from unrelated runs."""
import json
from pathlib import Path

from .actuals import digest, evaluate_actuals


def comparison_key(run):
    metrics = run.get('metrics', {})
    evaluation = metrics.get('evaluation_signature')
    if not all((run.get('unit'), run.get('site', {}).get('id'), run.get('run_settings', {}).get('frequency'), run.get('source_classification'))):
        return None
    if not evaluation or run.get('scenario_name') or run.get('run_settings', {}).get('scenario_adjustment_pct', 0):
        return None
    return digest({'evaluation': evaluation, 'unit': run.get('unit'), 'site': run.get('site', {}).get('id'),
                   'frequency': run.get('run_settings', {}).get('frequency'),
                   'classification': run.get('source_classification'),
                   'requested_horizon': metrics.get('requested_horizon'), 'evaluation_type': metrics.get('evaluation_type')})


def build_monitoring(runs_dir: Path, current: dict | None = None) -> dict:
    paths = sorted(runs_dir.glob('*/result.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    runs, seen = [], set()
    if current:
        runs.append(current)
        seen.add(current.get('run_id'))
    for path in paths:
        try:
            run = json.loads(path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        if run.get('run_id') not in seen:
            runs.append(run)
            seen.add(run.get('run_id'))
    latest = runs[0] if runs else {}
    key = comparison_key(latest)
    comparable = [r for r in runs[1:] if key is not None and comparison_key(r) == key]
    previous = comparable[0] if comparable else None
    now = latest.get('metrics', {}).get('wape_pct')
    before = previous.get('metrics', {}).get('wape_pct') if previous else None
    delta = None if now is None or before is None else now - before
    leaderboard = [r for r in latest.get('leaderboard', []) if r.get('wape_pct') is not None]
    history = [{'run_id': r.get('run_id'), 'data_end': r.get('summary', {}).get('end'),
                'wape_pct': r.get('metrics', {}).get('wape_pct'), 'bias_pct': r.get('metrics', {}).get('bias_pct'),
                'best_model': r.get('best_model'), 'comparable': r.get('run_id') == latest.get('run_id') or r in comparable}
               for r in runs[:30]]
    return {'champion': None, 'challenger': None, 'historical_candidates': leaderboard[:2], 'history': history,
            'comparison': {'previous_run_id': previous.get('run_id') if previous else None,
                           'wape_change_points': delta,
                           'reason': 'Identical held-out actuals, periods, horizons, site and units.' if previous else 'No run has matching recorded evaluation evidence.'},
            'model_drift_wape_points': None, 'data_quality_drift_points': None,
            'retrain': {'recommended': None, 'reasons': ['Historical model comparisons are not live drift monitoring. Review saved closed-period actuals before deciding to retrain.']},
            'policy': {'automatic_retraining': False, 'automatic_promotion': False}}


def forecast_value_add(run, plans, actuals, *, plan_id=None, unit=None, closed_through=None, classification=None):
    """Strict compatibility adapter. New API saves reviewed, immutable evaluations."""
    columns = [str(c).strip().lower() for c in actuals.columns]
    if len(set(columns)) != len(columns) or not {'item_id', 'timestamp', 'actual'}.issubset(columns):
        raise ValueError('Actuals need unique item_id, timestamp and actual columns.')
    table = {'columns': [{'id': c} for c in columns],
             'rows': [{'source_row': n + 2, 'values': dict(zip(columns, row))} for n, row in enumerate(actuals.itertuples(index=False, name=None))]}
    plan = next((p for p in plans if p['id'] == plan_id), None)
    if plan_id and not plan:
        raise ValueError('Selected plan not found.')
    result = evaluate_actuals(run, table, {'mapping': {c: c for c in ('item_id', 'timestamp', 'actual')},
                             'unit': unit, 'closed_through': closed_through, 'classification': classification}, plan)
    if result['issue_count']:
        raise ValueError(result['issues'][0]['message'])
    return {**result, 'baseline_wape_pct': result['paired_baseline']['wape_pct'] if plan else result['diagnostic']['wape_pct'],
            'approved_wape_pct': result['paired_approved']['wape_pct'], 'fva_points': result['improvement_points'],
            'observations': len(result['rows']), 'plan_id': plan_id}

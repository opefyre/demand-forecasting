"""Empirical planning ranges and reserved-period checks for frozen model choices.

NumPy supplies the order statistics. Time-series residuals are not assumed to be
exchangeable: a nominal 80% range is not an 80% future-coverage guarantee.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np


TARGET = 0.8
MIN_SCORES = 5


def range_parameters(rows: list[dict], item_ids: list[str], horizon: int) -> dict:
    """Fit only the supplied calibration rows; total errors retain co-movement."""
    by_item = defaultdict(lambda: defaultdict(list))
    by_date = defaultdict(list)
    seen = set()
    expected = set(item_ids)
    for row in rows:
        key = (row['item_id'], row['timestamp'])
        if key in seen:
            raise ValueError('Duplicate range-calibration item and period.')
        seen.add(key)
        actual, predicted = float(row['actual']), float(row['predicted'])
        if not np.isfinite([actual, predicted]).all():
            raise ValueError('Range-calibration values must be finite.')
        by_item[row['item_id']][int(row['step'])].append(actual - predicted)
        by_date[row['timestamp']].append(row)
    complete_dates = []
    for date, group in by_date.items():
        if {r['item_id'] for r in group} != expected or len({r['step'] for r in group}) != 1:
            continue
        residual = sum(float(r['actual']) - float(r['predicted']) for r in group)
        by_item['__portfolio__'][int(group[0]['step'])].append(residual)
        complete_dates.append(date)
    fitted = {}
    for item in [*item_ids, '__portfolio__']:
        steps = by_item[item]
        pooled = [x for values in steps.values() for x in values]
        fitted[item] = {}
        for step in range(1, horizon + 1):
            scores = steps.get(step, [])
            scope = 'same_horizon'
            if len(scores) < MIN_SCORES:
                scores, scope = pooled, 'pooled_horizons'
            n = len(scores)
            width = None
            if n >= MIN_SCORES:
                # Finite-sample corrected absolute-residual order statistic.
                rank = math.ceil((n + 1) * TARGET)
                if rank <= n:
                    # Exact index avoids floating quantile positions selecting
                    # the next rank (e.g. the 30th of 36 scores).
                    width = float(np.partition(np.abs(scores), rank - 1)[rank - 1])
            fitted[item][str(step)] = {'half_width': width, 'scores': n, 'scope': scope if width is not None else 'insufficient_history'}
    return {'target_pct': TARGET * 100, 'validated_horizon': horizon,
            'minimum_scores': MIN_SCORES, 'parameters': fitted,
            'complete_portfolio_dates': sorted(complete_dates)}


def bounds(model: dict, item: str, step: int, mean: float, multiplier: float = 1.0):
    parameter = model.get('parameters', {}).get(item, {}).get(str(step), {})
    width = parameter.get('half_width')
    if width is None:
        return None, None
    width *= multiplier
    return max(0.0, mean - width), mean + width


def check_ranges(model: dict, rows: list[dict], item_ids: list[str]) -> dict:
    """Score later actuals without changing any fitted range parameter."""
    checked = []
    by_date = defaultdict(list)
    seen = set()
    for row in rows:
        key = (row['item_id'], row['timestamp'])
        if key in seen:
            raise ValueError('Duplicate range-check item and period.')
        seen.add(key)
        by_date[row['timestamp']].append(row)
        checked.append(_check_row(model, row))
    portfolio = []
    skipped = 0
    expected = set(item_ids)
    for date, group in sorted(by_date.items()):
        if {r['item_id'] for r in group} != expected or len({r['step'] for r in group}) != 1:
            skipped += 1
            continue
        portfolio.append(_check_row(model, {'item_id': '__portfolio__', 'timestamp': date,
            'step': group[0]['step'], 'actual': sum(r['actual'] for r in group),
            'predicted': sum(r['predicted'] for r in group)}))
    return {'items': _summary(checked), 'portfolio': _summary(portfolio),
            'by_horizon': [{'step': step, **_summary([r for r in checked if r['step'] == step])}
                           for step in sorted({r['step'] for r in checked})],
            'by_item': {item: _summary([r for r in checked if r['item_id'] == item]) for item in item_ids},
            'skipped_incomplete_portfolio_periods': skipped,
            'rows': checked + portfolio}


def _check_row(model, row):
    low, high = bounds(model, row['item_id'], row['step'], row['predicted'])
    actual = row['actual']
    score = None if low is None else high - low + 2 / (1 - TARGET) * (max(0, low - actual) + max(0, actual - high))
    return {**row, 'lower': low, 'upper': high,
            'covered': None if low is None else bool(low <= actual <= high), 'interval_score': score}


def _summary(rows):
    available = [r for r in rows if r['covered'] is not None]
    n = len(available)
    return {'observations': len(rows), 'checked': n, 'unavailable': len(rows) - n,
            'inside': sum(r['covered'] for r in available),
            'coverage_pct': 100 * sum(r['covered'] for r in available) / n if n else None,
            'mean_width': float(np.mean([r['upper'] - r['lower'] for r in available])) if n else None,
            'mean_interval_score': float(np.mean([r['interval_score'] for r in available])) if n else None}

import copy
import json
import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import openpyxl
import pandas as pd

from app.uncertainty import range_parameters, bounds, check_ranges
from app.forecast_engine import ModelSpec, _fit_backtest, run_forecast


def rows(errors, item='A', scale=1):
    return [{'item_id': item, 'timestamp': f'2025-{i+1:02d}-01', 'step': i % 3 + 1,
             'actual': 1000 + error * scale, 'predicted': 1000.} for i, error in enumerate(errors)]


class RangeTests(unittest.TestCase):
    def test_order_statistic_and_own_item_scale(self):
        data = rows([1, 2, 3, 4, 5, 6]) + rows([1, 2, 3, 4, 5, 6], 'B', 100)
        model = range_parameters(data, ['A', 'B'], 3)
        self.assertEqual(model['parameters']['A']['1']['half_width'], 6)
        self.assertEqual(model['parameters']['B']['1']['half_width'], 600)
        self.assertEqual(model['parameters']['A']['1']['scope'], 'pooled_horizons')
        self.assertEqual(bounds(model, 'A', 1, 2), (0, 8))
        self.assertEqual(bounds(model, 'A', 1, 20, 2), (8, 32))

    def test_same_horizon_has_priority_when_supported(self):
        data = rows([1, 2, 3, 4, 5, 6])
        for r in data: r['step'] = 1
        model = range_parameters(data, ['A'], 2)
        self.assertEqual(model['parameters']['A']['1']['scope'], 'same_horizon')
        self.assertEqual(model['parameters']['A']['2']['scope'], 'pooled_horizons')

    def test_order_statistic_has_no_floating_rank_shift(self):
        for n in (5, 12, 36, 78, 136):
            data = [{'item_id': 'A', 'timestamp': str(i), 'step': 1,
                     'actual': 1000 + i, 'predicted': 1000.} for i in range(1, n + 1)]
            model = range_parameters(data, ['A'], 1)
            self.assertEqual(model['parameters']['A']['1']['half_width'], math.ceil((n+1)*.8))

    def test_sparse_or_untested_ranges_stay_unknown(self):
        model = range_parameters(rows([1, 2, 3, 4]), ['A'], 3)
        self.assertEqual(bounds(model, 'A', 1, 10), (None, None))
        full = range_parameters(rows([1, 2, 3, 4, 5, 6]), ['A'], 3)
        self.assertEqual(bounds(full, 'A', 4, 10), (None, None))
        self.assertEqual(bounds(full, 'missing', 1, 10), (None, None))

    def test_portfolio_preserves_joint_error_not_independence(self):
        errors = [1, 2, 3, 4, 5, 6]
        same = range_parameters(rows(errors) + rows(errors, 'B'), ['A', 'B'], 3)
        opposite = range_parameters(rows(errors) + rows([-x for x in errors], 'B'), ['A', 'B'], 3)
        self.assertEqual(same['parameters']['__portfolio__']['1']['half_width'], 12)
        self.assertEqual(opposite['parameters']['__portfolio__']['1']['half_width'], 0)

    def test_incomplete_totals_do_not_become_complete_evidence(self):
        data = rows([1, 2, 3, 4, 5, 6]) + rows([1, 2, 3, 4, 5, 6], 'B')[:3]
        model = range_parameters(data, ['A', 'B'], 3)
        self.assertEqual(len(model['complete_portfolio_dates']), 3)
        self.assertIsNone(model['parameters']['__portfolio__']['1']['half_width'])
        report = check_ranges(model, data, ['A', 'B'])
        self.assertEqual(report['skipped_incomplete_portfolio_periods'], 3)
        self.assertEqual(report['portfolio']['unavailable'], 3)

    def test_coverage_score_and_no_check_time_refitting(self):
        model = range_parameters(rows([1, 2, 3, 4, 5, 6]), ['A'], 3)
        before = copy.deepcopy(model)
        checked = check_ranges(model, rows([0, 6, 10]), ['A'])
        self.assertEqual(checked['items']['inside'], 2)
        self.assertAlmostEqual(checked['items']['coverage_pct'], 200/3)
        self.assertAlmostEqual(checked['rows'][-1]['interval_score'], 52)
        self.assertEqual(before, model)
        self.assertIsNone(check_ranges(model, [], ['A'])['items']['coverage_pct'])

    def test_duplicate_nonfinite_scores_rejected(self):
        data = rows([1, 2, 3, 4, 5, 6])
        with self.assertRaisesRegex(ValueError, 'Duplicate'): range_parameters(data + data[:1], ['A'], 3)
        data[0]['actual'] = math.nan
        with self.assertRaisesRegex(ValueError, 'finite'): range_parameters(data, ['A'], 3)

    def test_separate_windows_and_confirmation_cannot_change_ranges(self):
        h = pd.DataFrame({'item_id': 'A', 'timestamp': pd.date_range('2021-01-01', periods=60, freq='MS'),
                          'target': 100 + np.arange(60) + np.sin(np.arange(60))})
        with patch('app.forecast_engine._model_specs', return_value=[ModelSpec('Last observed', 'last')]):
            original = _fit_backtest(h, [], 6, 'monthly', 'deep', 'recommended')
            changed = h.copy(); changed.loc[54:, 'target'] *= 10
            after = _fit_backtest(changed, [], 6, 'monthly', 'deep', 'recommended')
        m = original[4]
        self.assertEqual(m['rolling_folds'], 5)
        self.assertTrue(m['range_fitting_separate'])
        self.assertFalse(set(m['selection_periods']) & set(m['range_fitting_periods']))
        self.assertFalse(set(m['confirmation_periods']) & set(m['range_fitting_periods']))
        self.assertEqual(original[7]['__range_model__'], after[7]['__range_model__'])
        self.assertEqual(original[3], after[3])
        self.assertNotEqual(m['range_check']['items']['coverage_pct'], after[4]['range_check']['items']['coverage_pct'])

    def test_calibration_cannot_change_selected_weights(self):
        h = pd.DataFrame({'item_id': 'A', 'timestamp': pd.date_range('2021-01-01', periods=60, freq='MS'), 'target': 100 + np.arange(60)})
        specs = [ModelSpec('Last observed', 'last'), ModelSpec('Recent average', 'average')]
        with patch('app.forecast_engine._model_specs', return_value=specs):
            before = _fit_backtest(h, [], 6, 'monthly', 'deep', 'recommended')
            h.loc[42:53, 'target'] *= 3
            after = _fit_backtest(h, [], 6, 'monthly', 'deep', 'recommended')
        self.assertEqual(before[3], after[3])
        self.assertNotEqual(before[7]['__range_model__'], after[7]['__range_model__'])

    def test_short_history_and_export_nulls_are_honest(self):
        history = pd.DataFrame({'item_id': 'A', 'timestamp': pd.date_range('2026-01-01', periods=7, freq='MS'), 'target': np.arange(7)+10.})
        future = pd.DataFrame({'item_id': 'A', 'timestamp': pd.date_range('2026-08-01', periods=3, freq='MS')})
        with TemporaryDirectory() as folder, patch('app.forecast_engine._model_specs', return_value=[ModelSpec('Last observed', 'last')]):
            result = run_forecast(history=history, future_covariates=future, known_driver_cols=[], horizon=3,
                frequency='monthly', profile='deep', runs_dir=Path(folder))
            self.assertFalse(result['metrics']['range_fitting_separate'])
            self.assertIsNone(result['metrics']['interval_coverage_pct'])
            self.assertTrue(all(r['p10'] is None and r['p90'] is None for r in result['forecast_rows']))
            json.dumps(result, allow_nan=False)
            book = openpyxl.load_workbook(Path(folder)/result['run_id']/'forecast_package.xlsx', data_only=True)
            self.assertTrue({'Range check', 'Range fitting', 'Range parameters', 'Range policy'} <= set(book.sheetnames))
            book.close()


if __name__ == '__main__': unittest.main()

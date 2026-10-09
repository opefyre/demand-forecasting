from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.data import actual_history, fit_history_window, prepare_history, read_table, add_calendar_covariates, build_future_covariates
from app.forecast_engine import ModelSpec, _fit_backtest, _stat_forecast


class ClientReadinessTests(unittest.TestCase):
    def test_plan_only_rows_never_become_training_actuals(self):
        for kind in ['forecast', 'plan', 'budget', 'unconfirmed']:
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, 'not labelled actuals'):
                actual_history(pd.DataFrame({'record_type': [kind], 'demand': [100]}))

    def test_unit_filter_does_not_convert_or_mix_quantities(self):
        raw = pd.DataFrame({'record_type': ['actual'] * 3, 'unit': ['KBlank', 'BOB', '-'], 'demand': [10, 20, 30]})
        with self.assertRaisesRegex(ValueError, 'mixes quantity units'):
            actual_history(raw)
        result, _ = actual_history(raw, unit_filter='KBlank')
        self.assertEqual(result.demand.tolist(), [10])
        with self.assertRaisesRegex(ValueError, 'no quantity unit'):
            actual_history(raw, unit_filter='-')

    def test_unlabelled_wide_workbook_is_not_assumed_actual(self):
        # Same date repeated in a second block = a different measure, not more demand.
        headers = ['Article Number', 'Customer Name', 'UOM'] + list(pd.date_range('2026-01-01', periods=3, freq='MS')) * 2
        raw = pd.DataFrame([headers, ['A', 'C', 'KBlank', 10, 20, 30, 1000, 2000, 3000]])
        buffer = BytesIO()
        raw.to_excel(buffer, index=False, header=False)
        frame = read_table('wide.xlsx', buffer.getvalue())
        self.assertEqual(frame.demand.tolist(), [10, 20, 30])
        self.assertEqual(frame.source_cell.tolist(), ['D2', 'E2', 'F2'])
        self.assertEqual(set(frame.record_type), {'unconfirmed'})

    def test_future_values_cannot_change_training_window_treatment(self):
        raw = pd.DataFrame({'date': pd.date_range('2024-01-01', periods=16, freq='MS'), 'qty': [10, 11, 12, 11, 12, 10, 13, 100, 12, 13, 12, 10, 11, 12, 13, 10], 'price': np.arange(16, dtype=float)})
        raw = raw.drop(index=[6, 7])
        raw.loc[raw.index == 5, 'price'] = np.nan
        changed = raw.copy()
        changed.loc[changed.date >= '2024-09-01', ['qty', 'price']] = 100000
        def training(frame):
            clean, _ = prepare_history(frame, date_col='date', target_col='qty', item_col=None, driver_cols=['price'], frequency='monthly', outlier_strategy='winsorize')
            return fit_history_window(clean[clean.timestamp < '2024-09-01'])
        left, right = training(raw), training(changed)
        np.testing.assert_allclose(left.target, right.target)
        np.testing.assert_allclose(left.price, right.price)

    def test_confirming_actuals_do_not_choose_the_model(self):
        dates = pd.date_range('2020-01-01', periods=36, freq='MS')
        history = pd.DataFrame({'item_id': 'A', 'timestamp': dates, 'target': np.arange(36) + 10.})
        specs = [ModelSpec('Last observed', 'last'), ModelSpec('Recent average', 'average')]
        changed = history.copy()
        changed.loc[changed.timestamp >= dates[-6], 'target'] *= 10
        with patch('app.forecast_engine._model_specs', return_value=specs):
            original = _fit_backtest(history, [], 6, 'monthly', 'deep', 'recommended')
            later = _fit_backtest(changed, [], 6, 'monthly', 'deep', 'recommended')
        self.assertEqual(original[3], later[3])
        self.assertNotEqual(original[4]['wape_pct'], later[4]['wape_pct'])
        self.assertNotEqual(original[4]['evaluation_signature'], later[4]['evaluation_signature'])
        self.assertTrue(original[4]['independent_accuracy_verified'])
        self.assertFalse(set(original[4]['selection_periods']) & set(original[4]['confirmation_periods']))

    def test_actual_outlier_is_scored_without_clipping(self):
        raw = pd.DataFrame({'date': pd.date_range('2024-01-01', periods=24, freq='MS'), 'qty': [10, 11, 12] * 7 + [400, 12, 11]})
        clean, _ = prepare_history(raw, date_col='date', target_col='qty', item_col=None, driver_cols=[], frequency='monthly', outlier_strategy='winsorize')
        with patch('app.forecast_engine._model_specs', return_value=[ModelSpec('Last observed', 'last')]):
            result = _fit_backtest(clean, [], 3, 'monthly', 'deep', 'recommended')
        self.assertGreater(result[4]['wape_pct'], 80)

    def test_seasonal_method_requires_a_cycle(self):
        with self.assertRaisesRegex(ValueError, '12 training periods'):
            _stat_forecast(ModelSpec('Seasonal naive', 'naive'), [10.] * 7, 6, 12)

    def test_short_history_does_not_invent_unseen_accuracy(self):
        history = pd.DataFrame({'item_id': 'A', 'timestamp': pd.date_range('2026-01-01', periods=7, freq='MS'), 'target': [10.] * 7})
        with patch('app.forecast_engine._model_specs', return_value=[ModelSpec('Last observed', 'last'), ModelSpec('Seasonal naive', 'naive')]):
            result = _fit_backtest(history, [], 6, 'monthly', 'deep', 'recommended')
        self.assertEqual(result[4]['evidence_level'], 'limited')
        self.assertFalse(result[4]['independent_accuracy_verified'])
        seasonal = next(row for row in result[5] if row['model'] == 'Seasonal naive')
        self.assertEqual(seasonal['status'], 'unavailable')
        self.assertIsNone(seasonal['wape_pct'])

    def test_iran_friday_and_nowruz_calendar(self):
        dates = pd.DataFrame({'timestamp': pd.to_datetime(['2026-03-20', '2026-03-21', '2026-03-22'])})
        result = add_calendar_covariates(dates, frequency='daily', country='IR', weekend_days=(4,))
        self.assertEqual(result.calendar_is_weekend.tolist(), [1., 0., 0.])
        self.assertEqual(result.calendar_nowruz_days.tolist(), [0., 1., 1.])
        self.assertEqual(result.calendar_working_days.tolist(), [0., 0., 0.])

    def test_future_calendar_keeps_site_closures(self):
        raw = pd.DataFrame({'date': pd.date_range('2025-01-01', periods=6, freq='MS'), 'qty': [10.] * 6})
        history, _ = prepare_history(raw, date_col='date', target_col='qty', item_col=None, driver_cols=[], frequency='monthly', calendar_country='IR', weekend_days=(4,), shutdown_dates=('2025-07-01',))
        future, _ = build_future_covariates(history, None, future_date_col=None, future_item_col=None, known_driver_cols=[], frequency='monthly', horizon=1)
        self.assertEqual(future.calendar_shutdown_days.iloc[0], 1.)
        self.assertEqual(future.attrs['calendar_profile']['country'], 'IR')

    def test_explicit_exclusions_preserve_original_values(self):
        raw = pd.DataFrame({'record_type': ['actual', 'actual'], 'series_id': ['A', 'B'], 'demand': [-5, 10]})
        result, warnings = actual_history(raw, excluded_items=['A'])
        self.assertEqual(result.series_id.tolist(), ['B'])
        self.assertEqual(raw.demand.tolist(), [-5, 10])
        self.assertTrue(any('1 item' in message for message in warnings))


if __name__ == '__main__':
    unittest.main()

"""Preparation reuse must not change inputs, predictions or model evidence."""
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge, ElasticNet

from app import forecast_engine as engine


def uncached_training(grp, known_driver_cols, lags, max_horizon):
    grp = grp.sort_values('timestamp').reset_index(drop=True)
    values = grp.target.astype(float).tolist()
    rows, targets = [], []
    for origin in range(max(max(lags, default=1), 3), len(grp)):
        for step in range(1, min(max_horizon, len(grp) - origin) + 1):
            index = origin + step - 1
            rows.append(engine._feature_row(target_history=values[:origin], driver_row=grp.iloc[index],
                time_idx=index, lags=lags, known_driver_cols=known_driver_cols,
                item_id=str(grp.iloc[0].item_id), forecast_step=step))
            targets.append(values[index])
    return pd.DataFrame(rows), pd.Series(targets, dtype=float)


class FeaturePreparationTests(unittest.TestCase):
    def history(self):
        return pd.DataFrame({'item_id': 'A', 'timestamp': pd.date_range('2022-01-01', periods=36, freq='MS'),
            'target': [0. if i % 7 == 0 else 40. + i * .3 for i in range(36)],
            'fx': np.arange(36) * 100. + 400000., 'calendar_month': np.arange(36) % 12 + 1})

    def test_history_values_keep_the_original_formulas(self):
        for values in ([], [0.], [0.] * 15, [1e-10, 1., 2., 0., 9., 12., 4.] * 5):
            actual = engine._history_features(values, [1, 3, 12])
            for lag in [1, 3, 12]:
                expected = float(values[-lag]) if len(values) >= lag else np.nan
                np.testing.assert_equal(actual[f'lag_{lag}'], expected)
            for window in [2, 3, 6, 12]:
                tail = values[-window:]
                np.testing.assert_equal(actual[f'rolling_mean_{window}'], float(np.mean(tail)) if tail else np.nan)
                np.testing.assert_equal(actual[f'rolling_median_{window}'], float(np.median(tail)) if tail else np.nan)
                np.testing.assert_equal(actual[f'nonzero_rate_{window}'], float(np.mean(np.asarray(tail) > 1e-9)) if tail else 0.)
            for span in [3, 6, 12]:
                tail = np.asarray(values[-max(span * 3, span):], dtype=float)
                expected = float(tail[0]) if len(tail) else np.nan
                for value in tail[1:]:
                    expected = 2. / (span + 1.) * float(value) + (1. - 2. / (span + 1.)) * expected
                np.testing.assert_equal(actual[f'ewm_{span}'], expected)
            for window in [3, 6]:
                tail = values[-window:]
                np.testing.assert_equal(actual[f'rolling_std_{window}'], float(np.std(tail, ddof=0)) if len(tail) >= 2 else 0.)
            recent, prior = (float(np.mean(values[-2:])), float(np.mean(values[-4:-2]))) if len(values) >= 4 else (0., 0.)
            np.testing.assert_equal(actual['recent_momentum'], recent / prior - 1. if abs(prior) > 1e-9 else 0.)
            zero_run = 0
            for value in reversed(values):
                if float(value) > 1e-9:
                    break
                zero_run += 1
            self.assertEqual(actual['zero_run_length'], float(zero_run))
            recent, annual = (float(np.mean(values[-3:])), float(np.mean(values[-12:]))) if len(values) >= 12 else (1., 1.)
            np.testing.assert_equal(actual['seasonal_level_ratio'], recent / annual if abs(annual) > 1e-9 else 1.)

    def test_training_frames_equal_uncached_rows_and_use_one_origin_preparation(self):
        data = self.history()
        for horizon in [1, 6, 10]:
            expected = uncached_training(data, ['fx'], [1, 3, 12], horizon)
            with patch.object(engine, '_history_features', wraps=engine._history_features) as prepare:
                actual = engine._direct_supervised_frame(data, ['fx'], [1, 3, 12], horizon)
                self.assertEqual(prepare.call_count, 24)
            pd.testing.assert_frame_equal(actual[0], expected[0], check_exact=True)
            pd.testing.assert_series_equal(actual[1], expected[1], check_exact=True)
            self.assertNotIn('timestamp', actual[0])

    def test_future_driver_overrides_do_not_change_shared_history_or_other_horizons(self):
        shared = engine._history_features([10., 20., 30.], [1, 3])
        original = shared.copy()
        first = engine._feature_row(target_history=[], driver_row={'lag_1': 999., 'calendar_month': 8},
            time_idx=3, lags=[1, 3], known_driver_cols=['lag_1'], item_id='A', history_features=shared)
        second = engine._feature_row(target_history=[], driver_row={'calendar_month': 9},
            time_idx=4, lags=[1, 3], known_driver_cols=['lag_1'], item_id='A', forecast_step=2, history_features=shared)
        self.assertEqual(first['lag_1'], 999.)
        self.assertEqual(second['lag_1'], 30.)
        self.assertEqual(shared, original)
        self.assertEqual(second['forecast_step'], 2.)
        self.assertEqual(second['calendar_month'], 9)

    def test_direct_predictions_are_exact_and_empty_future_does_no_work(self):
        data = self.history()
        X, y = uncached_training(data, ['fx'], [1, 3, 12], 6)
        pipe = engine._fit_pipeline(engine._make_pipeline(Ridge(alpha=1.), X), X, y)
        future = data.tail(6).copy()
        args = dict(target_history=data.target.tolist(), future_rows=future, lags=[1, 3, 12],
            known_driver_cols=['fx'], start_time_idx=len(data), item_id='A')
        rows = [engine._feature_row(target_history=args['target_history'], driver_row=row,
            time_idx=len(data) + step - 1, lags=args['lags'], known_driver_cols=['fx'], item_id='A', forecast_step=step)
            for step, (_, row) in enumerate(future.iterrows(), start=1)]
        expected = [max(0., float(value)) for value in pipe.predict(pd.DataFrame(rows))]
        with patch.object(engine, '_history_features', wraps=engine._history_features) as prepare:
            self.assertEqual(engine._direct_predict(pipe, **args), expected)
            self.assertEqual(prepare.call_count, 1)
            self.assertEqual(engine._direct_predict(pipe, **{**args, 'future_rows': future.iloc[:0]}), [])
            self.assertEqual(prepare.call_count, 1)

    def test_full_fit_reuses_each_factor_frame_without_removing_models(self):
        data = self.history()
        future = data.tail(6).copy()
        specs = [engine.ModelSpec('All factors', 'ml', Ridge()),
            engine.ModelSpec('History ridge', 'ml', Ridge(), ()),
            engine.ModelSpec('History elastic', 'ml', ElasticNet(max_iter=10000), ()),
            engine.ModelSpec('Last observed', 'last')]
        with patch.object(engine, '_global_direct_supervised_frame', wraps=engine._global_direct_supervised_frame) as frame:
            actual, fitted, failures = engine._fit_full_models_and_predict(data, future, ['fx'], 'monthly', specs)
            self.assertEqual(frame.call_count, 2)
        self.assertFalse(failures)
        self.assertEqual(set(actual), {spec.name for spec in specs})
        self.assertTrue(all(len(values['A']) == 6 for values in actual.values()))
        self.assertEqual(len(fitted), 3)
        with patch.object(engine, '_direct_supervised_frame', side_effect=uncached_training):
            reference, reference_fitted, reference_failures = engine._fit_full_models_and_predict(data, future, ['fx'], 'monthly', specs)
        self.assertEqual(actual, reference)
        self.assertEqual(failures, reference_failures)
        self.assertEqual(engine._driver_importance(fitted, {'All factors': 1.}, ['fx']),
            engine._driver_importance(reference_fitted, {'All factors': 1.}, ['fx']))


if __name__ == '__main__':
    unittest.main()

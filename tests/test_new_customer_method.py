import unittest
from unittest.mock import patch

import pandas as pd

from app.forecast_engine import ModelSpec, _fit_backtest


class NewCustomerMethodTests(unittest.TestCase):
    def history(self):
        dates = pd.date_range('2022-10-01', periods=48, freq='MS')
        return pd.DataFrame([dict(item_id=item, timestamp=day, target=10 + i * .1)
            for item, start in [('Established', 0), ('New', 30)]
            for i, day in enumerate(dates) if i >= start])

    def run_case(self, data, method):
        with patch('app.forecast_engine._model_specs', return_value=[ModelSpec('Last observed', 'last')]):
            return _fit_backtest(data, [], 12, 'monthly', 'fast', method)

    def test_explicit_method_without_selection_history_is_not_blocked(self):
        result = self.run_case(self.history(), 'model:Last observed')
        self.assertEqual(result[3]['New'], {'Last observed': 1.0})
        self.assertEqual(result[4]['untested_selection_series'], ['New'])
        self.assertFalse(result[-1]['New']['method_selection_tested'])
        self.assertTrue(result[-1]['Established']['method_selection_tested'])

    def test_confirmation_never_selects_a_new_customer_method(self):
        original = self.history()
        changed = original.copy()
        changed.loc[changed.timestamp >= '2025-10-01', 'target'] *= 100
        first = self.run_case(original, 'model:Last observed')
        second = self.run_case(changed, 'model:Last observed')
        self.assertEqual(first[3], second[3])
        self.assertNotEqual(first[4]['wape_pct'], second[4]['wape_pct'])

    def test_unknown_method_is_still_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            self.run_case(self.history(), 'model:Invented method')


if __name__ == '__main__':
    unittest.main()

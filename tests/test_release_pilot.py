"""Bounded synthetic samples and maximum supported order-book accounting."""
from datetime import timedelta
from decimal import Decimal
import json
import unittest

from scripts.verify_release_pilot import generate, read_export
from app.sales_conventions import local_today, period_start, month_label
from app.sales_demand import demand_outlook, export_demand


class PilotTests(unittest.TestCase):
    def test_reproducible_history_and_independent_weighted_baseline(self):
        history, expected = generate(8, 3, 60, 'gregorian')
        second, expected_second = generate(8, 3, 60, 'gregorian')
        self.assertTrue(history.equals(second)); self.assertEqual(expected, expected_second)
        self.assertEqual(len(history), 1440); self.assertEqual(history.item.nunique(), 24)
        self.assertTrue(history.qty.ge(0).all()); self.assertTrue(history.qty.eq(0).any())
        for key, group in history.groupby('item'):
            last = group.qty.tolist()[-3:]
            value = sum(Decimal(str(v)) * w for v, w in zip(last, (1,2,3))) / 6
            self.assertAlmostEqual(expected[key], float(value))

    def test_persian_periods_are_true_month_starts_not_relabelled_gregorian(self):
        history, _ = generate(2, 2, 36, 'jalali')
        self.assertEqual(history.date.nunique(), 36)
        for day in history.date.unique():
            self.assertEqual(str(period_start(day, 'jalali').date()), day)
        labels = [month_label(day, 'jalali') for day in history.date.unique()]
        self.assertEqual(len(set(labels)), 36)

    def test_ten_thousand_relationships_and_fifty_thousand_order_lines(self):
        # Test the existing validation boundary, not an inferred SaaS capacity.
        today = local_today(); period = str(period_start(today).date())
        run = dict(run_id='volume',unit='tonnes',source_classification='synthetic_sample',
            run_settings={'frequency':'monthly'},metadata={},series={})
        customers, orders = [], []
        for index in range(10000):
            name = f'Demo {index:05d}'
            customers.append(dict(customer=name,sku='0001',unit='tonnes',series_id=name))
            run['metadata'][name] = dict(customer=name,sku='0001')
            run['series'][name] = {'forecast':[{'timestamp':period,'mean':40}]}
            for line in range(5):
                orders.append(dict(reference=f'{index}-{line}',customer=name,sku='0001',unit='tonnes',
                    due_date=period,ordered=10,fulfilled=0,cancelled=0,status='confirmed'))
        inputs = dict(name='Maximum synthetic book',run_id='volume',as_of=str(today),
            valid_until=str(today+timedelta(days=7)),classification='synthetic_sample',
            order_feed='complete_snapshot',customers=customers,orders=orders,commitments=[],
            reviewed=True,note='Artificial quantity and matching boundary check.')
        result = demand_outlook(inputs,run)
        self.assertTrue(result['can_export']); self.assertEqual(len(result['rows']),10000)
        self.assertTrue(all(row['remaining']==0 and row['still_to_serve']==50 for row in result['rows']))
        content, _ = export_demand(result,'combined_demand','json')
        output = json.loads(content)
        self.assertEqual(sum(row['quantity'] for row in output),500000)
        inputs['orders'].append({**orders[0],'reference':'too-many'})
        with self.assertRaises(ValueError): demand_outlook(inputs,run)

    def test_excel_csv_and_json_readback(self):
        # Distinct reader paths matter: agreement between shared helpers alone
        # cannot verify that the exported workbook contains the intended values.
        from tests.test_sales_demand import fixture
        run, inputs = fixture(); result = demand_outlook(inputs,run)
        for kind in ('xlsx','csv','json'):
            rows = read_export(export_demand(result,'combined_demand',kind)[0],kind)
            self.assertEqual(len(rows),3)
            self.assertEqual(sum(float(row['quantity']) for row in rows),23)


if __name__ == '__main__': unittest.main()

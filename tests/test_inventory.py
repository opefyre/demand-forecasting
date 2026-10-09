from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import app.main as main
from app.datasets import DatasetStore
from app.inventory import InventoryStore, raw_table, review_inventory, project_inventory
from app.planning import PlanStore


CSV = b'SKU,Quantity,Unit,Status,Pallet,Order\n001,20,pieces,OK,032,100\n001,5,pieces,HOLD,033,100\n002,12,pieces,?,034,101\n003,8,boxes,OK,035,101\n'
CONFIG = {'mapping': {'sku': 'A', 'quantity': 'B', 'unit': 'C', 'quality': 'D', 'record_key': 'E', 'record_key_2': 'F'},
          'quality_mode': 'column', 'quality_map': {'OK': 'available', 'HOLD': 'hold'},
          'as_of': '2026-08-31', 'reviewed': True, 'classification': 'synthetic_sample'}


class InventoryTests(unittest.TestCase):
    def test_excel_export_without_optional_dimensions(self):
        from io import BytesIO
        from zipfile import ZipFile, ZIP_DEFLATED
        import re
        original = (Path(__file__).resolve().parents[1] / 'sample_data/iran_operations_master.xlsx').read_bytes()
        output = BytesIO()
        with ZipFile(BytesIO(original)) as source, ZipFile(output, 'w', ZIP_DEFLATED) as target:
            for entry in source.infolist():
                content = source.read(entry.filename)
                if entry.filename.startswith('xl/worksheets/'):
                    content = re.sub(rb'<dimension\b[^>]*/>', b'', content)
                target.writestr(entry, content)
        for preview in (True, False):
            expected = raw_table('source.xlsx', original, 'BOM', preview=preview)
            actual = raw_table('source.xlsx', output.getvalue(), 'BOM', preview=preview)
            self.assertEqual(actual, expected)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sources = DatasetStore(self.root / 'inputs')
        self.store = InventoryStore(self.root / 'stock.sqlite3', self.sources)
        source = self.sources.upload('stock.csv', CSV, 'inventory')
        self.config = {**deepcopy(CONFIG), 'source_id': source['id']}
        self.run = {'run_id': 'run', 'unit': 'pieces', 'source_classification': 'synthetic_sample',
                    'metadata': {'customer-a': {'sku': '001'}, 'customer-b': {'sku': '001'}},
                    'series': {item: {'forecast': [{'timestamp': '2026-09-01', 'mean': qty}, {'timestamp': '2026-10-01', 'mean': qty}]}
                               for item, qty in [('customer-a', 7), ('customer-b', 5), ('002', 3), ('003', 4), ('004', 1), ('__all__', 20)]}}

    def tearDown(self):
        self.store.engine.dispose()
        self.tmp.cleanup()

    def test_preserves_identifiers_units_and_source_cells(self):
        review = self.store.inspect(self.config)
        self.assertEqual(review['issue_count'], 0)
        self.assertEqual(review['rows'][0]['sku'], '001')
        self.assertEqual(review['rows'][0]['record_keys'], ['032', '100'])
        self.assertEqual(review['rows'][0]['quantity_cell'], 'B2')
        self.assertEqual(review['totals_by_unit'], {'pieces': 37, 'boxes': 8})
        self.assertEqual(review['unknown_quality_rows'], 1)
        self.assertEqual(len(review['source']['sha256']), 64)

    def test_positional_headers_and_missing_quantity(self):
        table = raw_table('stock.csv', b'SKU,Quantity,Quantity,Unit\n001,,9,pieces\n')
        config = {**CONFIG, 'mapping': {'sku': 'A', 'quantity': 'B', 'unit': 'D'}, 'quality_mode': 'unknown'}
        self.assertEqual([c['id'] for c in table['columns']], ['A', 'B', 'C', 'D'])
        self.assertEqual(review_inventory(table, config)['issues'][0]['cell'], 'B2')
        config['mapping']['quantity'] = 'C'
        self.assertEqual(review_inventory(table, config)['rows'][0]['quantity'], 9)

    def test_bad_quantities_are_not_zero(self):
        for value in ('', '-1', 'NaN', 'inf', '#VALUE!'):
            table = raw_table('stock.csv', f'SKU,Quantity,Unit\n001,{value},pieces\n'.encode())
            review = review_inventory(table, {**CONFIG, 'mapping': {'sku': 'A', 'quantity': 'B', 'unit': 'C'}, 'quality_mode': 'unknown'})
            self.assertEqual(review['issue_count'], 1, value)
            self.assertEqual(review['row_count'], 0)

    def test_date_and_unit_must_be_confirmed(self):
        for change in ({'as_of': ''}, {'as_of': '2026-02-31'}, {'mapping': {'sku': 'A', 'quantity': 'B'}, 'fixed_unit': ''}):
            with self.assertRaises(ValueError):
                self.store.inspect({**self.config, **change})
        with self.assertRaises(ValueError):
            self.store.save({**self.config, 'reviewed': False})

    def test_inventory_cannot_train_a_demand_forecast(self):
        with self.assertRaisesRegex(ValueError, 'wrong role'):
            self.sources.inspect({'history': self.config['source_id']}, {})
        with self.assertRaisesRegex(ValueError, 'separate operational input'):
            self.sources.inspect({'history': self.config['source_id'], 'inventory': self.config['source_id']}, {})

    def test_duplicates_require_keys_or_acknowledgement(self):
        source = self.sources.upload('duplicates.csv', b'SKU,Quantity,Unit,Key\n001,5,pieces,032\n001,5,pieces,032\n', 'inventory')
        config = {**self.config, 'source_id': source['id'], 'quality_mode': 'available', 'mapping': {'sku': 'A', 'quantity': 'B', 'unit': 'C', 'record_key': 'D'}}
        self.assertEqual(self.store.inspect(config)['issue_count'], 1)
        config['mapping'].pop('record_key')
        with self.assertRaisesRegex(ValueError, 'distinct physical stock'):
            self.store.save(config)
        saved = self.store.save({**config, 'distinct_records_confirmed': True})
        self.assertEqual(saved['totals_by_unit']['pieces'], 10)

    def test_persisted_snapshot_is_immutable_and_versioned(self):
        first = self.store.save(self.config)
        second = self.store.save({**self.config, 'as_of': '2026-09-30'})
        restored = InventoryStore(self.root / 'stock.sqlite3', self.sources)
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(restored.get(first['id']), first)
        self.assertNotIn('rows', restored.list()[0])
        self.assertEqual(first['classification'], 'synthetic_sample')
        restored.engine.dispose()

    def test_projection_aggregates_customers_excludes_holds_and_propagates_unknowns(self):
        result = project_inventory(self.run, self.store.save(self.config))
        rows = {(r['sku'], r['period']): r for r in result['rows']}
        september = rows['001', '2026-09-01']
        self.assertEqual((september['opening'], september['demand'], september['closing'], september['held_stock']), (20, 12, 8, 5))
        self.assertEqual(rows['001', '2026-10-01']['closing'], -4)
        self.assertEqual(rows['001', '2026-10-01']['shortfall'], 4)
        for sku, reason in [('002', 'Stock status not confirmed'), ('003', 'Unit conversion needed'), ('004', 'Stock not supplied')]:
            self.assertIsNone(rows[sku, '2026-09-01']['closing'])
            self.assertEqual(rows[sku, '2026-09-01']['status'], reason)
        self.assertEqual(len(result['rows']), 8)

    def test_no_partial_period_guessing_or_invalid_forecast(self):
        snapshot = self.store.save(self.config)
        with self.assertRaisesRegex(ValueError, 'Partial-period'):
            project_inventory(self.run, {**snapshot, 'as_of': '2026-09-15'})
        self.run['series']['customer-a']['forecast'][0]['mean'] = float('nan')
        with self.assertRaisesRegex(ValueError, 'invalid quantity'):
            project_inventory(self.run, snapshot)

    def test_bad_files_are_actionable_errors(self):
        for name, data in [('bad.xlsx', b'not excel'), ('blank.csv', b''), ('bad.csv', b'\xff')]:
            with self.assertRaisesRegex(ValueError, 'could not be read'):
                raw_table(name, data)

    def test_blank_header_preview_allows_selecting_a_different_row(self):
        content = b',,\nSKU,Quantity,Unit\n001,5,pieces\n'
        self.assertEqual(raw_table('stock.csv', content, preview=True)['columns'], [])
        self.assertEqual(raw_table('stock.csv', content, header_row=2)['rows'][0]['source_row'], 3)
        with self.assertRaisesRegex(ValueError, 'heading row is empty'):
            raw_table('stock.csv', content)

    def test_api_workflow_and_approved_adjustments(self):
        plans = PlanStore(self.root / 'plans.json')
        plan = plans.create(name='Test', run_id='run', site_id='site', owner='Planner', settings={}, metrics={'evidence_level': 'strong'})
        plans.add_override(plan['id'], item_id='customer-a', period='2026-09-01', value=10, reason='Confirmed demand', actor='Planner')
        with patch.object(main, 'DATASET_STORE', self.sources), patch.object(main, 'INVENTORY_STORE', self.store), patch.object(main, 'PLAN_STORE', plans), patch.object(main, '_load_run', return_value=self.run), TestClient(main.app) as client:
            self.assertEqual(client.post('/api/inventory/validate', json={**self.config, 'as_of': ''}).status_code, 400)
            values = client.post(f'/api/inventory/sources/{self.config["source_id"]}/values', json={'column': 'D'})
            self.assertEqual(values.json()['values'], ['?', 'HOLD', 'OK'])
            saved = client.post('/api/inventory', json=self.config)
            self.assertEqual(saved.status_code, 200, saved.text)
            key = saved.json()['id']
            url = f'/api/inventory/{key}/projection?run_id=run'
            self.assertEqual(client.get(url).json()['rows'][0]['demand'], 12)
            self.assertEqual(client.get(url + f'&plan_id={plan["id"]}').status_code, 400)
            plans.transition(plan['id'], status='review', actor='Planner')
            plans.transition(plan['id'], status='approved', actor='Reviewer')
            result = client.get(url + f'&plan_id={plan["id"]}')
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()['rows'][0]['demand'], 15)
            self.assertEqual(self.run['series']['customer-a']['forecast'][0]['mean'], 7)


if __name__ == '__main__':
    unittest.main()

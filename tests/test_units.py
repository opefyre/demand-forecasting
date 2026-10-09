from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main as main
from app.units import UnitStore, convert_stock, standard_factor, validate_rules
from app.inventory import project_inventory


RULE = {'sku': '001', 'from_unit': 'boxes', 'to_unit': 'pieces', 'factor': 12,
        'valid_from': '2026-01-01', 'valid_to': '', 'source': 'Synthetic packing specification'}
CONFIG = {'name': 'Sample packing', 'reviewed': True, 'reviewer': 'Tester',
          'classification': 'synthetic_sample', 'rules': [RULE]}


class UnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = UnitStore(Path(self.tmp.name) / 'units.sqlite3')
        self.row = {'sku': '001', 'unit': 'boxes', 'quantity': 5, 'source_row': 2, 'quality': 'available'}
        self.run = {'run_id': 'sample', 'unit': 'pieces', 'source_classification': 'synthetic_sample',
                    'series': {'001': {'forecast': [{'timestamp': '2026-09-01', 'mean': 17}]}}}
        self.stock = {'id': 'stock', 'as_of': '2026-08-31', 'classification': 'synthetic_sample',
                      'source': {'name': 'sample.csv'}, 'rows': [self.row]}

    def tearDown(self):
        self.store.engine.dispose()
        self.tmp.cleanup()

    def test_standard_units_use_physical_dimensions_only(self):
        self.assertEqual(standard_factor('kg', 'tonnes'), .001)
        self.assertEqual(standard_factor('L', 'ml'), 1000)
        self.assertIsNone(standard_factor('kg', 'L'))
        for source, target in [('ton', 'kg'), ('BOB', 'بوبین'), ('KBlank', 'KBLANK'), ('IRR', 'USD')]:
            self.assertIsNone(standard_factor(source, target))

    def test_custom_direction_dates_and_product_are_exact(self):
        version = self.store.save(CONFIG)
        converted, evidence = convert_stock(self.row, 'pieces', '2026-08-31', version)
        self.assertEqual(converted['quantity'], 60)
        self.assertEqual(evidence['source_quantity'], 5)
        self.assertEqual(evidence['version_id'], version['id'])
        self.assertEqual(self.row['quantity'], 5)
        for row, target, day in [(self.row, 'pieces', '2025-12-31'), ({**self.row, 'sku': '002'}, 'pieces', '2026-08-31'), ({**self.row, 'unit': 'pieces'}, 'boxes', '2026-08-31')]:
            with self.assertRaises(ValueError):
                convert_stock(row, target, day, version)

    def test_overlapping_definitions_and_invalid_inputs_rejected(self):
        for field, value in [('factor', 0), ('factor', -1), ('factor', 'NaN'), ('factor', True), ('valid_from', ''), ('valid_to', '2025-01-01'), ('source', '')]:
            with self.assertRaises(ValueError, msg=field):
                validate_rules({**CONFIG, 'rules': [{**RULE, field: value}]})
        with self.assertRaisesRegex(ValueError, 'overlap'):
            validate_rules({**CONFIG, 'rules': [RULE, RULE]})
        with self.assertRaisesRegex(ValueError, 'standard physical'):
            validate_rules({**CONFIG, 'rules': [{**RULE, 'from_unit': 'kg', 'to_unit': 'tonnes'}]})
        with self.assertRaises(ValueError):
            self.store.save({**CONFIG, 'reviewed': False})

    def test_inclusive_date_boundaries_and_new_period(self):
        version = self.store.save({**CONFIG, 'rules': [{**RULE, 'valid_to': '2026-08-31'}, {**RULE, 'valid_from': '2026-09-01', 'factor': 10}]})
        self.assertEqual(convert_stock(self.row, 'pieces', '2026-08-31', version)[0]['quantity'], 60)
        self.assertEqual(convert_stock(self.row, 'pieces', '2026-09-01', version)[0]['quantity'], 50)

    def test_revisions_never_change_old_projection_and_sample_gate(self):
        first = self.store.save(CONFIG)
        second = self.store.save({**CONFIG, 'parent_id': first['id'], 'rules': [{**RULE, 'factor': 10}]})
        self.assertEqual(self.store.get(first['id']), first)
        self.assertEqual(project_inventory(self.run, self.stock, first)['rows'][0]['closing'], 43)
        self.assertEqual(project_inventory(self.run, self.stock, second)['rows'][0]['closing'], 33)
        self.assertIsNone(project_inventory(self.run, self.stock)['rows'][0]['closing'])
        with self.assertRaisesRegex(ValueError, 'all be real'):
            project_inventory(self.run, {**self.stock, 'classification': 'user_provided'}, first)

    def test_mixed_mass_units_held_and_unknown_stock(self):
        stock = deepcopy(self.stock)
        stock['rows'] = [{**self.row, 'unit': 'kg', 'quantity': 1500}, {**self.row, 'unit': 'tonnes', 'quantity': 2}, {**self.row, 'unit': 'kg', 'quantity': 200, 'quality': 'hold'}]
        result = project_inventory({**self.run, 'unit': 'tonnes'}, stock)
        self.assertEqual(result['rows'][0]['opening'], 3.5)
        self.assertEqual(result['rows'][0]['held_stock'], .2)
        self.assertEqual(result['rows'][0]['closing'], -13.5)
        stock['rows'][0]['quality'] = 'unknown'
        self.assertIsNone(project_inventory({**self.run, 'unit': 'tonnes'}, stock)['rows'][0]['opening'])

    def test_api_explicit_version_and_bad_version(self):
        with patch.object(main, 'UNIT_STORE', self.store), patch.object(main, '_load_run', return_value=self.run), patch.object(main.INVENTORY_STORE, 'get', return_value=self.stock), TestClient(main.app) as client:
            self.assertEqual(client.post('/api/units', json={}).status_code, 400)
            saved = client.post('/api/units', json=CONFIG)
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(len(client.get('/api/units').json()['versions']), 1)
            url = '/api/inventory/stock/projection?run_id=sample'
            self.assertIsNone(client.get(url).json()['rows'][0]['opening'])
            result = client.get(url + '&unit_version_id=' + saved.json()['id'])
            self.assertEqual(result.json()['rows'][0]['opening'], 60)
            self.assertEqual(client.get(url + '&unit_version_id=missing').status_code, 400)

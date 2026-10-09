from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main as main

from tests import test_inventory as inventory_fixture
from app.inventory import InventoryStore, project_inventory


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.fixture = inventory_fixture.InventoryTests()
        self.fixture.setUp()
        self.store = self.fixture.store
        self.snapshot = self.store.save(self.fixture.config)
        self.run = {**self.fixture.run, 'run_settings': {'frequency': 'monthly'}}

    def tearDown(self):
        self.fixture.tearDown()

    def config(self, **changes):
        return dict(name='Reviewed deliveries', reason='Synthetic order check', reviewed=True, request_id='test',
                    rows=[dict(reference='PO-1/1', sku='001', quantity=6, unit='pieces', due_date='2026-10-31',
                               kind='purchase', status='confirmed')], **changes)

    def test_netting_carries_unmet_demand_and_preserves_source(self):
        original = deepcopy(self.run)
        receipt = self.store.save_receipts(self.snapshot['id'], self.config())
        result = project_inventory(self.run, self.snapshot, receipt_version=receipt)
        rows = [r for r in result['rows'] if r['sku'] == '001']
        self.assertEqual([(r['opening'], r['receipts'], r['closing']) for r in rows], [(20, 0, 8), (8, 6, 2)])
        self.assertEqual(self.run, original)
        # A later receipt does not remove an earlier shortfall.
        self.run['series']['customer-a']['forecast'][0]['mean'] = 30
        rows = [r for r in project_inventory(self.run, self.snapshot, receipt_version=receipt)['rows'] if r['sku'] == '001']
        self.assertEqual([r['closing'] for r in rows], [-15, -21])

    def test_exclusions_unknown_stock_and_production(self):
        config = self.config()
        row = config['rows'][0]
        config['rows'] = [dict(row, reference=str(i), **change) for i, change in enumerate([
            {'status':'unconfirmed'}, {'status':'cancelled'}, {'sku':'other'}, {'due_date':'2026-11-01'},
            {'sku':'004','kind':'production'}, {'sku':'001','kind':'production'}])]
        receipt = self.store.save_receipts(self.snapshot['id'], config)
        result = project_inventory(self.run, self.snapshot, receipt_version=receipt)
        self.assertEqual(len(result['excluded_receipts']), 4)
        unknown = next(r for r in result['rows'] if r['sku'] == '004' and r['period'] == '2026-10-01')
        self.assertEqual(unknown['receipts'], 6)
        self.assertIsNone(unknown['closing'])

    def test_retry_concurrency_versions_and_restart(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            saved = list(pool.map(lambda _: self.store.save_receipts(self.snapshot['id'], self.config()), range(2)))
        self.assertEqual(saved[0], saved[1])
        changed = self.config(); changed['rows'][0]['quantity'] = 8
        with self.assertRaisesRegex(ValueError, 'another receipt'):
            self.store.save_receipts(self.snapshot['id'], changed)
        changed.update(request_id='next', parent_id=saved[0]['id'])
        second = self.store.save_receipts(self.snapshot['id'], changed)
        self.assertEqual(self.store.receipt_version(self.snapshot['id'], saved[0]['id']), saved[0])
        restored = InventoryStore(self.fixture.root / 'stock.sqlite3', self.fixture.sources)
        self.assertEqual(len(restored.receipt_versions(self.snapshot['id'])), 2)
        self.assertEqual(restored.receipt_version(self.snapshot['id'], second['id']), second)
        restored.engine.dispose()

    def test_invalid_receipts_dates_keys_and_classification(self):
        for change in ({'quantity':-1}, {'quantity':float('nan')}, {'quantity':True}, {'due_date':'2026-08-31'},
                       {'due_date':'2026-02-30'}, {'sku':''}, {'status':'received'}, {'kind':'demand'}):
            config = self.config(); config['rows'][0].update(change)
            with self.assertRaises(ValueError): self.store.save_receipts(self.snapshot['id'], config)
        config = self.config(); config['rows'] *= 2
        with self.assertRaisesRegex(ValueError, 'unique'):
            self.store.save_receipts(self.snapshot['id'], config)
        with self.assertRaisesRegex(ValueError, 'both be real'):
            project_inventory({**self.run, 'source_classification':'user_provided'}, self.snapshot)

    def test_api_save_select_and_reset(self):
        with patch.object(main, 'INVENTORY_STORE', self.store), patch.object(main, '_load_run', return_value=self.run), TestClient(main.app) as client:
            base = f'/api/inventory/{self.snapshot["id"]}'
            saved = client.post(base + '/receipts', json=self.config())
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(client.get(base + '/receipts').json()['versions'][0]['id'], saved.json()['id'])
            result = client.get(base + '/projection?run_id=run&receipt_version_id=' + saved.json()['id'])
            self.assertEqual(result.status_code, 200, result.text)
            row = next(r for r in result.json()['rows'] if r['sku']=='001' and r['period']=='2026-10-01')
            self.assertEqual(row['closing'], 2)
            baseline = client.get(base + '/projection?run_id=run').json()
            self.assertIsNone(baseline['receipt_version'])
            self.assertEqual(next(r for r in baseline['rows'] if r['sku']=='001' and r['period']=='2026-10-01')['closing'], -4)
            self.assertEqual(client.get(base + '/projection?run_id=run&receipt_version_id=missing').status_code, 400)

    def test_date_bucket_boundaries_and_conversion(self):
        config = self.config(); config['rows'][0].update(unit='kg')
        receipt = self.store.save_receipts(self.snapshot['id'], config)
        with self.assertRaisesRegex(ValueError, 'confirm kg'):
            project_inventory(self.run, self.snapshot, receipt_version=receipt)
        for frequency, dates, arrival in [('daily', ['2026-09-01','2026-09-02'], '2026-09-02'),
                                          ('weekly', ['2026-09-01','2026-09-08'], '2026-09-07')]:
            run = deepcopy(self.run); run['run_settings']['frequency'] = frequency
            for series in run['series'].values():
                for row, period in zip(series['forecast'], dates): row['timestamp'] = period
            config = self.config(); config['request_id'] = frequency; config['rows'][0]['due_date'] = arrival
            version = self.store.save_receipts(self.snapshot['id'], config)
            rows = [r for r in project_inventory(run, self.snapshot, receipt_version=version)['rows'] if r['sku']=='001']
            self.assertEqual([r['receipts'] for r in rows], [0,6] if frequency == 'daily' else [6,0])


if __name__ == '__main__': unittest.main()

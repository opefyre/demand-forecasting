from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

import openpyxl
from fastapi.testclient import TestClient

import app.main as main
from app.planning import PlanStore
from app.plan_outputs import resolve_plan, plan_workbook


class PlanVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.store = PlanStore(Path(self.tmp.name)/'plans.json')
        self.parent = self.store.create(name='Original', run_id='run', site_id='site', owner='A', settings={'unit':'tonnes'}, metrics={'evidence_level':'strong'})
        for value in (120, 130, 140):
            self.store.add_override(self.parent['id'], item_id='A', period='2026-10-01', value=value, reason=f'Order {value}', actor='A')
        latest = self.store.get(self.parent['id'])['overrides'][-1]
        self.store.revert_override(self.parent['id'], latest['id'], reason='Cancelled', actor='A')
        self.store.transition(self.parent['id'], status='review', actor='A')
        self.store.transition(self.parent['id'], status='approved', actor='Reviewer')
        self.store.transition(self.parent['id'], status='published', actor='Reviewer')
        self.parent = self.store.get(self.parent['id'])
        self.run = {'run_id':'run', 'unit':'tonnes', 'series':{'A':{'forecast':[{'timestamp':'2026-10-01','mean':100}]}}}
        self.payload = {'name':'Revision', 'owner':'B', 'reason':'Updated order', 'request_id':str(uuid.uuid4())}

    def tearDown(self): self.tmp.cleanup()

    def test_parent_unchanged_and_only_effective_adjustment_copied(self):
        before = deepcopy(self.parent)
        draft = self.store.revise(self.parent['id'], **self.payload)
        self.assertEqual(self.store.get(self.parent['id']), before)
        self.assertEqual(draft['status'], 'draft')
        self.assertEqual(len(draft['overrides']), 1)
        change = draft['overrides'][0]
        self.assertEqual(change['value'], 130)
        self.assertEqual(change['inherited_from']['override_id'], before['overrides'][1]['id'])
        self.assertNotEqual(change['id'], before['overrides'][1]['id'])
        self.assertEqual(draft['comments'], [])
        self.assertEqual(len(draft['history']), 1)
        self.assertEqual(draft['parent_plan_id'], before['id'])
        self.assertEqual(draft['version'], 2)

    def test_same_request_retries_once_and_different_details_rejected(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: self.store.revise(self.parent['id'], **self.payload), range(5)))
        self.assertEqual(len({p['id'] for p in results}), 1)
        self.assertEqual(len(self.store.list()), 2)
        with self.assertRaisesRegex(ValueError, 'different details'):
            self.store.revise(self.parent['id'], **{**self.payload, 'reason':'Other order'})

    def test_branches_get_unique_family_version_numbers(self):
        first = self.store.revise(self.parent['id'], **self.payload)
        second = self.store.revise(self.parent['id'], **{**self.payload, 'request_id':str(uuid.uuid4())})
        self.assertEqual((first['version'],second['version']), (2,3))
        self.assertEqual(first['root_plan_id'], second['root_plan_id'])
        with self.assertRaisesRegex(ValueError, 'Edit an existing draft'):
            self.store.revise(first['id'], **{**self.payload, 'request_id':str(uuid.uuid4())})

    def test_input_and_missing_parent_guards(self):
        for changes in ({'reason':'  '}, {'owner':' '}, {'name':' '}, {'request_id':'bad'}):
            with self.assertRaises(ValueError): self.store.revise(self.parent['id'], **{**self.payload, **changes})
        with self.assertRaises(KeyError): self.store.revise('missing', **self.payload)

    def test_revised_quantities_compare_to_frozen_previous_version(self):
        draft = self.store.revise(self.parent['id'], **self.payload)
        self.store.add_override(draft['id'], item_id='A', period='2026-10-01', value=150, reason='Additional order', actor='B')
        draft = self.store.get(draft['id'])
        _, rows = resolve_plan(self.run, draft)
        self.assertEqual(rows[0]['forecast_quantity'], 100)
        self.assertEqual(rows[0]['previous_plan_quantity'], 130)
        self.assertEqual(rows[0]['plan_quantity'], 150)
        self.assertEqual(rows[0]['revision_change'], 20)
        self.assertEqual(resolve_plan(self.run, self.store.get(self.parent['id']))[1][0]['plan_quantity'], 130)
        book = openpyxl.load_workbook(BytesIO(plan_workbook(draft, rows)), data_only=True)
        meta = dict(book['Plan version'].iter_rows(min_row=2, values_only=True))
        self.assertEqual(meta['parent_plan_id'], self.parent['id'])
        self.assertEqual(meta['revision_reason'], 'Updated order')
        values = list(book['Plan quantities'].values)
        self.assertEqual(dict(zip(values[0],values[1]))['revision_change'], 20)
        book.close()

    def test_api_creates_version_and_rejects_invalid_source(self):
        with patch.object(main,'PLAN_STORE',self.store), patch.object(main,'_load_run',return_value=self.run), TestClient(main.app) as client:
            response = client.post(f"/api/plans/{self.parent['id']}/versions", json=self.payload)
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(client.post(f"/api/plans/{self.parent['id']}/versions", json=self.payload).json()['id'], response.json()['id'])
            quantities = client.get(f"/api/plans/{response.json()['id']}/quantities").json()['rows']
            self.assertEqual(quantities[0]['revision_change'], 0)
            self.assertEqual(client.post('/api/plans/missing/versions',json=self.payload).status_code, 404)
            with patch.object(main,'_load_run',return_value={**self.run,'run_id':'different'}):
                self.assertEqual(client.post(f"/api/plans/{self.parent['id']}/versions",json={**self.payload,'request_id':str(uuid.uuid4())}).status_code,400)


if __name__ == '__main__': unittest.main()

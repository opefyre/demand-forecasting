"""Reviewed cumulative order updates, immutable evidence and concurrent edits."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.sales_demand import DemandStore, revise_orders, StaleOrderRevision
from app.sales_api import install_sales_routes, run_hash
from app.datasets import DatasetStore
from tests.test_sales_demand import fixture, order, TODAY


class OrderRevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.run, self.inputs = fixture()
        self.inputs['orders'] = [order(quantity=6), order('B', 3)]
        self.store = DemandStore(Path(self.tmp.name)/'sales.sqlite3')
        self.sources = DatasetStore(Path(self.tmp.name)/'datasets')
        self.base = self.store.save(self.inputs,self.run,'initial-order-book','Planner',[{'run_sha256':run_hash(self.run)}])
        app = FastAPI()
        @app.middleware('http')
        async def identity(request: Request, call_next):
            request.state.principal = {'issuer':'company','subject':'planner'}
            return await call_next(request)
        install_sales_routes(app,self.store,self.sources,lambda _:self.run)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def payload(self, orders=None, **kw):
        inputs = deepcopy(self.inputs)
        inputs['orders'] = orders if orders is not None else [order(quantity=16)]
        return {'inputs':inputs, 'base_snapshot_id':self.base['id'], 'order_mode':'changes',
                'request_id':'updated-order-book', **kw}

    def test_preview_merges_without_writes_and_retry_is_not_added_twice(self):
        payload = self.payload()
        preview = self.client.post('/api/sales/validate',json=payload)
        self.assertEqual(preview.status_code,200,preview.text)
        data = preview.json()
        self.assertEqual(len(self.store.list('forecast1')),1)
        a,b,_ = data['rows']
        self.assertEqual((a['booked'],a['remaining'],a['total']),(16,0,16))
        self.assertEqual((b['booked'],b['remaining'],b['total']),(3,5,8))
        self.assertEqual(data['order_changes'][0]['before']['ordered'],'6')
        saved = self.client.post('/api/sales/inputs',json=payload)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.client.post('/api/sales/inputs',json=payload).json(),saved.json())
        self.assertEqual(len(self.store.list('forecast1')),2)
        self.assertEqual(self.store.get(self.base['id']),self.base)
        self.assertEqual(saved.json()['base_snapshot_id'],self.base['id'])
        self.assertEqual(saved.json()['actor'],'["company", "planner"]')
        payload['inputs']['orders'][0]['ordered']=17
        self.assertEqual(self.client.post('/api/sales/inputs',json=payload).status_code,400)

    def test_delivery_movement_leaves_no_order_in_old_month(self):
        next_month=(TODAY.replace(day=28)+timedelta(days=4)).replace(day=1)
        for series in self.run['series'].values():
            series['forecast'].append({'timestamp':str(next_month),'mean':10})
        # Create a reviewed base bound to the expanded forecast.
        self.base=self.store.save(self.inputs,self.run,'expanded-baseline','Planner',[{'run_sha256':run_hash(self.run)}])
        data=self.client.post('/api/sales/validate',json=self.payload([order(quantity=16,due_date=str(next_month))])).json()
        rows=[r for r in data['rows'] if r['customer']=='A']
        self.assertEqual([(r['booked'],r['remaining']) for r in rows],[(0,10),(16,0)])

    def test_cancelled_quantities_release_expected_demand_once(self):
        data=self.client.post('/api/sales/validate',json=self.payload([order(quantity=6,cancelled=4)])).json()
        a=data['rows'][0]
        self.assertEqual((a['booked'],a['remaining'],a['total']),(2,8,10))
        data=self.client.post('/api/sales/validate',json=self.payload([order(quantity=6,cancelled=6,status='cancelled')])).json()
        self.assertEqual(data['rows'][0]['booked'],0)
        self.assertEqual(data['rows'][0]['remaining'],10)

    def test_duplicate_and_reassigned_reference_rejected(self):
        for rows in ([order(),order()], [order(customer='C',reference='A/1')]):
            response=self.client.post('/api/sales/validate',json=self.payload(rows))
            self.assertEqual(response.status_code,400,response.text)

    def test_full_replacement_previews_removed_lines(self):
        data=self.client.post('/api/sales/validate',json=self.payload([],order_mode='replace')).json()
        self.assertEqual(len(data['orders']),0)
        self.assertEqual([r['change'] for r in data['order_changes']],['removed','removed'])
        self.assertEqual(sum(r['remaining'] for r in data['rows']),23)

    def test_rejected_correction_can_be_fixed_without_changing_original(self):
        for invalid in ([order(), order()], [order(customer='C', reference='A/1')]):
            response = self.client.post('/api/sales/inputs', json=self.payload(invalid))
            self.assertEqual(response.status_code, 400, response.text)
            self.assertEqual(len(self.store.list('forecast1')), 1)
            self.assertEqual(self.store.get(self.base['id']), self.base)
        corrected = self.payload([order(quantity=16)])
        saved = self.client.post('/api/sales/inputs', json=corrected)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(self.client.post('/api/sales/inputs', json=corrected).json(), saved.json())
        self.assertEqual(len(self.store.list('forecast1')), 2)
        self.assertEqual(self.store.get(self.base['id']), self.base)

    def test_customer_file_replaces_relationships_and_preserves_original(self):
        source = self.sources.upload('customers.csv',
            b'customer,sku,unit,series_id\nA,001,tonnes,A\nB,001,tonnes,B\nC,001,tonnes,C\n',
            'sales_customers')
        payload = self.payload()
        payload['imports'] = {'customers': {'source_id': source['id'], 'header_row': 1,
            'mapping': dict(zip(['customer', 'sku', 'unit', 'series_id'], 'ABCD'))}}
        saved = self.client.post('/api/sales/inputs', json=payload)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual([r['customer'] for r in saved.json()['inputs']['customers']], ['A', 'B', 'C'])
        self.assertTrue(all(r['sku'] == '001' for r in saved.json()['inputs']['customers']))
        self.assertEqual(self.store.get(self.base['id']), self.base)

    def test_fulfilled_cannot_disappear_decrease_or_move_month(self):
        old=[order(quantity=6,fulfilled=2)]
        next_month=(TODAY.replace(day=28)+timedelta(days=4)).replace(day=1)
        for rows in ([],[order(quantity=6,fulfilled=1)],[order(quantity=6,fulfilled=2,due_date=str(next_month))]):
            with self.assertRaises(ValueError):
                revise_orders(old,rows,'replace',str(TODAY))
        rows,_=revise_orders(old,[order(quantity=6,fulfilled=2,cancelled=4,status='cancelled')],'changes',str(TODAY))
        self.assertEqual(rows[0]['fulfilled'],'2')

    def test_stale_editor_cannot_overwrite_new_version(self):
        first=self.client.post('/api/sales/inputs',json=self.payload())
        self.assertEqual(first.status_code,200)
        stale=self.client.post('/api/sales/inputs',json=self.payload(request_id='another-editor'))
        self.assertEqual(stale.status_code,409)
        self.assertEqual(len(self.store.list('forecast1')),2)

    def test_concurrent_writers_have_one_winner(self):
        def save(i):
            try:
                return self.store.save(self.inputs,self.run,f'parallel-edit-{i}','Planner',base_snapshot_id=self.base['id'])['id']
            except StaleOrderRevision:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(save,range(2)))
        self.assertEqual(sum(r is not None for r in results),1)

    def test_incomplete_base_or_backdated_updates_do_not_create_current_order_book(self):
        payload=self.payload()
        payload['inputs']['as_of']=str(TODAY-timedelta(days=1))
        self.assertEqual(self.client.post('/api/sales/validate',json=payload).status_code,400)
        self.inputs['order_feed']='unknown'
        self.base=self.store.save(self.inputs,self.run,'incomplete-orders','Planner',[{'run_sha256':run_hash(self.run)}])
        self.assertEqual(self.client.post('/api/sales/validate',json=self.payload()).status_code,400)
        payload=self.payload(base_snapshot_id=None)
        self.assertEqual(self.client.post('/api/sales/validate',json=payload).status_code,400)

    def test_imported_changes_keep_other_lines_and_source_evidence(self):
        source=self.sources.upload('changes.csv',b'reference,customer,sku,unit,due_date,ordered,status\nA/1,A,001,tonnes,'+str(TODAY).encode()+b',16,confirmed\n','sales_orders')
        payload=self.payload()
        payload['imports']={'orders':{'source_id':source['id'],'header_row':1,'mapping':dict(zip(['reference','customer','sku','unit','due_date','ordered','status'],'ABCDEFG'))}}
        response=self.client.post('/api/sales/inputs',json=payload)
        self.assertEqual(response.status_code,200,response.text)
        saved=response.json()
        self.assertEqual(len(saved['inputs']['orders']),2)
        self.assertEqual(saved['evidence'][0]['source']['sha256'],source['sha256'])
        self.assertEqual(saved['evidence'][1]['base_sha256'],self.base['sha256'])

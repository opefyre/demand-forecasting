import csv
from io import StringIO
import os
from pathlib import Path
import time
import unittest
from copy import deepcopy
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.order_folders import OrderFolders
from app.sales_demand import import_rows
from app.sales_api import run_hash
from app.sales_api import install_sales_routes
from tests import test_order_revisions as revisions
from tests.test_sales_demand import order


class OrderFolderTests(unittest.TestCase):
    def setUp(self):
        revisions.OrderRevisionTests.setUp(self)
        self.exports=Path(self.tmp.name)/'exports';self.exports.mkdir()
        self.write([order(quantity=6),order('B',3)])
        source=self.sources.upload('orders.csv',self.file.read_bytes(),'sales_orders')
        self.mapping={'source_id':source['id'],'header_row':1,'mapping':{k:chr(65+i) for i,k in enumerate(order())}}
        rows,proof=import_rows(self.sources,'orders',self.mapping)
        self.inputs['orders']=rows
        self.base=self.store.save(self.inputs,self.run,'mapped-order-book','Planner',[{'run_sha256':run_hash(self.run)},proof])
        self.folders=OrderFolders(Path(self.tmp.name)/'folders.sqlite3',self.sources,[self.exports],self.store)
        self.config=dict(path=str(self.exports),filename='orders.csv',minutes=15,confirmed_local_access=True)

    def write(self, rows):
        text=StringIO();w=csv.DictWriter(text,fieldnames=list(order()));w.writeheader();w.writerows(rows)
        self.file=self.exports/'orders.csv';self.file.write_text(text.getvalue());os.utime(self.file,(time.time()-5,)*2)

    def test_refresh_review_save_reuses_existing_calculation_and_retry(self):
        self.folders.configure('forecast1',self.config)
        self.write([order(quantity=16,fulfilled=2,cancelled=1),order('B',3)])
        first=self.folders.check('forecast1');second=self.folders.check('forecast1')
        self.assertEqual(first['candidate'],second['candidate'])
        draft=self.folders.review('forecast1')
        self.assertFalse(draft['inputs']['reviewed'])
        self.assertEqual(draft['inputs']['as_of'],self.base['inputs']['as_of'])
        self.assertEqual(draft['inputs']['valid_until'],self.base['inputs']['valid_until'])
        self.assertEqual(len(self.store.list('forecast1')),2)
        preview=self.client.post('/api/sales/validate',json={**draft,'inputs':{**draft['inputs'],'note':'Reviewed export','reviewed':True}})
        self.assertEqual(preview.status_code,200,preview.text)
        a=preview.json()['rows'][0]
        self.assertEqual((a['booked'],a['fulfilled'],a['remaining'],a['total']),(13,2,0,15))
        payload={**draft,'inputs':{**draft['inputs'],'note':'Reviewed export','reviewed':True},'request_id':'folder-review-001'}
        saved=self.client.post('/api/sales/inputs',json=payload)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.client.post('/api/sales/inputs',json=payload).json(),saved.json())
        self.assertEqual(self.store.get(self.base['id']),self.base)

    def test_failed_file_does_not_expose_old_candidate_as_current(self):
        self.folders.configure('forecast1',self.config)
        good=self.folders.check('forecast1')['candidate']
        self.write([order(quantity=2,fulfilled=9)])
        with self.assertRaises(ValueError):self.folders.review('forecast1')
        config=self.folders.get_config('forecast1')
        self.assertEqual(config['status'],'failed')
        self.assertEqual(config['candidate'],good)
        self.write([])
        with self.assertRaisesRegex(ValueError,'Empty export'):self.folders.review('forecast1')

    def test_changed_headings_and_paths_are_blocked(self):
        self.folders.configure('forecast1',self.config)
        content=self.file.read_text().replace('reference','different_heading',1)
        self.file.write_text(content);os.utime(self.file,(time.time()-5,)*2)
        with self.assertRaisesRegex(ValueError,'headings changed'):self.folders.review('forecast1')
        for patch in ({'path':self.tmp.name},{'filename':'../orders.csv'},{'confirmed_local_access':False}):
            with self.assertRaises(ValueError):self.folders.configure('forecast1',{**self.config,**patch})

    def test_pause_and_configuration_survive_restart(self):
        self.folders.configure('forecast1',self.config)
        self.folders.set_enabled('forecast1',False)
        reopened=OrderFolders(self.folders.path,self.sources,[self.exports],self.store)
        self.assertFalse(reopened.get_config('forecast1')['enabled'])
        self.assertEqual(reopened.review('forecast1')['base_snapshot_id'],self.base['id'])

    def cross_run(self):
        target=deepcopy(self.run);target['run_id']='new-forecast'
        runs={'forecast1':self.run,'new-forecast':target}
        self.folders.load_run=runs.__getitem__
        self.folders.configure('forecast1',self.config)
        self.folders.reuse('new-forecast','forecast1')
        app=FastAPI()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal=None
            return await call_next(request)
        install_sales_routes(app,self.store,self.sources,runs.__getitem__)
        client=TestClient(app);self.addCleanup(client.close)
        return target,client

    def test_cross_forecast_refresh_export_and_exact_retry(self):
        target,client=self.cross_run()
        self.assertFalse(self.folders.get_config('new-forecast')['enabled'])
        self.write([order(quantity=16,fulfilled=2,cancelled=1),order('B',3)])
        draft=self.folders.review('new-forecast')
        self.assertIsNone(draft['base_snapshot_id'])
        self.assertEqual(draft['inputs']['run_id'],'new-forecast')
        payload={**draft,'inputs':{**draft['inputs'],'reviewed':True,'note':'Reviewed fresh full export'},'request_id':'new-forecast-orders'}
        preview=client.post('/api/sales/validate',json=payload)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertTrue(preview.json()['order_changes'])
        saved=client.post('/api/sales/inputs',json=payload)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(client.post('/api/sales/inputs',json=payload).json(),saved.json())
        changed=deepcopy(payload);changed['inputs']['note']='Different content'
        self.assertEqual(client.post('/api/sales/inputs',json=changed).status_code,400)
        proof=next(e for e in saved.json()['evidence'] if e.get('type')=='connected_order_refresh')
        self.assertEqual(proof['source_snapshot_id'],self.base['id'])
        self.assertEqual(self.store.get(self.base['id']),self.base)
        from app.sales_demand import export_demand
        outlook=client.get('/api/sales/inputs/'+saved.json()['id']+'/outlook').json()
        import json
        rows=json.loads(export_demand(outlook,'combined_demand','json')[0])
        self.assertEqual(sum(r['quantity'] for r in rows),26) # A13+B8+C5, fulfilled excluded.

    def test_cross_forecast_scope_and_stale_source_block(self):
        target,client=self.cross_run()
        draft=self.folders.review('new-forecast')
        payload={**draft,'inputs':{**draft['inputs'],'reviewed':True,'note':'Reviewed orders'},'request_id':'stale-source-order'}
        self.store.save(self.inputs,self.run,'new-source-version','Planner',[{'run_sha256':run_hash(self.run)}])
        self.assertEqual(client.post('/api/sales/inputs',json=payload).status_code,409)
        self.assertEqual(self.store.list('new-forecast'),[])
        target['unit']='kg'
        self.assertEqual(self.folders.choices('new-forecast'),[])
        with self.assertRaisesRegex(ValueError,'scope changed'):self.folders.review('new-forecast')

    def test_cross_forecast_concurrent_target_blocks_first_save(self):
        target,client=self.cross_run()
        draft=self.folders.review('new-forecast')
        self.store.save({**self.inputs,'run_id':'new-forecast'},target,'other-target-orders','Planner',[{'run_sha256':run_hash(target)}])
        payload={**draft,'inputs':{**draft['inputs'],'reviewed':True,'note':'Reviewed orders'},'request_id':'old-target-review'}
        self.assertEqual(client.post('/api/sales/inputs',json=payload).status_code,409)
        self.assertEqual(len(self.store.list('new-forecast')),1)

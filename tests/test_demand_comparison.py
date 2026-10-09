from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.datasets import DatasetStore
from app.sales_api import install_sales_routes, run_hash
from app.sales_demand import DemandStore, demand_outlook, StaleOrderRevision, export_demand
from app.demand_comparison import compare_orders, save_comparison
from tests.test_sales_demand import fixture, order, TODAY


class DemandComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        self.store=DemandStore(self.root/'orders.sqlite3')
        self.base,self.inputs=fixture()
        self.inputs['orders']=[order('A',16),order('B',6,fulfilled=2,cancelled=1),
                              order('C',4,cancelled=4,status='cancelled')]
        self.source=self.store.save(self.inputs,self.base,'original-orders','Test',[{'run_sha256':run_hash(self.base)}])
        self.target=deepcopy(self.base);self.target.update(run_id='linked',base_run_id=self.base['run_id'],scenario={'type':'factor_link'})
        for item,qty in [('A',12),('B',10),('C',7)]:self.target['series'][item]['forecast'][0]['mean']=qty
        self.runs={self.base['run_id']:self.base,'linked':self.target}

    def tearDown(self):self.tmp.cleanup()
    def compare(self):return compare_orders(self.store,self.runs.__getitem__,'linked',self.source['id'])[0]
    def payload(self):return {'snapshot_id':self.source['id'],'reviewed':True,'review_token':self.compare()['review_token'],'request_id':'review-copy-123'}

    def test_math_keeps_orders_fulfillment_cancellations_and_absent_orders(self):
        rows=self.compare()['rows']
        self.assertEqual((rows[0]['before_total'],rows[0]['after_total'],rows[0]['booked']),(16,16,16))
        self.assertEqual((rows[1]['fulfilled'],rows[1]['booked'],rows[1]['before_remaining'],rows[1]['after_remaining']),(2,3,3,5))
        self.assertEqual((rows[2]['booked'],rows[2]['before_total'],rows[2]['after_total']),(0,5,7))
        self.assertEqual(sum(r['after_total'] for r in rows),33)

    def test_saved_copy_is_immutable_idempotent_and_draft_export_reconciles(self):
        payload=self.payload();before=deepcopy(self.source)
        saved=save_comparison(self.store,self.runs.__getitem__,'linked',payload,'Planner')
        self.assertEqual(saved,save_comparison(self.store,self.runs.__getitem__,'linked',payload,'Planner'))
        self.assertEqual(before,self.store.get(self.source['id']))
        for field in ['customers','orders','commitments','as_of','valid_until','order_feed']:
            self.assertEqual(saved['inputs'][field],before['inputs'][field])
        self.assertFalse(saved['evidence'][1]['publication_approval_carried'])
        outlook=demand_outlook(saved['inputs'],self.target)
        exported=json.loads(export_demand(outlook,'combined_demand','json')[0])
        self.assertEqual(sum(r['quantity'] for r in exported),31) # Excludes 2 delivered.
        self.assertEqual({r['approval'] for r in exported},{'draft'})
        with self.assertRaises(ValueError):save_comparison(self.store,self.runs.__getitem__,'linked',{**payload,'review_token':'bad'},'Planner')

    def test_new_source_version_invalidates_preview(self):
        payload=self.payload()
        self.store.save(self.inputs,self.base,'updated-orders','Test',[{'run_sha256':run_hash(self.base)}])
        with self.assertRaises(StaleOrderRevision):self.compare()
        with self.assertRaises(StaleOrderRevision):save_comparison(self.store,self.runs.__getitem__,'linked',payload,'Planner')

    def test_atomic_guard_rejects_intervening_source_or_target_review(self):
        report,inputs,target,evidence=compare_orders(self.store,self.runs.__getitem__,'linked',self.source['id'])
        self.store.save(inputs,target,'another-target-review','Test',evidence)
        with self.assertRaises(StaleOrderRevision):
            self.store.save(inputs,target,'guarded-new-review','Test',evidence,comparison_guard=report['guard'])
        report,inputs,target,evidence=compare_orders(self.store,self.runs.__getitem__,'linked',self.source['id'])
        self.store.save(self.inputs,self.base,'new-source-review','Test',[{'run_sha256':run_hash(self.base)}])
        with self.assertRaises(StaleOrderRevision):
            self.store.save(inputs,target,'guarded-next-review','Test',evidence,comparison_guard=report['guard'])

    def test_changed_run_or_scope_blocked(self):
        original=deepcopy(self.target)
        for field,value in [('unit','kg'),('source_classification','user_provided'),('base_run_id','unknown')]:
            self.target[field]=value
            with self.assertRaises((ValueError,KeyError)):self.compare()
            self.target.clear();self.target.update(deepcopy(original))
        self.target['series']['A']['forecast'][0]['timestamp']='2099-01-01'
        with self.assertRaises(ValueError):self.compare()
        self.target.clear();self.target.update(original)
        self.base['unit']='kg'
        with self.assertRaisesRegex(ValueError,'baseline changed'):self.compare()

    def test_stale_or_incomplete_sources_preserve_unknowns_and_block_save(self):
        for patch in ({'valid_until':str(TODAY-timedelta(days=1)),'as_of':str(TODAY-timedelta(days=2))},
                      {'order_feed':'unknown'},
                      {'customers':self.inputs['customers']+[{'customer':'New','sku':'001','unit':'tonnes'}]}):
            inputs={**self.inputs,**patch}
            self.source=self.store.save(inputs,self.base,'source-case-'+str(len(self.store.list(self.base['run_id']))),'Test',[{'run_sha256':run_hash(self.base)}])
            report=self.compare();self.assertFalse(report['can_save'])
            self.assertTrue(any(r['after_total'] is None for r in report['rows']))
            with self.assertRaises(ValueError):save_comparison(self.store,self.runs.__getitem__,'linked',self.payload(),'Planner')

    def test_complete_commitment_is_preserved(self):
        inputs=deepcopy(self.inputs)
        inputs['commitments']=[{'customer':'B','sku':'001','unit':'tonnes','period':str(TODAY.replace(day=1)),
            'quantity':6,'owner':'Planner','reason':'Full monthly requirement','valid_until':str(TODAY+timedelta(days=7))}]
        self.source=self.store.save(inputs,self.base,'with-commitment','Test',[{'run_sha256':run_hash(self.base)}])
        row=self.compare()['rows'][1]
        self.assertEqual((row['before_total'],row['after_total']),(6,6))

    def test_api_preview_save_and_export(self):
        app=FastAPI()
        @app.middleware('http')
        async def principal(request:Request,call_next):
            request.state.principal=None;return await call_next(request)
        install_sales_routes(app,self.store,DatasetStore(self.root/'sources'),self.runs.__getitem__)
        with TestClient(app) as client:
            url='/api/sales/runs/linked/order-comparison'
            preview=client.post(url+'/preview',json={'snapshot_id':self.source['id']})
            self.assertEqual(preview.status_code,200,preview.text)
            body={**self.payload(),'review_token':preview.json()['review_token']}
            saved=client.post(url,json=body);self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(saved.json(),client.post(url,json=body).json())
            export=client.get('/api/sales/inputs/'+saved.json()['id']+'/export?mode=combined_demand&kind=json')
            self.assertEqual(export.status_code,200,export.text)
            self.assertEqual(sum(r['quantity'] for r in export.json()),31)

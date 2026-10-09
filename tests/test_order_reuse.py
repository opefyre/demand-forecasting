from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from app.sales_demand import DemandStore
from app.sales_api import install_sales_routes,run_hash
from app.order_reuse import preview_reuse,save_reuse
from tests.test_sales_demand import fixture,order,TODAY


class OrderReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.store=DemandStore(Path(self.temp.name)/'orders.sqlite3')
        self.base,self.inputs=fixture();self.inputs['orders']=[order('A',16),order('B',6,fulfilled=2,cancelled=1)]
        self.source=self.store.save(self.inputs,self.base,'original-orders','Planner',[{'run_sha256':run_hash(self.base)}])
        self.target=deepcopy(self.base);self.target['run_id']='new-run'
        self.later=str((TODAY.replace(day=1)+timedelta(days=32)).replace(day=1))
        for s in self.target['series'].values():s['forecast'].append({'timestamp':self.later,'mean':20})
        self.runs={self.base['run_id']:self.base,'new-run':self.target}
    def preview(self):return preview_reuse(self.store,self.runs.__getitem__,'new-run',self.source['id'])[0]
    def payload(self):return {'snapshot_id':self.source['id'],'review_token':self.preview()['review_token'],
                              'reviewed':True,'coverage_confirmed':True,'request_id':'reuse-new-months'}
    def test_extended_horizon_retains_orders_and_forecasts_no_order_customers(self):
        report=self.preview();self.assertEqual(report['added_months'],[self.later])
        self.assertEqual(report['months'][0]['booked'],19)
        self.assertEqual(report['months'][0]['total'],29)
        self.assertEqual(report['months'][1]['booked'],0);self.assertEqual(report['months'][1]['total'],60)
        self.assertEqual(self.store.list('new-run'),[])
    def test_confirmation_idempotence_and_original_preservation(self):
        payload=self.payload()
        with self.assertRaises(ValueError):save_reuse(self.store,self.runs.__getitem__,'new-run',{**payload,'coverage_confirmed':False},'Planner')
        saved=save_reuse(self.store,self.runs.__getitem__,'new-run',payload,'Planner')
        self.assertEqual(saved,save_reuse(self.store,self.runs.__getitem__,'new-run',payload,'Planner'))
        for field in ('orders','customers','commitments','as_of','valid_until'):
            self.assertEqual(saved['inputs'][field],self.source['inputs'][field])
        self.assertEqual(self.store.get(self.source['id']),self.source)
    def test_shrinking_horizon_discloses_but_does_not_delete_open_orders(self):
        for s in self.target['series'].values():s['forecast']=s['forecast'][1:]
        report=self.preview();self.assertEqual(len(report['outside_open_orders']),2)
        self.assertEqual(report['months'][0]['total'],60)
        saved=save_reuse(self.store,self.runs.__getitem__,'new-run',self.payload(),'Planner')
        self.assertEqual(len(saved['inputs']['orders']),2)
    def test_mismatched_identity_units_and_classification_rejected(self):
        for field,value in [('unit','kg'),('source_classification','user_provided'),('metadata',{})]:
            original=self.target[field];self.target[field]=value
            with self.assertRaises(ValueError):self.preview()
            self.target[field]=original
        self.target['run_settings']['calendar_profile']={'month_basis':'jalali'}
        with self.assertRaisesRegex(ValueError,'planning calendar'):self.preview()
    def test_new_source_or_target_version_and_changed_forecast_invalidate_review(self):
        payload=self.payload();self.target['series']['A']['forecast'][0]['mean']=200
        with self.assertRaises(ValueError):save_reuse(self.store,self.runs.__getitem__,'new-run',payload,'Planner')
        self.store.save(self.inputs,self.base,'new-source-orders','Planner',[{'run_sha256':run_hash(self.base)}])
        with self.assertRaisesRegex(ValueError,'newer'):self.preview()
    def test_expired_source_stays_unknown_not_refreshed(self):
        self.inputs.update(as_of=str(TODAY-timedelta(days=2)),valid_until=str(TODAY-timedelta(days=1)))
        self.source=self.store.save(self.inputs,self.base,'expired-source-orders','Planner',[{'run_sha256':run_hash(self.base)}])
        self.assertFalse(self.preview()['can_save']);self.assertIsNone(self.preview()['months'][1]['total'])
        with self.assertRaises(ValueError):save_reuse(self.store,self.runs.__getitem__,'new-run',self.payload(),'Planner')
    def test_another_target_order_review_invalidates_open_preview(self):
        payload=self.payload()
        other={**self.inputs,'run_id':'new-run'}
        self.store.save(other,self.target,'concurrent-target-orders','Planner',[{'run_sha256':run_hash(self.target)}])
        with self.assertRaisesRegex(ValueError,'changed'):
            save_reuse(self.store,self.runs.__getitem__,'new-run',payload,'Planner')
        self.assertEqual(len(self.store.list('new-run')),1)
    def test_missing_customer_forecast_blocks_reuse_without_erasing_orders(self):
        self.inputs['customers'].append({'customer':'New customer','sku':'001','unit':'tonnes'})
        self.source=self.store.save(self.inputs,self.base,'extra-customer-source','Planner',[{'run_sha256':run_hash(self.base)}])
        report=self.preview();self.assertFalse(report['can_save'])
        self.assertIsNone(report['months'][1]['total'])
        self.assertEqual(report['months'][0]['booked'],19)
    def test_unlabelled_customer_series_are_not_reusable(self):
        self.base['metadata']={};self.target['metadata']={}
        with self.assertRaisesRegex(ValueError,'same customer'):
            self.preview()
    def test_api_choices_preview_save_export(self):
        app=FastAPI()
        @app.middleware('http')
        async def principal(request:Request,call_next):request.state.principal=None;return await call_next(request)
        listing=lambda:{'runs':[{'run_id':r['run_id'],'name':r['run_id']} for r in self.runs.values()]}
        install_sales_routes(app,self.store,None,self.runs.__getitem__,listing)
        with TestClient(app) as client:
            url='/api/sales/runs/new-run/order-reuse'
            self.assertEqual(client.get(url+'/choices').json()['sources'][0]['id'],self.source['id'])
            report=client.post(url+'/preview',json={'snapshot_id':self.source['id']});self.assertEqual(report.status_code,200)
            saved=client.post(url,json=self.payload());self.assertEqual(saved.status_code,200,saved.text)
            response=client.get('/api/sales/inputs/'+saved.json()['id']+'/export?mode=combined_demand&kind=json')
            self.assertEqual(response.status_code,200);self.assertEqual(sum(r['quantity'] for r in response.json()),87)

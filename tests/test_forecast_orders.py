"""Unified first-use workflow, with isolated synthetic sales and no external calls."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
import json
import unittest

import pandas as pd

from tests.test_sales_import_journey import SalesImportJourneyTests
from app.forecast_orders import context, reviewed
from app.sales_api import run_hash
from app.sales_demand import demand_outlook
from app.jobs import JobStore, execute_job
from app.sales_conventions import local_today


class UnifiedForecastTests(unittest.TestCase):
    setUp = SalesImportJourneyTests.setUp
    post = SalesImportJourneyTests.post
    upload = SalesImportJourneyTests.upload

    def setup_inputs(self):
        from app.order_books import OrderBooks
        from app.customers import CustomerStore
        customer_store=CustomerStore(self.orders.path.parent/'customers.sqlite3')
        self.stack.enter_context(patch.object(self.main,'ORDER_BOOKS',OrderBooks(self.orders.path.parent/'books.sqlite3',self.datasets,customer_store)))
        self.stack.enter_context(patch.object(self.main, 'SALES_STORE', self.orders))
        paths = {'/api/datasets/{dataset_id}/forecast-orders',
                 '/api/datasets/{dataset_id}/forecast-orders/preview',
                 '/api/datasets/{dataset_id}/forecast-orders/template/{role}'}
        self.client.app.router.routes.extend(r for r in self.main.app.routes if getattr(r, 'path', None) in paths)
        self.today = local_today()
        dates = pd.date_range(end=pd.Timestamp(self.today.replace(day=1))-pd.offsets.MonthBegin(), periods=36, freq='MS')
        frame = pd.DataFrame([dict(date=str(d.date()), customer=c, sku='001', quantity=q)
                              for c,q in [('A',10),('B',20),('C',5)] for d in dates])
        source = self.upload(frame, 'history')
        config = dict(name='Synthetic unified forecast', sources={'history':source['id']},
                      settings=dict(date_col='date',target_col='quantity',customer_col='customer',sku_col='sku',
                          series_mode='customer_product',unit='tonnes',frequency='monthly',horizon=2,profile='fast',
                          drivers=[],method_selection='model:Last observed',calendar_country='IR',weekend_days=[4]),
                      classification='synthetic_sample',accept_warnings=True)
        self.dataset = self.post('/api/datasets',config)
        self.path = '/api/datasets/'+self.dataset['id']+'/forecast-orders'
        loaded = self.client.get(self.path)
        self.assertEqual(loaded.status_code,200,loaded.text)
        self.initial = loaded.json()
        inputs = deepcopy(self.initial['inputs'])
        inputs.update(reviewed=True,note='Synthetic full list including customer C with no orders.',
                      order_feed='complete_snapshot',valid_until=str(self.today+timedelta(days=7)))
        inputs['orders'] = [dict(reference='A/1',customer='A',sku='001',unit='tonnes',due_date=str(self.today),
                                 ordered=16,fulfilled=2,cancelled=0,status='confirmed'),
                            dict(reference='B/1',customer='B',sku='001',unit='tonnes',due_date=str(self.today),
                                 ordered=6,fulfilled=0,cancelled=0,status='confirmed')]
        self.body = {'inputs':inputs,'request_id':'unified-synthetic-orders'}

    def stage(self, body=None):
        body = body or self.body
        report = self.post(self.path+'/preview',body)
        saved = self.post(self.path,{**body,'review_token':report['review_token']})
        return report,saved

    def test_orders_are_reviewed_before_any_model_and_every_method_publishes_combined_demand(self):
        self.setup_inputs()
        with patch('app.forecast_engine._fit_full_models_and_predict',side_effect=AssertionError('Must not fit')):
            report,saved = self.stage()
        self.assertEqual((report['customer_count'],report['order_count']),(3,2))
        self.assertNotIn('mean',json.dumps(self.initial['context']['series']))
        self.assertEqual(list(self.main.RUNS_DIR.iterdir()),[])
        self.assertEqual(saved,self.post(self.path,{**self.body,'review_token':report['review_token']}))
        for method in ['model:Last observed','model:Recent average']:
            result = self.post('/api/run-saved',{'dataset_id':self.dataset['id'], 'sales_input_id':saved['id'],'method':method})
            self.assertEqual(result['demand_summary']['total'],76)
            book = self.orders.get(result['sales_input_snapshot_id'])
            self.assertEqual(next(e['run_sha256'] for e in book['evidence'] if 'run_sha256' in e),run_hash(result))
            outlook = demand_outlook(book['inputs'],result)
            first = [r for r in outlook['rows'] if r['period']==str(self.today.replace(day=1))]
            self.assertEqual(sum(r['total'] for r in first),41)
            self.assertEqual(next(r['total'] for r in first if r['customer']=='A'),16)
            self.assertEqual(next(r['remaining'] for r in first if r['customer']=='C'),5)
            export = self.client.get('/api/sales/inputs/'+book['id']+'/export?mode=combined_demand&kind=csv')
            self.assertEqual(export.status_code,200,export.text)
            with pd.ExcelFile(self.main.RUNS_DIR/result['run_id']/'forecast_package.xlsx') as workbook:
                self.assertIn('Combined demand',workbook.sheet_names)
        self.assertEqual(self.orders.get(saved['id'])['inputs'],saved['inputs'])

    def test_unknown_orders_remain_unknown_and_new_customers_do_not_get_invented_forecasts(self):
        self.setup_inputs()
        self.body['inputs']['order_feed']='unknown'
        report,saved = self.stage()
        self.assertTrue(report['warnings'])
        result = self.post('/api/run-saved',{'dataset_id':self.dataset['id'],'sales_input_id':saved['id']})
        self.assertIsNone(result['demand_summary']['total'])
        self.assertFalse(result['demand_summary']['can_export'])
        self.assertEqual(self.client.get('/api/sales/inputs/'+result['sales_input_snapshot_id']+'/export?mode=combined_demand&kind=csv').status_code,400)
        self.body['request_id']='unified-new-customer'
        self.body['inputs']['order_feed']='complete_snapshot'
        self.body['inputs']['customers'].append(dict(customer='New',sku='001',unit='tonnes',series_id=''))
        _,saved = self.stage()
        result = self.post('/api/run-saved',{'dataset_id':self.dataset['id'],'sales_input_id':saved['id']})
        outlook = demand_outlook(self.orders.get(result['sales_input_snapshot_id'])['inputs'],result)
        self.assertTrue(all(r['total'] is None for r in outlook['rows'] if r['customer']=='New'))

    def test_directory_and_order_book_are_reused_and_versioned(self):
        from app.order_books import BookRequest
        self.setup_inputs();books=self.main.ORDER_BOOKS
        from app.customers import Customer
        books.customers.save([Customer(customer='D',products=[{'sku':'001','unit':'tonnes'}])])
        loaded=books.get(self.dataset['id'])
        self.assertIn('D',[c['customer'] for c in loaded['inputs']['customers']])
        body={k:self.body['inputs'][k] for k in ('as_of','valid_until','order_feed','orders')}
        saved=books.save(self.dataset['id'],BookRequest(version=0,**body))
        self.assertEqual(saved['version'],1);self.assertEqual(len(saved['inputs']['orders']),2)
        with self.assertRaisesRegex(ValueError,'Orders changed'):books.save(self.dataset['id'],BookRequest(version=0,**body))
        child=self.datasets.save('Updated settings',self.dataset['sources'],{**self.dataset['settings'],'horizon':3},'synthetic_sample',True,parent_dataset_id=self.dataset['id'])
        self.assertEqual(books.get(child['id'])['inputs']['orders'],saved['inputs']['orders'])

    def test_one_named_forecast_keeps_each_method_and_immutable_order_evidence(self):
        self.setup_inputs();_,saved=self.stage();group='a'*32
        for method in ['model:Last observed','model:Recent average']:
            run=self.post('/api/run-saved',{'dataset_id':self.dataset['id'],'sales_input_id':saved['id'],'method':method,'forecast_group_id':group,'forecast_name':'October demand'})
            self.assertEqual(run['forecast_group_id'],group);self.assertEqual(run['forecast_name'],'October demand')
            receipt=self.orders.get(run['sales_input_snapshot_id'])
            self.assertEqual(next(e['run_sha256'] for e in receipt['evidence'] if 'run_sha256' in e),run_hash(run))
        rows=self.main.run_list()['runs'];self.assertEqual(len(rows),2)
        self.assertEqual({r['forecast_group_id'] for r in rows},{group})
        self.assertEqual({r['name'] for r in rows},{'October demand'})
        response=self.client.post('/api/run-saved',json={'dataset_id':self.dataset['id'],'forecast_group_id':group,'forecast_name':'Invalid'})
        self.assertEqual(response.status_code,400)
        response=self.client.post('/api/run-saved',json={'dataset_id':self.dataset['id'],'sales_input_id':saved['id'],'forecast_group_id':group,'forecast_name':'Different name'})
        self.assertEqual(response.status_code,400)
        self.main.validate_forecast_group(self.main.SavedRunConfig(dataset_id=self.dataset['id'],sales_input_id=saved['id'],forecast_group_id=group,forecast_name='October demand'))

    def test_inline_settings_are_versioned_and_keep_orders_linked(self):
        self.setup_inputs()
        self.client.app.router.routes.extend(r for r in self.main.app.routes if getattr(r,'path',None)=='/api/datasets/{dataset_id}/forecast-settings')
        path='/api/datasets/'+self.dataset['id']+'/forecast-settings'
        before=deepcopy(self.datasets.get(self.dataset['id']))
        changed=self.post(path,dict(horizon=10,month_basis='gregorian',calendar_country='IR',request_id='inline-settings-test'))
        self.assertEqual(changed['parent_dataset_id'],before['id'])
        self.assertEqual(changed['settings']['horizon'],10)
        self.assertEqual(self.datasets.get(before['id']),before)
        from app.order_books import lineage
        self.assertEqual(lineage(self.datasets,changed['id']),lineage(self.datasets,before['id']))
        self.assertEqual(self.client.post(path,json=dict(horizon=0,month_basis='gregorian',calendar_country='IR',request_id='invalid-settings-test')).status_code,422)

    def test_changed_input_review_missing_customers_and_expired_orders_are_rejected(self):
        self.setup_inputs()
        report = self.post(self.path+'/preview',self.body)
        changed = deepcopy(self.body)
        changed['inputs']['orders'][0]['ordered']=999
        self.assertEqual(self.client.post(self.path,json={**changed,'review_token':report['review_token']}).status_code,400)
        incomplete = deepcopy(self.body)
        incomplete['inputs']['customers'].pop()
        self.assertEqual(self.client.post(self.path+'/preview',json=incomplete).status_code,400)
        mixed = deepcopy(self.body)
        mixed['inputs']['customers'].append(dict(customer='New',sku='001',unit='kg',series_id=''))
        self.assertEqual(self.client.post(self.path+'/preview',json=mixed).status_code,400)
        expired = deepcopy(self.body)
        expired['inputs'].update(as_of=str(self.today-timedelta(days=5)),valid_until=str(self.today-timedelta(days=1)))
        self.assertEqual(self.client.post(self.path+'/preview',json=expired).status_code,400)
        _,saved = self.stage()
        with patch('app.forecast_orders.context',return_value={**context(self.datasets,self.dataset['id']),'unit':'kg'}):
            with self.assertRaisesRegex(ValueError,'changed'):
                reviewed(self.datasets,self.orders,self.dataset['id'],saved['id'])

    def test_background_publication_hash_includes_job_identity_and_reused_orders_are_guarded(self):
        self.setup_inputs()
        _,saved = self.stage()
        ledger = JobStore(self.main.RUNS_DIR.parent/'unified-jobs.sqlite',self.main.RUNS_DIR)
        self.addCleanup(ledger.close)
        job = ledger.create({'dataset_id':self.dataset['id'],'sales_input_id':saved['id'],'method':'model:Last observed'},'Synthetic unified','unified-worker-job')
        execute_job(job['id'],store=ledger)
        complete = ledger.get(job['id'])
        self.assertEqual(complete['state'],'succeeded',complete.get('error'))
        result = self.main._load_run(complete['run_id'])
        book = self.orders.get(result['sales_input_snapshot_id'])
        self.assertEqual(next(e['run_sha256'] for e in book['evidence'] if 'run_sha256' in e),run_hash(result))
        body={'inputs':{**book['inputs'],'run_id':self.initial['context']['run_id']},
              'reuse_snapshot_id':book['id'],'request_id':'reuse-in-wizard'}
        _,reused = self.stage(body)
        self.assertEqual(reused['inputs']['orders'],book['inputs']['orders'])
        newer = self.orders.save(book['inputs'],result,'newer-unified-orders','Test',book['evidence'])
        with self.assertRaisesRegex(ValueError,'changed'):
            reviewed(self.datasets,self.orders,self.dataset['id'],reused['id'])

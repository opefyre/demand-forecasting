"""Company-bound future edits/no-factor comparisons, with reviewed mixed orders."""
from copy import deepcopy
from io import BytesIO
import unittest
import uuid
import pandas as pd

from tests import test_platform_sales as fixtures
from tests.test_company_context import VIEW
from app.company_jobs import execute_company_job
from app.company_workflows import review_scenario


class LegacyScenarioWizardTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PublicSalesTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        _,original,body=self.f.history()
        frame=pd.read_csv(BytesIO(self.f.ws.datasets.source(original['sources']['history'])[1]),dtype={'sku':str})
        frame['fx']=400000.+pd.to_datetime(frame.date).dt.month*1000.
        history=self.f.ws.datasets.upload('factor-history.csv',frame.to_csv(index=False).encode(),'history')
        body.update(name='Sales with currency',sources={'history':history['id']},request_id=str(uuid.uuid4()))
        body['settings'].update(drivers=['fx'],future_driver_policy='carry',method_selection='model:Ridge + drivers')
        self.dataset=self.f.post('/datasets',body,201)
        self.group,_=self.f.calculate(self.dataset,self.f.orders(self.dataset),['model:Ridge + drivers'])
        self.base=self.f.ws.load_run(self.group['jobs'][0]['run_id'])
        self.path='/runs/'+self.base['run_id']

    def edit(self):
        preview=self.f.get(self.path+'/assumptions')
        row=preview['rows'][0]
        payload=dict(name='Currency assumption',owner='Synthetic planner',reason='Synthetic currency shock',reviewed=True,
            request_id=str(uuid.uuid4()),definitions=[dict(factor='fx',unit='IRR per USD',geography='Iran',source='Planning assumption')],
            changes=[dict(factor='fx',item_id=row['item_id'],period=row['timestamp'],value=row['fx']*1.2)])
        saved=self.f.post(self.path+'/assumptions',payload,201)
        self.assertEqual(self.f.post(self.path+'/assumptions',payload,201)['id'],saved['id'])
        return saved

    def check_proof(self,saved):
        return review_scenario(saved,self.f.ws.datasets,self.f.ws.factors,self.f.ws.load_run,self.f.ws.live_sources,self.f.ws.profiles)

    def test_future_edit_review_orders_group_revision_exports_and_foreign_access(self):
        original=deepcopy(self.base);saved=self.edit()
        self.assertEqual(self.check_proof(saved),self.base['run_id'])
        snapshot=self.f.orders(saved)
        body=dict(name='Reviewed currency scenario',dataset_id=saved['id'],sales_input_id=snapshot['id'],
            methods=['reviewed_factors'],request_id=str(uuid.uuid4()),parent_forecast_id=self.group['id'])
        group=self.f.post('/forecasts',body,202)
        execute_company_job(self.f.ws,group['jobs'][0]['id'])
        job=self.f.get('/jobs/'+group['jobs'][0]['id']);self.assertEqual(job['state'],'succeeded',job)
        run=self.f.get('/runs/'+job['run_id'])
        self.assertEqual(run['base_run_id'],self.base['run_id'])
        self.assertEqual(run['method_selection'],self.base['method_selection'])
        demand=self.f.get('/runs/'+job['run_id']+'/demand')
        self.assertTrue(any(row['customer']=='Pars' and row['remaining']>0 for row in demand['rows']))
        self.assertTrue(any(row['customer']=='Mehr' and row['booked']>0 for row in demand['rows']))
        for kind in ['csv','xlsx','json']:
            self.assertEqual(self.f.client.get('/api/v1/runs/'+job['run_id']+'/export?mode=combined_demand&kind='+kind).status_code,200)
        self.assertEqual(self.f.ws.load_run(self.base['run_id']),original)
        self.f.company='tehran_b'
        self.assertEqual(self.f.client.get('/api/v1'+self.path+'/assumptions').status_code,404)
        self.f.permissions=VIEW.copy()
        self.assertEqual(self.f.client.get('/api/v1'+self.path+'/assumptions').status_code,403)

    def test_no_factor_review_preserves_method_and_blocks_tampered_comparison(self):
        saved=self.f.post(self.path+'/factor-comparison',dict(reviewed=True,request_id=str(uuid.uuid4())),201)
        self.assertEqual(self.check_proof(saved),self.base['run_id'])
        self.assertEqual(saved['settings']['drivers'],[])
        self.f.get('/datasets/'+saved['id']+'/orders')
        changed=deepcopy(saved);changed['settings']['horizon']=4
        with self.assertRaisesRegex(ValueError,'changed'):self.check_proof(changed)
        snapshot=self.f.orders(saved)
        group,_=self.f.calculate(saved,snapshot,['reviewed_factors'])
        run=self.f.ws.load_run(group['jobs'][0]['run_id'])
        self.assertEqual(run['scenario']['type'],'factor_comparison')
        self.assertEqual(run['method_selection'],self.base['method_selection'])

    def test_changed_sources_and_baseline_are_rejected_again_at_worker_time(self):
        saved=self.edit();changed=deepcopy(saved);changed['settings']['horizon']=4
        with self.assertRaisesRegex(ValueError,'changed'):self.check_proof(changed)
        snapshot=self.f.orders(saved)
        body=dict(name='Blocked changed factors',dataset_id=saved['id'],sales_input_id=snapshot['id'],methods=['reviewed_factors'],request_id=str(uuid.uuid4()))
        group=self.f.post('/forecasts',body,202)
        # Mutate only disposable bytes after dispatch. Revalidation must fail,
        # not replace a selected method or invent a finished forecast.
        path=self.f.ws.datasets.root/(saved['sources']['future']+'.bin')
        path.write_bytes(path.read_bytes()+b'changed')
        execute_company_job(self.f.ws,group['jobs'][0]['id'])
        self.assertEqual(self.f.get('/jobs/'+group['jobs'][0]['id'])['state'],'failed')


if __name__=='__main__':unittest.main()

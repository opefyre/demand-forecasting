"""Shared monthly/recurring contract; real scoped stores and model jobs."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import unittest
import uuid
from unittest.mock import patch

from app.company_context import personal_owner
from app.company_jobs import execute_company_job
from app.company_workflows import recurring
from app.recurring_forecasts import RecurringConfig
from tests import test_platform_sales as fixtures


class GroupedUpdateTests(unittest.TestCase):
    def setUp(self):
        vault=patch.dict('os.environ',{'DEMANDLAB_COMPANY_VAULT_KEY':'ab'*32})
        vault.start();self.addCleanup(vault.stop)
        self.f=fixtures.PublicSalesTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        from tests.test_company_context import ALL
        self.f.permissions=ALL.copy();self.f.role='admin'
        _,self.dataset,_=self.f.history()
        self.base_group,_=self.f.calculate(self.dataset,self.f.orders(self.dataset),['model:Last observed'])
        self.base=self.f.ws.load_run(self.base_group['jobs'][0]['run_id'])
        self.original=deepcopy(self.base)
        self.update=self.f.post('/forecast-updates',dict(run_id=self.base['run_id'],workflow='grouped',request_id=str(uuid.uuid4())),201)
        self.assertTrue(self.update['name'].endswith(' · R2'),self.update['name'])
        self.path='/forecast-updates/'+self.update['id']
        self.owner=personal_owner(dict(company_id=self.f.company,issuer='https://company.test',subject=self.f.subject))

    def body(self,dataset=None,snapshot=None,**changes):
        dataset=dataset or self.dataset
        snapshot=snapshot or self.f.orders(dataset)
        return dict(revision=self.update['revision'],action='calculate_group',reviewed=True,
            dataset_id=dataset['id'],sales_input_id=snapshot['id'],methods=['model:Last observed','model:Recent average'],
            name='Tehran · October revision',request_id=str(uuid.uuid4()),**changes)

    def post(self,body,status=200):
        response=self.f.client.post('/api/v1'+self.path+'/steps',json=body)
        self.assertEqual(response.status_code,status,response.text)
        return response.json()

    def finish(self,value):
        for job in value['group']['jobs']:
            execute_company_job(self.f.ws,job['id'])
        return self.f.get(self.path)

    def test_one_named_revision_two_methods_current_orders_and_three_exports(self):
        self.assertEqual(self.update['stage'],'prepared')
        old_count=len(self.f.ws.jobs.list())
        corrected=self.f.ws.datasets.upload('corrected.csv',self.f.ws.datasets.source(self.dataset['sources']['history'])[1].replace(b',Aftab,001,20\n',b',Aftab,001,26\n'),'history')
        updated=self.f.ws.datasets.save('Corrected Tehran history',{'history':corrected['id']},self.dataset['settings'],
            'synthetic_sample',True,parent_dataset_id=self.dataset['id'])
        body=self.body(updated)
        value=self.post(body)
        self.assertEqual(value['stage'],'grouped')
        self.assertEqual(len(value['group']['jobs']),2)
        self.assertEqual({j['name'] for j in value['group']['jobs']},{body['name']})
        self.assertTrue(all(j['payload']['parent_forecast_id']==self.base_group['id'] for j in value['group']['jobs']))
        self.assertTrue(all(j['payload']['sales_input_id']==body['sales_input_id'] for j in value['group']['jobs']))
        retry=self.post(body);self.assertEqual(retry['group']['id'],value['group']['id'])
        self.assertEqual(len(self.f.ws.jobs.list()),old_count+2)
        finished=self.finish(value);self.assertEqual(finished['stage'],'grouped_complete')
        self.assertEqual(self.f.get('/forecast-updates')['updates'][0]['stage'],'grouped_complete')
        for job in finished['group']['jobs']:
            self.assertEqual(job['state'],'succeeded',job)
            run=self.f.ws.load_run(job['run_id'])
            self.assertEqual(run['forecast_group_id'],value['group']['id'])
            self.assertEqual(run['forecast_order_inputs_id'],body['sales_input_id'])
            self.assertEqual(run['metadata'][next(s for s,m in run['metadata'].items() if m.get('customer')=='Aftab')]['sku'],'001')
            demand=self.f.get('/runs/'+job['run_id']+'/demand')
            current=[r for r in demand['rows'] if r['period']==str(self.f.today.replace(day=1))]
            self.assertAlmostEqual(sum(r['total'] for r in current),55)
            self.assertGreater(next(r['remaining'] for r in current if r['customer']=='Pars'),0)
            for kind in ('csv','xlsx','json'):
                response=self.f.client.get('/api/v1/runs/'+job['run_id']+'/export',params={'mode':'combined_demand','kind':kind})
                self.assertEqual(response.status_code,200)
        self.assertEqual(self.f.ws.load_run(self.base['run_id']),self.original)
        self.assertNotIn('owner',json.dumps(finished['group']))

    def test_no_calculation_without_exact_current_order_review(self):
        first=self.f.orders(self.dataset);body=self.body(snapshot=first)
        self.f.orders(self.dataset)
        self.post(body,409)
        latest=self.f.orders(self.dataset)
        body=self.body(snapshot=latest)
        with patch('app.forecast_orders.run_today',return_value=self.f.today+timedelta(days=31)):
            self.post(body,400)
        for edits in ({'reviewed':False},{'sales_input_id':None},{'methods':[]},{'name':'   '},
                      {'methods':['invented']},{'methods':['model:Last observed','model:Last observed']}):
            self.post({**body,**edits,'request_id':str(uuid.uuid4())},422 if edits.get('methods')==[] else 400)
        self.assertEqual(len(self.f.ws.jobs.list()),1)

    def test_foreign_history_owner_company_and_legacy_sequence_cannot_bypass(self):
        unrelated=self.f.ws.datasets.save('Unrelated',self.dataset['sources'],self.dataset['settings'],'synthetic_sample',True)
        self.post(self.body(unrelated),400)
        body=self.body()
        self.post({**body,'action':'calculate'},400)
        self.f.subject='different-admin'
        self.assertEqual(self.f.client.get('/api/v1'+self.path).status_code,404)
        self.f.subject='planner_a';self.f.company='tehran_b'
        self.assertEqual(self.f.client.get('/api/v1'+self.path).status_code,404)
        self.assertEqual(self.f.client.post('/api/v1'+self.path+'/steps',json=body).status_code,400)

    def test_older_local_result_without_durable_group_can_start_a_reviewed_update(self):
        with patch.object(self.f.ws.jobs,'get_group',side_effect=ValueError('Forecast not found.')):
            update=self.f.post('/forecast-updates',dict(run_id=self.base['run_id'],workflow='grouped',
                request_id='older-local-update'),201)
        self.assertIsNone(update['parent_forecast_id'])
        self.assertEqual(update['base_run_id'],self.base['run_id'])
        self.update=update;self.path='/forecast-updates/'+update['id']
        value=self.post(self.body())
        self.assertTrue(all(not j['payload'].get('parent_forecast_id') for j in value['group']['jobs']))
        self.assertEqual(self.f.ws.load_run(self.base['run_id']),self.original)

    def test_schedule_prepares_multiple_methods_without_running_until_orders_reviewed(self):
        service=recurring(self.f.ws,lambda *_:None,None)
        cfg=RecurringConfig(run_id=self.base['run_id'],request_id='grouped-schedule',day=1,months=3,
            workflow='grouped',methods=['model:Last observed','model:Recent average'],enabled=True,confirmed=True)
        schedule=service.save(self.owner,cfg)
        with patch.object(service,'authorized',return_value=True):
            cycle=service.check(schedule['id'],self.owner,datetime.now(timezone.utc))
            again=service.check(schedule['id'],self.owner,datetime.now(timezone.utc))
        self.assertEqual(cycle['state'],'review',cycle)
        self.assertEqual(cycle['stage'],'prepared')
        self.assertEqual(cycle['update_id'],again['update_id'])
        self.assertEqual(len(self.f.ws.jobs.list()),1)
        self.update=self.f.get('/forecast-updates/'+cycle['update_id']);self.path='/forecast-updates/'+cycle['update_id']
        self.assertEqual(self.update['methods'],cfg.methods)
        value=self.post(self.body())
        self.assertEqual(service.listing(self.owner)[0]['cycle']['state'],'calculating')
        self.finish(value)
        self.assertEqual(service.listing(self.owner)[0]['cycle']['state'],'review')
        with patch.object(service,'authorized',return_value=False):
            self.assertEqual(service.check(schedule['id'],self.owner)['state'],'attention')
        self.assertEqual(service.listing('another-owner'),[])


if __name__=='__main__':unittest.main()

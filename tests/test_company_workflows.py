"""Company workflow acceptance with real stores/math; never calls external AI."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch,AsyncMock
import pandas as pd
from tests import test_platform_sales as fixtures
from tests.test_company_context import ALL,VIEW
from app.company_context import personal_owner
from app.company_workflows import recurring,schedule_authorized
from app.company_jobs import execute_company_job
from app.ai_workspace import build_agent
from app.input_review import digest


class CompanyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.PublicSalesTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.f.permissions=ALL.copy();self.f.role='admin'
        _,self.dataset,_=self.f.history()
        group,_=self.f.calculate(self.dataset,self.f.orders(self.dataset),['model:Last observed'])
        self.run_id=group['jobs'][0]['run_id'];self.base=self.f.ws.load_run(self.run_id)
        self.state=None

    @property
    def owner(self):
        return personal_owner(dict(company_id=self.f.company,issuer='https://company.test',subject=self.f.subject))

    def start(self):
        self.state=self.f.post('/forecast-updates',dict(run_id=self.run_id,request_id=str(uuid.uuid4())),201)
        return self.state

    def step(self,action,**values):
        self.state=self.f.post('/forecast-updates/'+self.state['id']+'/steps',
            dict(revision=self.state['revision'],action=action,request_id=str(uuid.uuid4()),**values))
        return self.state

    def monthly_result(self):
        self.start();self.step('history',dataset_id=self.dataset['id'],reviewed=True)
        self.step('calculate',months=4,method='model:Last observed',reviewed=True)
        key=self.state['job']['id'];execute_company_job(self.f.ws,key)
        self.assertEqual(self.f.get('/jobs/'+key)['state'],'succeeded')
        self.step('calculated');self.step('no_factors',reviewed=True)
        return self.f.ws.load_run(self.state['run_id'])

    def factor(self):
        dates=pd.date_range(end=pd.Timestamp(self.f.today.replace(day=1))-pd.Timedelta(days=1),periods=39,freq='ME')
        rows=pd.DataFrame([dict(period=str(d.date()),value=100+i,published=str((d+pd.Timedelta(days=5)).date())) for i,d in enumerate(dates)])
        response=self.f.client.post('/api/v1/sources',data={'role':'factor_observations'},files={'file':('index.csv',rows.to_csv(index=False).encode(),'text/csv')})
        body=dict(source_id=response.json()['id'],name='Iran index',unit='index',geography='Iran',provider='Synthetic test',
            frequency='monthly',classification='synthetic_sample',mapping={'period':'A','value':'B','available_at':'C'},request_id=str(uuid.uuid4()))
        report=self.f.post('/factors/imports/preview',body)
        return self.f.post('/factors/imports',{**body,'review_token':report['review_token'],'reviewed':True},201)

    def link(self,factor,scope=None):
        body=dict(snapshot_id=factor['id'],lag_months=2,future_value=145,method='model:Ridge + drivers')
        if scope:body['series_ids']=scope
        path='/runs/'+self.run_id+'/factor-links'
        report=self.f.post(path+'/preview',body)
        return self.f.post(path,{**body,'reviewed':True,'review_token':report['review_token'],'request_id':str(uuid.uuid4())},201)

    def test_monthly_full_journey_fresh_orders_and_exports_are_company_and_owner_bound(self):
        original=deepcopy(self.base);run=self.monthly_result()
        choices=self.f.get('/runs/'+run['run_id']+'/order-reuse/choices')['sources']
        self.assertTrue(choices)
        self.assertTrue(all(row['id']==row['snapshot_id'] for row in choices))
        path='/forecast-updates/'+self.state['id']
        self.assertEqual(self.f.client.get('/api/v1'+path+'/export?mode=combined_demand').status_code,400)
        inputs=deepcopy(self.f.ws.sales.list(self.run_id)[0]['inputs']);inputs['run_id']=run['run_id']
        body=dict(inputs=inputs,request_id=str(uuid.uuid4()))
        review=self.f.post('/runs/'+run['run_id']+'/order-snapshots/preview',body)
        saved=self.f.post('/runs/'+run['run_id']+'/order-snapshots',{**body,'review_token':review['review_token']},201)
        self.step('orders',snapshot_id=saved['id']);report=self.state['comparison']
        self.step('review',reviewed=True,review_token=report['review_token']);self.assertTrue(self.state['ready'])
        for kind in ('csv','xlsx','json'):
            result=self.f.client.get('/api/v1'+path+'/export?mode=combined_demand&kind='+kind)
            self.assertEqual(result.status_code,200)
        self.assertEqual(self.f.ws.load_run(self.run_id),original)
        self.f.subject='other_admin';self.assertEqual(self.f.get('/forecast-updates')['updates'],[])
        self.assertEqual(self.f.client.get('/api/v1'+path).status_code,404)
        self.f.subject='planner_a';self.f.company='tehran_b'
        self.assertEqual(self.f.get('/forecast-updates')['updates'],[])
        self.assertEqual(self.f.client.get('/api/v1'+path).status_code,404)
        self.f.permissions=VIEW.copy();self.f.role='viewer'
        self.assertEqual(self.f.client.get('/api/v1/forecast-updates').status_code,403)

    def test_monthly_stale_revision_foreign_history_and_unknown_method_block(self):
        self.start();path='/api/v1/forecast-updates/'+self.state['id']+'/steps'
        body=dict(revision=0,action='history',dataset_id=self.dataset['id'],reviewed=True,request_id=str(uuid.uuid4()))
        self.f.post(path.removeprefix('/api/v1'),body)
        self.assertEqual(self.f.client.post(path,json={**body,'request_id':str(uuid.uuid4())}).status_code,400)
        self.assertEqual(self.f.client.post(path,json=dict(revision=1,action='calculate',method='unknown',reviewed=True,request_id=str(uuid.uuid4()))).status_code,400)
        self.assertEqual(len(self.f.ws.jobs.list()),1)

    def test_scoped_factor_calculation_keeps_orders_separate_and_worker_rechecks_sources(self):
        factor=self.factor();linked=self.link(factor)
        job=self.f.post('/scenario-jobs',dict(dataset_id=linked['id'],request_id=str(uuid.uuid4())),202)
        execute_company_job(self.f.ws,job['id']);complete=self.f.get('/jobs/'+job['id'])
        self.assertEqual(complete['state'],'succeeded',complete)
        calculated=self.f.ws.load_run(complete['run_id'])
        self.assertEqual(calculated['base_run_id'],self.run_id)
        self.assertTrue(calculated['forecast_rows']);self.assertEqual(self.f.ws.sales.list(calculated['run_id']),[])
        self.assertNotIn('sales_input_snapshot_id',calculated)
        second=self.f.post('/scenario-jobs',dict(dataset_id=linked['id'],request_id=str(uuid.uuid4())),202)
        with patch.object(self.f.ws.factors,'get',side_effect=ValueError('Factor evidence unavailable.')):
            execute_company_job(self.f.ws,second['id'])
        self.assertEqual(self.f.get('/jobs/'+second['id'])['state'],'failed')

    def test_factor_batch_disjoint_scopes_use_company_engine_without_inherited_orders(self):
        factor=self.factor();keys=sorted(set(self.base['series'])-{'__all__'})
        links=[self.link(factor,[key]) for key in keys[:2]]
        path='/runs/'+self.run_id+'/factor-batch'
        body=dict(dataset_ids=[r['id'] for r in links])
        report=self.f.post(path+'/preview',body)
        saved=self.f.post(path,{**body,'reviewed':True,'review_token':report['review_token'],'request_id':str(uuid.uuid4())},201)
        job=self.f.post('/scenario-jobs',dict(dataset_id=saved['id'],request_id=str(uuid.uuid4())),202)
        execute_company_job(self.f.ws,job['id']);complete=self.f.get('/jobs/'+job['id'])
        self.assertEqual(complete['state'],'succeeded',complete)
        run=self.f.ws.load_run(complete['run_id'])
        self.assertEqual(run['scenario']['type'],'factor_batch')
        for key in ('sales_input_snapshot_id','forecast_order_inputs_id','forecast_group_id'):self.assertNotIn(key,run)
        self.assertEqual(len(run['batch_evidence']),2)
        self.assertEqual(self.f.ws.sales.list(run['run_id']),[])

    def test_foreign_scenario_refs_and_baseline_bypass_are_denied(self):
        factor=self.factor();linked=self.link(factor)
        self.f.post('/scenario-jobs',dict(dataset_id=self.dataset['id'],request_id=str(uuid.uuid4())),400)
        self.f.company='tehran_b'
        for path in ('factor-links','factor-profiles','factors'):
            self.assertEqual(self.f.client.get('/api/v1/runs/'+self.run_id+'/'+path).status_code,404)
        self.f.post('/scenario-jobs',dict(dataset_id=linked['id'],request_id=str(uuid.uuid4())),404)
        self.f.company='tehran_a';self.f.permissions=VIEW.copy()
        self.f.post('/runs/'+self.run_id+'/factor-links/preview',{},403)

    def test_monthly_jobs_can_retry_without_bypassing_input_review(self):
        self.start();self.step('history',dataset_id=self.dataset['id'],reviewed=True)
        self.step('calculate',months=3,method='model:Last observed',reviewed=True)
        key=self.state['job']['id'];self.f.ws.jobs.cancel(key)
        retried=self.f.post('/jobs/'+key+'/retry',dict(request_id=str(uuid.uuid4())),202)
        self.assertEqual(retried['retry_of'],key)
        execute_company_job(self.f.ws,retried['id']);self.assertEqual(self.f.get('/jobs/'+retried['id'])['state'],'succeeded')

    def test_schedules_crud_durable_cycles_calendar_timezone_and_revoked_owner(self):
        body=dict(run_id=self.run_id,request_id=str(uuid.uuid4()),day=1,months=3,method='model:Last observed',enabled=True,confirmed=True)
        config=self.f.post('/recurring-forecasts',body,201);key=config['id']
        with patch('app.company_workflows.schedule_authorized',return_value=True):
            cycle=self.f.post('/recurring-forecasts/'+key+'/check',{})
            self.assertEqual(cycle['state'],'calculating',cycle)
            again=self.f.post('/recurring-forecasts/'+key+'/check',{})
            self.assertEqual(again['update_id'],cycle['update_id'])
            state=self.f.get('/forecast-updates/'+cycle['update_id'])
            execute_company_job(self.f.ws,state['job']['id'])
            complete=self.f.post('/recurring-forecasts/'+key+'/check',{})
            self.assertEqual(complete['stage'],'factors');self.assertEqual(complete['state'],'review')
        with patch('app.company_workflows.schedule_authorized',return_value=False):
            self.assertEqual(self.f.post('/recurring-forecasts/'+key+'/check',{})['state'],'attention')
        self.f.ws.save_site(dict(name='Tehran',province='Tehran',timezone='UTC'))
        store=recurring(self.f.ws,lambda *_:None,None)
        config=dict(config,day=2)
        with patch.object(store,'config',return_value=(self.owner,config)):
            self.assertEqual(store.check(key,now=datetime(2026,10,1,22,tzinfo=timezone.utc)),{'state':'not_due','period':'2026-10'})
        self.assertEqual(self.f.client.put('/api/v1/recurring-forecasts/'+key,json={**body,'enabled':False,'request_id':str(uuid.uuid4())}).status_code,200)
        self.assertEqual(self.f.client.delete('/api/v1/recurring-forecasts/'+key).status_code,200)
        self.assertFalse(self.f.get('/recurring-forecasts/'+key)['enabled'])
        self.f.company='tehran_b';self.assertEqual(self.f.get('/recurring-forecasts')['schedules'],[])
        self.assertEqual(self.f.client.get('/api/v1/recurring-forecasts/'+key).status_code,404)
        self.f.role='planner';self.assertEqual(self.f.client.get('/api/v1/recurring-forecasts').status_code,403)

    def test_scheduler_bridge_fails_closed_wrong_company_unavailable_or_nonboolean_grant(self):
        service=SimpleNamespace(call=AsyncMock(return_value={'allowed':True}))
        self.assertTrue(schedule_authorized(service,self.f.ws,self.owner))
        service.call.assert_awaited_once_with('schedules/authorize',dict(company_id=self.f.company,issuer='https://company.test',subject=self.f.subject))
        self.assertFalse(schedule_authorized(None,self.f.ws,self.owner))
        self.assertFalse(schedule_authorized(service,self.f.ws,json.dumps(['another','https://company.test',self.f.subject])))
        service.call.return_value={'allowed':'true'};self.assertFalse(schedule_authorized(service,self.f.ws,self.owner))
        service.call.side_effect=OSError('Unavailable');self.assertFalse(schedule_authorized(service,self.f.ws,self.owner))

    def test_queued_scheduled_job_rechecks_owner_at_execution_not_only_dispatch(self):
        body=dict(run_id=self.run_id,request_id=str(uuid.uuid4()),day=1,months=3,method='model:Last observed',enabled=True,confirmed=True)
        config=self.f.post('/recurring-forecasts',body,201)
        with patch('app.company_workflows.schedule_authorized',return_value=True):
            cycle=self.f.post('/recurring-forecasts/'+config['id']+'/check',{})
        state=self.f.get('/forecast-updates/'+cycle['update_id']);key=state['job']['id']
        with patch('app.company_workflows.schedule_authorized',return_value=False):execute_company_job(self.f.ws,key)
        job=self.f.get('/jobs/'+key)
        self.assertEqual(job['state'],'failed');self.assertIsNone(job.get('run_id'))
        self.assertEqual(len(self.f.ws.list_runs()),1)

    def test_advanced_assistant_tools_and_actions_have_live_permissions_and_private_context(self):
        ai=AsyncMock(return_value=dict(answer='Review the monthly inputs.',actions=[],run_id=self.run_id,dataset_id=None,snapshot_id=None))
        with patch('app.ai_workspace.run_chat',ai),patch('app.ai_workspace.ai_status',return_value={'ready':False}):
            self.f.post('/ai/chat',dict(question='Prepare a monthly update',run_id=self.run_id))
        tools=ai.await_args.kwargs['allowed_tools']
        self.assertTrue({'prepare_monthly_update','prepare_factor_batch','prepare_saved_orders','prepare_factor_scenario'}<=tools)
        self.assertIsNotNone(ai.await_args.kwargs['factor_batch'])
        action=dict(kind='monthly_update',run_id=self.run_id,run_sha256=digest(self.base),dataset_id=self.dataset['id'],dataset_sha256=digest(self.dataset))
        key=self.f.ws.journal.put(self.owner,dict(question='Update',answer='Review',actions=[action],run_id=self.run_id,dataset_id=None,snapshot_id=None))
        path='/ai/turns/'+key+'/actions/0'
        self.assertEqual(self.f.post(path,{})['workflow'],'monthly_update')
        self.f.permissions.remove('forecasts:run');self.f.post(path,{},403)
        self.f.permissions=ALL.copy();self.f.company='tehran_b';self.f.post(path,{},400)

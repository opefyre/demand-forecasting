"""Exercise the public sales pipeline with two isolated companies, no live calls."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
import json
import unittest
import uuid
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.company_workspace import CompanyWorkspaces
from app.platform_api import create_platform_api
from app.company_jobs import execute_company_job
from app.sales_conventions import local_today
from app.sales_api import run_hash
from app.demand_releases import identity
from tests.test_sales_demand import fixture


ALL = ['inputs:read','inputs:write','customers:read','customers:write','orders:read','orders:write',
       'factors:read','factors:write','drafts:read','forecasts:run','forecasts:write',
       'reports:read','reports:export','releases:approve']


class PublicSalesTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspaces = CompanyWorkspaces(self.root / 'companies')
        self.company, self.subject, self.role, self.permissions = 'tehran_a', 'planner_a', 'planner', ALL.copy()
        self.dispatched = []
        self.app = FastAPI()
        @self.app.middleware('http')
        async def identity_middleware(request: Request, next):
            # Identity bridge/CSRF is separately exercised by test_platform_access.
            request.state.principal = {'company_id':self.company,'issuer':'https://company.test',
                'subject':self.subject,'role':self.role,'permissions':self.permissions,
                'mfa_required':False,'auth_kind':'api_key'}
            return await next(request)
        self.api = create_platform_api(None, self.workspaces,
            dispatcher=lambda ws, key: self.dispatched.append((ws.company_id,key)))
        self.app.mount('/api/v1', self.api)
        self.client = TestClient(self.app)
        self.today = local_today()

    def tearDown(self):
        self.client.close()
        self.workspaces.close()
        self.temp.cleanup()

    @property
    def ws(self):
        return self.workspaces.for_principal({'company_id':self.company})

    def get(self, path):
        result = self.client.get('/api/v1'+path)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def post(self, path, body, status=200):
        result = self.client.post('/api/v1'+path, json=body)
        self.assertEqual(result.status_code, status, result.text)
        return result.json()

    def history(self, multiplier=1, calendar='gregorian'):
        dates = pd.date_range(end=pd.Timestamp(self.today.replace(day=1))-pd.offsets.MonthBegin(), periods=36, freq='MS')
        if calendar == 'jalali':
            from app.sales_conventions import month_range, shift_month, period_start
            from persiantools.jdatetime import JalaliDate
            dates = month_range(shift_month(period_start(self.today,'jalali'),-36,'jalali'),periods=36,basis='jalali')
        rows = [dict(date=str(d.date()), customer=c, sku=sku, quantity=q*multiplier)
            for c,sku,q in [('Mehr','001',10),('Aftab','001',20),('Pars','002',5),('Negin','002',8)] for d in dates]
        if calendar == 'jalali':
            for row in rows:
                row['date'] = str(JalaliDate(pd.Timestamp(row['date']).date()))
        response = self.client.post('/api/v1/sources', data={'role':'history'},
            files={'file':('sales.csv', pd.DataFrame(rows).to_csv(index=False).encode(),'text/csv')})
        self.assertEqual(response.status_code,201,response.text)
        source = response.json()
        for customer,sku in [('Mehr','001'),('Aftab','001'),('Pars','002'),('Negin','002')]:
            self.post('/customers', {'customer':customer,'products':[{'sku':sku,'unit':'tonnes'}]},201)
        body = dict(name='Tehran monthly sales', sources={'history':source['id']},
            settings=dict(date_col='date',target_col='quantity',customer_col='customer',sku_col='sku',
                series_mode='customer_product',unit='tonnes',frequency='monthly',horizon=3,profile='fast',
                drivers=[],method_selection='model:Last observed',calendar_country='IR',weekend_days=[4],
                sales_measure='customer_demand',month_basis=calendar,history_calendar=calendar,history_grain='monthly_totals'),
            classification='synthetic_sample',accept_warnings=True,request_id=str(uuid.uuid4()))
        self.post('/datasets/preview',body)
        return source, self.post('/datasets',body,201), body

    def orders(self, dataset, *, unknown=False):
        path='/datasets/'+dataset['id']+'/orders'
        inputs=self.get(path)['inputs']
        inputs.update(reviewed=True,note='Synthetic complete customer order review.',
            valid_until=str(self.today+timedelta(days=30)),order_feed='unknown' if unknown else 'complete_snapshot')
        inputs['orders']=[dict(reference='Mehr-001',customer='Mehr',sku='001',unit='tonnes',
            due_date=str(self.today),ordered=16,fulfilled=2,cancelled=0,status='confirmed'),
            dict(reference='Aftab-001',customer='Aftab',sku='001',unit='tonnes',
            due_date=str(self.today),ordered=6,fulfilled=0,cancelled=0,status='confirmed')]
        body={'inputs':inputs,'request_id':str(uuid.uuid4())}
        report=self.post(path+'/preview',body)
        return self.post(path+'/snapshots',{**body,'review_token':report['review_token']},201)

    def calculate(self, dataset, snapshot, methods=None):
        body={'name':'Autumn customer demand','dataset_id':dataset['id'],'sales_input_id':snapshot['id'],
              'methods':methods or ['model:Last observed','model:Recent average'],'request_id':str(uuid.uuid4())}
        group=self.post('/forecasts',body,202)
        for job in group['jobs']:
            execute_company_job(self.ws,job['id'])
        complete=self.get('/forecasts/'+group['id'])
        self.assertTrue(all(job['state']=='succeeded' for job in complete['jobs']),complete)
        return complete,body

    def test_two_companies_grouped_models_orders_and_exports_use_only_their_own_data(self):
        import app.main as main
        source_a, dataset_a, _ = self.history()
        snapshot_a = self.orders(dataset_a)
        # Any legacy store access would fail this actual engine calculation.
        with patch.object(main.DATASET_STORE,'get',side_effect=AssertionError('Unscoped data access')), \
             patch.object(main.SALES_STORE,'get',side_effect=AssertionError('Unscoped orders access')):
            group_a,body_a=self.calculate(dataset_a,snapshot_a)
        self.assertEqual(len(self.get('/forecasts')['forecasts']),1)
        self.assertEqual(len(group_a['jobs']),2)
        self.assertEqual(self.get('/sources')['total'],1)
        self.assertIn('model:Last observed',[row['id'] for row in self.get('/forecast-methods')['methods']])
        self.assertEqual({j['payload']['forecast_name'] for j in group_a['jobs']},{body_a['name']})
        self.assertEqual(self.post('/forecasts',body_a,202)['id'],group_a['id'])
        self.assertNotIn('owner',json.dumps(group_a))
        first=group_a['jobs'][0]['run_id']
        value=self.get('/runs/'+first)
        self.assertEqual(value['site']['province'],'Tehran')
        receipt=self.ws.sales.get(value['sales_input_snapshot_id'])
        raw=self.ws.load_run(first)
        self.assertEqual(next(e['run_sha256'] for e in receipt['evidence'] if 'run_sha256' in e),run_hash(raw))
        result=self.get('/runs/'+first+'/demand')
        current=[r for r in result['rows'] if r['period']==str(self.today.replace(day=1))]
        self.assertEqual(sum(r['total'] for r in current),49)
        self.assertEqual(next(r['remaining'] for r in current if r['customer']=='Pars'),5)
        self.assertEqual(next(r['remaining'] for r in current if r['customer']=='Mehr'),0)
        self.assertEqual(len(self.get('/runs/'+first+'/demand?customer=Pars&sku=002')['rows']),3)
        for kind in ['csv','xlsx','json']:
            response=self.client.get('/api/v1/runs/'+first+'/export',params={'mode':'combined_demand','kind':kind})
            self.assertEqual(response.status_code,200,response.text[:200] if kind!='xlsx' else 'xlsx')
            self.assertTrue(response.content)
        for kind in ['csv','xlsx','models','drivers']:
            response=self.client.get('/api/v1/runs/'+first+'/files/'+kind)
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.content)
        export=self.client.get('/api/v1/runs/'+first+'/export?mode=combined_demand&kind=json&customer=Pars&sku=002')
        self.assertEqual(export.status_code,200,export.text)
        self.assertEqual({r['customer'] for r in export.json()},{'Pars'})
        self.assertEqual(len(export.json()),3)
        self.assertEqual(self.client.get('/api/v1/runs/'+first+'/export?mode=combined_demand&customer=Missing').status_code,400)
        self.assertEqual(self.ws.sales.get(snapshot_a['id']),snapshot_a)
        self.company='tehran_b'
        for path in ['/datasets/'+dataset_a['id'],'/sources/'+source_a['id'],
                '/order-snapshots/'+snapshot_a['id'],'/forecasts/'+group_a['id'],'/jobs/'+group_a['jobs'][0]['id'],'/runs/'+first]:
            self.assertEqual(self.client.get('/api/v1'+path).status_code,404,path)
        self.assertEqual(self.get('/forecasts')['forecasts'],[])
        _,dataset_b,_=self.history(2)
        snapshot_b=self.orders(dataset_b)
        group_b,_=self.calculate(dataset_b,snapshot_b,['model:Last observed'])
        demand_b=self.get('/runs/'+group_b['jobs'][0]['run_id']+'/demand')
        self.assertEqual(sum(r['total'] for r in demand_b['rows'] if r['period']==str(self.today.replace(day=1))),86)
        self.company='tehran_a'
        self.assertEqual(len(self.get('/forecasts')['forecasts']),1)
        self.assertEqual(self.client.get('/api/v1/runs/'+group_b['jobs'][0]['run_id']).status_code,404)

    def test_customer_order_book_versions_and_review_guard(self):
        _,dataset,_=self.history()
        path='/datasets/'+dataset['id']+'/orders'
        book=self.get(path)
        self.assertEqual(len(book['inputs']['customers']),4)
        body={k:book['inputs'][k] for k in ('as_of','valid_until','order_feed','orders')}
        body.update(version=0,order_feed='complete_snapshot')
        response=self.client.put('/api/v1'+path,json=body)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['version'],1)
        self.assertEqual(self.client.put('/api/v1'+path,json=body).status_code,409)
        snapshot=self.orders(dataset)
        wrong={'name':'Wrong orders','dataset_id':dataset['id'],'sales_input_id':snapshot['id'],
               'methods':['model:Last observed','model:Last observed'],'request_id':str(uuid.uuid4())}
        self.assertEqual(self.client.post('/api/v1/forecasts',json=wrong).status_code,400)
        self.assertEqual(self.get('/forecasts')['forecasts'],[])
        self.assertEqual(self.client.post('/api/v1/forecasts',json={**wrong,'company_id':'another'}).status_code,422)

    def test_viewer_and_approver_permissions_do_not_expose_private_inputs_or_allow_calculation(self):
        _,dataset,_=self.history()
        self.permissions=['reports:read','reports:export']
        self.role='viewer'
        for path in ['/sources','/datasets','/forecasts','/datasets/'+dataset['id']+'/orders','/factors']:
            self.assertEqual(self.client.get('/api/v1'+path).status_code,403,path)
        self.assertEqual(self.get('/releases')['releases'],[])
        self.assertEqual(self.client.post('/api/v1/forecasts',json={'name':'Blocked','dataset_id':dataset['id'],
            'sales_input_id':'a'*32,'methods':['model:Last observed'],'request_id':'viewer-blocked'}).status_code,403)
        self.role='approver';self.permissions+=['drafts:read','releases:approve']
        self.assertEqual(self.get('/forecasts')['forecasts'],[])
        self.assertEqual(self.client.post('/api/v1/forecasts',json={'name':'Blocked','dataset_id':dataset['id'],
            'sales_input_id':'a'*32,'methods':['model:Last observed'],'request_id':'approver-blocked'}).status_code,403)

    def test_unknown_order_coverage_blocks_final_export(self):
        _,dataset,_=self.history()
        snapshot=self.orders(dataset,unknown=True)
        group,_=self.calculate(dataset,snapshot,['model:Last observed'])
        key=group['jobs'][0]['run_id']
        self.assertIsNone(self.get('/runs/'+key)['demand_summary']['total'])
        self.assertEqual(self.client.get('/api/v1/runs/'+key+'/export?mode=combined_demand&kind=json').status_code,400)

    def test_atomic_group_creation_under_concurrent_retries_and_cancel(self):
        _,dataset,_=self.history()
        snapshot=self.orders(dataset)
        body={'name':'Same forecast','dataset_id':dataset['id'],'sales_input_id':snapshot['id'],
              'methods':['model:Last observed','model:Recent average'],'request_id':'concurrent-forecast'}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.client.post('/api/v1/forecasts',json=body),range(2)))
        self.assertTrue(all(r.status_code==202 for r in results),[r.text for r in results])
        self.assertEqual(results[0].json()['id'],results[1].json()['id'])
        self.assertEqual(len(self.get('/forecasts')['forecasts']),1)
        self.assertEqual(len(self.ws.jobs.queued()),2)
        self.assertEqual(self.client.post('/api/v1/forecasts',json={**body,'name':'Changed'}).status_code,400)
        for job in results[0].json()['jobs']:
            self.post('/jobs/'+job['id']+'/cancel',{})
            execute_company_job(self.ws,job['id'])
            self.assertEqual(self.get('/jobs/'+job['id'])['state'],'cancelled')
        self.assertEqual(self.ws.list_runs(),[])

    def test_independent_approval_viewer_report_access_and_cross_company_release_denial(self):
        # Existing release maths is exercised with a known frozen result, avoiding
        # a second model fit in permission-only checks.
        value,inputs=fixture()
        key='a'*12;value['run_id']=key;inputs['run_id']=key
        folder=self.ws.runs/key;folder.mkdir()
        (folder/'result.json').write_text(json.dumps(value))
        snapshot=self.ws.sales.save(inputs,value,'company-release-snapshot',identity({'issuer':'company','subject':'planner'}),
            [{'run_sha256':run_hash(value)}])
        body={'snapshot_id':snapshot['id'],'receiver':'Client ERP','mode':'combined_demand','request_id':'company-release-request'}
        with patch('app.sales_demand.run_today',return_value=pd.Timestamp(inputs['as_of']).date()):
            report=self.post('/releases/preview',body)
            record=self.post('/releases',{**body,'review_token':report['review_token'],'reviewed':True},201)
            approval={'review_token':record['report']['review_token'],'reviewed':True}
            self.assertEqual(self.client.post('/api/v1/releases/'+record['id']+'/approve',json=approval).status_code,403)
            self.role='viewer';self.permissions=['reports:read','reports:export']
            self.assertEqual(self.get('/releases')['releases'],[])
            self.assertEqual(self.client.get('/api/v1/releases/'+record['id']).status_code,404)
            self.role='approver';self.subject='reviewer_b';self.permissions+=['drafts:read','releases:approve']
            self.post('/releases/'+record['id']+'/approve',approval)
            self.role='viewer';self.permissions=['reports:read','reports:export']
            self.assertEqual(len(self.get('/releases')['releases']),1)
            self.assertEqual(self.client.get('/api/v1/releases/'+record['id']+'/export?kind=json').status_code,200)
            self.company='tehran_b'
            self.assertEqual(self.client.get('/api/v1/releases/'+record['id']).status_code,404)

    def test_api_documentation_describes_bearer_for_business_routes(self):
        schema=self.get('/openapi.json')
        self.assertIn({'ApiKey':[]},schema['paths']['/forecasts']['post']['security'])
        self.assertEqual(schema['paths']['/members']['get']['security'],[{'BrowserSession':[]}])

    def test_reviewed_factor_inputs_are_company_scoped_frozen_and_used_by_the_engine(self):
        _,dataset,_=self.history()
        dates=pd.date_range(end=pd.Timestamp(self.today.replace(day=1))-pd.Timedelta(days=1),periods=39,freq='ME')
        frame=pd.DataFrame([dict(period=str(d.date()),value=100+i,
            published=str((d+pd.Timedelta(days=5)).date())) for i,d in enumerate(dates)])
        response=self.client.post('/api/v1/sources',data={'role':'factor_observations'},
            files={'file':('inflation.csv',frame.to_csv(index=False).encode(),'text/csv')})
        self.assertEqual(response.status_code,201,response.text)
        body=dict(source_id=response.json()['id'],name='Inflation index',unit='index points',
            geography='Iran · national',provider='Synthetic test',frequency='monthly',classification='synthetic_sample',
            mapping={'period':'A','value':'B','available_at':'C'},request_id=str(uuid.uuid4()))
        review=self.post('/factors/imports/preview',body)
        factor=self.post('/factors/imports',{**body,'review_token':review['review_token'],'reviewed':True},201)
        self.assertEqual(len(self.get('/factors')['snapshots']),1)
        path='/datasets/'+dataset['id']+'/factors'
        self.assertIn(factor['id'],[r['id'] for r in self.get(path)['snapshots']])
        selection={'snapshot_id':factor['id'],'lag_months':2,'future_value':145,'method':'model:Ridge + drivers'}
        preview=self.post(path+'/preview',selection)
        linked=self.post(path,{**selection,'review_token':preview['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())},201)
        self.assertEqual(linked['parent_dataset_id'],dataset['id'])
        self.assertEqual(self.ws.datasets.get(dataset['id'])['settings']['drivers'],[])
        self.assertTrue(linked['settings']['drivers'])
        snapshot=self.orders(linked)
        group,_=self.calculate(linked,snapshot,['model:Ridge + drivers'])
        value=self.get('/runs/'+group['jobs'][0]['run_id'])
        self.assertTrue(value['input_manifest']['settings']['factor_definitions'])
        for column in linked['settings']['drivers']:
            self.assertTrue(all(column in row and row[column] > 0 for row in value['forecast_rows']))
        self.assertEqual(value['input_manifest']['import_provenance']['type'],'forecast_factors')
        self.company='tehran_b'
        self.assertEqual(self.get('/factors')['snapshots'],[])
        self.assertEqual(self.client.get('/api/v1/factors/'+factor['id']).status_code,404)
        self.assertEqual(self.client.get('/api/v1/datasets/'+linked['id']).status_code,404)

    def test_wrong_source_role_and_foreign_source_are_not_accepted_as_history(self):
        source,dataset,body=self.history()
        self.company='tehran_b'
        self.assertEqual(self.client.post('/api/v1/datasets',json=body).status_code,404)
        self.company='tehran_a'
        response=self.client.post('/api/v1/sources',data={'role':'future'},
            files={'file':('future.csv',b'date,qty\n2026-10-01,10\n','text/csv')})
        self.assertEqual(response.status_code,201,response.text)
        wrong={**body,'sources':{'history':response.json()['id']},'request_id':str(uuid.uuid4())}
        self.assertEqual(self.client.post('/api/v1/datasets',json=wrong).status_code,400)
        self.assertEqual(len(self.get('/datasets')['datasets']),1)
        self.assertEqual(self.post('/datasets',body,201)['id'],dataset['id'])

    def test_stale_order_reviews_cannot_start_a_new_forecast(self):
        _,dataset,_=self.history()
        old=self.orders(dataset)
        newer=self.orders(dataset)
        body={'name':'Stale forecast','dataset_id':dataset['id'],'sales_input_id':old['id'],
            'methods':['model:Last observed'],'request_id':str(uuid.uuid4())}
        self.assertEqual(self.client.post('/api/v1/forecasts',json=body).status_code,409)
        self.assertEqual(self.get('/forecasts')['forecasts'],[])
        self.assertEqual(self.post('/forecasts',{**body,'sales_input_id':newer['id']},202)['jobs'][0]['state'],'queued')

    def test_worker_recovery_staging_gate_and_symlink_guards(self):
        from app.jobs import LEASE_SECONDS
        from app.company_jobs import recover_companies
        import time
        job=self.ws.jobs.create({'dataset_id':'unused'},'Interrupted','interrupted-company-job')
        self.ws.jobs.claim(job['id'])
        self.ws.jobs.recover(time.time()+LEASE_SECONDS+1)
        self.assertEqual(self.ws.jobs.get(job['id'])['state'],'interrupted')
        recover_companies(self.workspaces)
        foreign=self.root/'outside';foreign.mkdir()
        (self.ws.runs/('a'*12)).symlink_to(foreign,target_is_directory=True)
        (foreign/'result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'not found'):
            self.ws.load_run('a'*12)
        self.assertEqual(self.ws.list_runs(),[])
        with self.assertRaises(ValueError):
            self.workspaces.for_principal({'company_id':'../other'})
        self.assertEqual(self.client.get('/api/v1/runs/../../other').status_code,404)

    def test_persian_month_forecast_orders_and_export_keep_real_boundaries(self):
        from persiantools.jdatetime import JalaliDate
        _,dataset,_=self.history(calendar='jalali')
        snapshot=self.orders(dataset)
        group,_=self.calculate(dataset,snapshot,['model:Last observed'])
        key=group['jobs'][0]['run_id']
        value=self.get('/runs/'+key+'/demand')
        self.assertEqual(value['planning_calendar'],'jalali')
        current=JalaliDate(self.today)
        label=f'{current.year}-{current.month:02d}'
        rows=[r for r in value['rows'] if r['period_label']==label]
        self.assertEqual(sum(r['total'] for r in rows),49)
        response=self.client.get('/api/v1/runs/'+key+'/export?mode=combined_demand&kind=json&customer=Mehr')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()[0]['period_label'],label)
        self.assertEqual(response.json()[0]['planning_calendar'],'jalali')

    def test_group_write_failure_rolls_back_every_method(self):
        store=self.ws.jobs
        payloads=[{'method':'model:Last observed'},{'method':'model:Recent average'}]
        insert=store.jobs.insert
        with patch.object(store.jobs,'insert',side_effect=[insert(),ValueError('Simulated storage failure')]):
            with self.assertRaisesRegex(ValueError,'Simulated'):
                store.create_group(payloads,'Never partial','atomic-rollback-test')
        self.assertEqual(store.list_groups(),[])
        self.assertEqual(store.queued(),[])

    def test_scoped_worker_cannot_fall_back_to_legacy_order_finalization(self):
        from app.jobs import execute_job
        from app.runtime import output_directory
        store=self.ws.jobs
        job=store.create({'sales_input_id':'a'*32},'Fail closed','worker-finalizer-test')
        def executor(payload):
            folder=output_directory(self.ws.runs)/('a'*12)
            folder.mkdir()
            return {'run_id':'a'*12}
        with self.assertLogs('app.jobs',level='ERROR'):
            execute_job(job['id'],store,executor)
        self.assertEqual(store.get(job['id'])['state'],'failed')
        self.assertIn('scoped order finalizer',store.get(job['id'])['error'])
        self.assertEqual(self.ws.list_runs(),[])


if __name__ == '__main__':
    unittest.main()

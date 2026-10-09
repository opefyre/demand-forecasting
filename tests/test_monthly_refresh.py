"""Complete local update journey; real numerical engine/stores, no OpenAI calls."""
import asyncio
from copy import deepcopy
from datetime import date,timedelta
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from unittest.mock import patch,MagicMock

import pandas as pd
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from agents.tool_context import ToolContext

from app.datasets import DatasetStore
from app.jobs import JobStore
from app.monthly_refresh import MonthlyRefresh,StartUpdate,UpdateStep,install_monthly_refresh
from app.sales_api import install_sales_routes,run_hash
from app.sales_demand import DemandStore,demand_outlook,export_demand
from app.ai_workspace import build_agent,AIJournal,install_ai_routes


class MonthlyTests(unittest.TestCase):
    def setUp(self):
        import app.main as main
        self.main=main;self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.runs=self.root/'runs';self.runs.mkdir()
        self.datasets=DatasetStore(self.root/'datasets');self.sales=DemandStore(self.root/'sales.sqlite')
        self.jobs=JobStore(self.root/'jobs.sqlite',self.runs);self.addCleanup(self.jobs.close)
        dates=pd.date_range(end=pd.Timestamp(date.today().replace(day=1))-pd.offsets.MonthBegin(1),periods=30,freq='MS')
        self.history=('date,item,customer,sku,qty\n'+''.join(f'{d.date()},{c}/P,{c},0001,{quantity}\n' for d in dates for c,quantity in [('A',10),('B',8)])).encode()
        file=self.datasets.upload('monthly.csv',self.history,'history')
        settings={'date_col':'date','target_col':'qty','item_col':'item','customer_col':'customer','sku_col':'sku',
            'frequency':'monthly','horizon':3,'unit':'tonnes','profile':'deep','method_selection':'model:Last observed',
            'missing_strategy':'auto','outlier_strategy':'none','history_calendar':'gregorian','month_basis':'gregorian',
            'history_grain':'monthly_totals','sales_measure':'customer_demand','returns_policy':'reject'}
        self.source=self.datasets.save('Synthetic monthly sales',{'history':file['id']},settings,'synthetic_sample',True)
        self.patch_store=patch.object(main,'DATASET_STORE',self.datasets);self.patch_store.start();self.addCleanup(self.patch_store.stop)
        self.patch_runs=patch.object(main,'RUNS_DIR',self.runs);self.patch_runs.start();self.addCleanup(self.patch_runs.stop)
        self.base=self.calculate(self.source['id'])
        app=FastAPI()
        @app.middleware('http')
        async def actor(request:Request,call_next):
            request.state.principal={'issuer':'test','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        outlook=install_sales_routes(app,self.sales,self.datasets,main._load_run)
        self.submit=MagicMock(side_effect=lambda payload,name,key:self.jobs.create(payload,name,key))
        self.live=MagicMock();self.live.listing.return_value={'sources':[{'id':'supply','name':'Global supply','enabled':True,'status':'failed','series':[],'error':'Cooling down'}]}
        self.service=MonthlyRefresh(self.root/'updates.sqlite',self.datasets,main._load_run,self.sales,outlook,self.jobs,self.submit,self.live)
        install_monthly_refresh(app,self.service)
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.actor=json.dumps(['test','alice']);self.counter=0
        started=self.client.post('/api/forecast-updates',json={'run_id':self.base['run_id'],'request_id':'start-monthly'})
        self.assertEqual(started.status_code,200,started.text)
        self.state=started.json()
        self.assertEqual(self.state['stage'],'history',self.state)

    def calculate(self,key,method='model:Last observed',**kw):
        return asyncio.run(self.main.run_saved(self.main.SavedRunConfig(dataset_id=key,method=method,**kw)))

    def step(self,action,**kw):
        self.counter+=1
        payload={'revision':self.state['revision'],'action':action,'request_id':'step-'+str(self.counter).zfill(8),**kw}
        response=self.client.post('/api/forecast-updates/'+self.state['id']+'/steps',json=payload)
        self.assertEqual(response.status_code,200,response.text);self.state=response.json();return self.state

    def forecast(self,skip_factors=True):
        self.step('history',dataset_id=self.source['id'],reviewed=True)
        self.step('calculate',months=3,method='model:Last observed',reviewed=True)
        job=self.jobs.get(self.state['job_id']);owner=self.jobs.claim(job['id'])
        new=self.calculate(job['payload']['dataset_id'])
        self.jobs.begin_publish(job['id'],owner,new['run_id']);self.jobs.finish(job['id'],owner,'succeeded')
        self.step('calculated')
        if skip_factors:self.step('no_factors',reviewed=True)
        return new

    def orders(self,run,request='new-orders',**kw):
        today=date.today();inputs={'name':'Reviewed synthetic orders','run_id':run['run_id'],'classification':'synthetic_sample',
            'as_of':str(today),'valid_until':str(today+timedelta(days=7)),'order_feed':'complete_snapshot',
            'customers':[{'customer':c,'sku':'0001','unit':'tonnes','series_id':c+'/P'} for c in ['A','B']],
            'orders':[{'reference':'A/1','customer':'A','sku':'0001','unit':'tonnes','due_date':str(today),
                       'ordered':14,'fulfilled':2,'cancelled':0,'status':'confirmed'}],
            'commitments':[],'reviewed':True,'note':'All known orders checked.',**kw}
        return self.sales.save(inputs,run,request,self.actor,[{'run_sha256':run_hash(run)}])

    def test_full_journey_exports_match_partial_orders_without_double_counting(self):
        original=deepcopy(self.source);new=self.forecast();saved=self.orders(new)
        self.step('orders',snapshot_id=saved['id'])
        report=self.state['comparison'];self.assertEqual(report['overlapping_rows'],6)
        self.assertEqual((report['overlap_before'],report['overlap_after']),(54,54))
        self.assertEqual(report['rows'][0]['after_to_serve'],12) # A 14, fulfilled 2; forecast 10 already consumed
        self.assertEqual(report['rows'][1]['after_to_serve'],10)
        self.step('review',reviewed=True,review_token=report['review_token']);self.assertTrue(self.state['ready'])
        outlook=self.service.fresh_orders(self.service.get(self.state['id'],self.actor))
        for mode,total in [('combined_demand',56),('remaining_forecast',44)]:
            for kind in ['csv','json','xlsx']:
                response=self.client.get(f'/api/forecast-updates/{self.state["id"]}/export?mode={mode}&kind={kind}')
                self.assertEqual(response.status_code,200,response.text[:120] if kind!='xlsx' else '')
                if kind=='json':rows=response.json()
                elif kind=='csv':rows=pd.read_csv(BytesIO(response.content)).to_dict('records')
                else:rows=pd.read_excel(BytesIO(response.content),sheet_name=0).to_dict('records')
                self.assertAlmostEqual(sum(row['quantity'] for row in rows),total)
        self.assertEqual(self.datasets.get(original['id']),original)
        self.assertEqual(self.datasets.source(original['sources']['history'])[1],self.history)
        self.assertEqual(self.main._load_run(self.base['run_id']),self.base)
        self.live.refresh.assert_not_called();self.assertEqual(len(self.jobs.list()),1)

    def test_owner_concurrency_exact_retries_and_sequence(self):
        path='/api/forecast-updates/'+self.state['id']
        self.assertEqual(self.client.get(path,headers={'actor':'bob'}).status_code,400)
        self.assertEqual(self.client.get('/api/forecast-updates',headers={'actor':'bob'}).json()['updates'],[])
        bad={'revision':0,'action':'no_factors','reviewed':True,'request_id':'wrong-step'}
        self.assertEqual(self.client.post(path+'/steps',json=bad).status_code,400)
        payload={**bad,'action':'history','dataset_id':self.source['id'],'request_id':'exact-retry'}
        first=self.client.post(path+'/steps',json=payload);self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post(path+'/steps',json=payload).json(),first.json())
        self.assertEqual(self.client.post(path+'/steps',json={**payload,'reviewed':False}).status_code,400)
        self.assertEqual(self.client.post(path+'/steps',json={**payload,'request_id':'stale-view'}).status_code,400)
        self.assertEqual(self.client.post(path+'/steps',json={**payload,'revision':'1'}).status_code,422)
        resumed=MonthlyRefresh(self.root/'updates.sqlite',self.datasets,self.main._load_run,self.sales,self.service.outlook,self.jobs,self.submit)
        self.assertEqual(resumed.get(self.state['id'],self.actor)['stage'],'forecast')

    def test_changed_and_foreign_history_and_method_block_without_job(self):
        foreign=self.datasets.save('Unrelated',self.source['sources'],self.source['settings'],'synthetic_sample',True)
        path='/api/forecast-updates/'+self.state['id']+'/steps'
        payload={'revision':0,'action':'history','reviewed':True,'request_id':'foreign-data','dataset_id':foreign['id']}
        self.assertEqual(self.client.post(path,json=payload).status_code,400)
        self.step('history',dataset_id=self.source['id'],reviewed=True)
        payload={'revision':1,'action':'calculate','reviewed':True,'request_id':'bad-method','method':'invented','months':3}
        self.assertEqual(self.client.post(path,json=payload).status_code,400);self.submit.assert_not_called()
        self.assertEqual(self.client.post(path,json={**payload,'method':'recommended','reviewed':'true'}).status_code,422)

    def test_latest_orders_expiry_and_review_token_rechecked(self):
        run=self.forecast();saved=self.orders(run);self.step('orders',snapshot_id=saved['id'])
        report=self.state['comparison'];path='/api/forecast-updates/'+self.state['id']+'/steps'
        payload={'revision':self.state['revision'],'action':'review','reviewed':True,'review_token':'tampered','request_id':'wrong-token'}
        self.assertEqual(self.client.post(path,json=payload).status_code,400)
        self.step('review',reviewed=True,review_token=report['review_token'])
        export_path='/api/forecast-updates/'+self.state['id']+'/export?mode=combined_demand&kind=csv'
        self.assertEqual(self.client.get(export_path).status_code,200)
        newer=self.orders(run,'newer-orders');view=self.client.get('/api/forecast-updates/'+self.state['id']).json()
        self.assertEqual(self.client.get(export_path).status_code,400)
        self.assertEqual(self.client.get(export_path,headers={'actor':'bob'}).status_code,400)
        self.assertFalse(view['ready']);self.assertIn('Orders changed',view['attention'])
        self.step('orders',snapshot_id=newer['id']);self.step('review',reviewed=True,review_token=self.state['comparison']['review_token'])
        with patch('app.sales_demand.run_today',return_value=date.today()+timedelta(days=8)):
            view=self.client.get('/api/forecast-updates/'+self.state['id']).json()
            self.assertFalse(view['ready']);self.assertIn('expired',view['attention'])
            self.assertEqual(self.client.get(export_path).status_code,400)

    def test_changed_forecast_blocks_resume_review(self):
        run=self.forecast();saved=self.orders(run);self.step('orders',snapshot_id=saved['id'])
        run['series']['A/P']['forecast'][0]['timestamp']='2099-01-01'
        (self.runs/run['run_id']/'result.json').write_text(json.dumps(run))
        self.assertIn('forecast changed',self.client.get('/api/forecast-updates/'+self.state['id']).json()['attention'])

    def test_reviewed_replacement_and_shifted_horizon_only_compare_matching_months(self):
        new_row=f'{date.today().replace(day=1)},A/P,A,0001,16\n{date.today().replace(day=1)},B/P,B,0001,8\n'.encode()
        file=self.datasets.upload('updated.csv',self.history+new_row,'history')
        source=self.datasets.save('New history',{'history':file['id']},self.source['settings'],'synthetic_sample',True,parent_dataset_id=self.source['id'])
        self.step('history',dataset_id=source['id'],reviewed=True)
        self.step('calculate',months=3,method='model:Last observed',reviewed=True)
        job=self.jobs.get(self.state['job_id']);owner=self.jobs.claim(job['id']);new=self.calculate(job['payload']['dataset_id'])
        self.jobs.begin_publish(job['id'],owner,new['run_id']);self.jobs.finish(job['id'],owner,'succeeded')
        self.step('calculated');self.step('no_factors',reviewed=True)
        saved=self.orders(new,orders=[]);self.step('orders',snapshot_id=saved['id'])
        report=self.state['comparison']
        self.assertEqual((report['overlapping_rows'],report['added_rows'],report['removed_rows']),(4,2,2))
        self.assertEqual((report['overlap_before'],report['overlap_after']),(36,48))
        self.assertTrue(all(row['after_forecast'] is None for row in report['rows'] if row['change']=='removed'))
        self.assertTrue(all(row['before_forecast'] is None for row in report['rows'] if row['change']=='added'))

    def factor_handoff(self,kind):
        from app.factors import FactorStore
        from app.factor_imports import review_import,save_import
        from app.factor_links import preview_link,save_link
        run=self.forecast(skip_factors=False);factors=FactorStore(self.root/'factors')
        dates=pd.date_range(end=date.today().replace(day=1)-timedelta(days=1),periods=36,freq='ME')
        frame=pd.DataFrame([{'period':str(day.date()),'value':100+i,'published':str(day.date()+timedelta(days=4))} for i,day in enumerate(dates)])
        source=self.datasets.upload('synthetic-index.csv',frame.to_csv(index=False).encode(),'factor_observations')
        config={'source_id':source['id'],'name':'Synthetic index','unit':'index','geography':'Iran · synthetic','provider':'Test',
            'frequency':'monthly','classification':'synthetic_sample','mapping':{'period':'A','value':'B','available_at':'C'}}
        review=review_import(self.datasets,config)
        self.assertEqual(review['issue_count'],0,review)
        snapshot=save_import(self.datasets,factors,{**config,'review_token':review['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())})
        payload={'snapshot_id':snapshot['id'],'lag_months':2,'future_value':140,'method':'model:Ridge + drivers',
                 **({'series_ids':[next(k for k in run['series'] if k!='__all__')]} if kind=='factor_batch' else {})}
        reviewed=preview_link(run,self.datasets,factors,payload)
        linked=save_link(run,self.datasets,factors,{**payload,'reviewed':True,'review_token':reviewed['review_token'],'request_id':str(uuid.uuid4())})
        if kind=='factor_batch':
            from app.factor_batch import preview_batch,save_batch
            inputs={'dataset_ids':[linked['id']]};report=preview_batch(run,self.datasets,factors,inputs)
            linked=save_batch(run,self.datasets,factors,{**inputs,'reviewed':True,'review_token':report['review_token'],'request_id':str(uuid.uuid4())})
        job=self.jobs.create({'dataset_id':linked['id'],'method':None,'adjustment':0,'scenario_name':None,'base_run_id':run['run_id']},linked['name'],'factor-dispatch')
        self.step('factor_job',job_id=job['id']);self.assertEqual(self.state['stage'],'factor_calculating')
        owner=self.jobs.claim(job['id'])
        with patch.object(self.main,'FACTOR_STORE',factors):
            scenario=self.calculate(linked['id'],method=None,base_run_id=run['run_id'])
        self.jobs.begin_publish(job['id'],owner,scenario['run_id']);self.jobs.finish(job['id'],owner,'succeeded')
        self.step('factor_calculated');self.assertEqual(self.state['stage'],'orders')
        self.assertEqual(self.state['run_id'],scenario['run_id']);self.assertEqual(self.sales.list(scenario['run_id']),[])
        self.assertEqual(scenario['scenario']['type'],kind)

    def test_existing_factor_review_and_engine_handoff_without_order_copy(self):
        self.factor_handoff('factor_link')

    def test_batch_factor_review_advances_to_orders_without_copying_them(self):
        self.factor_handoff('factor_batch')

    def test_stopped_job_retry_requires_fresh_confirmation(self):
        self.step('history',dataset_id=self.source['id'],reviewed=True);self.step('calculate',months=3,method='model:Last observed',reviewed=True)
        self.jobs.cancel(self.state['job_id']);self.step('retry_calculation')
        self.assertEqual(self.state['stage'],'forecast');self.assertEqual(len(self.jobs.list()),1)

    def test_source_corruption_is_not_a_resume_approval(self):
        (self.datasets.root/(self.source['sources']['history']+'.bin')).write_bytes(b'changed')
        response=self.client.get('/api/forecast-updates/'+self.state['id'])
        self.assertEqual(response.status_code,400);self.assertIn('changed since import',response.text)

    def test_real_sdk_monthly_tool_is_navigation_only_and_stale_bound(self):
        actions=[];agent=build_agent('decision','test',self.base,None,actions,self.datasets)
        tool=next(t for t in agent.tools if t.name=='prepare_monthly_update')
        result=asyncio.run(tool.on_invoke_tool(ToolContext(context=None,tool_name=tool.name,tool_call_id='test',tool_arguments='{}'),'{}'))
        self.assertFalse(result['workflow_opened']);self.assertEqual(actions[0]['kind'],'monthly_update')
        journal=AIJournal(self.root/'ai.sqlite');app=FastAPI()
        @app.middleware('http')
        async def identity(request:Request,call_next):request.state.principal={'issuer':'test','subject':'alice'};return await call_next(request)
        install_ai_routes(app,journal,self.main._load_run,self.service.outlook,self.datasets,self.submit)
        key=journal.put(self.actor,{'run_id':self.base['run_id'],'actions':actions})
        with TestClient(app) as client:
            response=client.post(f'/api/ai/turns/{key}/actions/0')
            self.assertEqual(response.json()['workflow'],'monthly_update')
        self.submit.assert_not_called();self.assertEqual(len(self.datasets.list()),1)

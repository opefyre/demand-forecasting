"""First-forecast assistant path: real local inputs and SDK tools, no paid calls."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.tool_context import ToolContext
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.ai_workspace import AIJournal, build_agent, input_context, install_ai_routes
from app.datasets import DatasetStore


class OnboardingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = DatasetStore(Path(self.tmp.name)/'inputs')
        raw = 'date,item,customer,sku,quantity,correct_quantity\n'
        for year in (2023,2024,2025):
            for month in range(1,13):
                for customer in ('A','B'):
                    raw += f'{year}-{month:02d}-01,{customer}/P,{customer},P,{month+20},{month+30}\n'
        self.file = self.store.upload('Synthetic sales.csv', raw.encode(), 'history')
        self.source = self.store.save('Synthetic sales', {'history':self.file['id']},
            {'date_col':'date','item_col':'item','customer_col':'customer','sku_col':'sku',
             'target_col':'quantity','frequency':'monthly','horizon':10,'unit':'tonnes',
             'sales_measure':'customer_demand','outlier_strategy':'none'},
            'synthetic_sample', True)
        self.journal = AIJournal(Path(self.tmp.name)/'ai.sqlite3')
        self.submit = MagicMock(return_value={'id':'synthetic-job','state':'queued'})
        self.load_run = MagicMock(side_effect=AssertionError('No forecast should be loaded'))
        app = FastAPI()
        @app.middleware('http')
        async def identity(request:Request, call_next):
            request.state.principal={'issuer':'company','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_ai_routes(app,self.journal,self.load_run,None,self.store,self.submit)
        self.client=TestClient(app); self.addCleanup(self.client.close)
        self.actor=json.dumps(['company','alice'])

    async def invoke(self, agent, name, args):
        tool=next(t for t in agent.tools if t.name==name)
        return await tool.on_invoke_tool(ToolContext(context=None,tool_name=name,
            tool_call_id='test',tool_arguments=json.dumps(args)),json.dumps(args))

    async def test_saved_inputs_have_no_invented_forecast_and_support_customer_or_all(self):
        context=input_context(self.store,self.source); actions=[]
        self.assertIsNone(context['run_id']); self.assertEqual(context['series'],{})
        self.assertEqual({m['customer'] for m in context['metadata'].values()},{'A','B'})
        agent=build_agent('decision','test',context,None,actions,self.store)
        self.assertIn('No forecast', (await self.invoke(agent,'inspect_forecast',{}))['error'])
        choices=await self.invoke(agent,'compare_methods',{})
        self.assertFalse(choices['tested']); self.assertIn('model:Weighted recent average',choices['methods'])
        report=await self.invoke(agent,'inspect_inputs',{})
        self.assertEqual(report['files']['history']['rows'],72)
        self.assertEqual(report['errors'],[])
        self.assertIn('error',await self.invoke(agent,'prepare_forecast',{'customer':'Unknown','months':10,'method':'recommended'}))
        self.assertEqual(actions,[])
        before=self.store.list()
        for customer in ('A',''):
            proposal=await self.invoke(agent,'prepare_forecast',{'customer':customer,'months':10,'method':'model:Weighted recent average'})
            self.assertTrue(proposal['requires_review'])
        self.assertEqual(self.store.list(),before); self.submit.assert_not_called()
        self.assertEqual([a['customer'] for a in actions],['A',''])
        alias=await self.invoke(agent,'prepare_forecast',{'customer':'A','months':10,'method':'Weighted recent average'})
        self.assertTrue(alias['requires_review']);self.assertEqual(len(actions),2)

    async def test_chat_to_confirmed_job_uses_real_dataset_and_keeps_parent_unchanged(self):
        actions=[]
        agent=build_agent('decision','test',input_context(self.store,self.source),None,actions,self.store)
        await self.invoke(agent,'prepare_forecast',{'customer':'A','months':10,'method':'model:Weighted recent average'})
        fake=AsyncMock(return_value={'answer':'Ready to run; please confirm.', 'actions':actions,
            'dataset_id':self.source['id'],'run_id':None,'snapshot_id':None})
        with patch('app.ai_workspace.run_chat',fake):
            response=self.client.post('/api/ai/chat',json={'question':'Forecast A for 10 months',
                'dataset_id':self.source['id'],'consent':True})
        self.assertEqual(response.status_code,200,response.text)
        key=response.json()['id']; self.load_run.assert_not_called(); self.submit.assert_not_called()
        proposal_count=len(self.store.list())
        path=f'/api/ai/turns/{key}/actions/0'
        self.assertEqual(self.client.post(path,headers={'actor':'bob'}).status_code,400)
        confirmed=self.client.post(path)
        self.assertEqual(confirmed.status_code,200,confirmed.text)
        self.assertEqual(confirmed.json()['customer'],'A')
        self.assertEqual(confirmed.json()['workflow'],'new_forecast')
        self.submit.assert_not_called()
        draft=self.store.get(confirmed.json()['dataset_id'])
        self.assertEqual(draft['sources'],self.source['sources'])
        self.assertEqual(draft['settings']['horizon'],10)
        self.assertEqual(draft['parent_dataset_id'],self.source['id'])
        self.assertEqual(self.store.get(self.source['id']),self.source)
        self.assertEqual(self.client.post(path).json(),confirmed.json())
        self.assertEqual(len(self.store.list()),proposal_count+1)
        restored=self.client.get(f'/api/ai/turns/{key}/history?dataset_id={self.source["id"]}')
        self.assertEqual(restored.status_code,200)
        self.assertIn('0',restored.json()['turns'][0]['results'])

    async def test_context_is_bound_to_exact_inputs_and_cannot_cross_to_run_or_other_dataset(self):
        fake=AsyncMock(return_value={'answer':'Review ready','actions':[],
            'dataset_id':self.source['id'],'run_id':None,'snapshot_id':None})
        with patch('app.ai_workspace.run_chat',fake):
            parent=self.client.post('/api/ai/chat',json={'question':'Review inputs','dataset_id':self.source['id']}).json()['id']
            follow=self.client.post('/api/ai/chat',json={'question':'Now 10 months',
                'dataset_id':self.source['id'],'previous_turn_id':parent})
        self.assertEqual(follow.status_code,200,follow.text)
        self.assertEqual(fake.call_args.kwargs['history'][0]['id'],parent)
        with patch('app.ai_workspace.run_chat',new_callable=AsyncMock) as not_called:
            rejected=self.client.post('/api/ai/chat',json={'question':'Continue','previous_turn_id':parent})
            self.assertEqual(rejected.status_code,400); not_called.assert_not_called()
        self.assertEqual(self.client.get(f'/api/ai/turns/{parent}/history').status_code,400)
        for extra in ({'run_id':'some-run'},{'snapshot_id':'orders'}):
            rejected=self.client.post('/api/ai/chat',json={'question':'Forecast', 'dataset_id':self.source['id'],**extra})
            self.assertEqual(rejected.status_code,400)

    async def test_changed_inputs_during_provider_cannot_create_approvable_action(self):
        async def changed(*args,**kwargs):
            altered={**self.source,'name':'Changed'}
            self.store._write(self.store._path('dataset',self.source['id']),altered)
            return {'answer':'Prepared','actions':[{'kind':'forecast'}],'run_id':None,
                    'dataset_id':self.source['id'],'snapshot_id':None}
        with patch('app.ai_workspace.run_chat',changed):
            response=self.client.post('/api/ai/chat',json={'question':'Forecast A','dataset_id':self.source['id']})
        self.assertEqual(response.status_code,400); self.assertIn('changed',response.json()['detail'])
        self.submit.assert_not_called()

    async def test_corrupted_source_blocks_replay_before_job(self):
        actions=[];agent=build_agent('decision','test',input_context(self.store,self.source),None,actions,self.store)
        await self.invoke(agent,'prepare_forecast',{'customer':'','months':10,'method':'recommended'})
        key=self.journal.put(self.actor,{'dataset_id':self.source['id'],
            'dataset_sha256':hashlib.sha256(json.dumps(self.source,sort_keys=True).encode()).hexdigest(),'actions':actions})
        (self.store.root/f'{self.file["id"]}.bin').write_bytes(b'changed')
        response=self.client.post(f'/api/ai/turns/{key}/actions/0')
        self.assertEqual(response.status_code,400);self.submit.assert_not_called()

    async def test_no_inputs_has_guidance_but_cannot_run_and_still_needs_sharing_consent(self):
        empty={'run_id':None,'metadata':{},'series':{},'run_settings':{}}
        actions=[];agent=build_agent('query','test',empty,None,actions,self.store)
        report=await self.invoke(agent,'inspect_inputs',{})
        self.assertIn('Add sales history',report['next_step'])
        self.assertIn('error',await self.invoke(agent,'prepare_forecast',{'customer':'','months':6,'method':'recommended'}))
        self.assertEqual(actions,[])
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-'+'x'*40,'DEMANDLAB_AI_ENABLED':'true'}), patch('app.ai_workspace.Runner.run',new_callable=AsyncMock) as forbidden:
            response=self.client.post('/api/ai/chat',json={'question':'How do I start?'})
        self.assertEqual(response.status_code,400);self.assertIn('Confirm sending',response.json()['detail'])
        forbidden.assert_not_called()

    async def test_reviewed_mapping_can_be_used_for_first_forecast_without_editing_original(self):
        context=input_context(self.store,self.source);actions=[]
        agent=build_agent('review','test',context,None,actions,self.store)
        await self.invoke(agent,'prepare_input_mapping',{'changes':[{'field':'target_col','column':'correct_quantity'}],
            'reason':'The user confirmed correct_quantity is requested demand.'})
        key=self.journal.put(self.actor,{'actions':actions,'dataset_id':self.source['id']})
        response=self.client.post(f'/api/ai/turns/{key}/actions/0')
        self.assertEqual(response.status_code,200,response.text)
        saved=self.store.get(response.json()['dataset_id'])
        self.assertEqual(saved['settings']['target_col'],'correct_quantity')
        self.assertEqual(self.store.get(self.source['id']),self.source)
        next_actions=[];next_agent=build_agent('decision','test',input_context(self.store,saved),None,next_actions,self.store)
        proposal=await self.invoke(next_agent,'prepare_forecast',{'customer':'B','months':10,'method':'recommended'})
        self.assertTrue(proposal['requires_review']);self.assertEqual(next_actions[0]['dataset_id'],saved['id'])
        self.submit.assert_not_called()

import json
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from agents.tool_context import ToolContext
from app.ai_workspace import AIJournal,ChatRequest,Route,ai_status,build_agent,run_chat,install_ai_routes
from tests.test_sales_demand import fixture,demand_outlook


class AITests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_ai_makes_no_provider_call(self):
        run,_=fixture()
        async def forbidden(*args,**kwargs): raise AssertionError('Provider called without key')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'','DEMANDLAB_AI_ENABLED':'false'}):
            self.assertFalse(ai_status()['ready'])
            with self.assertRaisesRegex(ValueError,'Configure'):
                await run_chat(ChatRequest(question='Explain',run_id=run['run_id'],consent=True),run,None,runner=forbidden)

    async def test_routes_by_job_and_uses_local_tools(self):
        run,inputs=fixture();outlook={**demand_outlook(inputs,run),'snapshot_id':'snapshot'}
        calls=[]
        async def fake_runner(agent,question,**kwargs):
            calls.append((agent.name,agent.model,kwargs))
            if agent.name=='Request router': return SimpleNamespace(final_output=Route(role='decision'),context_wrapper=SimpleNamespace(usage=SimpleNamespace(requests=1,input_tokens=10,output_tokens=2)))
            tool=next(t for t in agent.tools if t.name=='inspect_forecast')
            result=await tool.on_invoke_tool(ToolContext(context=None,tool_name=tool.name,tool_call_id='test',tool_arguments='{}'),json.dumps({'customer':'B'}))
            self.assertEqual(result['rows'][0]['total'],8)
            return SimpleNamespace(final_output='Expected demand is 8 tonnes.',context_wrapper=SimpleNamespace(usage=SimpleNamespace(requests=1,input_tokens=100,output_tokens=20)))
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-'+'x'*40,'DEMANDLAB_AI_ENABLED':'true',
                'DEMANDLAB_AI_QUERY_MODEL':'query-test','DEMANDLAB_AI_DECISION_MODEL':'decision-test'}):
            result=await run_chat(ChatRequest(question='Which method?',run_id='forecast1',consent=True),run,outlook,runner=fake_runner)
        self.assertEqual([c[1] for c in calls],['query-test','decision-test'])
        self.assertTrue(calls[0][2]['run_config'].tracing_disabled)
        self.assertEqual(result['model'],'decision-test')
        self.assertEqual(result['usage']['input_tokens'],110)

    async def test_explicit_review_uses_review_model_and_consent_required(self):
        run,_=fixture();calls=[]
        async def fake_runner(agent,*args,**kwargs):
            calls.append(agent.model)
            return SimpleNamespace(final_output='Review',context_wrapper=SimpleNamespace(usage=SimpleNamespace(requests=1,input_tokens=1,output_tokens=1)))
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-'+'x'*40,'DEMANDLAB_AI_ENABLED':'true','DEMANDLAB_AI_REVIEW_MODEL':'review-test'}):
            with self.assertRaisesRegex(ValueError,'Confirm sending'):
                await run_chat(ChatRequest(question='Review',run_id='forecast1'),run,None,runner=fake_runner)
            await run_chat(ChatRequest(question='Review',run_id='forecast1',consent=True,mode='review'),run,None,runner=fake_runner)
        self.assertEqual(calls,['review-test'])

    async def test_tools_only_propose_no_mutation(self):
        run,_=fixture();run['dataset_id']='dataset';actions=[]
        agent=build_agent('decision','test',run,None,actions)
        tool=next(t for t in agent.tools if t.name=='prepare_forecast')
        context=ToolContext(context=None,tool_name=tool.name,tool_call_id='test',tool_arguments='{}')
        rejected=await tool.on_invoke_tool(context,json.dumps({'customer':'Not listed','months':10,'method':'recommended'}))
        self.assertIn('error',rejected);self.assertEqual(actions,[])
        proposal=await tool.on_invoke_tool(context,json.dumps({'customer':'A','months':10,'method':'recommended'}))
        self.assertTrue(proposal['requires_review']);self.assertEqual(actions[0]['months'],10)
        self.assertFalse(agent.model_settings.store)
        self.assertEqual({t.name for t in agent.tools},{'inspect_forecast','compare_methods','prepare_forecast','prepare_export','inspect_inputs','prepare_input_mapping','prepare_order_import','prepare_monthly_update','inspect_input_formatting','prepare_input_corrections','prepare_history_refresh'})


class AIJournalTests(unittest.TestCase):
    def test_confirmed_forecast_action_reuses_saved_pipeline(self):
        with tempfile.TemporaryDirectory() as root:
            journal=AIJournal(Path(root)/'ai.sqlite3')
            source={'id':'original','name':'History','classification':'synthetic_sample',
                    'sources':{'history':'h','future':'f','operations':'legacy'},
                    'settings':{'horizon':6,'frequency':'monthly'},'review':{'warnings':[]}}
            dataset=MagicMock();dataset.get.return_value=source
            dataset.inspect.return_value={'warnings':[]}
            dataset.save.return_value={'id':'draft','name':'Assistant draft'}
            submit=MagicMock(return_value={'id':'job','state':'queued'})
            key=journal.put('local',{'dataset_sha256':hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest(),
                'actions':[{'kind':'forecast','dataset_id':'original','customer':'A','months':10,'method':'recommended'}]})
            app=FastAPI()
            @app.middleware('http')
            async def local(request,call_next):
                request.state.principal=None
                return await call_next(request)
            install_ai_routes(app,journal,None,None,dataset,submit)
            client=TestClient(app)
            result=client.post(f'/api/ai/turns/{key}/actions/0')
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['customer'],'A')
            self.assertEqual(dataset.save.call_args.args[1],{'history':'h','future':'f'})
            self.assertEqual(dataset.save.call_args.args[2]['horizon'],10)
            self.assertEqual(result.json()['dataset_id'],'draft')
            self.assertEqual(result.json()['workflow'],'new_forecast')
            submit.assert_not_called()
            dataset.inspect.return_value={'warnings':['New future-data gap']}
            submit.reset_mock()
            self.assertEqual(client.post(f'/api/ai/turns/{key}/actions/0').status_code,400)
            submit.assert_not_called()

    def test_actions_owned_and_expiring(self):
        with tempfile.TemporaryDirectory() as root:
            journal=AIJournal(Path(root)/'ai.sqlite3')
            key=journal.put('alice',{'actions':[]})
            self.assertEqual(journal.get(key,'alice'),{'actions':[]})
            with self.assertRaises(ValueError): journal.get(key,'bob')
            with patch('app.ai_workspace.time.time',return_value=10**12):
                with self.assertRaisesRegex(ValueError,'expired'): journal.get(key,'alice')

    def test_execute_checks_subject_not_shared_local_identity(self):
        with tempfile.TemporaryDirectory() as root:
            journal=AIJournal(Path(root)/'ai.sqlite3')
            key=journal.put(json.dumps(['issuer','alice']),{'actions':[{'kind':'export','snapshot_id':'s','mode':'remaining_forecast','format':'csv'}]})
            app=FastAPI()
            @app.middleware('http')
            async def principal(request:Request,call_next):
                request.state.principal={'issuer':'issuer','subject':request.headers.get('actor','bob')}
                return await call_next(request)
            install_ai_routes(app,journal,lambda _:None,lambda _:{'can_export':True},None,None)
            client=TestClient(app)
            self.assertEqual(client.post(f'/api/ai/turns/{key}/actions/0').status_code,400)
            self.assertEqual(client.post(f'/api/ai/turns/{key}/actions/0',headers={'actor':'alice'}).status_code,200)

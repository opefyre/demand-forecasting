"""Real SDK tools and local review/save paths; no OpenAI calls."""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from agents.tool_context import ToolContext
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.ai_factor_scenarios import AssistantFactorScenarios, FactorAssumption
from app.ai_workspace import AIJournal, build_agent, context_hash, install_ai_routes
from tests import test_factor_links as fixtures
from tests.test_public_factor_links import matrix
from tests.test_sales_demand import fixture, demand_outlook


async def invoke(agent, name, arguments):
    tool = next(t for t in agent.tools if t.name == name)
    raw = json.dumps(arguments)
    return await tool.on_invoke_tool(ToolContext(context=None,tool_name=name,
        tool_call_id='synthetic',tool_arguments=raw),raw)


def client_for(journal, load, outlook, datasets=None, submit=None, factors=None):
    app = FastAPI()
    @app.middleware('http')
    async def identity(request: Request, call_next):
        request.state.principal = {'issuer':'company','subject':request.headers.get('actor','alice')}
        return await call_next(request)
    install_ai_routes(app,journal,load,outlook,datasets,submit,factors=factors)
    return TestClient(app)


class GuidedOrderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.run, self.inputs=fixture()
        self.outlook={**demand_outlook(self.inputs,self.run),'snapshot_id':'saved-orders'}
        self.journal=AIJournal(Path(self.tmp.name)/'journal.sqlite')
        self.client=client_for(self.journal,lambda _:self.run,lambda _:self.outlook)
        self.addCleanup(self.client.close);self.actor=json.dumps(['company','alice'])

    async def test_first_order_upload_and_update_are_navigation_not_writes(self):
        for outlook in (None,self.outlook):
            actions=[];agent=build_agent('decision','test',self.run,outlook,actions)
            result=await invoke(agent,'prepare_order_import',{})
            self.assertTrue(result['requires_review']);self.assertEqual(len(actions),1)
            self.assertEqual(result['status'],'prepared_not_opened');self.assertFalse(result['workflow_opened'])
            self.assertEqual(actions[0]['snapshot_id'],outlook['snapshot_id'] if outlook else None)
            await invoke(agent,'prepare_order_import',{});self.assertEqual(len(actions),1)
            key=self.journal.put(self.actor,{'run_id':self.run['run_id'],
                'snapshot_id':actions[0]['snapshot_id'],'actions':actions})
            route=f'/api/ai/turns/{key}/actions/0'
            self.assertEqual(self.client.post(route,headers={'actor':'bob'}).status_code,400)
            opened=self.client.post(route)
            self.assertEqual(opened.status_code,200,opened.text)
            self.assertEqual(opened.json()['workflow'],'order_import')
            self.assertEqual(self.client.post(route).json(),opened.json())
            self.assertNotIn('results',self.journal.get(key,self.actor))
        self.assertEqual(self.inputs,fixture()[1])

    async def test_changed_context_cross_run_and_expiration_block_opening(self):
        actions=[];agent=build_agent('decision','test',self.run,self.outlook,actions)
        await invoke(agent,'prepare_order_import',{})
        key=self.journal.put(self.actor,{'run_id':self.run['run_id'],'snapshot_id':'saved-orders','actions':actions})
        route=f'/api/ai/turns/{key}/actions/0'
        self.outlook['can_export']=not self.outlook['can_export']
        self.assertEqual(self.client.post(route).status_code,400)
        wrong=self.journal.put(self.actor,{'run_id':'another','snapshot_id':'saved-orders','actions':actions})
        self.assertEqual(self.client.post(f'/api/ai/turns/{wrong}/actions/0').status_code,400)
        with patch('app.ai_workspace.time.time',return_value=10**12):
            self.assertEqual(self.client.post(route).status_code,400)


class GuidedFactorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f=fixtures.FactorLinkTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.f.base['metadata']={'A':{'customer':'A','sku':'SKU'},'B':{'customer':'B','sku':'SKU'}}
        self.f.base['leaderboard']=[{'model':'Ridge + drivers'},{'model':'Seasonal naive'}]
        self.snapshot=self.f.factors.refresh('global_supply_pressure',transport=httpx.MockTransport(
            lambda r:httpx.Response(200,content=matrix())))
        self.adapter=AssistantFactorScenarios(self.f.base,self.f.store,self.f.factors)
        self.links=[{'snapshot_id':self.snapshot['id'],'lag_months':2,'future_value':1.0}]
        self.method='model:Ridge + drivers'
        self.journal=AIJournal(self.f.root/'ai.sqlite')
        self.submit=MagicMock(return_value={'id':'synthetic-job','state':'queued'})
        self.client=client_for(self.journal,lambda _:self.f.base,None,self.f.store,self.submit,self.f.factors)
        self.addCleanup(self.client.close);self.actor=json.dumps(['company','alice'])

    async def test_tools_list_connected_sources_and_exact_scope_without_saving(self):
        actions=[];agent=build_agent('decision','test',self.f.base,None,actions,factor_scenarios=self.adapter)
        choices=await invoke(agent,'inspect_factor_sources',{})
        self.assertEqual([s['id'] for s in choices['snapshots']],[self.snapshot['id']])
        self.assertEqual(choices['methods'],[self.method])
        before=self.f.store.list()
        report=await invoke(agent,'preview_factor_scenario',{'links':self.links,'method':self.method,'customer':'A','sku':'SKU'})
        self.assertEqual(report['missing'],0);self.assertEqual(report['series_count'],1)
        result=await invoke(agent,'prepare_factor_scenario',{'links':self.links,'method':self.method,'customer':'A'})
        self.assertTrue(result['requires_review']);self.assertEqual(actions[0]['payload']['series_ids'],['A'])
        self.assertEqual(self.f.store.list(),before);self.submit.assert_not_called()

    async def test_unknown_sources_scope_method_and_missing_observations_never_propose(self):
        for changes in ({'links':[{'snapshot_id':self.f.snapshot['id'],'lag_months':2,'future_value':1.0}]},
                        {'customer':'Not A'}, {'method':'recommended'},
                        {'links':[{'snapshot_id':self.snapshot['id'],'lag_months':1,'future_value':None}]}):
            args={'links':self.links,'method':self.method,**changes}
            actions=[];agent=build_agent('decision','test',self.f.base,None,actions,factor_scenarios=self.adapter)
            self.assertIn('error',await invoke(agent,'prepare_factor_scenario',args));self.assertEqual(actions,[])
        self.submit.assert_not_called()

    async def test_monthly_assumptions_are_strict_dated_and_not_silently_duplicated(self):
        rows=[{'period':'2026-02-01','value':2.0}]
        links=[{'snapshot_id':self.snapshot['id'],'lag_months':2,'future_values':rows}]
        payload,report,_=self.adapter.preview(links,self.method)
        self.assertEqual(payload['links'][0]['future_values'],{'2026-02-01':2.0})
        self.assertEqual([r['value'] for r in report['rows'] if r['kind']=='future'][-1],2.0)
        with self.assertRaisesRegex(ValueError,'only once'):
            self.adapter.preview([{**links[0],'future_values':rows+rows}],self.method)
        for field in ({'lag_months':True},{'future_value':float('inf')},{'future_values':[{'period':'fake','value':2.0}]},
                      {'unreviewed':True}):
            with self.assertRaises(ValueError):FactorAssumption.model_validate({**self.links[0],**field})

    async def test_confirmation_uses_existing_save_and_job_contract_with_idempotent_retry(self):
        parent=deepcopy(self.f.dataset)
        action=self.adapter.proposal(self.links,self.method,'A')
        key=self.journal.put(self.actor,{'run_id':'base','actions':[action]})
        route=f'/api/ai/turns/{key}/actions/0'
        for body in (None,{}, {'assumptions_confirmed':False},{'assumptions_confirmed':'true'}):
            self.assertEqual(self.client.post(route,json=body).status_code,400)
        self.submit.assert_not_called()
        self.assertEqual(self.client.post(route,json={'assumptions_confirmed':True},headers={'actor':'bob'}).status_code,400)
        saved=self.client.post(route,json={'assumptions_confirmed':True})
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertFalse(saved.json()['orders_copied'])
        draft=self.f.store.get(saved.json()['dataset_id'])
        self.assertEqual(draft['scenario_provenance']['alignment']['series_ids'],['A'])
        self.assertEqual(self.submit.call_args.args[0]['method'],None) # Saved scenario owns its method.
        self.assertEqual(self.submit.call_args.args[0]['base_run_id'],'base')
        count=len(self.f.store.list());request=self.submit.call_args.args[2]
        self.assertEqual(self.client.post(route,json={'assumptions_confirmed':True}).json(),saved.json())
        self.assertEqual(self.submit.call_args.args[2],request);self.assertEqual(len(self.f.store.list()),count)
        self.assertEqual(self.f.store.get(parent['id']),parent)

    async def test_changed_inputs_and_corrupt_retained_factor_block_confirmation(self):
        action=self.adapter.proposal(self.links,self.method)
        key=self.journal.put(self.actor,{'run_id':'base','actions':[action]})
        route=f'/api/ai/turns/{key}/actions/0'
        changed={**self.f.dataset,'name':'Changed inputs'}
        self.f.store._write(self.f.store._path('dataset',self.f.dataset['id']),changed)
        self.assertEqual(self.client.post(route,json={'assumptions_confirmed':True}).status_code,400)
        self.f.store._write(self.f.store._path('dataset',self.f.dataset['id']),self.f.dataset)
        (self.f.factors.root/'raw'/f'{self.snapshot["id"]}.csv').write_bytes(b'altered')
        self.assertEqual(self.client.post(route,json={'assumptions_confirmed':True}).status_code,400)
        self.submit.assert_not_called()

    async def test_chat_routes_new_service_and_restores_review_action(self):
        action=self.adapter.proposal(self.links,self.method)
        fake=AsyncMock(return_value={'answer':'Review this scenario.','actions':[action],
            'run_id':'base','snapshot_id':None,'dataset_id':None})
        with patch('app.ai_workspace.run_chat',fake):
            response=self.client.post('/api/ai/chat',json={'question':'Compare supply pressure','run_id':'base'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertIsInstance(fake.call_args.kwargs['factor_scenarios'],AssistantFactorScenarios)
        restored=self.client.get(f'/api/ai/turns/{response.json()["id"]}/history?run_id=base')
        self.assertEqual(restored.json()['turns'][0]['actions'][0]['kind'],'factor_scenario')
        self.submit.assert_not_called()

    async def test_confirmed_job_runs_the_existing_engine_not_ai_generated_numbers(self):
        import app.main as main
        runs=self.f.root/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.f.store),patch.object(main,'FACTOR_STORE',self.f.factors),patch.object(main,'RUNS_DIR',runs),TestClient(main.app) as real_client:
            response=real_client.post('/api/run-saved',json={'dataset_id':self.f.dataset['id']})
            self.assertEqual(response.status_code,200,response.text)
            base=response.json()
            adapter=AssistantFactorScenarios(base,self.f.store,self.f.factors)
            action=adapter.proposal(self.links,self.method,'A')
            key=self.journal.put(self.actor,{'run_id':base['run_id'],'actions':[action]})
            with client_for(self.journal,lambda _:base,None,self.f.store,self.submit,self.f.factors) as client:
                confirmed=client.post(f'/api/ai/turns/{key}/actions/0',json={'assumptions_confirmed':True})
            self.assertEqual(confirmed.status_code,200,confirmed.text)
            result=real_client.post('/api/run-saved',json=self.submit.call_args.args[0])
            self.assertEqual(result.status_code,200,result.text)
            candidate=result.json()
            self.assertEqual(candidate['base_run_id'],base['run_id'])
            self.assertEqual(candidate['scenario']['type'],'factor_link')
            self.assertEqual(candidate['scenario']['alignment']['series_ids'],['A'])
            self.assertEqual(candidate['series']['B']['forecast'],base['series']['B']['forecast'])
            self.assertEqual(len(candidate['series']['A']['forecast']),2)

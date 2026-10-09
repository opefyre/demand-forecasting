"""Real SDK tools and reviewed local services. Provider payloads are fixtures."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
import httpx
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from app.ai_factor_batch import AssistantFactorBatch,FactorGroup
from app.ai_workspace import AIJournal,build_agent,install_ai_routes
from app.factor_batch import check_saved_batch
from tests import test_factor_links as fixtures
from tests.test_public_factor_links import matrix
from tests.test_ai_guided_workflows import invoke


class AIBatchTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f=fixtures.FactorLinkTests();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.f.base.update(metadata={'A':{'customer':'A','sku':'SKU'},'B':{'customer':'B','sku':'SKU'}},unit='tonnes',
            leaderboard=[{'model':'Ridge + drivers'},{'model':'Seasonal naive'}])
        self.snapshot=self.f.factors.refresh('global_supply_pressure',transport=httpx.MockTransport(lambda r:httpx.Response(200,content=matrix())))
        self.state={'id':'supply','refresh_overdue':False,'series':[{'id':self.snapshot['id'],'data_behind':False}]}
        self.live=SimpleNamespace(listing=lambda:{'sources':[deepcopy(self.state)]})
        self.adapter=AssistantFactorBatch(self.f.base,self.f.store,self.f.factors,self.live)
        self.groups=[{'series_ids':[key],'method':'model:Ridge + drivers','links':[
            {'snapshot_id':self.snapshot['id'],'lag_months':2,'future_value':float(i+2)}]} for i,key in enumerate(('A','B'))]
        self.journal=AIJournal(self.f.root/'ai.sqlite');self.actor=json.dumps(['company','alice'])
        self.submit=MagicMock(return_value={'id':'job','state':'queued'})
        self.job=MagicMock(return_value={'state':'queued','payload':{},'id':'job'})
        self.loaded=deepcopy(self.f.base)
        app=FastAPI()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal={'issuer':'company','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_ai_routes(app,self.journal,lambda _:self.loaded,lambda _:None,self.f.store,self.submit,
            factors=self.f.factors,live=self.live,job_status=self.job)
        self.client=TestClient(app);self.addCleanup(self.client.close)

    def record(self,action):
        key=self.journal.put(self.actor,{'run_id':'base','question':'Synthetic batch','answer':'Review','actions':[action]})
        return key,f'/api/ai/turns/{key}/actions/0'

    async def test_sdk_choices_preview_and_proposal_are_read_only_and_deduplicated(self):
        actions=[];agent=build_agent('decision','test',self.f.base,None,actions,factor_batch=self.adapter)
        before=deepcopy(self.f.store.list())
        options=await invoke(agent,'inspect_factor_batch',{})
        self.assertEqual([s['id'] for s in options['snapshots']],[self.snapshot['id']]);self.assertTrue(options['snapshots'][0]['ready'])
        result=await invoke(agent,'preview_factor_batch',{'groups':self.groups})
        self.assertEqual([g['scope'][0]['id'] for g in result['groups']],['A','B'])
        self.assertEqual([g['future_rows'][-1]['value'] for g in result['groups']],[2.,3.])
        self.assertEqual(actions,[])
        for _ in range(2):await invoke(agent,'prepare_factor_batch',{'groups':self.groups})
        self.assertEqual(len(actions),1);self.assertEqual(self.f.store.list(),before);self.submit.assert_not_called()

    async def test_explicit_scope_overlap_unknown_method_and_manual_sources_block(self):
        bad=[[],self.groups*11,[self.groups[0],self.groups[0]],
            [{**self.groups[0],'series_ids':['unknown']}],
            [{**self.groups[0],'method':'new invented method'}],
            [{**self.groups[0],'links':[{'snapshot_id':self.f.snapshot['id'],'lag_months':2,'future_value':1.}]}]]
        for groups in bad:
            with self.subTest(groups=groups),self.assertRaises(ValueError):self.adapter.proposal(groups)
        for value in ({'series_ids':[True]},{'extra':True},{'links':[{'snapshot_id':self.snapshot['id'],'lag_months':True}]},
                      {'links':[{'snapshot_id':self.snapshot['id'],'lag_months':2,'future_value':float('nan')}]}):
            with self.assertRaises(ValueError):FactorGroup.model_validate({**self.groups[0],**value})

    async def test_automatic_method_reuses_existing_public_history_models(self):
        for method in ('factor_test','recommended'):
            payloads,report,_=self.adapter.preview([{**self.groups[0],'method':method}])
            self.assertEqual(payloads[0]['payload']['method'],method);self.assertEqual(report['groups'][0]['method'],method)

    async def test_stale_unconnected_permissions_and_missing_values_never_propose(self):
        self.state['refresh_overdue']=True
        self.assertFalse(self.adapter.choices()['snapshots'][0]['ready'])
        with self.assertRaises(ValueError):self.adapter.proposal(self.groups)
        self.state.update(refresh_overdue=False,id='iran_cpi',permission_confirmed=False)
        with self.assertRaises(ValueError):self.adapter.proposal(self.groups)
        self.state.update(id='supply',permission_confirmed=True,series=[])
        with self.assertRaises(ValueError):self.adapter.proposal(self.groups)
        self.state['series']=[{'id':self.snapshot['id'],'data_behind':False}]
        missing=deepcopy(self.groups);missing[0]['links'][0]['future_value']=None
        self.assertGreater(self.adapter.preview(missing)[1]['groups'][0]['missing'],0)
        with self.assertRaises(ValueError):self.adapter.proposal(missing)

    async def test_scoped_handoff_no_writes_owner_expiry_and_changed_baseline(self):
        before=self.f.store.list();actions=[]
        agent=build_agent('decision','test',self.f.base,None,actions,factor_batch=self.adapter)
        await invoke(agent,'prepare_customer_factor_batch',{'series_ids':['A','B']})
        key,path=self.record(actions[0]);result=self.client.post(path)
        self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['series_ids'],['A','B'])
        self.assertEqual(self.client.post(path,headers={'actor':'bob'}).status_code,400)
        self.loaded['metadata']['A']['customer']='changed'
        self.assertEqual(self.client.post(path).status_code,400)
        with patch('app.ai_workspace.time.time',return_value=10**12):self.assertEqual(self.client.post(path).status_code,400)
        self.assertEqual(before,self.f.store.list());self.submit.assert_not_called()

    async def test_confirmation_saves_disjoint_groups_once_and_never_orders(self):
        parent=deepcopy(self.f.dataset);key,path=self.record(self.adapter.proposal(self.groups))
        for body in ({},{'batch_confirmed':False},{'batch_confirmed':'true'}):
            self.assertEqual(self.client.post(path,json=body).status_code,400)
        self.submit.assert_not_called()
        self.assertEqual(self.client.post(path,json={'batch_confirmed':True},headers={'actor':'bob'}).status_code,400)
        response=self.client.post(path,json={'batch_confirmed':True});self.assertEqual(response.status_code,200,response.text)
        result=response.json();self.assertFalse(result['orders_copied']);saved=self.f.store.get(result['dataset_id'])
        self.assertEqual(saved['scenario_provenance']['type'],'factor_batch');self.assertTrue(saved['scenario_provenance']['require_connected_sources'])
        self.assertEqual([g['series_ids'] for g in saved['scenario_provenance']['alignment']['groups']],[['A'],['B']])
        count=len(self.f.store.list());self.assertEqual(self.client.post(path,json={'batch_confirmed':True}).json(),result)
        self.assertEqual(len(self.f.store.list()),count);self.submit.assert_called_once();self.assertEqual(self.f.store.get(parent['id']),parent)
        self.state['refresh_overdue']=True
        with self.assertRaises(ValueError):check_saved_batch(self.f.base,saved,self.f.store,self.f.factors,self.live)

    async def test_changes_before_confirmation_block_without_saving(self):
        action=self.adapter.proposal(self.groups);_,path=self.record(action);before=self.f.store.list()
        self.state['series'][0]['data_behind']=True
        self.assertEqual(self.client.post(path,json={'batch_confirmed':True}).status_code,400)
        self.state['series'][0]['data_behind']=False;self.loaded['metadata']['A']['customer']='changed'
        self.assertEqual(self.client.post(path,json={'batch_confirmed':True}).status_code,400)
        self.loaded=deepcopy(self.f.base)
        (self.f.factors.root/'raw'/f'{self.snapshot["id"]}.csv').write_bytes(b'changed')
        self.assertEqual(self.client.post(path,json={'batch_confirmed':True}).status_code,400)
        self.assertEqual(self.f.store.list(),before);self.submit.assert_not_called()

    async def test_progress_is_owner_bound_exact_result_no_private_job_fields(self):
        key,path=self.record(self.adapter.proposal(self.groups))
        response=self.client.post(path,json={'batch_confirmed':True}).json();dataset=response['dataset_id']
        self.job.return_value={'state':'running','payload':{'dataset_id':dataset,'base_run_id':'base'},'owner':'PRIVATE','run_id':None}
        progress=self.client.get(path+'/progress');self.assertEqual(progress.status_code,200,progress.text)
        self.assertEqual(progress.json(),{'state':'running','run_id':None,'orders_copied':False})
        self.assertEqual(self.client.get(path+'/progress',headers={'actor':'bob'}).status_code,400)
        self.job.return_value.update(state='succeeded',run_id='result')
        self.loaded={'dataset_id':dataset,'base_run_id':'base'}
        self.assertEqual(self.client.get(path+'/progress').json()['run_id'],'result')
        self.loaded['dataset_id']='foreign';self.assertEqual(self.client.get(path+'/progress').status_code,400)
        self.assertEqual(self.client.get(path.replace('/0','/-1')+'/progress').status_code,400)

    async def test_chat_passes_batch_tools_through_existing_provider_loop(self):
        async def fake(payload,run,outlook,**kwargs):
            action=kwargs['factor_batch'].handoff(['A','B'])
            return {'answer':'Review both products.','actions':[action],'run_id':run['run_id'],'snapshot_id':None,'dataset_id':None}
        with patch('app.ai_workspace.run_chat',side_effect=fake):
            reply=self.client.post('/api/ai/chat',json={'question':'Prepare A and B','run_id':'base'})
        self.assertEqual(reply.status_code,200,reply.text);self.assertEqual(reply.json()['actions'][0]['kind'],'factor_batch_review')
        restored=self.client.get('/api/ai/turns/'+reply.json()['id']+'/history?run_id=base')
        self.assertEqual(restored.status_code,200);self.assertEqual(restored.json()['turns'][0]['actions'][0]['series_ids'],['A','B'])

    async def test_confirmed_batch_runs_existing_engine_with_distinct_groups(self):
        import app.main as main
        runs=self.f.root/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.f.store),patch.object(main,'FACTOR_STORE',self.f.factors),patch.object(main,'LIVE_SOURCES',self.live),patch.object(main,'RUNS_DIR',runs),TestClient(main.app) as real_client:
            response=real_client.post('/api/run-saved',json={'dataset_id':self.f.dataset['id']})
            self.assertEqual(response.status_code,200,response.text)
            base=response.json();self.loaded=base
            adapter=AssistantFactorBatch(base,self.f.store,self.f.factors,self.live)
            action=adapter.proposal(self.groups)
            key=self.journal.put(self.actor,{'run_id':base['run_id'],'actions':[action]})
            confirmed=self.client.post(f'/api/ai/turns/{key}/actions/0',json={'batch_confirmed':True})
            self.assertEqual(confirmed.status_code,200,confirmed.text)
            result=real_client.post('/api/run-saved',json=self.submit.call_args.args[0])
            self.assertEqual(result.status_code,200,result.text)
            candidate=result.json()
            self.assertEqual(candidate['base_run_id'],base['run_id'])
            self.assertEqual(candidate['scenario']['type'],'factor_batch')
            self.assertEqual([g['alignment']['series_ids'] for g in candidate['scenario']['alignment']['groups']],[['A'],['B']])
            for key in ('A','B'):
                self.assertEqual(len(candidate['series'][key]['forecast']),2)
                self.assertTrue(all(row['mean']>=0 for row in candidate['series'][key]['forecast']))


if __name__=='__main__':unittest.main()

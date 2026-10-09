from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from unittest.mock import MagicMock
from fastapi import FastAPI,HTTPException,Request
from fastapi.testclient import TestClient
from agents.tool_context import ToolContext

from app.customers import Customer,CustomerStore
from app.factor_profiles import FactorProfiles,install_profile_routes
from app.factor_preparation import preparation_report
from app.factor_links import preview_link,save_link
from app.ai_source_preparation import AssistantSourcePreparation
from app.ai_factor_scenarios import AssistantFactorScenarios
from app.ai_workspace import AIJournal,build_agent,install_ai_routes
from tests import test_factor_preparation as preparation_fixtures


class ProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.customers=CustomerStore(Path(self.tmp.name)/'customers.sqlite')
        self.id=self.customers.save([Customer(customer='A',products=[{'sku':'P','unit':'tonnes'}])])['ids'][0]
        self.store=FactorProfiles(self.customers)
        self.run={'unit':'tonnes','metadata':{'a':{'customer':'A','sku':'P'},'b':{'customer':'B','sku':'P'}},'series':{'a':{},'b':{}}}

    def save(self,context,sku='',unit='',revision=0):
        return self.store.save(self.id,{'context':context,'sku':sku,'unit':unit,'expected_revision':revision})

    def test_restart_keeps_default_and_no_mutation_to_forecast(self):
        before=deepcopy(self.run);self.save({'currency_exposure':True})
        rows=FactorProfiles(CustomerStore(self.customers.path)).for_run(self.run)['profiles']
        self.assertEqual(len(rows),1);self.assertTrue(rows[0]['inherited']);self.assertTrue(rows[0]['context']['currency_exposure'])
        self.assertEqual(self.run,before)

    def test_product_replaces_not_unions_default_and_clear_inherits(self):
        self.save({'currency_exposure':True,'materials':['lead']})
        self.save({'global_supply':True},'P','tonnes')
        row=self.store.for_run(self.run)['profiles'][0]
        self.assertFalse(row['inherited']);self.assertFalse(row['context']['currency_exposure']);self.assertEqual(row['context']['materials'],[])
        self.save(None,'P','tonnes',1)
        self.assertTrue(self.store.for_run(self.run)['profiles'][0]['inherited'])
        with self.customers.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM factor_profiles').fetchone()[0],3)

    def test_conflicting_save_does_not_overwrite_and_strict_declarations(self):
        self.save({'materials':['lead']})
        with self.assertRaises(HTTPException) as cm:self.save({'materials':['zinc']})
        self.assertEqual(cm.exception.status_code,409)
        for patch in ({'context':{'currency_exposure':'yes'}},{'expected_revision':True},
                      {'context':{'materials':['lead','lead']}},{'context':{'url':'https://bad.invalid'}},
                      {'sku':'P'},{'sku':'Other','unit':'tonnes'}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                self.store.save(self.id,{'context':{},'expected_revision':1,**patch})
        self.assertEqual(self.store.rows(self.id)[0]['revision'],1)

    def test_inactive_renamed_missing_units_and_removed_products_not_guessed(self):
        self.save({'materials':['lead']},'P','tonnes')
        run=deepcopy(self.run);run['unit']='kg';self.assertEqual(self.store.for_run(run)['profiles'],[])
        run=deepcopy(self.run);run['metadata']['a']['customer']='a';self.assertEqual(self.store.for_run(run)['profiles'],[])
        self.customers.save([Customer(customer='A',products=[])],self.id)
        self.assertEqual(self.store.for_run(self.run)['profiles'],[])
        self.customers.save([Customer(customer='A',active=False)],self.id)
        with self.assertRaises(ValueError):self.save({})

    def test_routes_profile_save_does_not_change_directory_and_empty_profile_is_explicit(self):
        app=FastAPI();install_profile_routes(app,self.store);client=TestClient(app);self.addCleanup(client.close)
        before=self.customers.list();url=f'/api/customers/{self.id}/factor-profiles'
        self.assertEqual(client.put(url,json={'context':{},'expected_revision':0}).status_code,200)
        self.assertEqual(client.get(url).json()['profiles'][0]['context']['materials'],[])
        self.assertEqual(self.customers.list(),before)
        self.assertEqual(client.put(url,json={'context':{},'expected_revision':0}).status_code,409)
        self.assertEqual(client.get('/api/customers/missing/factor-profiles').status_code,404)


class ProfileWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.p=preparation_fixtures.PreparationTests();self.p.setUp();self.addCleanup(self.p.doCleanups)
        self.f=self.p.f;self.f.base['metadata']={'A':{'customer':'A','sku':'SKU'},'B':{'customer':'B','sku':'SKU'}}
        self.f.base['unit']='tonnes'
        self.customers=CustomerStore(self.f.root/'customers.sqlite');self.profiles=FactorProfiles(self.customers)
        self.customer=self.customers.save([Customer(customer='A',products=[{'sku':'SKU','unit':'tonnes'}])])['ids'][0]
        self.profiles.save(self.customer,{'context':{'materials':['aluminum']},'expected_revision':0})
        self.adapter=AssistantSourcePreparation(self.f.base,self.f.store,self.f.factors,self.p.live,self.profiles)
        self.journal=AIJournal(self.f.root/'journal.sqlite');self.submit=MagicMock()

    def payload(self):
        report=self.adapter.preview('A');row=report['recommendations'][-1]
        return {'links':[{**row['link'],'future_value':150}],'method':row['method'],'series_ids':['A'],
                'preparation':{'context':report['context'],'review_token':report['review_token'],
                               'snapshot_ids':[row['snapshot_id']],'profile_series_id':'A'}}

    async def test_exact_scope_save_provenance_and_original_preserved(self):
        payload=self.payload();before=deepcopy(self.f.dataset)
        report=preview_link(self.f.base,self.f.store,self.f.factors,payload,self.p.live,self.profiles)
        saved=save_link(self.f.base,self.f.store,self.f.factors,{**payload,'reviewed':True,
            'review_token':report['review_token'],'request_id':str(uuid.uuid4())},self.p.live,self.profiles)
        binding=saved['scenario_provenance']['alignment']['preparation']['profile']
        self.assertEqual(binding['customer_id'],self.customer);self.assertEqual(binding['revision'],1)
        self.assertEqual(saved['scenario_provenance']['alignment']['series_count'],1)
        self.assertEqual(self.f.store.get(before['id']),before)

    async def test_scope_expansion_and_tampered_context_are_blocked(self):
        for patch in ({'series_ids':['A','B']},{'series_ids':['B']},{'series_ids':None},
                      {'preparation':{**self.payload()['preparation'],'context':{'materials':['lead']}}}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                preview_link(self.f.base,self.f.store,self.f.factors,{**self.payload(),**patch},self.p.live,self.profiles)

    async def test_profile_drives_real_scoped_calculation_without_changing_other_customer(self):
        from app import main
        from unittest.mock import patch
        runs=self.f.root/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.f.store),patch.object(main,'RUNS_DIR',runs):
            base=await main.run_saved(main.SavedRunConfig(dataset_id=self.f.dataset['id']))
            self.f.base=base;self.adapter=AssistantSourcePreparation(base,self.f.store,self.f.factors,self.p.live,self.profiles)
            series_id=next(p['series_id'] for p in self.adapter.choices()['profiles'])
            report=self.adapter.preview(series_id);row=report['recommendations'][-1]
            body={'links':[{**row['link'],'future_value':150}],'method':row['method'],'series_ids':[series_id],
                  'preparation':{'context':report['context'],'snapshot_ids':[row['snapshot_id']],
                                 'review_token':report['review_token'],'profile_series_id':series_id}}
            preview=preview_link(base,self.f.store,self.f.factors,body,self.p.live,self.profiles)
            saved=save_link(base,self.f.store,self.f.factors,{**body,'reviewed':True,
                'review_token':preview['review_token'],'request_id':str(uuid.uuid4())},self.p.live,self.profiles)
            candidate=await main.run_saved(main.SavedRunConfig(dataset_id=saved['id'],base_run_id=base['run_id']))
            other=next(k for k,v in base['metadata'].items() if v.get('customer')=='B')
            self.assertEqual(candidate['series'][other]['forecast'],base['series'][other]['forecast'])
            self.assertIsNone(candidate['metrics']['wape_pct'])
            self.assertEqual(candidate['scenario']['alignment']['preparation']['profile']['customer_id'],self.customer)

    async def test_profile_revision_archive_and_source_change_invalidate_prepared_evidence(self):
        payload=self.payload();action=self.adapter.proposal('A')
        self.profiles.save(self.customer,{'context':{'materials':['aluminum']},'expected_revision':1})
        with self.assertRaises(ValueError):self.adapter.open(action)
        with self.assertRaises(ValueError):preview_link(self.f.base,self.f.store,self.f.factors,payload,self.p.live,self.profiles)
        action=self.adapter.proposal('A');self.p.live.write('commodities',{'enabled':True,'last_success':'2026-09-01T00:00:00Z'})
        with self.assertRaises(ValueError):self.adapter.open(action)
        self.customers.save([Customer(customer='A',active=False)],self.customer)
        self.assertEqual(self.adapter.choices()['profiles'],[])

    async def test_unknown_profiles_and_factor_test_variant_methods(self):
        with self.assertRaises(ValueError):self.adapter.preview('B')
        with self.assertRaises(ValueError):preparation_report(self.f.base,self.f.store,self.f.factors,self.p.live,{'profile_series_id':'A','url':'x'},self.profiles)
        self.f.base['method_selection']='factor_test';self.f.base['leaderboard']=[{'model':'Ridge + drivers [FX]'}]
        self.assertEqual(AssistantFactorScenarios(self.f.base,self.f.store,self.f.factors).choices()['methods'],['model:Ridge + drivers'])

    async def test_real_sdk_tools_prepare_only_and_no_writes(self):
        before=self.f.store.list();actions=[]
        agent=build_agent('decision','test',self.f.base,None,actions,source_preparation=self.adapter)
        async def invoke(name,args):
            raw=json.dumps(args);tool=next(t for t in agent.tools if t.name==name)
            return await tool.on_invoke_tool(ToolContext(context=None,tool_name=name,tool_call_id='synthetic',tool_arguments=raw),raw)
        self.assertEqual((await invoke('inspect_factor_profiles',{}))['profiles'][0]['series_id'],'A')
        self.assertEqual((await invoke('preview_profile_sources',{'series_id':'A'}))['series_ids'],['A'])
        self.assertIn('error',await invoke('prepare_profile_sources',{'series_id':'B'}));self.assertEqual(actions,[])
        result=await invoke('prepare_profile_sources',{'series_id':'A'})
        self.assertTrue(result['requires_review']);self.assertFalse(result['workflow_opened'])
        await invoke('prepare_profile_sources',{'series_id':'A'});self.assertEqual(len(actions),1)
        self.assertEqual(self.f.store.list(),before);self.submit.assert_not_called()

    async def test_owner_bound_expired_changed_and_repeat_navigation_no_jobs(self):
        app=FastAPI()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal={'issuer':'test','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_ai_routes(app,self.journal,lambda _:self.f.base,None,self.f.store,self.submit,
                          factors=self.f.factors,live=self.p.live,profiles=self.profiles)
        client=TestClient(app);self.addCleanup(client.close)
        actor=json.dumps(['test','alice']);key=self.journal.put(actor,{'run_id':self.f.base['run_id'],'actions':[self.adapter.proposal('A')]})
        url=f'/api/ai/turns/{key}/actions/0'
        self.assertEqual(client.post(url,headers={'actor':'bob'}).status_code,400)
        response=client.post(url);self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['workflow'],'factor_preparation');self.assertEqual(response.json(),client.post(url).json())
        self.assertNotIn('results',self.journal.get(key,actor));self.submit.assert_not_called()
        from unittest.mock import patch
        with patch('app.ai_workspace.time.time',return_value=10**12):self.assertEqual(client.post(url).status_code,400)
        self.profiles.save(self.customer,{'context':{},'expected_revision':1})
        self.assertEqual(client.post(url).status_code,400)

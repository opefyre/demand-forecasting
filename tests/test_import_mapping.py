import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.datasets import DatasetStore
from app.ai_workspace import AIJournal, install_ai_routes
from app.import_mapping import ImportMappingRequest, MappingSuggestion, mapping_evidence, suggest_import_mapping
from app.input_review import validate_import


class ImportMappingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store=DatasetStore(Path(self.tmp.name)/'datasets')
        self.raw=('date,series,customer,sku,revenue,quantity\n'+''.join(
            f'2025-{m:02d}-01,A/P,A,P,{m*100},{m}\n' for m in range(1,7))).encode()
        self.source=self.store.upload('history.csv',self.raw,'history')
        self.payload=ImportMappingRequest(sources={'history':self.source['id']},settings={
            'date_col':'date','target_col':'revenue','item_col':'series','customer_col':'customer',
            'sku_col':'sku','unit':'tonnes','frequency':'monthly','horizon':3},consent=True)
        self.status={'ready':True,'models':{'review':'review-test'}}
        self.suggestion=MappingSuggestion(changes=[{'field':'target_col','column':'quantity'}],
                                         reason='Use actual quantity, not revenue.',questions=[])

    async def run_suggestion(self, suggestion=None, callback=None):
        async def fake(agent, message, **kw):
            self.assertEqual(agent.model,'review-test')
            self.assertIs(agent.output_type,MappingSuggestion)
            self.assertTrue(kw['run_config'].tracing_disabled)
            self.assertFalse(agent.model_settings.store)
            self.assertEqual(kw['max_turns'],1)
            if callback: callback(agent,json.loads(message))
            return SimpleNamespace(final_output=suggestion or self.suggestion,
                context_wrapper=SimpleNamespace(usage=SimpleNamespace(requests=1,input_tokens=20,output_tokens=10)))
        with patch.dict(os.environ,{'OPENAI_API_KEY':'sk-'+'x'*40,'DEMANDLAB_AI_ENABLED':'true',
                                  'DEMANDLAB_AI_REVIEW_MODEL':'review-test'}):
            return await suggest_import_mapping(self.store,self.payload,self.status,runner=fake)

    async def test_first_upload_suggestion_has_real_totals_and_no_writes(self):
        self.assertEqual(self.store.list(),[])
        result=await self.run_suggestion()
        self.assertEqual((result['before_total'],result['after_total']),(2100,21))
        self.assertEqual(result['diff'],[{'field':'target_col','before':'revenue','after':'quantity'}])
        self.assertEqual(result['errors'],[])
        self.assertEqual(self.store.list(),[])
        self.assertEqual(self.store.source(self.source['id'])[1],self.raw)

    async def test_pair_grouping_is_visible_to_mapping_reviewer_without_extra_id(self):
        self.payload.settings.update(series_mode='customer_product',item_col='')
        def inspect(agent,evidence):
            self.assertEqual(evidence['series_mode'],'customer_product')
            self.assertNotIn('item_col',evidence['current_mappings'])
            self.assertIn('do not ask for an extra identifier',agent.instructions)
        result=await self.run_suggestion(callback=inspect)
        self.assertEqual(result['errors'],[])
        self.assertEqual(self.store.list(),[])

    async def test_no_key_or_no_consent_never_calls_provider(self):
        runner=AsyncMock()
        for consent, ready in ((False,True),(True,False)):
            with self.assertRaises(ValueError):
                await suggest_import_mapping(self.store,self.payload.model_copy(update={'consent':consent}),
                                             {**self.status,'ready':ready},runner=runner)
        runner.assert_not_called()

    def test_evidence_comes_from_server_with_bounded_sample_not_extra_settings(self):
        self.payload.settings['private_notes']='must not leave server'
        self.payload.settings['target_col']='invented browser content'
        evidence=mapping_evidence(self.store,self.payload)
        self.assertNotIn('must not leave server',json.dumps(evidence))
        self.assertNotIn('invented browser content',json.dumps(evidence))
        self.assertEqual(len(evidence['files']['history']['sample']),3)
        self.assertEqual(evidence['files']['history']['rows'],6)
        self.assertNotIn('name',evidence['files']['history'])
        with self.assertRaises(ValueError):
            ImportMappingRequest.model_validate({**self.payload.model_dump(),'sample':[{'quantity':999}]})

    async def test_invented_wrong_role_and_repeated_fields_are_rejected(self):
        for changes in ([{'field':'target_col','column':'invented'}],
                        [{'field':'future_date_col','column':'date'}],
                        [{'field':'target_col','column':'quantity'}]*2):
            with self.assertRaises(ValueError):
                await self.run_suggestion(MappingSuggestion(changes=changes,reason='Review',questions=[]))
        self.assertEqual(self.store.list(),[])

    def test_unsupported_fields_and_edits_rejected(self):
        for change in ({'field':'unit','column':'kg'}, {'field':'target_col','column':'quantity','cells':[0]}):
            with self.assertRaises(ValueError):
                MappingSuggestion(changes=[change],reason='Review',questions=[])

    async def test_incomplete_factor_setup_reports_problem_without_inventing_values(self):
        self.payload.settings['drivers']=['revenue']
        result=await self.run_suggestion()
        self.assertTrue(any('Future values are missing' in e for e in result['errors']))
        self.assertEqual(self.store.list(),[])

    async def test_empty_suggestion_is_allowed(self):
        result=await self.run_suggestion(MappingSuggestion(changes=[],reason='Need confirmation.',questions=['Which column holds actual sales?']))
        self.assertEqual(result['diff'],[])
        self.assertEqual(len(result['questions']),1)

    def test_role_mismatch_and_excessive_columns_rejected(self):
        future=self.store.upload('factors.csv',self.raw,'future')
        with self.assertRaisesRegex(ValueError,'wrong role'):
            mapping_evidence(self.store,self.payload.model_copy(update={'sources':{'history':future['id']}}))
        wide=','.join('c'+str(i) for i in range(41))+'\n'+','.join('1' for i in range(41))+'\n'
        source=self.store.upload('wide.csv',wide.encode(),'history')
        with self.assertRaisesRegex(ValueError,'40 columns'):
            mapping_evidence(self.store,self.payload.model_copy(update={'sources':{'history':source['id']}}))

    async def test_corruption_during_request_blocks_return(self):
        def corrupt(*args):
            (self.store.root/f'{self.source["id"]}.bin').write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError,'changed since import'):
            await self.run_suggestion(callback=corrupt)

    def test_manual_validation_blocks_mixed_customers_and_retains_original(self):
        raw=self.raw+b'2025-06-01,A/P,B,P,600,6\n'
        source=self.store.upload('mixed.csv',raw,'history')
        with self.assertRaisesRegex(ValueError,'different customer'):
            validate_import(self.store,{'history':source['id']},self.payload.settings)
        self.assertEqual(self.store.list(),[])

    def test_manual_duplicates_are_warned_not_removed(self):
        raw=self.raw+self.raw.splitlines(keepends=True)[1]
        source=self.store.upload('repeat.csv',raw,'history')
        review=validate_import(self.store,{'history':source['id']},{**self.payload.settings,'target_col':'quantity'})
        self.assertTrue(any('identical rows' in w for w in review['warnings']))
        self.assertEqual(review['summary']['total_demand'],22)

    def test_route_needs_no_run_and_sanitizes_provider_failure(self):
        app=FastAPI()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal=None
            return await call_next(request)
        install_ai_routes(app,AIJournal(Path(self.tmp.name)/'ai.sqlite3'),None,None,self.store,None)
        with TestClient(app) as client, patch('app.ai_workspace.suggest_import_mapping',new_callable=AsyncMock) as mocked:
            mocked.return_value={'diff':[]}
            self.assertEqual(client.post('/api/ai/import-mapping',json=self.payload.model_dump()).json(),{'diff':[]})
            mocked.side_effect=RuntimeError('secret provider payload')
            failed=client.post('/api/ai/import-mapping',json=self.payload.model_dump())
            self.assertEqual(failed.status_code,502)
            self.assertNotIn('secret',failed.text)
        self.assertEqual(self.store.list(),[])

    def test_public_save_cannot_skip_validation(self):
        from app.main import save_dataset, validate_dataset, DatasetConfig
        from fastapi import HTTPException
        source=self.store.upload('mixed.csv',self.raw+b'2025-06-01,A/P,B,P,600,6\n','history')
        config=DatasetConfig(name='Mixed',sources={'history':source['id']},settings=self.payload.settings,accept_warnings=True)
        with patch('app.main.DATASET_STORE',self.store):
            for action in (validate_dataset,save_dataset):
                with self.assertRaises(HTTPException): action(config)
        self.assertEqual(self.store.list(),[])

    def test_public_save_acknowledgement_and_retry(self):
        from app.main import save_dataset, DatasetConfig
        from fastapi import HTTPException
        settings={**self.payload.settings,'customer_col':'','sku_col':''}
        config=DatasetConfig(name='History',sources=self.payload.sources,settings=settings,request_id='first-import')
        with patch('app.main.DATASET_STORE',self.store):
            with self.assertRaises(HTTPException): save_dataset(config)
            config.accept_warnings=True
            saved=save_dataset(config)
            self.assertEqual(saved,save_dataset(config))
        self.assertEqual(len(self.store.list()),1)
        self.assertEqual(self.store.source(self.source['id'])[1],self.raw)

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from agents.tool_context import ToolContext
from app.datasets import DatasetStore
from app.input_corrections import correction_evidence, correction_proposal, apply_correction
from app.input_review import input_report
from app.input_refresh import repeat_review
from app.ai_workspace import AIJournal, build_agent, install_ai_routes


def fixture(root):
    store=DatasetStore(Path(root)/'datasets')
    raw=('date,item,customer,sku,qty\n'+''.join(
        f'2025-{m:02d}-01,A/P, A ,0001, {m} \n' for m in range(1,7))).encode()
    file=store.upload('sales.csv',raw,'history')
    settings={'date_col':'date','target_col':'qty','item_col':'item','customer_col':'customer',
        'sku_col':'sku','frequency':'monthly','horizon':3,'unit':'tonnes','outlier_strategy':'none'}
    parent=store.save('Sales',{'history':file['id']},settings,'synthetic_sample',True)
    return store,file,parent,raw


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store,self.file,self.parent,self.raw=fixture(self.tmp.name)

    def proposal(self):
        return correction_proposal(self.store,self.parent['id'],correction_evidence(self.store,self.parent)['cells'],'Trim outer spaces only')

    def test_readonly_exact_cells_and_identifiers(self):
        evidence=correction_evidence(self.store,self.parent)
        self.assertEqual(evidence['candidate_count'],6)
        self.assertEqual(evidence['cells'][0],{'row':1,'column':'customer','before':' A ','after':'A'})
        self.assertFalse(any(c['column']=='sku' for c in evidence['cells']))
        self.assertEqual(len(self.store.list()),1)

    def test_save_preserves_numbers_rows_originals_and_retry(self):
        proposal=self.proposal()
        self.assertEqual((proposal['before_prepared_total'],proposal['after_prepared_total']),(21,21))
        saved=apply_correction(self.store,proposal,'Planner','format-save')
        self.assertEqual(saved['sources'],self.parent['sources'])
        self.assertEqual(saved['parent_dataset_id'],self.parent['id'])
        self.assertEqual(self.store.get(self.parent['id']),self.parent)
        self.assertEqual(self.store.source(self.file['id'])[1],self.raw)
        self.assertEqual(apply_correction(self.store,proposal,'Planner','format-save'),saved)
        self.assertEqual(input_report(self.store,saved)['summary']['total_demand'],21)
        self.assertEqual(correction_evidence(self.store,saved)['candidate_count'],0)

    def test_forbidden_guesses_duplicates_missing_and_nonexistent_rows(self):
        for changes in ([{'row':1,'column':'qty','before':'1','after':'999'}],
            [{'row':100,'column':'customer','before':' A ','after':'A'}],
            [{'row':1,'column':'sku','before':'0001','after':'1'}],
            [{'row':1,'column':'customer','before':' A ','after':'B'}],
            [correction_evidence(self.store,self.parent)['cells'][0]]*2,[]):
            with self.assertRaises(ValueError):
                correction_proposal(self.store,self.parent['id'],changes,'No guessing')

    def test_stale_corrupt_or_tampered_proposals_block(self):
        proposal=self.proposal(); proposal['after_prepared_total']=999
        with self.assertRaisesRegex(ValueError,'evidence changed'):apply_correction(self.store,proposal,'P','bad')
        proposal=self.proposal()
        (self.store.root/f'{self.file["id"]}.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed since import'):apply_correction(self.store,proposal,'P','stale')

    def test_persian_digits_keep_declared_dates_quantities_and_codes(self):
        raw=('date,item,customer,sku,qty\n'+''.join(
            f'۱۴۰۴/۰{m}/۰۱,A/P,A,۰۰۰۱,{str(m).translate(str.maketrans("123456","۱۲۳۴۵۶"))}\n' for m in range(1,7))).encode()
        file=self.store.upload('persian.csv',raw,'history')
        settings={**self.parent['settings'],'history_calendar':'jalali','month_basis':'jalali'}
        source=self.store.save('Persian',{'history':file['id']},settings,'synthetic_sample',True)
        evidence=correction_evidence(self.store,source)
        self.assertEqual(len(evidence['cells']),12)
        self.assertFalse(any(c['column']=='sku' for c in evidence['cells']))
        proposal=correction_proposal(self.store,source['id'],evidence['cells'],'Keep same Persian dates and quantities')
        self.assertEqual((proposal['before_prepared_total'],proposal['after_prepared_total']),(21,21))

    def test_new_file_cannot_inherit_row_overlays(self):
        saved=apply_correction(self.store,self.proposal(),'P','format')
        new=self.store.upload('updated.csv',self.raw.replace(b' A ',b' B '),'history')
        with self.assertRaisesRegex(ValueError,'another history file'):
            self.store.save('Bad reuse',{'history':new['id']},saved['settings'],accept_warnings=True)

    def test_repeat_reports_changed_removed_added_periods_no_append(self):
        raw=self.raw.replace(b'2025-01-01,A/P, A ,0001, 1 \n',b'').replace(b'0001, 6 ',b'0001, 60 ')+b'2025-07-01,A/P, A ,0001,7\n'
        new=self.store.upload('updated.csv',raw,'history')
        review=repeat_review(self.store,self.parent['id'],{'history':new['id']},self.parent['settings'],'synthetic_sample')
        self.assertEqual((review['added_groups'],review['removed_groups'],review['changed_groups']),(1,1,1))
        self.assertEqual(review['removed_periods'],['2025-01-01'])
        self.assertEqual((review['before_total'],review['after_total']),(21,81))
        self.assertEqual(review['mode'],'replacement_not_append')
        self.assertEqual(len(self.store.list()),1)

    def test_repeat_same_contents_and_meaning_change(self):
        new=self.store.upload('copy.csv',self.raw,'history')
        review=repeat_review(self.store,self.parent['id'],{'history':new['id']},self.parent['settings'],'synthetic_sample')
        self.assertTrue(review['same_file_contents']);self.assertEqual(review['change_count'],0)
        with self.assertRaisesRegex(ValueError,'same unit'):
            repeat_review(self.store,self.parent['id'],{'history':new['id']},{**self.parent['settings'],'unit':'kg'},'synthetic_sample')

    def test_execute_confirmation_actor_and_no_forecast(self):
        app=FastAPI();journal=AIJournal(Path(self.tmp.name)/'ai.sqlite3');submit=MagicMock()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal={'issuer':'company','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        key=journal.put(json.dumps(['company','alice']),{'actions':[self.proposal()]})
        install_ai_routes(app,journal,None,None,self.store,submit)
        with TestClient(app) as client:
            path=f'/api/ai/turns/{key}/actions/0'
            for payload in (None,{'corrections_confirmed':'true'},{'corrections_confirmed':False}):
                self.assertEqual(client.post(path,json=payload).status_code,400)
            self.assertEqual(client.post(path,json={'corrections_confirmed':True},headers={'actor':'bob'}).status_code,400)
            result=client.post(path,json={'corrections_confirmed':True});self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(client.post(path,json={'corrections_confirmed':True}).json(),result.json())
        submit.assert_not_called()

    def test_repeat_api_review_required_and_receipt_preserved(self):
        import app.main as main
        new=self.store.upload('updated.csv',self.raw+b'2025-07-01,A/P, A ,0001,7\n','history')
        payload={'name':'Updated','sources':{'history':new['id']},'settings':self.parent['settings'],
            'classification':'synthetic_sample','parent_dataset_id':self.parent['id'],'request_id':'repeat-test'}
        with patch.object(main,'DATASET_STORE',self.store),TestClient(main.app) as client:
            preview=client.post('/api/datasets/validate',json=payload)
            self.assertEqual(preview.status_code,200,preview.text)
            self.assertEqual(preview.json()['repeat_upload']['after_total'],28)
            self.assertEqual(client.post('/api/datasets',json=payload).status_code,400)
            saved=client.post('/api/datasets',json={**payload,'accept_warnings':True})
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(saved.json()['import_provenance']['kind'],'repeat_history_review')
            self.assertEqual(client.post('/api/datasets',json={**payload,'accept_warnings':True}).json(),saved.json())

    def test_actual_forecast_uses_corrected_names_and_preserves_quantities(self):
        import app.main as main
        saved=apply_correction(self.store,self.proposal(),'P','actual-format')
        runs=Path(self.tmp.name)/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.store),patch.object(main,'RUNS_DIR',runs),TestClient(main.app) as client:
            response=client.post('/api/run-saved',json={'dataset_id':saved['id'],'method':'model:Last observed'})
            self.assertEqual(response.status_code,200,response.text)
            run=response.json()
            self.assertEqual(run['metadata']['A/P']['customer'],'A')
            self.assertEqual(run['metadata']['A/P']['sku'],'0001')
            self.assertEqual(run['summary']['total_demand'],21)
            self.assertEqual(run['input_manifest']['sources'][0]['sha256'],self.file['sha256'])


class CorrectionToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_tools_propose_only(self):
        with tempfile.TemporaryDirectory() as root:
            store,file,parent,raw=fixture(root);actions=[]
            agent=build_agent('review','test',{'run_id':None,'dataset_id':parent['id'],'metadata':{}},None,actions,store)
            async def invoke(name,args):
                tool=next(t for t in agent.tools if t.name==name)
                context=ToolContext(context=None,tool_name=name,tool_call_id='test',tool_arguments=json.dumps(args))
                return await tool.on_invoke_tool(context,json.dumps(args))
            evidence=await invoke('inspect_input_formatting',{})
            proposal=await invoke('prepare_input_corrections',{'changes':evidence['cells'],'reason':'Remove outer spaces'})
            self.assertTrue(proposal['requires_review'])
            refresh=await invoke('prepare_history_refresh',{})
            self.assertFalse(refresh['workflow_opened']);self.assertEqual(len(store.list()),1)
            self.assertEqual([a['kind'] for a in actions],['input_correction','history_refresh'])

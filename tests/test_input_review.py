import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from agents.tool_context import ToolContext
from app.datasets import DatasetStore
from app.input_review import input_report, mapping_proposal, apply_mapping
from app.ai_workspace import AIJournal, build_agent, install_ai_routes


def fixture(root):
    store=DatasetStore(Path(root)/'datasets')
    data=('date,item,customer,sku,qty,actual\n'+''.join(
        f'2025-{m:02d}-01,A/P,A,P,{m},{m*10}\n' for m in range(1,7))).encode()
    source=store.upload('history.csv',data,'history')
    settings={'date_col':'date','target_col':'qty','item_col':'item','customer_col':'customer',
        'sku_col':'sku','frequency':'monthly','horizon':3,'unit':'tonnes','outlier_strategy':'none'}
    parent=store.save('History',{'history':source['id']},settings,accept_warnings=True)
    return store,source,parent,data


class InputReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store,self.source,self.parent,self.raw=fixture(self.tmp.name)

    def proposal(self,**kw):
        return mapping_proposal(self.store,self.parent['id'],kw.get('changes',[{'field':'target_col','column':'actual'}]),'Client confirmed actual is the sales quantity.')

    def test_preview_has_no_writes_and_reports_actual_numeric_impact(self):
        before=self.store.list();proposal=self.proposal()
        self.assertEqual(self.store.list(),before)
        self.assertEqual((proposal['before_total'],proposal['after_total']),(21,210))
        self.assertEqual((proposal['before_prepared_total'],proposal['after_prepared_total']),(21,210))
        self.assertEqual(proposal['diff'],[{'field':'target_col','before':'qty','after':'actual'}])

    def test_approval_creates_reversible_version_preserving_source_and_retry(self):
        proposal=self.proposal()
        saved=apply_mapping(self.store,proposal,'Planner','mapping-confirmation-1')
        self.assertEqual(saved['parent_dataset_id'],self.parent['id'])
        self.assertEqual(saved['settings']['target_col'],'actual')
        self.assertEqual(saved['classification'],self.parent['classification'])
        self.assertEqual(saved['sources'],self.parent['sources'])
        self.assertEqual(self.store.get(self.parent['id']),self.parent)
        self.assertEqual(self.store.source(self.source['id'])[1],self.raw)
        self.assertEqual(apply_mapping(self.store,proposal,'Planner','mapping-confirmation-1'),saved)
        self.assertEqual(len(self.store.list()),2)
        self.assertEqual(saved['import_provenance']['actor'],'Planner')

    def test_forbidden_or_invented_mapping_changes_are_rejected(self):
        for changes in ([],[{'field':'unit','column':'kg'}],[{'field':'target_col','column':'invented'}],
            [{'field':'target_col','column':'actual'},{'field':'target_col','column':'qty'}],
            [{'field':'target_col','column':'qty'}],[{'field':'target_col','column':'actual','replace_values':0}]):
            with self.assertRaises(ValueError):self.proposal(changes=changes)

    def test_source_corruption_cannot_be_approved(self):
        proposal=self.proposal()
        # Simulate external corruption only inside the temporary test workspace.
        (self.store.root/f'{self.source["id"]}.bin').write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError,'changed since import'):
            apply_mapping(self.store,proposal,'Planner','changed-source')

    def test_tampered_preview_cannot_be_approved(self):
        proposal=self.proposal();proposal['after_total']=999
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            apply_mapping(self.store,proposal,'Planner','bad-preview')

    def test_missing_factors_are_explained_not_invented(self):
        source={**self.parent,'settings':{**self.parent['settings'],'drivers':['actual']}}
        report=input_report(self.store,source)
        self.assertTrue(any('Future values are missing' in e for e in report['errors']))
        self.assertEqual(self.store.source(self.source['id'])[1],self.raw)

    def test_ambiguous_customer_series_blocks_proposal(self):
        raw=self.raw+b'2025-06-01,A/P,B,P,6,60\n'
        source=self.store.upload('ambiguous.csv',raw,'history')
        # A legacy saved input may predate the grouping guard; read-only review
        # must still explain it, while new saves now reject the ambiguous input.
        parent={**self.parent,'sources':{'history':source['id']}}
        report=input_report(self.store,parent)
        self.assertTrue(any('different customer' in e for e in report['errors']))
        with patch.object(self.store,'get',return_value=parent), self.assertRaisesRegex(ValueError,'customer'):
            mapping_proposal(self.store,parent['id'],[{'field':'target_col','column':'actual'}],'Confirmed quantity')

    def test_identical_rows_are_flagged_not_deleted(self):
        source=self.store.upload('repeated.csv',self.raw+self.raw.splitlines(keepends=True)[1],'history')
        parent=self.store.save('Repeated',{'history':source['id']},self.parent['settings'],accept_warnings=True)
        report=input_report(self.store,parent)
        self.assertEqual(report['files']['history']['rows'],7)
        self.assertTrue(any('2 identical rows' in w for w in report['warnings']))
        self.assertEqual(report['source_quantity_total'],22)

    def test_route_requires_own_proposal_and_saves_without_running_forecast(self):
        journal=AIJournal(Path(self.tmp.name)/'ai.sqlite3')
        key=journal.put(json.dumps(['company','alice']),{'actions':[self.proposal()]})
        app=FastAPI();submit=MagicMock()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal={'issuer':'company','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_ai_routes(app,journal,None,None,self.store,submit)
        with TestClient(app) as client:
            path=f'/api/ai/turns/{key}/actions/0'
            self.assertEqual(client.post(path,headers={'actor':'bob'}).status_code,400)
            response=client.post(path);self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(client.post(path).json(),response.json())
        submit.assert_not_called()
        self.assertEqual(len(self.store.list()),2)


class InputReviewToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_sdk_tools_read_and_propose_without_writing(self):
        with tempfile.TemporaryDirectory() as root:
            store,source,parent,raw=fixture(root)
            actions=[];run={'run_id':'run','dataset_id':parent['id'],'metadata':{}}
            agent=build_agent('review','test-review',run,None,actions,store)
            async def invoke(name,args):
                tool=next(t for t in agent.tools if t.name==name)
                context=ToolContext(context=None,tool_name=name,tool_call_id='test',tool_arguments=json.dumps(args))
                return await tool.on_invoke_tool(context,json.dumps(args))
            report=await invoke('inspect_inputs',{})
            self.assertEqual(report['source_quantity_total'],21)
            proposed=await invoke('prepare_input_mapping',{'changes':[{'field':'target_col','column':'actual'}],'reason':'Confirmed actual quantity'})
            self.assertTrue(proposed['requires_review']);self.assertEqual(actions[0]['after_total'],210)
            self.assertEqual(len(store.list()),1)

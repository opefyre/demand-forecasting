import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from agents.tool_context import ToolContext
from app.ai_forecast import forecast_preflight, method_evidence
from app.ai_workspace import build_agent, AIJournal, install_ai_routes
from tests.test_sales_demand import fixture


class ForecastPreflightTests(unittest.TestCase):
    def setUp(self):
        self.run,_=fixture();self.run['dataset_id']='dataset'
        self.source={'settings':{'frequency':'monthly','horizon':6},'sources':{'history':'h','future':'f','operations':'old'},
                     'classification':'synthetic_sample','review':{'warnings':[]}}
        self.store=MagicMock();self.store.get.return_value=self.source;self.store.inspect.return_value={'warnings':[]}

    def proposal(self):
        actions=[];agent=build_agent('decision','fake',self.run,None,actions,datasets=self.store)
        tool=next(t for t in agent.tools if t.name=='prepare_forecast')
        result=asyncio.run(tool.on_invoke_tool(ToolContext(context=None,tool_name=tool.name,tool_call_id='t',tool_arguments='{}'),
            json.dumps({'customer':'A','months':10,'method':'recommended'})))
        return result,actions

    def test_preflight_passes_and_only_proposes(self):
        result,actions=self.proposal()
        self.assertTrue(result['requires_review']);self.assertEqual(actions[0]['months'],10)
        self.store.save.assert_not_called()
        self.assertEqual(self.store.inspect.call_args.args[0],{'history':'h','future':'f'})

    def test_missing_future_values_block_proposal(self):
        self.store.inspect.side_effect=ValueError('Future factor values missing for new months')
        result,actions=self.proposal();self.assertIn('missing',result['error']);self.assertEqual(actions,[])

    def test_new_warnings_block_but_accepted_warnings_do_not(self):
        self.store.inspect.return_value={'warnings':['Gap warning']}
        self.assertEqual(self.proposal()[1],[])
        self.source['review']['warnings']=['Gap warning']
        self.assertEqual(len(self.proposal()[1]),1)

    def test_scenario_horizon_is_blocked_before_review_card(self):
        self.source['scenario_provenance']={'factor':'rate'}
        result,actions=self.proposal();self.assertIn('baseline',result['error']);self.assertEqual(actions,[])
        self.store.inspect.assert_not_called()

    def test_model_evidence_preserves_errors_and_limits_traces(self):
        run={'leaderboard':[{'model':'A','wape_pct':5,'confirmation':{'wape_pct':8},'horizon_metrics':['x']*1000}]*41,
             'metrics':{'wape_pct':8,'independent_accuracy_verified':False,'range_check':{'rows':['x']*1000}},
             'warnings':['Short history'],'source_classification':'synthetic_sample'}
        result=method_evidence(run)
        self.assertEqual(len(result['leaderboard']),40);self.assertTrue(result['truncated'])
        self.assertEqual(result['leaderboard'][0]['confirmation']['wape_pct'],8)
        self.assertFalse(result['metrics']['independent_accuracy_verified'])
        self.assertNotIn('range_check',result['metrics']);self.assertNotIn('horizon_metrics',result['leaderboard'][0])
        self.assertEqual(result['warnings'],['Short history'])


class AssistantFailureRecoveryTests(unittest.TestCase):
    def test_provider_failure_is_redacted_and_next_request_can_run(self):
        with tempfile.TemporaryDirectory() as directory:
            app=FastAPI(); journal=AIJournal(Path(directory)/'ai.sqlite3'); run,_=fixture()
            @app.middleware('http')
            async def principal(request:Request,call_next):
                request.state.principal=None;return await call_next(request)
            install_ai_routes(app,journal,lambda _:run,lambda _:None,None,None)
            with TestClient(app) as client:
                payload={'run_id':run['run_id'],'question':'Explain','consent':True}
                with patch('app.ai_workspace.run_chat',new=AsyncMock(side_effect=RuntimeError('PRIVATE provider body'))):
                    bad=client.post('/api/ai/chat',json=payload)
                self.assertEqual(bad.status_code,502);self.assertNotIn('PRIVATE',bad.text)
                with patch('app.ai_workspace.run_chat',new=AsyncMock(return_value={'answer':'Ready','actions':[]})):
                    good=client.post('/api/ai/chat',json=payload)
                self.assertEqual(good.status_code,200)

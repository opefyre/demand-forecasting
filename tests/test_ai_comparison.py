from copy import deepcopy
from datetime import timedelta
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from agents.tool_context import ToolContext
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.ai_comparison import AssistantComparisons, summarize
from app.ai_workspace import AIJournal, build_agent, install_ai_routes
from app.sales_api import run_hash
from app.sales_demand import DemandStore, demand_outlook
from tests.test_sales_demand import fixture, order, TODAY


class AssistantComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name); self.store=DemandStore(root/'orders.sqlite3')
        self.run, self.inputs=fixture(); self.inputs['orders']=[order('A',16),order('B',6,fulfilled=2,cancelled=1)]
        self.source=self.store.save(self.inputs,self.run,'initial-orders','Planner',[{'run_sha256':run_hash(self.run)}])
        self.target=deepcopy(self.run); self.target.update(run_id='scenario',base_run_id=self.run['run_id'],scenario={'type':'factor_link'})
        for key,qty in [('A',12),('B',10),('C',7)]: self.target['series'][key]['forecast'][0]['mean']=qty
        self.runs={self.run['run_id']:self.run,'scenario':self.target}
        self.list_runs=lambda:{'runs':[{'run_id':r['run_id'],'base_run_id':r.get('base_run_id'),'name':r['run_id']} for r in self.runs.values()]}
        self.outlook={**demand_outlook(self.inputs,self.run),'snapshot_id':self.source['id']}
        self.adapter=AssistantComparisons(self.store,self.runs.__getitem__,self.list_runs,self.run,self.outlook)
        self.journal=AIJournal(root/'ai.sqlite3'); app=FastAPI()
        @app.middleware('http')
        async def principal(request:Request,call_next):
            request.state.principal={'issuer':'test','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_ai_routes(app,self.journal,self.runs.__getitem__,lambda _:self.outlook,None,None,self.store,self.list_runs)
        self.client=TestClient(app); self.addCleanup(self.client.close)
        self.actor=json.dumps(['test','alice'])

    def propose(self):
        action=self.adapter.proposal('scenario')
        turn=self.journal.put(self.actor,{'run_id':self.run['run_id'],'snapshot_id':self.source['id'],'actions':[action]})
        return turn, action

    def test_exact_scope_and_full_population_aggregation(self):
        self.runs['unrelated']={**self.target,'run_id':'unrelated','base_run_id':'other'}
        self.assertEqual(self.adapter.choices(),[{'run_id':'scenario','name':'scenario'}])
        with self.assertRaisesRegex(ValueError,'exact'):self.adapter.preview('unrelated')
        report=self.adapter.preview('scenario'); result=summarize(report)
        self.assertEqual(result['totals'][0]['booked'],19)
        self.assertEqual(result['totals'][0]['before_total'],29)
        self.assertEqual(result['totals'][0]['after_total'],33)
        self.assertEqual(result['totals'][0]['after_remaining'],12)
        filtered=summarize(report,'B','001')
        self.assertEqual(filtered['totals'][0]['after_total'],10)
        self.assertEqual(filtered['matched_rows'],1)
        with self.assertRaises(ValueError): summarize(report,'not B')
        with self.assertRaises(ValueError): summarize(report,'B','other')

    def test_unknowns_and_different_units_are_never_summed_as_zero(self):
        report=self.adapter.preview('scenario'); report['rows'][1]['after_total']=None
        report['rows'][1]['difference']=None; report['rows'][2]['unit']='kg'
        result=summarize(report)
        self.assertEqual(len(result['totals']),2)
        self.assertIsNone(result['totals'][0]['after_total'])
        self.assertIsNone(result['totals'][0]['difference'])

    def test_tools_preview_and_propose_without_saving(self):
        actions=[]; agent=build_agent('decision','fake',self.run,self.outlook,actions,comparisons=self.adapter)
        async def invoke(name,values):
            tool=next(t for t in agent.tools if t.name==name)
            return await tool.on_invoke_tool(ToolContext(context=None,tool_name=name,tool_call_id='test',tool_arguments='{}'),json.dumps(values))
        preview=asyncio.run(invoke('preview_order_scenario',{'scenario_id':'scenario','customer':'A','sku':'001'}))
        self.assertEqual(preview['totals'][0]['after_total'],16);self.assertEqual(actions,[])
        for _ in range(2):asyncio.run(invoke('prepare_order_scenario',{'scenario_id':'scenario'}))
        self.assertEqual(len(actions),1);self.assertEqual(actions[0]['preview']['customer_count'],3)
        self.assertEqual(self.store.list('scenario'),[])

    def test_confirmation_is_owned_idempotent_and_survives_receipt_failure(self):
        turn, action=self.propose(); url=f'/api/ai/turns/{turn}/actions/0'
        self.assertEqual(self.client.post(url,headers={'actor':'bob'}).status_code,400)
        self.assertEqual(self.store.list('scenario'),[])
        result=self.client.post(url);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json(),self.client.post(url).json())
        self.assertEqual(len(self.store.list('scenario')),1)
        self.assertTrue(result.json()['draft'])
        saved=self.store.get(result.json()['snapshot_id'])
        self.assertEqual(saved['inputs']['orders'],self.source['inputs']['orders'])
        self.assertEqual(self.store.get(self.source['id']),self.source)
        self.assertEqual(self.journal.get(turn,self.actor)['results']['0'],result.json())
        # Store's stable request ID also protects a retry if a response/journal receipt was lost.
        self.journal.record_result(turn,self.actor,0,{})
        self.assertEqual(result.json(),self.client.post(url).json())

    def test_new_order_version_or_changed_scenario_blocks_approval(self):
        turn,_=self.propose()
        self.target['series']['A']['forecast'][0]['mean']=50
        response=self.client.post(f'/api/ai/turns/{turn}/actions/0')
        self.assertEqual(response.status_code,400);self.assertEqual(self.store.list('scenario'),[])
        self.store.save(self.inputs,self.run,'new-orders-version','Planner',[{'run_sha256':run_hash(self.run)}])
        with self.assertRaisesRegex(ValueError,'newer'): self.adapter.preview('scenario')

    def test_expired_orders_and_missing_context_cannot_propose(self):
        self.adapter.outlook=None
        with self.assertRaisesRegex(ValueError,'reviewed'): self.adapter.choices()
        self.adapter.outlook=self.outlook
        self.inputs.update(as_of=str(TODAY-timedelta(days=2)),valid_until=str(TODAY-timedelta(days=1)))
        saved=self.store.save(self.inputs,self.run,'expired-orders','Planner',[{'run_sha256':run_hash(self.run)}])
        self.adapter.outlook={**self.outlook,'snapshot_id':saved['id']}
        with self.assertRaisesRegex(ValueError,'expired'): self.adapter.proposal('scenario')

    def test_approval_checks_originating_context(self):
        action=self.adapter.proposal('scenario')
        turn=self.journal.put(self.actor,{'run_id':'other','snapshot_id':self.source['id'],'actions':[action]})
        self.assertEqual(self.client.post(f'/api/ai/turns/{turn}/actions/0').status_code,400)
        self.assertEqual(self.store.list('scenario'),[])

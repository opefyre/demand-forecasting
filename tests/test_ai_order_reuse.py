"""Agentic order reuse uses the exact existing consumption and review rules."""
from datetime import timedelta
import json
from pathlib import Path
import unittest

from agents.tool_context import ToolContext
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.ai_workspace import AIJournal, build_agent, install_ai_routes
from app.ai_order_reuse import AssistantOrderReuse
from app.sales_demand import demand_outlook
from tests import test_order_reuse
from tests.test_sales_demand import TODAY


class AIOrderReuseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        test_order_reuse.OrderReuseTests.setUp(self)
        self.listing=lambda:{'runs':[{'run_id':r['run_id'],'name':r['run_id']} for r in self.runs.values()]}
        self.adapter=AssistantOrderReuse(self.store,self.runs.__getitem__,self.listing,self.target)
        self.journal=AIJournal(Path(self.temp.name)/'ai.sqlite3')
        app=FastAPI()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal={'issuer':'company','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_ai_routes(app,self.journal,self.runs.__getitem__,None,None,None,self.store,self.listing)
        self.client=TestClient(app);self.addCleanup(self.client.close)
        self.actor=json.dumps(['company','alice'])

    async def tool(self,agent,name,args):
        method=next(t for t in agent.tools if t.name==name)
        return await method.on_invoke_tool(ToolContext(context=None,tool_name=name,
            tool_call_id='test',tool_arguments=json.dumps(args)),json.dumps(args))

    async def test_exact_choices_preview_and_proposal_do_not_save_or_guess(self):
        actions=[];agent=build_agent('decision','test',self.target,None,actions,order_reuse=self.adapter)
        choices=await self.tool(agent,'inspect_saved_orders',{})
        self.assertEqual(choices['sources'][0]['snapshot_id'],self.source['id'])
        for name in ('preview_saved_orders','prepare_saved_orders'):
            self.assertIn('error',await self.tool(agent,name,{'snapshot_id':'invented'}))
        report=await self.tool(agent,'preview_saved_orders',{'snapshot_id':self.source['id']})
        self.assertEqual(report['months'][0]['booked'],19)
        self.assertEqual(report['months'][0]['total'],29)
        self.assertEqual(report['months'][1]['total'],60)
        proposed=await self.tool(agent,'prepare_saved_orders',{'snapshot_id':self.source['id']})
        self.assertTrue(proposed['coverage_confirmation_required'])
        self.assertEqual(actions[0]['kind'],'order_reuse')
        self.assertEqual(self.store.list('new-run'),[])

    async def test_human_coverage_confirmation_is_required_and_exports_reconcile(self):
        action=self.adapter.proposal(self.source['id'])
        turn=self.journal.put(self.actor,{'run_id':'new-run','actions':[action]})
        path=f'/api/ai/turns/{turn}/actions/0'
        for body in (None,{}, {'coverage_confirmed':False},{'coverage_confirmed':'true'}):
            self.assertEqual(self.client.post(path,json=body).status_code,400)
        self.assertEqual(self.store.list('new-run'),[])
        self.assertEqual(self.client.post(path,json={'coverage_confirmed':True},headers={'actor':'bob'}).status_code,400)
        response=self.client.post(path,json={'coverage_confirmed':True})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post(path,json={'coverage_confirmed':True}).json(),response.json())
        saved=self.store.get(response.json()['snapshot_id'])
        outlook=demand_outlook(saved['inputs'],self.target)
        self.assertEqual(sum(row['total']-row['fulfilled'] for row in outlook['rows']),87)
        self.assertEqual(self.store.get(self.source['id']),self.source)
        self.assertEqual(len(self.store.list('new-run')),1)

    async def test_expired_orders_do_not_become_fresh_and_no_proposal_is_created(self):
        changed={**self.inputs,'as_of':str(TODAY-timedelta(days=2)),'valid_until':str(TODAY-timedelta(days=1))}
        self.source=self.store.save(changed,self.base,'expired-order-source','Planner',self.source['evidence'])
        actions=[];agent=build_agent('decision','test',self.target,None,actions,order_reuse=self.adapter)
        report=await self.tool(agent,'preview_saved_orders',{'snapshot_id':self.source['id']})
        self.assertFalse(report['can_save'])
        response=await self.tool(agent,'prepare_saved_orders',{'snapshot_id':self.source['id']})
        self.assertIn('error',response);self.assertEqual(actions,[])

    async def test_concurrent_order_change_invalidates_approval_and_cross_run_rejected(self):
        action=self.adapter.proposal(self.source['id'])
        turn=self.journal.put(self.actor,{'run_id':'new-run','actions':[action]})
        self.store.save(self.inputs,self.base,'updated-source-orders','Planner',self.source['evidence'])
        response=self.client.post(f'/api/ai/turns/{turn}/actions/0',json={'coverage_confirmed':True})
        self.assertEqual(response.status_code,400);self.assertEqual(self.store.list('new-run'),[])
        wrong=self.journal.put(self.actor,{'run_id':'wrong','actions':[action]})
        self.assertEqual(self.client.post(f'/api/ai/turns/{wrong}/actions/0',json={'coverage_confirmed':True}).status_code,400)

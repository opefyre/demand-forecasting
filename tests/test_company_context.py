"""Real scoped HTTP/store checks. AI is mocked; no provider or real client data."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
import uuid
import pandas as pd
from unittest.mock import AsyncMock,patch
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from app.company_workspace import CompanyWorkspaces
from app.company_context import personal_owner
from app.platform_api import create_platform_api
from app.ai_workspace import build_agent
from app.demand_releases import identity
from app.sales_api import run_hash
from tests.test_sales_demand import fixture

ALL=['inputs:read','inputs:write','customers:read','customers:write','orders:read','orders:write',
     'factors:read','factors:write','drafts:read','forecasts:run','forecasts:write','reports:read','reports:export',
     'releases:approve','views:own','chats:own','ai:query','ai:actions','settings:manage','connections:read',
     'connections:manage','connections:sync']
VIEW=['reports:read','reports:export','views:own','chats:own','ai:query']


class CompanyContextTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.workspaces=CompanyWorkspaces(Path(self.temp.name)/'companies')
        self.company,self.user,self.role,self.scopes='tehran_a','planner_a','planner',ALL.copy()
        self.app=FastAPI()
        @self.app.middleware('http')
        async def authenticated(request:Request,next):
            request.state.principal=self.who
            return await next(request)
        self.api=create_platform_api(None,self.workspaces,dispatcher=lambda *_:None)
        self.app.mount('/api/v1',self.api);self.client=TestClient(self.app)
        self.run,self.inputs=fixture();self.run['run_id']=uuid.uuid4().hex;self.inputs['run_id']=self.run['run_id']
        folder=self.ws.runs/self.run['run_id'];folder.mkdir();(folder/'result.json').write_text(json.dumps(self.run))
        self.saved=self.ws.sales.save(self.inputs,self.run,str(uuid.uuid4()),identity(self.who),[{'run_sha256':run_hash(self.run)}])
        self.run_id=self.run['run_id'];self.snapshot_id=self.saved['id']
        self.ai=AsyncMock(side_effect=self.reply)
        self.mock=patch('app.ai_workspace.run_chat',self.ai);self.mock.start()
        self.title=patch('app.ai_workspace.ai_status',return_value={'ready':False,'models':{},'configured':False,'enabled':False});self.title.start()

    @property
    def who(self):return dict(company_id=self.company,issuer='https://company.test',subject=self.user,role=self.role,
        permissions=self.scopes,mfa_required=False,auth_kind='session',session_id='test-session')
    @property
    def ws(self):return self.workspaces.for_principal(self.who)

    async def reply(self,payload,run,outlook,**kwargs):
        return dict(answer='Saved demand: '+str(sum(r['total'] for r in outlook['rows'])) if outlook else 'No forecast selected.',
            actions=[],run_id=run['run_id'],dataset_id=payload.dataset_id,snapshot_id=payload.snapshot_id,
            role='query',model='mock',usage={},provider='mock')

    def tearDown(self):
        self.mock.stop();self.title.stop();self.client.close();self.workspaces.close();self.temp.cleanup()

    def get(self,path,status=200):
        r=self.client.get('/api/v1'+path);self.assertEqual(r.status_code,status,r.text);return r.json()
    def post(self,path,body,status=200):
        r=self.client.post('/api/v1'+path,json=body);self.assertEqual(r.status_code,status,r.text);return r.json()
    def chat(self,**kwargs):return self.post('/ai/chat',dict(question='Show saved demand',run_id=self.run_id,snapshot_id=self.snapshot_id,**kwargs))
    def approve(self):
        body=dict(snapshot_id=self.snapshot_id,receiver='MRP',mode='remaining_forecast',request_id=str(uuid.uuid4()))
        report=self.post('/releases/preview',body);record=self.post('/releases',{**body,'reviewed':True,'review_token':report['review_token']},201)
        self.user='approver_a';self.role='approver'
        self.post('/releases/'+record['id']+'/approve',{'reviewed':True,'review_token':report['review_token']})
        return record

    def test_chats_are_private_to_user_and_company_including_names_and_actions(self):
        turn=self.chat();self.get('/ai/conversations/'+turn['id'])
        self.post('/ai/conversations/'+turn['id']+'/rename',{'title':'Autumn demand'})
        self.assertEqual(self.get('/ai/conversations')['chats'][0]['title'],'Autumn demand')
        self.user='other_planner';self.assertEqual(self.get('/ai/conversations')['chats'],[])
        self.get('/ai/conversations/'+turn['id'],400)
        self.user='planner_a';self.company='tehran_b'
        self.assertEqual(self.get('/ai/conversations')['chats'],[])
        self.get('/ai/conversations/'+turn['id'],400)
        self.post('/ai/chat',{'question':'Read another company','run_id':self.run_id,'snapshot_id':self.snapshot_id},404)
        self.assertEqual(self.ai.await_count,1)

    def test_role_demotion_removes_draft_context_before_provider_or_saved_text(self):
        turn=self.chat();self.role='viewer';self.scopes=VIEW.copy()
        self.assertEqual(self.get('/ai/conversations')['chats'],[])
        self.get('/ai/conversations/'+turn['id'],404)
        self.post('/ai/chat',{'question':'Read draft','run_id':self.run_id,'snapshot_id':self.snapshot_id},404)
        self.assertEqual(self.ai.await_count,1)

    def test_report_only_assistant_reads_approved_orders_not_unselected_drafts(self):
        self.approve();self.user='viewer_a';self.role='viewer';self.scopes=VIEW.copy()
        self.chat()
        kwargs=self.ai.await_args.kwargs
        self.assertIsNone(kwargs['datasets']);self.assertEqual(kwargs['allowed_tools'],{'inspect_forecast','compare_methods','prepare_export'})
        self.assertEqual(len(self.get('/runs')['runs']),1)
        self.get('/runs/'+self.run_id)
        self.get('/order-snapshots/'+self.snapshot_id+'/demand')
        # Newer, unapproved order versions are not automatically exposed as reports.
        new=self.ws.sales.save(self.inputs,self.run,str(uuid.uuid4()),identity(self.who),[{'run_sha256':run_hash(self.run)}],self.snapshot_id)
        self.get('/order-snapshots/'+new['id']+'/demand',404)
        self.assertEqual(self.get('/runs')['runs'],[])

    def test_action_rights_are_rechecked_on_old_proposals(self):
        owner=personal_owner(self.who)
        key=self.ws.journal.put(owner,dict(question='Prepare forecast',answer='Review it.',run_id=self.run_id,
            snapshot_id=self.snapshot_id,dataset_id=None,actions=[{'kind':'input_mapping'}]))
        self.scopes.remove('ai:actions')
        self.post('/ai/turns/'+key+'/actions/0',{},403)

    def test_company_service_keys_cannot_read_personal_context(self):
        self.user='service:some-key'
        self.get('/ai/conversations',403)
        self.get('/views?run_id='+self.run_id,403)

    def test_conversation_management_export_and_archive_are_owner_bound(self):
        turn=self.chat();key=turn['id']
        self.post('/ai/conversations/'+key+'/manage',{'operation':'pin'})
        self.assertTrue(self.get('/ai/conversations')['chats'][0]['pinned'])
        self.post('/ai/conversations/'+key+'/manage',{'operation':'archive'})
        self.assertEqual(self.get('/ai/conversations')['chats'],[])
        self.assertEqual(len(self.get('/ai/conversations?status=archived')['chats']),1)
        self.assertEqual(self.client.get('/api/v1/ai/conversations/'+key+'/export').status_code,200)
        self.post('/ai/conversations/'+key+'/manage',{'operation':'restore'})
        self.post('/ai/conversations/'+key+'/manage',{'operation':'trash'})
        self.post('/ai/conversations/'+key+'/manage',{'operation':'restore'})

    def test_saved_views_have_owner_bound_crud_and_company_bound_forecast_references(self):
        body=dict(name='Mehr demand',run_id=self.run_id,snapshot_id=self.snapshot_id,settings={'unit':'tonnes','customer':'A'})
        view=self.post('/views',body,201)
        r=self.client.put('/api/v1/views/'+view['id'],json={**body,'name':'All demand'});self.assertEqual(r.status_code,200)
        self.assertEqual(self.get('/views/'+view['id'])['name'],'All demand')
        self.user='planner_b';self.get('/views/'+view['id'],404)
        self.assertEqual(self.get('/views?run_id='+self.run_id)['views'],[])
        self.user='planner_a';self.company='tehran_b';self.post('/views',body,404)
        self.company='tehran_a';self.assertEqual(self.client.delete('/api/v1/views/'+view['id']).status_code,200)

    def test_settings_and_external_source_connections_do_not_share_state_or_credentials(self):
        r=self.client.put('/api/v1/settings/site',json={'name':'Tehran plant','province':'Tehran','timezone':'Asia/Tehran'});self.assertEqual(r.status_code,200)
        self.assertEqual(self.get('/workspace')['site']['name'],'Tehran plant')
        self.client.put('/api/v1/connections/external-sources/industry',json={'enabled':True})
        self.assertTrue(next(r for r in self.get('/connections/external-sources')['sources'] if r['id']=='industry')['enabled'])
        self.company='tehran_b'
        self.assertNotEqual(self.get('/workspace')['site']['name'],'Tehran plant')
        self.assertFalse(next(r for r in self.get('/connections/external-sources')['sources'] if r['id']=='industry').get('enabled'))
        self.scopes=VIEW.copy()
        self.assertEqual(self.client.put('/api/v1/settings/site',json={'name':'Wrong','province':'Tehran','timezone':'UTC'}).status_code,403)
        self.get('/connections/external-sources',403)

    def test_filtered_tool_set_is_read_only_even_for_decision_model(self):
        agent=build_agent('decision','mock',self.run,None,[],allowed_tools={'inspect_forecast','compare_methods'})
        self.assertEqual({tool.name for tool in agent.tools},{'inspect_forecast','compare_methods'})

    def test_actual_result_comparisons_are_company_scoped_and_permissioned(self):
        rows='item,period,qty\n'+''.join(f'{c},{self.inputs["as_of"][:7]}-01,{q}\n' for c,q in [('A',11),('B',8),('C',5)])
        upload=self.client.post('/api/v1/sources',data={'role':'actuals'},files={'file':('actuals.csv',rows.encode(),'text/csv')})
        self.assertEqual(upload.status_code,201)
        table=self.post('/sources/'+upload.json()['id']+'/preview',{'header_row':1})
        config=dict(source_id=upload.json()['id'],mapping=dict(zip(['item_id','timestamp','actual'],[c['id'] for c in table['columns']])),
            unit='tonnes',classification='synthetic_sample',closed_through=str(pd.Timestamp(self.inputs['as_of'])+pd.offsets.MonthEnd(1))[:10],reviewed=True,
            owner='Synthetic reviewer',request_id=str(uuid.uuid4()))
        self.post('/runs/'+self.run_id+'/actuals/preview',config)
        record=self.post('/runs/'+self.run_id+'/actuals',config,201)
        self.get('/actuals/'+record['id'])
        self.company='tehran_b';self.get('/actuals/'+record['id'],404)
        self.scopes=VIEW.copy();self.post('/runs/'+self.run_id+'/actuals',config,403)

    def test_company_openapi_includes_personal_and_company_routes(self):
        schema=self.get('/openapi.json')
        for path in ['/ai/chat','/ai/conversations','/views','/runs/{run_id}/actuals','/settings/site','/connections/external-sources']:
            self.assertIn(path,schema['paths'])
        self.assertEqual(schema['paths']['/connections/external-sources/servix/credential']['put']['security'],[{'BrowserSession':[]}])

    def test_order_update_templates_and_starters_use_the_selected_company(self):
        value=self.get('/runs/'+self.run_id+'/orders/starter')
        self.assertEqual(value['run_id'],self.run_id)
        self.assertTrue(value['customers']);self.assertFalse(value['reviewed'])
        r=self.client.get('/api/v1/runs/'+self.run_id+'/orders/template/customers')
        self.assertEqual(r.status_code,200);self.assertIn('customer',r.text)
        self.company='tehran_b';self.get('/runs/'+self.run_id+'/orders/starter',404)

    def test_assistant_cannot_read_reports_with_only_ai_permission(self):
        self.scopes=['ai:query','chats:own','drafts:read']
        self.post('/ai/chat',{'question':'Read draft','run_id':self.run_id},403)
        self.assertEqual(self.ai.await_count,0)
        self.scopes=VIEW.copy()
        self.post('/ai/chat',{'question':'Read inputs','dataset_id':uuid.uuid4().hex},404)
        self.assertEqual(self.ai.await_count,0)

    def test_assistant_export_keeps_the_exact_selected_order_revision(self):
        key=self.ws.journal.put(personal_owner(self.who),dict(question='Export',answer='Review export',run_id=self.run_id,
            snapshot_id=self.snapshot_id,dataset_id=None,actions=[{'kind':'export','snapshot_id':self.snapshot_id,
                'mode':'remaining_forecast','format':'csv'}]))
        value=self.post('/ai/turns/'+key+'/actions/0',{})
        self.assertEqual(value['url'],f'/api/v1/order-snapshots/{self.snapshot_id}/export?mode=remaining_forecast&kind=csv')
        self.assertEqual(self.client.get(value['url']).status_code,200)

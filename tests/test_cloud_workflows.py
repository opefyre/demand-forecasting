"""Cold cloud workflows with original adapters. Synthetic data, no provider calls."""
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import time
import unittest
import uuid
from unittest.mock import patch,AsyncMock

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.cloud_api import operate
from app.cloud_network import Bridge,RelayTransport,RelayAsyncTransport,RelaySocket,bind_bridge,active_bridge
from app.cloud_schedules import descriptors,record_source_owner,metadata
from app.cloud_state import restore
from app.company_workspace import CompanyWorkspaces
from tests.test_company_context import ALL


class RelayTests(unittest.TestCase):
    def test_delivery_is_single_claim_and_attempt_context_never_leaks(self):
        with bind_bridge('one') as bridge,ThreadPoolExecutor() as pool:
            future=pool.submit(bridge.exchange,{'kind':'http','url':'https://test.invalid'})
            until=time.monotonic()+2;request=None
            while request is None and time.monotonic()<until:request=bridge.next()
            self.assertIsNotNone(request);self.assertIsNone(bridge.next())
            bridge.answer(request['id'],{'body':'one'})
            with self.assertRaises(ValueError):bridge.answer(request['id'],{'body':'again'})
            self.assertEqual(future.result(2),{'body':'one'})
            self.assertIs(active_bridge('one'),bridge)
        with self.assertRaises(ValueError):active_bridge('one')
        with self.assertRaises(ValueError):bridge.exchange({})

    def test_existing_httpx_transports_rebuild_host_and_async_requests_without_real_network(self):
        class Fake:
            calls=[]
            def exchange(self,item):
                self.calls.append(item);return {'status':200,'body':base64.b64encode(b'{"ok":true}').decode()}
        bridge=Fake()
        with httpx.Client(transport=RelayTransport(bridge,'connection'),trust_env=False) as client:
            self.assertTrue(client.get('https://192.0.2.1/orders',extensions={'sni_hostname':'erp.example'}).json()['ok'])
        self.assertEqual(bridge.calls[0]['url'],'https://erp.example/orders')
        async def call():
            async with httpx.AsyncClient(transport=RelayAsyncTransport(bridge)) as client:
                return await client.post('https://api.openai.com/v1/responses',json={'model':'synthetic-model'})
        self.assertEqual(asyncio.run(call()).status_code,200)
        self.assertEqual(bridge.calls[1]['category'],'ai')

    def test_socket_contract_preserves_read_timeout_and_closes_once(self):
        class Fake:
            calls=[]
            def exchange(self,item):
                self.calls.append(item)
                return {'socket_id':'one'} if item['kind']=='tcp-open' else {'timeout':True} if item['kind']=='tcp-read' else {}
        bridge=Fake()
        with RelaySocket(bridge,{'host':'sftp.example','port':22}) as sock:
            sock.connect(None);sock.settimeout(3);self.assertEqual(sock.getpeername(),('sftp.example',22))
            self.assertEqual(sock.send(b'hello'),5)
            with self.assertRaises(socket.timeout):sock.recv(1024)
        sock.close();self.assertEqual(sum(c['kind']=='tcp-close' for c in bridge.calls),1)


class ColdWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.env=patch.dict('os.environ',{'DEMANDLAB_CLOUD_RUNTIME':'true','DEMANDLAB_COMPANY_VAULT_KEY':'ab'*32})
        self.env.start();self.addCleanup(self.env.stop)
        self.who={'company_id':'tehran_a','issuer':'https://forecast.vrolen.com','subject':'owner-a','role':'admin',
            'auth_kind':'session','session_id':'test-only','mfa_required':False,'permissions':ALL.copy()}
        self.checkpoint=b'';self.calls=[];self.count=0

    def command(self,method,path,body=None,*,sealed=False,handler=None,who=None):
        self.count+=1;folder=self.root/str(self.count);folder.mkdir();source=folder/'input.zip';source.write_bytes(self.checkpoint)
        raw=json.dumps(body).encode();digest=hashlib.sha256(raw).hexdigest()
        if sealed:
            nonce=b'x'*12;raw=nonce+AESGCM(bytes.fromhex('ab'*32)).encrypt(nonce,raw,json.dumps(['tehran_a','api-request',digest],separators=(',',':')).encode())
        body_path=folder/'body';body_path.write_bytes(raw)
        with bind_bridge(uuid.uuid4().hex) as bridge:
            def exchange(item):
                self.calls.append(item)
                if item['kind']=='identity':return {'body':{'allowed':True,'permissions':ALL,'role':'admin'}}
                return handler(item) if handler else {'status':503,'body':base64.b64encode(b'{}').decode()}
            bridge.exchange=exchange
            result=operate(source,folder/'workspace','tehran_a',uuid.uuid4().hex,
                {'method':method,'path':path,'principal':who or self.who,'content_type':'application/json',
                 'sealed':sealed,'body_hash':digest},body_path)
        value=json.loads((folder/'api-output/api-response.json').read_text())
        if result.get('committed'):self.checkpoint=(folder/'completed.zip').read_bytes()
        return result,value,folder

    def workspace(self):
        folder=self.root/uuid.uuid4().hex;folder.mkdir();source=folder/'input.zip';source.write_bytes(self.checkpoint)
        restore(source,folder/'restore','tehran_a')
        stores=CompanyWorkspaces(folder/'restore/data/companies');self.addCleanup(stores.close)
        return stores.for_principal(self.who)

    def test_four_connected_customers_cold_receipts_review_and_encrypted_credentials(self):
        config={'name':'Tehran customer directory','provider':'http','role':'sales_customers','filename':'customers.json',
            'url':'https://erp.example/customers','credential':'synthetic-readonly-credential','confirmed_read_access':True}
        result,connection,_=self.command('POST','/connections/inputs',config,sealed=True)
        self.assertEqual(result['api_status'],201,connection)
        self.assertNotIn('synthetic-readonly-credential',json.dumps(connection))
        rows=[{'customer':name,'external_id':str(i),'active':True} for i,name in enumerate(['Mehr','Aftab','Pars','Negin'])]
        def reply(item):
            self.assertEqual(item['url'],config['url']);self.assertEqual(item['method'],'GET')
            self.assertEqual(item['headers']['authorization'],'Bearer synthetic-readonly-credential')
            return {'status':200,'body':base64.b64encode(json.dumps(rows).encode()).decode()}
        path='/connections/inputs/'+connection['id']+'/fetch'
        result,pulled,_=self.command('POST',path,{'request_id':'cold-customers-pull'},handler=reply)
        self.assertEqual(pulled['state'],'ready',pulled)
        count=len(self.calls);_,again,_=self.command('POST',path,{'request_id':'cold-customers-pull'},handler=reply)
        self.assertEqual(again['id'],pulled['id']);self.assertEqual(len(self.calls),count)
        self.assertEqual(self.workspace().connections.vault.get(connection['id']+':1'),'synthetic-readonly-credential')
        preview_path='/connections/imports/'+pulled['candidate_id']+'/rows/preview'
        _,preview,_=self.command('POST',preview_path,{'mapping':{'customer':'A','external_id':'B','active':'C'}})
        self.assertEqual(preview['count'],4,preview)
        _,accepted,_=self.command('POST',preview_path.replace('/preview','/accept'),
            {'mapping':{'customer':'A','external_id':'B','active':'C'},'review_token':preview['review_token'],'reviewed':True})
        self.assertEqual(len(self.workspace().customers.list()),4,accepted)

    def test_source_refresh_failure_and_cooldown_survive_a_cold_restart(self):
        self.command('PUT','/connections/external-sources/industry',{'enabled':True})
        _,state,_=self.command('POST','/connections/external-sources/industry/refresh',handler=lambda item:
            {'status':429,'body':base64.b64encode(b'{}').decode()})
        self.assertEqual(state['status'],'queued')
        saved=self.workspace().live_sources.state('industry');self.assertEqual(saved['status'],'failed');self.assertTrue(saved['cooldown_until'])
        self.assertTrue(any(item.get('category')=='source' for item in self.calls))
        count=len(self.calls);result,value,_=self.command('POST','/connections/external-sources/industry/refresh')
        self.assertEqual(result['api_status'],400,value);self.assertTrue(result['committed']);self.assertEqual(len(self.calls),count)
        schedules=descriptors(self.workspace())['schedules'];self.assertEqual(len(schedules),1)
        self.assertEqual(schedules[0]['subject'],'owner-a');self.assertGreater(schedules[0]['due'],datetime.now(timezone.utc).timestamp()*1000)

    def test_monthly_commodity_refresh_reaches_relay_and_survives_cold_restore(self):
        from app.commodity_prices import LANDING,SERIES
        from tests.test_live_sources import URL,workbook
        def reply(item):
            self.assertEqual(item['category'],'source')
            raw=f'<a href="{URL}">Monthly prices</a>'.encode() if item['url']==LANDING else workbook()
            return {'status':200,'body':base64.b64encode(raw).decode()}
        self.command('POST','/connections/external-sources/commodities/refresh',handler=reply)
        workspace=self.workspace()
        self.assertEqual(workspace.live_sources.state('commodities')['status'],'healthy')
        self.assertEqual(len(workspace.factors.list()),len(SERIES))
        self.assertEqual([item['url'] for item in self.calls],[LANDING,URL])

    def test_input_schedule_is_durable_rechecks_owner_and_never_auto_accepts(self):
        _,connection,_=self.command('POST','/connections/inputs',{'name':'Sales feed','provider':'http','role':'history',
            'filename':'sales.csv','url':'https://erp.example/sales','confirmed_read_access':True},sealed=True)
        path='/connections/inputs/'+connection['id']+'/schedule'
        self.command('PUT',path,{'connection_version':1,'minutes':60,'enabled':True,'confirmed':True})
        result,value,_=self.command('POST',path+'/check',handler=lambda item:{'status':200,'body':base64.b64encode(b'date,quantity\n2026-01-01,10\n').decode()})
        self.assertEqual(result['api_status'],200,value)
        self.assertTrue(any(item['kind']=='identity' for item in self.calls));self.assertTrue(any(item['kind']=='http' for item in self.calls))
        workspace=self.workspace();self.assertEqual(workspace.datasets.list(),[])
        schedules=descriptors(workspace)['schedules'];self.assertEqual(len(schedules),1);self.assertGreater(schedules[0]['due'],time.time()*1000)
        self.command('DELETE',path,{'version':value['version']});self.assertEqual(descriptors(self.workspace())['schedules'],[])

    def test_admin_and_company_fences_are_checked_before_scratch_restore(self):
        for who in [{**self.who,'company_id':'tehran_b'},{**self.who,'role':'planner'},{**self.who,'auth_kind':'api_key'}]:
            with self.assertRaises(ValueError):self.command('POST','/notifications/check',who=who)
        self.assertEqual(self.calls,[])

    def test_disabled_cloud_ai_uses_cloud_configuration_not_local_secret(self):
        from app.ai_provider import ai_status
        with patch.dict('os.environ',{'DEMANDLAB_AI_ENABLED':'true','OPENAI_API_KEY':'sk-'+'synthetic'*12}):  # pragma: allowlist secret - test fake
            with bind_bridge('status',{'enabled':False,'configured':False,'models':{'query':'test-query','title':'test-title','review':'test-review','decision':'test-decision'}}):
                status=ai_status();self.assertFalse(status['ready']);self.assertEqual(status['models']['query'],'test-query')

    def test_cloud_chat_parallel_title_is_saved_before_sleep_and_stays_personal(self):
        async def reply(payload,run,outlook,**kwargs):
            return dict(answer='Ready to review sales.',actions=[],run_id=None,dataset_id=None,snapshot_id=None,
                role='query',model='synthetic-query',usage={},provider='synthetic')
        settings={'ready':True,'consent_id':'c'*64,'models':{},'configured':True,'enabled':True}
        with (patch('app.ai_workspace.run_chat',side_effect=reply),patch('app.ai_workspace.ai_status',return_value=settings),
                patch('app.ai_workspace.generate_chat_title',new=AsyncMock(return_value='Tehran autumn sales'))):
            result,turn,_=self.command('POST','/ai/chat',{'question':'Show Tehran sales','consent':True,'provider_id':'c'*64})
        self.assertEqual(result['api_status'],200,turn);self.assertFalse(turn['title_pending'])
        _,saved,_=self.command('GET','/ai/conversations')
        self.assertEqual(saved['chats'][0]['title'],'Tehran autumn sales')
        _,other,_=self.command('GET','/ai/conversations',who={**self.who,'subject':'other-owner'})
        self.assertEqual(other['chats'],[])

    def test_monthly_calculation_and_recurring_review_survive_separate_cold_requests(self):
        import shutil
        from app.cloud_state import capture
        from tests.test_platform_sales import PublicSalesTests
        f=PublicSalesTests();f.setUp()
        try:
            _,dataset,_=f.history();group,_=f.calculate(dataset,f.orders(dataset),['model:Last observed'])
            run_id=group['jobs'][0]['run_id']
            base=self.root/'baseline';shutil.copytree(f.root/'companies',base/'data/companies')
            archive=self.root/'baseline.zip';capture(base,'tehran_a',archive);self.checkpoint=archive.read_bytes()
            _,update,_=self.command('POST','/forecast-updates',{'run_id':run_id,'request_id':'cold-monthly-update'})
            path='/forecast-updates/'+update['id']+'/steps'
            _,update,_=self.command('POST',path,{'revision':update['revision'],'action':'history','dataset_id':dataset['id'],'reviewed':True,'request_id':'cold-monthly-history'})
            result,update,_=self.command('POST',path,{'revision':update['revision'],'action':'calculate','months':4,'method':'model:Last observed','reviewed':True,'request_id':'cold-monthly-calculate'})
            self.assertEqual(result['api_status'],200,update)
            self.assertEqual(self.workspace().jobs.get(update['job']['id'])['state'],'succeeded')
            _,update,_=self.command('POST',path,{'revision':update['revision'],'action':'calculated','request_id':'cold-monthly-result'})
            self.assertNotEqual(update['run_id'],run_id)
            _,schedule,_=self.command('POST','/recurring-forecasts',{'run_id':run_id,'request_id':'cold-recurring-setup','day':1,'months':4,'method':'model:Last observed','enabled':True,'confirmed':True})
            self.assertEqual(schedule['run_id'],run_id,schedule)
            before=len(self.workspace().list_runs())
            _,cycle,_=self.command('POST','/recurring-forecasts/'+schedule['id']+'/check')
            self.assertTrue(any(c['kind']=='identity' for c in self.calls))
            self.assertEqual(cycle['state'],'calculating',cycle)
            self.assertEqual(len(self.workspace().list_runs()),before+1,'One unapproved draft, not an approved report')
            _,cycle,_=self.command('POST','/recurring-forecasts/'+schedule['id']+'/check')
            self.assertEqual(cycle['state'],'review',cycle)
            self.assertEqual(len(self.workspace().list_runs()),before+1,'Restart reuses the monthly draft instead of calculating twice')
            timers=descriptors(self.workspace())['schedules'];self.assertEqual(len(timers),1)
            self.assertGreater(timers[0]['due'],time.time()*1000,'A recorded cycle waits for next month, not a hot retry loop')
        finally:f.tearDown()

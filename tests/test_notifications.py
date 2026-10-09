"""Synthetic notifications only: real Apprise adapters, no external messages."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import httpx
from pydantic import SecretStr
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient

from app.company_context import personal_owner
from app.company_workspace import CompanyWorkspaces
from app.notifications import DestinationInput,Notifications,NotificationConflict,NotificationError,private_config,tick,collect_events
from app.notification_sender import deliver,PinnedRequests,IsolatedSender
from app.platform_api import create_platform_api


class MemoryVault:
    def __init__(self):self.values={}
    def get(self,key):return self.values.get(key)
    def set(self,key,value):self.values[key]=value

class Sender:
    def __init__(self):self.calls=[];self.state='accepted'
    def send(self,*args):self.calls.append(args);return self.state

def body(**kwargs):
    return DestinationInput(name='Planning alerts',provider='slack',destination='Planning team',
        webhook='https://hooks.slack.com/services/SYNTHETIC/ONLY/NOTACREDENTIAL',confirmed=True,
        **kwargs)


class NotificationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.sender=Sender();self.vault=MemoryVault()
        self.store=Notifications(Path(self.temp.name)/'notifications.sqlite3',sender=self.sender,vault=self.vault)
        self.owner=json.dumps(['tehran_a','https://company.test','admin_a'])
    def tearDown(self):self.temp.cleanup()
    def save(self,**kwargs):return self.store.save(body(**kwargs),self.owner)
    def queue(self,row,event='test',key=None):return self.store.queue(row['id'],event,key or uuid.uuid4().hex,self.owner,version=row['version'])
    def drain(self,grant=lambda owner:True):return self.store.drain(grant,'https://company.test')

    def test_credentials_are_not_in_database_public_responses_or_messages(self):
        row=self.save();receipt=self.queue(row);self.drain()
        public=json.dumps([row,self.store.delivery(receipt['id']),self.store.history()])
        raw=self.store.path.read_bytes()
        self.assertNotIn('NOTACREDENTIAL',public);self.assertNotIn(b'NOTACREDENTIAL',raw)
        self.assertNotIn('owner',public);self.assertNotIn('secret_id',public)
        self.assertEqual(self.sender.calls[0][2],'Notification connection test.')
        self.assertEqual(self.sender.calls[0][3],'https://company.test/settings')
        self.assertEqual(self.store.delivery(receipt['id'])['state'],'accepted')

    def test_confirmed_events_required_and_paused_creation_sends_nothing(self):
        with self.assertRaises(NotificationError):self.store.save(body(enabled=True),self.owner)
        value=body();value.confirmed=False
        with self.assertRaises(NotificationError):self.store.save(value,self.owner)
        row=self.save()
        with self.assertRaises(NotificationError):self.queue(row,'forecast_ready')
        self.assertEqual(self.sender.calls,[])

    def test_version_conflict_and_credential_rotation_cancel_pending(self):
        row=self.save();receipt=self.queue(row)
        newer=self.store.save(body(),self.owner,row['id'],row['version'])
        self.assertEqual(newer['version'],2)
        self.assertEqual(self.store.delivery(receipt['id'])['state'],'cancelled')
        with self.assertRaises(NotificationConflict):self.store.save(body(),self.owner,row['id'],1)
        self.assertEqual(self.drain(),[])

    def test_archive_restore_stays_paused_and_history_kept(self):
        row=self.save(enabled=True,events=['forecast_ready']);receipt=self.queue(row)
        row=self.store.archive(row['id'],1,True,self.owner)
        self.assertEqual(self.store.list(),[]);self.assertEqual(len(self.store.list(True)),1)
        with self.assertRaises(NotificationError):self.queue(row)
        row=self.store.archive(row['id'],2,False,self.owner)
        self.assertFalse(row['enabled']);self.assertFalse(row['archived'])
        self.assertEqual(self.store.delivery(receipt['id'])['state'],'cancelled')

    def test_duplicate_request_is_repeat_safe_and_different_content_conflicts(self):
        row=self.save(enabled=True,events=['forecast_ready']);receipt=self.queue(row,key='same-request')
        self.assertEqual(self.queue(row,key='same-request')['id'],receipt['id'])
        with self.assertRaises(NotificationConflict):self.queue(row,'forecast_ready','same-request')
        self.drain();self.drain();self.assertEqual(len(self.sender.calls),1)

    def test_concurrent_delivery_has_one_sender(self):
        row=self.save();self.queue(row)
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:self.drain(),range(2)))
        self.assertEqual(len(self.sender.calls),1)

    def test_access_revoked_or_unavailable_cancels_pending(self):
        row=self.save();receipt=self.queue(row);self.drain(lambda _:False)
        self.assertEqual(self.store.delivery(receipt['id'])['state'],'cancelled');self.assertEqual(self.sender.calls,[])

    def test_access_rechecked_immediately_before_send(self):
        row=self.save();receipt=self.queue(row);grants=iter([True,False])
        self.drain(lambda _:next(grants))
        self.assertEqual(self.store.delivery(receipt['id'])['state'],'cancelled');self.assertEqual(self.sender.calls,[])

    def test_uncertain_delivery_requires_manual_duplicate_acknowledgement(self):
        row=self.save();receipt=self.queue(row);self.sender.state='unknown';self.drain()
        self.assertEqual(self.store.delivery(receipt['id'])['state'],'unknown')
        with self.assertRaises(NotificationError):self.store.retry(receipt['id'],'retry-id-1',1,self.owner)
        retry=self.store.retry(receipt['id'],'retry-id-1',1,self.owner,True)
        self.assertEqual(retry['retry_of'],receipt['id']);self.assertEqual(self.store.retry(receipt['id'],'retry-id-1',1,self.owner,True)['id'],retry['id'])
        self.assertEqual(self.store.delivery(receipt['id'])['state'],'unknown')

    def test_interrupted_send_is_unknown_not_replayed(self):
        row=self.save();receipt=self.queue(row)
        with self.store.db() as db:
            value=json.loads(db.execute('SELECT record FROM deliveries').fetchone()[0]);value.update(state='sending',started_at=time.time()-100)
            db.execute('UPDATE deliveries SET record=?',(json.dumps(value),))
        self.drain();self.assertEqual(self.sender.calls,[]);self.assertEqual(self.store.delivery(receipt['id'])['state'],'unknown')

    def test_old_events_skipped_and_persian_status_does_not_include_business_data(self):
        row=self.save(enabled=True,events=['forecast_ready'],language='fa')
        self.assertIsNone(self.store.queue(row['id'],'forecast_ready','old',self.owner,created=0))
        receipt=self.queue(row,'forecast_ready');self.assertIn('پیش‌بینی',receipt['text'])
        self.assertNotIn('Planning',receipt['text'])

    def test_credentials_fail_closed_without_plaintext_fallback(self):
        with patch.object(self.vault,'set',side_effect=ValueError('secret text')):
            with self.assertRaisesRegex(NotificationError,'could not be saved'):self.save()
        self.assertEqual(self.store.list(),[])


class NotificationAdapterTests(unittest.TestCase):
    def payload(self,provider):
        config=body().public();config['provider']=provider
        secrets={'slack':{'webhook':'https://hooks.slack.com/services/SYNTHETIC/ONLY/NOTACREDENTIAL'},
          'teams':{'webhook':'https://sample.environment.api.powerplatform.com/powerautomate/automations/direct/workflows/example/triggers/manual/paths/invoke?api-version=1&sig=synthetic'},
          'telegram':{'token':'123456:abcdefghijklmnopqrstuvwxyz','recipient':'-10012345'},
          'whatsapp':{'token':'syntheticTokenThatIsNotReal','sender_id':'123456789012345','recipient':'+15555550101'}}
        config.update(template='demand_status',template_language='en_US')
        return dict(config=config,secret=secrets[provider],text='A forecast is ready for review.',link='https://company.test/demand')

    def factory(self,responder):
        class Policy:
            def resolve(self,host,port):return (2,1,6,'',('93.184.216.34',443))
        return lambda host:PinnedRequests(host,policy=Policy(),transport=httpx.MockTransport(responder))

    def test_real_apprise_slack_telegram_whatsapp_and_teams_cards(self):
        for provider in ('slack','telegram','whatsapp','teams'):
            with self.subTest(provider=provider):
                seen=[]
                def response(req):
                    seen.append(req)
                    if provider=='slack':return httpx.Response(200,text='ok')
                    if provider=='teams':return httpx.Response(202)
                    if provider=='telegram':return httpx.Response(200,json={'ok':True,'result':{'message_id':1}})
                    return httpx.Response(200,json={'messages':[{'id':'synthetic-receipt'}]})
                self.assertEqual(deliver(self.payload(provider),self.factory(response)),'accepted')
                self.assertEqual(len(seen),1)
                req=seen[0];data=json.loads(req.content)
                self.assertEqual(req.method,'POST');self.assertEqual(req.extensions['sni_hostname'],req.headers['host'])
                self.assertIn('company.test',req.content.decode())
                if provider=='telegram':self.assertEqual(data['chat_id'],-10012345)
                if provider=='whatsapp':
                    self.assertEqual(data['type'],'template');self.assertEqual(data['template']['name'],'demand_status')
                    self.assertIn('forecast',data['template']['components'][0]['parameters'][0]['text'])
                if provider=='teams':self.assertEqual(data['type'],'message')

    def test_redirect_errors_and_timeout_never_claim_recipient_delivery(self):
        for code,state in [(302,'unknown'),(429,'rejected'),(401,'rejected'),(500,'unknown')]:
            for provider in ('slack','telegram','whatsapp','teams'):
                with self.subTest(code=code,provider=provider):
                    self.assertEqual(deliver(self.payload(provider),self.factory(lambda r:httpx.Response(code)) ),state)
        self.assertEqual(deliver(self.payload('slack'),self.factory(lambda r:(_ for _ in ()).throw(httpx.ReadTimeout('token')))),'unknown')

    def test_strict_hosts_templates_and_single_recipients(self):
        for url in ['http://hooks.slack.com/services/a/b/c','https://localhost/services/a/b/c',
                    'https://hooks.slack.com.evil.test/services/a/b/c','https://hooks.slack.com/services/a/b/c?template=/etc/passwd',
                    'https://hooks.slack.com@evil.test/services/a/b/c','https://hooks.slack.com:8443/services/a/b/c']:
            with self.subTest(url=url):
                value=body();value.webhook=SecretStr(url)
                with self.assertRaises(NotificationError):private_config(value)
        value=DestinationInput(name='Teams',destination='Team',provider='teams',webhook='https://outlook.office.com/webhook/legacy')
        with self.assertRaises(NotificationError):private_config(value)
        value=DestinationInput(name='WhatsApp',destination='Planner',provider='whatsapp',token='abcdefghijklmnopqrst',recipient='+15555550101',sender_id='12345678',template='status',eligible=False)
        with self.assertRaises(NotificationError):private_config(value)
        value.eligible=True;self.assertIn('token',private_config(value))
        value.recipient=SecretStr('+15555550101/+15555550102')
        with self.assertRaises(NotificationError):private_config(value)

    def test_transport_blocks_private_addresses_and_second_request(self):
        import requests
        value=PinnedRequests('127.0.0.1')
        with self.assertRaises(Exception):value.post('https://127.0.0.1/send',verify=True,allow_redirects=False)
        value=self.factory(lambda r:httpx.Response(200))('hooks.slack.com')
        with self.assertRaises(requests.RequestException):value.post('https://evil.test/send')
        value.post('https://hooks.slack.com/send')
        with self.assertRaises(requests.RequestException):value.post('https://hooks.slack.com/send')

    def test_child_timeout_and_invalid_output_are_uncertain(self):
        import subprocess
        sender=IsolatedSender()
        with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('safe',35)):
            self.assertEqual(sender.send({}, {},'status','https://company.test'),'unknown')
        with patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'invalid')):
            self.assertEqual(sender.send({}, {},'status','https://company.test'),'unknown')

    def test_real_child_process_rejects_unknown_provider_without_network(self):
        self.assertEqual(IsolatedSender().send({'provider':'invalid'}, {},'status','https://company.test'),'rejected')


class NotificationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.workspaces=CompanyWorkspaces(Path(self.temp.name)/'companies')
        self.w=self.workspaces.for_principal({'company_id':'tehran_a'})
        self.sender=Sender();self.store=Notifications(self.w.path('notifications.sqlite3'),vault=MemoryVault(),sender=self.sender)
        self.w._stores['notifications']=self.store;self.owner=json.dumps(['tehran_a','https://company.test','admin_a'])
        self.destination=self.store.save(body(enabled=True,events=['forecast_ready','forecast_failed','inputs_ready','import_failed','forecast_approved']),self.owner)
    def tearDown(self):self.workspaces.close();self.temp.cleanup()
    def group(self):
        request=uuid.uuid4().hex;group_id=uuid.uuid5(uuid.NAMESPACE_URL,'demandlab-group:'+request).hex
        return self.w.jobs.create_group([{'forecast_group_id':group_id,'method':name} for name in ['model:Last observed','model:Recent average']],'Private customer quantities',request)
    def finish(self,job,state):
        owner=self.w.jobs.claim(job['id']);self.w.jobs.finish(job['id'],owner,state)
    def test_group_finishes_once_and_retry_supersedes_failed_method(self):
        group=self.group();a,b=group['jobs'];self.finish(a,'succeeded')
        self.assertEqual(collect_events(self.w),[])
        self.finish(b,'failed');tick(self.w,lambda _:True,'https://company.test')
        self.assertEqual(self.store.history()['deliveries'][0]['event'],'forecast_failed')
        retry=self.w.jobs.create(b['payload'],'Retry',uuid.uuid4().hex);self.finish(retry,'succeeded')
        tick(self.w,lambda _:True,'https://company.test');tick(self.w,lambda _:True,'https://company.test')
        self.assertEqual([r['event'] for r in self.store.history()['deliveries']],['forecast_ready','forecast_failed'])
        self.assertEqual(len(self.sender.calls),2)
        self.assertTrue(all('Private' not in call[2] for call in self.sender.calls))
        other=self.workspaces.for_principal({'company_id':'tehran_b'});self.assertEqual(collect_events(other),[])
    def test_publishing_waits_and_interrupted_forecasts_need_attention(self):
        group=self.group();a,b=group['jobs'];self.finish(a,'failed')
        owner=self.w.jobs.claim(b['id']);self.w.jobs.begin_publish(b['id'],owner,'synthetic')
        self.assertEqual(collect_events(self.w),[])
        self.w.jobs.finish(b['id'],owner,'interrupted')
        self.assertEqual([r['event'] for r in collect_events(self.w)],['forecast_failed'])
    def test_real_capture_ledger_ignores_unchanged_data_and_keeps_failed_attempt(self):
        from app.business_connections import BusinessConnections,ConnectionInput
        class Remote:
            failure=False
            def fetch(self,config,secret):
                if self.failure:raise RuntimeError('PRIVATE-ERROR')
                return b'date,quantity\n2026-09-01,42\n'
        remote=Remote();store=BusinessConnections(self.w.path('connections.sqlite3'),self.w.datasets,fetcher=remote)
        self.w._stores['connections']=store
        destination=store.save(ConnectionInput(name='Private ERP export',provider='http',role='history',filename='sales.csv',url='https://erp.example/sales',confirmed_read_access=True))
        store.pull(destination['id'],'synthetic-new-capture');store.pull(destination['id'],'synthetic-unchanged-capture')
        remote.failure=True;store.pull(destination['id'],'synthetic-failed-capture')
        events=collect_events(self.w);self.assertCountEqual([r['event'] for r in events],['inputs_ready','import_failed'])
        tick(self.w,lambda _:True,'https://company.test');tick(self.w,lambda _:True,'https://company.test')
        self.assertEqual(self.store.history()['total'],2)
        self.assertNotIn('PRIVATE-ERROR',json.dumps(self.store.history()))
    def test_approved_release_ledger_notifies_without_business_payload(self):
        from tests.test_platform_sales import PublicSalesTests
        fixture=PublicSalesTests();fixture.setUp()
        try:
            fixture.test_independent_approval_viewer_report_access_and_cross_company_release_denial()
            fixture.company='tehran_a';events=collect_events(fixture.ws)
            self.assertEqual(len(events),1);self.assertEqual(events[0]['event'],'forecast_approved')
            self.assertNotIn('Client ERP',json.dumps(events));self.assertGreater(events[0]['created'],0)
        finally:fixture.tearDown()


class NotificationAPITests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.workspaces=CompanyWorkspaces(Path(self.temp.name)/'companies')
        self.company='tehran_a';self.role='admin';self.kind='session';self.grant=True
        self.principal=lambda:{'company_id':self.company,'issuer':'https://company.test','subject':'admin_a',
            'role':self.role,'permissions':['connections:manage'],'mfa_required':False,'auth_kind':self.kind,'session_id':'fixture'}
        self.sender=Sender()
        for company in ('tehran_a','tehran_b'):
            w=self.workspaces.for_principal({'company_id':company});w._stores['notifications']=Notifications(w.path('notifications.sqlite3'),vault=MemoryVault(),sender=self.sender)
        class Service:
            config=SimpleNamespace(origin='https://company.test')
            async def call(inner,operation,values):return {'allowed':self.grant and values['company_id']==self.company}
        self.service=Service();self.app=FastAPI()
        @self.app.middleware('http')
        async def who(request:Request,next):request.state.principal=self.principal();return await next(request)
        self.api=create_platform_api(self.service,self.workspaces);self.app.mount('/api/v1',self.api);self.client=TestClient(self.app)
    def tearDown(self):self.client.close();self.workspaces.close();self.temp.cleanup()
    def create(self):
        data=body().model_dump(mode='json');data['webhook']=body().webhook.get_secret_value()
        r=self.client.post('/api/v1/notifications/destinations',json=data);self.assertEqual(r.status_code,201,r.text);return r.json()
    def test_company_crud_secret_redaction_version_archive_and_history(self):
        row=self.create();base='/api/v1/notifications/destinations/'+row['id']
        test={'request_id':'synthetic-test-1','version':1,'confirmed':True}
        r=self.client.post(base+'/test',json=test);self.assertEqual(r.status_code,202,r.text)
        self.assertEqual(r.json()['state'],'accepted');self.assertEqual(len(self.sender.calls),1)
        self.assertEqual(self.client.post(base+'/test',json=test).json()['id'],r.json()['id']);self.assertEqual(len(self.sender.calls),1)
        self.assertNotIn('NOTACREDENTIAL',self.client.get('/api/v1/notifications/deliveries').text)
        changed=body(events=['forecast_ready'],enabled=True).public()|{'confirmed':True,'version':1}
        updated=self.client.put(base,json=changed)
        self.assertEqual(updated.status_code,200,updated.text);self.assertEqual(updated.json()['version'],2)
        self.assertEqual(self.client.put(base,json=changed).status_code,409)
        self.company='tehran_b'
        self.assertEqual(self.client.get('/api/v1/notifications/destinations').json()['destinations'],[])
        self.assertEqual(self.client.get(base).status_code,404)
        self.assertEqual(self.client.get('/api/v1/notifications/deliveries/'+r.json()['id']).status_code,404)
        self.assertEqual(self.client.post(base+'/test',json=test).status_code,404)
        self.company='tehran_a'
        self.assertEqual(self.client.request('DELETE',base,json={'version':2}).status_code,200)
        self.assertEqual(self.client.post(base+'/restore',json={'version':3}).json()['enabled'],False)
        self.assertEqual(self.client.request('DELETE',base,json={'version':1}).status_code,409)

    def test_only_interactive_admin_with_scope_may_access_any_route(self):
        row=self.create();paths=[('GET','/destinations',None),('GET','/deliveries',None),('POST','/check',None),
            ('POST','/destinations',{}),('GET','/destinations/'+row['id'],None),
            ('PUT','/destinations/'+row['id'],{}),('DELETE','/destinations/'+row['id'],{}),
            ('POST','/destinations/'+row['id']+'/restore',{}),('POST','/destinations/'+row['id']+'/test',{}),
            ('GET','/deliveries/synthetic',None),('POST','/deliveries/synthetic/retry',{})]
        for role,kind in [('planner','session'),('approver','session'),('viewer','session'),('admin','api_key')]:
            self.role,self.kind=role,kind
            for method,path,value in paths:
                r=self.client.request(method,'/api/v1/notifications'+path,json=value)
                self.assertEqual(r.status_code,403,(role,kind,path,r.text))

    def test_live_admin_check_and_safe_validation(self):
        row=self.create();self.grant=False
        result=self.client.post('/api/v1/notifications/destinations/'+row['id']+'/test',json={'request_id':'revoked-test','version':1,'confirmed':True})
        self.assertEqual(result.status_code,202,result.text);self.assertEqual(result.json()['state'],'cancelled');self.assertEqual(self.sender.calls,[])
        value=body().model_dump(mode='json');value.update(webhook='SECRET-MUST-NOT-ECHO',provider='invalid')
        result=self.client.post('/api/v1/notifications/destinations',json=value)
        self.assertEqual(result.status_code,422);self.assertNotIn('SECRET-MUST',result.text)
        self.assertEqual(self.api.openapi()['paths']['/notifications/destinations']['get']['security'],[{'BrowserSession':[]}])

    def test_observer_queues_only_new_company_events_once(self):
        w=self.workspaces.for_principal({'company_id':self.company})
        row=w.notifications.save(body(enabled=True,events=['forecast_ready']),personal_owner(self.principal()))
        event=dict(event='forecast_ready',key='forecast:synthetic',resource={'kind':'forecast','id':'synthetic'},created=time.time()+1)
        with patch('app.notifications.collect_events',return_value=[event]):
            tick(w,lambda _:True,'https://company.test');tick(w,lambda _:True,'https://company.test')
        self.assertEqual(len(self.sender.calls),1)
        other=self.workspaces.for_principal({'company_id':'tehran_b'})
        self.assertEqual(other.notifications.history()['total'],0)


if __name__=='__main__':unittest.main()

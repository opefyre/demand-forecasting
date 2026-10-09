"""No client systems or real credentials: scoped API, provider and evidence checks."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json
import socket
from types import SimpleNamespace
from threading import Thread,Event
import unittest
from unittest.mock import Mock,patch
import uuid

import httpx
import paramiko
from pydantic import ValidationError
from app.business_connections import (BusinessConnections,ConnectionInput,ConnectionError,ConnectionConflict,
    InputFetcher,TargetPolicy,check_payload)
from tests import test_platform_sales as sales_fixture
from tests.test_company_context import ALL,VIEW


class FakeVault:
    def __init__(self):self.values={}
    def get(self,key):return self.values.get(key)
    def set(self,key,value):self.values[key]=value


def config(**kwargs):
    return dict(name='Tehran sales export',provider='http',role='history',filename='sales.csv',
        url='https://erp.example/sales/export',confirmed_read_access=True,**kwargs)


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.f=sales_fixture.PublicSalesTests();self.f.setUp();self.f.permissions=ALL.copy();self.f.role='admin'
        _,self.dataset,self.body=self.f.history()
        self.vault=FakeVault();self.fetcher=Mock()
        source,_=self.f.ws.datasets.source(self.dataset['sources']['history'])
        self.payload=self.f.ws.datasets.source(source['id'])[1]
        self.fetcher.fetch.return_value=self.payload
        self.store=BusinessConnections(self.f.ws.path('connections.sqlite3'),self.f.ws.datasets,vault=self.vault,fetcher=self.fetcher)
        self.f.ws._stores['connections']=self.store

    def tearDown(self):self.f.tearDown()
    def create(self,**values):return self.f.post('/connections/inputs',config(**values),201)
    def pull(self,connection,request_id=None):return self.f.post('/connections/inputs/'+connection['id']+'/fetch',{'request_id':request_id or str(uuid.uuid4())})
    def candidate(self,pull):return self.f.get('/connections/imports/'+pull['candidate_id'])
    def accept(self,candidate,**changes):
        body={**self.body,'sources':candidate['sources'],'parent_dataset_id':candidate['parent_dataset_id'],
              'classification':'user_provided',**changes}
        return self.f.post('/connections/imports/'+candidate['id']+'/accept',body,201)

    def test_complete_capture_review_forecast_and_no_unscoped_fallback(self):
        connection=self.create(template_dataset_id=self.dataset['id'])
        pull=self.pull(connection);self.assertEqual(pull['state'],'ready',pull)
        candidate=self.candidate(pull)
        saved=self.accept(candidate)
        self.assertEqual(saved['parent_dataset_id'],self.dataset['id'])
        self.assertEqual(saved['import_provenance']['source_sha256'],candidate['digest'])
        self.assertEqual(self.accept(candidate)['id'],saved['id'])
        orders=self.f.orders(saved);group,_=self.f.calculate(saved,orders)
        result=self.f.get('/runs/'+group['jobs'][0]['run_id']+'/demand')
        self.assertEqual({r['customer'] for r in result['rows']},{'Mehr','Aftab','Pars','Negin'})
        self.assertTrue(result['can_export'])

    def test_request_retries_and_unchanged_bytes_do_not_duplicate_inputs(self):
        connection=self.create();request_id=str(uuid.uuid4())
        one=self.pull(connection,request_id);two=self.pull(connection,request_id)
        self.assertEqual(one,two);self.fetcher.fetch.assert_called_once()
        three=self.pull(connection)
        self.assertEqual(three['message'],'No changes')
        self.assertEqual(one['candidate_id'],three['candidate_id'])
        self.assertEqual(len(self.f.ws.datasets.list_sources()),2)

    def test_new_bytes_create_new_capture_and_leave_old_review_unchanged(self):
        connection=self.create();one=self.candidate(self.pull(connection));saved=self.accept(one)
        self.fetcher.fetch.return_value=self.payload.replace(b',10\n',b',11\n')
        two=self.candidate(self.pull(connection))
        self.assertNotEqual(one['id'],two['id'])
        self.assertEqual(self.f.ws.datasets.get(saved['id']),saved)
        self.assertEqual(self.candidate({'candidate_id':one['id']})['accepted_dataset_id'],saved['id'])

    def test_permissions_and_company_bound_identifiers(self):
        connection=self.create();candidate=self.candidate(self.pull(connection))
        self.f.permissions=VIEW.copy();self.f.role='viewer'
        self.assertEqual(self.f.client.get('/api/v1/connections/inputs').status_code,403)
        self.f.post('/connections/inputs/'+connection['id']+'/fetch',{'request_id':'viewer-001'},403)
        self.f.permissions=ALL.copy();self.f.permissions.remove('connections:manage');self.f.role='planner'
        self.f.post('/connections/inputs',config(),403)
        self.pull(connection)
        self.f.company='tehran_b'
        self.assertEqual(self.f.get('/connections/inputs')['connections'],[])
        self.assertEqual(self.f.client.get('/api/v1/connections/inputs/'+connection['id']).status_code,404)
        self.assertEqual(self.f.client.get('/api/v1/connections/imports/'+candidate['id']).status_code,404)
        self.f.permissions=ALL.copy();self.f.role='admin'
        self.f.post('/connections/inputs',config(template_dataset_id=self.dataset['id']),400)

    def test_role_write_scope_needed_before_fetch_or_accept(self):
        connection=self.create();candidate=self.candidate(self.pull(connection))
        self.f.permissions.remove('inputs:write')
        self.f.post('/connections/inputs/'+connection['id']+'/fetch',{'request_id':'no-write-1'},403)
        self.f.post('/connections/imports/'+candidate['id']+'/accept',self.body,403)

    def test_versioned_edit_archive_restore_and_recoverable_evidence(self):
        connection=self.create();pull=self.pull(connection)
        path='/api/v1/connections/inputs/'+connection['id']
        updated=self.f.client.put(path,json={**config(),'name':'Sales export','version':1})
        self.assertEqual(updated.status_code,200,updated.text)
        self.assertEqual(self.f.client.put(path,json={**config(),'version':1}).status_code,409)
        archived=self.f.client.request('DELETE',path,json={'version':2});self.assertEqual(archived.status_code,200)
        self.assertEqual(self.f.get('/connections/inputs')['connections'],[])
        self.assertEqual(len(self.f.get('/connections/inputs?include_archived=true')['connections']),1)
        self.f.post(path.removeprefix('/api/v1')+'/fetch',{'request_id':'archived-1'},400)
        self.f.post(path.removeprefix('/api/v1')+'/restore',{'version':3})
        self.candidate(pull)

    def test_no_secret_in_storage_responses_validation_or_failed_provider_errors(self):
        secret='synthetic-fixture-credential-not-real'  # pragma: allowlist secret -- fake credential only
        connection=self.create(credential=secret)
        self.assertNotIn(secret,json.dumps(connection))
        self.assertNotIn(secret,self.store.path.read_bytes().decode('utf8',errors='ignore'))
        bad=self.f.client.post('/api/v1/connections/inputs',json={**config(credential=secret),'provider':'bad'})
        self.assertEqual(bad.status_code,422);self.assertNotIn(secret,bad.text)
        self.fetcher.fetch.side_effect=RuntimeError('Remote traceback '+secret)
        failed=self.pull(connection)
        self.assertEqual(failed['state'],'failed');self.assertNotIn(secret,json.dumps(failed))
        # Credentials do not follow a newly chosen endpoint unless explicitly replaced.
        changed=self.f.client.put('/api/v1/connections/inputs/'+connection['id'],json={**config(),'url':'https://other.example/export','version':1})
        self.assertEqual(changed.status_code,400)

    def test_changed_sources_cannot_claim_import_receipt(self):
        connection=self.create();candidate=self.candidate(self.pull(connection))
        body={**self.body,'classification':'user_provided'}
        self.f.post('/connections/imports/'+candidate['id']+'/accept',body,400)
        self.assertIsNone(self.candidate({'candidate_id':candidate['id']})['accepted_dataset_id'])

    def test_mapping_warnings_are_not_silently_accepted_and_old_corrections_are_removed(self):
        parent={**self.dataset,'settings':{**self.dataset['settings'],'history_cell_corrections':[{'row':1}],'history_corrections_sha256':'old'}}
        with patch.object(self.f.ws.datasets,'get',return_value=parent):
            candidate=self.candidate(self.pull(self.create(template_dataset_id=self.dataset['id'])))
        self.assertNotIn('history_cell_corrections',candidate['settings'])
        self.assertNotIn('history_corrections_sha256',candidate['settings'])
        with patch('app.input_review.validate_import',return_value={'warnings':['Review adjustment']}):
            body={**self.body,'sources':candidate['sources'],'parent_dataset_id':candidate['parent_dataset_id'],
                  'classification':'user_provided','accept_warnings':False}
            self.f.post('/connections/imports/'+candidate['id']+'/accept',body,400)

    def test_edit_during_fetch_does_not_publish_old_destination_capture(self):
        connection=self.create()
        def edited(*args):
            self.store.save(ConnectionInput(**{**config(),'name':'Changed'}),connection['id'],1)
            return self.payload
        self.fetcher.fetch.side_effect=edited
        result=self.pull(connection)
        self.assertEqual(result['state'],'failed');self.assertIsNone(result['candidate_id'])
        self.assertEqual(len(self.f.ws.datasets.list_sources()),1)

    def test_concurrent_fetch_guard_prevents_duplicate_calls(self):
        connection=self.create()
        def inside(*args):
            with self.assertRaises(ConnectionConflict):self.store.pull(connection['id'],'second-request')
            return self.payload
        self.fetcher.fetch.side_effect=inside
        self.assertEqual(self.pull(connection)['state'],'ready')

    def test_crash_between_capture_and_receipt_recovers_without_duplicate_source(self):
        connection=self.create(template_dataset_id=self.dataset['id'])
        original=self.f.ws.datasets.get
        with patch.object(self.f.ws.datasets,'get',side_effect=RuntimeError('Simulated receipt interruption')):
            failed=self.pull(connection)
        self.assertEqual(failed['state'],'failed')
        self.assertEqual(len(self.f.ws.datasets.list_sources()),2)
        ready=self.pull(connection);self.assertEqual(ready['state'],'ready')
        self.assertEqual(len(self.f.ws.datasets.list_sources()),2)
        self.assertEqual(self.candidate(ready)['parent_dataset_id'],self.dataset['id'])

    def test_future_connection_requires_owned_history_and_retains_other_sources(self):
        invalid={**config(),'role':'future'}
        self.f.post('/connections/inputs',invalid,422)
        connection=self.f.post('/connections/inputs',{**invalid,'template_dataset_id':self.dataset['id']},201)
        self.fetcher.fetch.return_value=b'date,fx\n2027-01-01,1200000\n'
        candidate=self.candidate(self.pull(connection))
        self.assertEqual(candidate['sources']['history'],self.dataset['sources']['history'])
        self.assertIn('future',candidate['sources'])

    def test_private_target_approval_does_not_cross_company_boundaries(self):
        self.f.ws._stores.pop('connections')
        with patch.dict('os.environ',{'DEMANDLAB_CONNECTOR_PRIVATE_TARGETS':json.dumps({'tehran_a':['erp.example:443']})}):
            self.assertEqual(self.f.ws.connections.fetcher.policy.private_hosts,{'erp.example:443'})
            self.f.company='tehran_b'
            self.assertEqual(self.f.ws.connections.fetcher.policy.private_hosts,frozenset())


class AdapterTests(unittest.TestCase):
    def config(self,**values):return ConnectionInput(**config(**values)).public_config()
    def address(self,ip):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))]

    def test_policy_blocks_loopback_metadata_private_reserved_and_mixed_dns(self):
        for ip in ['127.0.0.1','169.254.169.254','10.0.0.1','0.0.0.0','224.0.0.1','192.0.2.1','::1','::ffff:127.0.0.1']:
            with self.subTest(ip=ip),patch('socket.getaddrinfo',return_value=self.address(ip)):
                with self.assertRaises(ConnectionError):TargetPolicy().resolve('erp.example',443)
        with patch('socket.getaddrinfo',return_value=self.address('8.8.8.8')+self.address('10.0.0.1')):
            with self.assertRaises(ConnectionError):TargetPolicy().resolve('erp.example',443)

    def test_operator_can_allow_exact_private_host_but_never_metadata_or_loopback(self):
        policy=TargetPolicy(['erp.example:443'])
        with patch('socket.getaddrinfo',return_value=self.address('10.0.0.1')):
            self.assertEqual(policy.resolve('erp.example',443)[4][0],'10.0.0.1')
            with self.assertRaises(ConnectionError):policy.resolve('other.example',443)
        for ip in ['127.0.0.1','169.254.169.254']:
            with patch('socket.getaddrinfo',return_value=self.address(ip)):
                with self.assertRaises(ConnectionError):policy.resolve('erp.example',443)

    def test_https_pins_dns_preserves_tls_hostname_and_only_sends_get(self):
        seen=[]
        def reply(request):seen.append(request);return httpx.Response(200,content=b'date,quantity\n2026-01-01,10\n')
        with patch('socket.getaddrinfo',return_value=self.address('8.8.8.8')):
            data=InputFetcher(transport=httpx.MockTransport(reply)).fetch(self.config(),None)
        self.assertTrue(data);request=seen[0]
        self.assertEqual(str(request.url),'https://8.8.8.8/sales/export')
        self.assertEqual(request.headers['host'],'erp.example')
        self.assertEqual(request.extensions['sni_hostname'],'erp.example')
        self.assertEqual(request.method,'GET')

    def test_redirect_partial_error_pagination_and_oversize_exports_are_rejected(self):
        for response in [httpx.Response(302,headers={'location':'http://127.0.0.1'}),httpx.Response(206,content=b'partial'),
                         httpx.Response(403),httpx.Response(200,headers={'link':'<https://erp.example/page2>; rel=next'},content=b'csv'),
                         httpx.Response(200,content=b'x'*100)]:
            calls=[]
            def reply(request):calls.append(request);return response
            with patch('socket.getaddrinfo',return_value=self.address('8.8.8.8')),patch('app.business_connections.LIMIT',50):
                with self.assertRaises(ConnectionError):InputFetcher(transport=httpx.MockTransport(reply)).fetch(self.config(),None)
            self.assertEqual(len(calls),1)

    def test_no_embedded_credentials_query_tokens_insecure_urls_or_traversal(self):
        for url in ['http://erp.example/export','https://user:pass@erp.example/export','https://erp.example/export?token=test','https://erp.example:8080/export','https://erp.example/export#x']: # pragma: allowlist secret -- deliberately invalid synthetic addresses
            with self.subTest(url=url),self.assertRaises(ValidationError):ConnectionInput(**{**config(),'url':url})
        for filename in ['../sales.csv','folder/sales.csv','sales.exe','folder\\sales.csv']:
            with self.assertRaises(ValidationError):ConnectionInput(**{**config(),'filename':filename})
        with self.assertRaises(ValidationError):ConnectionInput(**{**config(),'confirmed_read_access':False})

    def test_json_next_page_and_expanded_xlsx_limits(self):
        with self.assertRaises(ConnectionError):check_payload(b'{"data":[],"has_more":true}','sales.json')
        with self.assertRaises(ConnectionError):check_payload(b'broken','sales.xlsx')
        import zipfile
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:archive.writestr('sheet.xml',b'x'*10000)
        with patch('app.business_connections.LIMIT',100):
            with self.assertRaises(ConnectionError):check_payload(out.getvalue(),'sales.xlsx')

    def test_sftp_exact_file_pinned_hostkey_no_agent_or_machine_credentials(self):
        host_key=paramiko.RSAKey.generate(2048)
        config=ConnectionInput(name='SFTP sales',provider='sftp',role='history',filename='sales.csv',
            host='sftp.example',port=2222,username='readonly',path='/exports/sales.csv',
            host_key=host_key.get_name()+' '+host_key.get_base64(),confirmed_read_access=True).public_config()
        client=Mock();client.__enter__=Mock(return_value=client);client.__exit__=Mock(return_value=False)
        sftp=Mock();sftp.__enter__=Mock(return_value=sftp);sftp.__exit__=Mock(return_value=False)
        client.open_sftp.return_value=sftp;sftp.stat.return_value=SimpleNamespace(st_size=8,st_mtime=12)
        stream=io.BytesIO(b'a,b\n1,2\n');sftp.open.return_value=stream
        sock=Mock();sock.__enter__=Mock(return_value=sock);sock.__exit__=Mock(return_value=False)
        with patch('paramiko.SSHClient',return_value=client),patch('socket.socket',return_value=sock),patch('socket.getaddrinfo',return_value=self.address('8.8.8.8')):
            result=InputFetcher().fetch(config,'synthetic-password')
        self.assertEqual(result,b'a,b\n1,2\n');self.assertFalse(client.connect.call_args.kwargs['allow_agent'])
        self.assertFalse(client.connect.call_args.kwargs['look_for_keys'])
        self.assertIsInstance(client.set_missing_host_key_policy.call_args.args[0],paramiko.RejectPolicy)
        self.assertEqual(client.get_host_keys().add.call_args.args[0],'[sftp.example]:2222')
        sftp.open.assert_called_once_with('/exports/sales.csv','rb')

    def test_missing_sftp_credential_is_rejected_before_network_access(self):
        with self.assertRaises(ConnectionError),patch('socket.getaddrinfo') as resolve:
            InputFetcher().fetch({'provider':'sftp'},None)
        resolve.assert_not_called()

    def sftp_pair(self,wrong_key=False,changed=False):
        """Actual encrypted Paramiko/SFTP handshake over local socketpair; no mock SSH."""
        remote,local=socket.socketpair()
        transport=paramiko.Transport(remote)
        host=paramiko.RSAKey.generate(2048);transport.add_server_key(host)
        payload=b'a,b\n1,2\n'
        stopped=Event()
        class Server(paramiko.ServerInterface):
            def check_auth_password(self,username,password):
                return paramiko.AUTH_SUCCESSFUL if username=='readonly' and password=='synthetic-password' else paramiko.AUTH_FAILED # pragma: allowlist secret -- disposable socketpair fixture only
            def check_channel_request(self,kind,chanid):
                return paramiko.OPEN_SUCCEEDED if kind=='session' else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        class Files(paramiko.SFTPServerInterface):
            count=0
            def stat(self,path):
                if path!='/exports/sales.csv':return paramiko.SFTP_NO_SUCH_FILE
                self.count+=1;attrs=paramiko.SFTPAttributes();attrs.st_size=len(payload)
                attrs.st_atime=100;attrs.st_mtime=100+(int(changed) if self.count>1 else 0);return attrs
            def open(self,path,flags,attr):
                if path!='/exports/sales.csv' or flags!=0:return paramiko.SFTP_PERMISSION_DENIED
                handle=paramiko.SFTPHandle(flags);handle.readfile=io.BytesIO(payload);return handle
        transport.set_subsystem_handler('sftp',paramiko.SFTPServer,Files)
        def serve():
            try:
                transport.start_server(server=Server())
                channel=transport.accept(10)
                stopped.wait(15)
                if channel:channel.close()
            except (EOFError,paramiko.SSHException):pass
        thread=Thread(target=serve,daemon=True);thread.start()
        class ConnectedSocket:
            def __getattr__(self,name):return getattr(local,name)
            def connect(self,address):pass
            def __enter__(self):return self
            def __exit__(self,*args):local.close()
        pinned=paramiko.RSAKey.generate(2048) if wrong_key else host
        config=ConnectionInput(name='SFTP sales',provider='sftp',role='history',filename='sales.csv',host='sftp.example',
            username='readonly',path='/exports/sales.csv',host_key=pinned.get_name()+' '+pinned.get_base64(),confirmed_read_access=True).public_config()
        try:
            with patch('socket.getaddrinfo',return_value=self.address('8.8.8.8')):
                return InputFetcher(socket_factory=lambda *args:ConnectedSocket()).fetch(config,'synthetic-password')
        finally:
            stopped.set();transport.close();local.close();remote.close();thread.join(2)

    def test_real_sftp_library_handshake_and_file_read(self):
        self.assertEqual(self.sftp_pair(),b'a,b\n1,2\n')

    def test_real_sftp_changed_host_key_is_rejected(self):
        with self.assertRaisesRegex(ConnectionError,'could not be read'):self.sftp_pair(wrong_key=True)

    def test_real_sftp_file_changed_during_read_is_rejected(self):
        with self.assertRaisesRegex(ConnectionError,'file changed'):self.sftp_pair(changed=True)


if __name__=='__main__':unittest.main()

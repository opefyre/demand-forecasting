import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.cloud_api import CONTRACT, route
from app.cloud_compute import app
from app.cloud_state import capture, restore
from app.company_workspace import CompanyWorkspaces
from app.platform_api import create_platform_api
from tests import test_platform_sales as sales_fixture


class CloudApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = TestClient(app)
        self.who = {'company_id': 'tehran_a', 'issuer': 'https://forecast.vrolen.com', 'subject': 'planner-a',
            'role': 'planner', 'auth_kind': 'session', 'session_id': 'test-only', 'mfa_required': False,
            'permissions': sales_fixture.ALL.copy()}
        self.environment = patch.dict('os.environ', {'DEMANDLAB_CLOUD_RUNTIME': 'true', 'DEMANDLAB_COMPANY_VAULT_KEY': 'ab'*32})
        self.environment.start()
        self.attempts = []

    def tearDown(self):
        for attempt in self.attempts: self.client.delete('/output/' + attempt)
        self.client.close()
        self.environment.stop()
        self.temp.cleanup()

    def command(self, method, path, body, checkpoint=b'', who=None, content_type='application/json'):
        attempt = uuid.uuid4().hex
        self.attempts.append(attempt)
        staged = self.client.put('/request/' + attempt, content=body if isinstance(body,bytes) else json.dumps(body).encode())
        self.assertEqual(staged.status_code, 200, staged.text)
        response = self.client.post('/api-operation', content=checkpoint, headers={'x-forecast-job': json.dumps({
            'company_id': 'tehran_a', 'job_id': attempt, 'payload': {
                'method': method, 'path': path, 'content_type': content_type, 'principal': who or self.who}})})
        if response.status_code != 200: return response, None, None, b''
        metadata = response.json()
        value = self.client.get('/output/' + attempt + '/artifact/api-response.json').json()
        if method == 'GET':
            self.assertEqual(self.client.get('/output/' + attempt + '/snapshot').status_code, 404)
            return response, value, None, checkpoint
        if metadata['api_status'] >= 300:
            self.assertEqual(self.client.get('/output/' + attempt + '/snapshot').status_code, 404)
            return response, value, None, b''
        view = self.client.get('/output/' + attempt + '/artifact/company-view.json').json()
        checkpoint = self.client.get('/output/' + attempt + '/snapshot').content
        self.client.delete('/output/' + attempt)
        return response, value, view, checkpoint

    def test_contract_routes_exist_and_reject_unscoped_or_network_actions(self):
        api = create_platform_api(None, CompanyWorkspaces(self.root/'contract'))
        import re
        actual = {(method.upper(),re.sub(r'\{[^}]+\}', '{id}', path)) for path,methods in api.openapi()['paths'].items() for method in methods}
        for entry in CONTRACT:
            path = entry['path'].replace('{id}', 'test-id').replace('{index}', '0')
            self.assertTrue(any(method == entry['method'] and re.fullmatch(re.escape(pattern).replace(r'\{id\}', '[^/]+'),path)
                for method,pattern in actual),entry)
        for path,methods in api.openapi()['paths'].items():
            # Identity is intentionally native Better Auth/D1, not a scratch API.
            if path.split('/')[1] in {'me','api-keys','access-options','members','invitations','audit-events'}:continue
            examples=[path]
            for parameter,values in [('kind',['csv','xlsx','models','drivers'] if '/files/' in path else ['sources','datasets','forecasts','runs']),
                                     ('role',['customers','orders','commitments'])]:
                if '{'+parameter+'}' in path:
                    examples=[example.replace('{'+parameter+'}',value) for example in examples for value in values]
            for method in methods:
                for example in examples:
                    example=re.sub(r'\{[^}]+\}',lambda match:'0' if match.group(0)=='{index}' else 'test-id',example)
                    self.assertEqual(route(method.upper(),example)['method'],method.upper(),(method,path))
        for path in ['/api-keys', '/members', '/assistant', '/external-sources/refresh', '/../customers', '/customers/a/b']:
            with self.assertRaises(ValueError): route('POST', path)

    def test_four_customers_survive_cold_updates_archiving_and_validation_errors(self):
        checkpoint = b''
        records = []
        for name in ['Mehr Packaging', 'Aftab Printing', 'Pars Trading', 'Negin Cartons']:
            response, customer, view, checkpoint = self.command('POST', '/customers', {
                'customer': name, 'products': [{'sku': '001', 'unit': 'tonnes'}]}, checkpoint)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['api_status'], 201)
            records.append(customer)
            self.assertEqual(view['views']['/customers']['total'], len(records))
        response, _, view, checkpoint = self.command('PUT', '/customers/'+records[0]['id'], {
            'customer':'Mehr Packaging Tehran', 'products':[{'sku':'001','unit':'tonnes'},{'sku':'002','unit':'tonnes'}]}, checkpoint)
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(view['views']['/customers/'+records[0]['id']+'/products']['products']),2)
        response, _, view, checkpoint = self.command('DELETE', '/customers/'+records[1]['id'], None, checkpoint)
        self.assertEqual(response.status_code,200,response.text)
        self.assertFalse(view['views']['/customers/'+records[1]['id']]['active'])
        unchanged = checkpoint
        response, error, _, bad_checkpoint = self.command('POST', '/customers', {'customer':''}, checkpoint)
        self.assertEqual(response.json()['api_status'],422)
        self.assertTrue(error.get('detail'))
        self.assertEqual(bad_checkpoint,b'')
        wrong = {**self.who,'company_id':'tehran_b'}
        self.assertEqual(self.command('POST','/customers',{'customer':'Wrong company'},checkpoint,wrong)[0].status_code,422)
        self.assertEqual(self.command('POST','/customers',{'customer':'No write'},checkpoint,{**self.who,'permissions':['customers:read']})[0].status_code,422)
        archive=self.root/'restored.zip';archive.write_bytes(unchanged)
        restore(archive,self.root/'restored','tehran_a')
        workspaces=CompanyWorkspaces(self.root/'restored/data/companies')
        try: self.assertEqual(len(workspaces.for_principal(self.who).customers.list()),4)
        finally: workspaces.close()

    def test_real_grouped_models_and_partial_orders_have_saved_read_views(self):
        fixture=sales_fixture.PublicSalesTests();fixture.setUp()
        try:
            _, dataset, _ = fixture.history()
            orders=fixture.orders(dataset)
            import shutil
            shutil.copytree(fixture.root/'companies',self.root/'input/data/companies')
            archive=self.root/'input.zip';capture(self.root/'input','tehran_a',archive)
            response, group, view, checkpoint=self.command('POST','/forecasts',{
                'name':'Tehran sales outlook','dataset_id':dataset['id'],'sales_input_id':orders['id'],
                'methods':['model:Last observed','model:Recent average'],'request_id':'cloud-grouped-forecast'},archive.read_bytes())
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['api_status'],202)
            self.assertEqual(len(group['jobs']),2)
            self.assertTrue(all(job['state']=='succeeded' for job in group['jobs']))
            self.assertEqual(view['views']['/forecasts']['total'],1)
            self.assertEqual(view['views']['/runs']['total'],2)
            self.assertIn('/order-snapshots/'+orders['id'],view['views'])
            for job in group['jobs']:
                demand=view['views']['/runs/'+job['run_id']+'/demand']
                current=[r for r in demand['rows'] if r['period']==str(fixture.today.replace(day=1))]
                self.assertEqual(sum(r['total'] for r in current),49)
                self.assertNotIn('job_owner',view['views']['/runs/'+job['run_id']])
            self.assertTrue(checkpoint.startswith(b'PK'))
        finally: fixture.tearDown()

    def test_upload_mapping_order_book_and_review_use_existing_company_routes(self):
        fixture=sales_fixture.PublicSalesTests();fixture.setUp()
        try:
            source, dataset, _=fixture.history()
            _, saved=fixture.ws.datasets.source(source['id'])
            boundary='forecast-cloud-test-boundary'
            body=(f'--{boundary}\r\nContent-Disposition: form-data; name="role"\r\n\r\nhistory\r\n'
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="tehran-sales.csv"\r\n'
                f'Content-Type: text/csv\r\n\r\n').encode()+saved+f'\r\n--{boundary}--\r\n'.encode()
            response, uploaded, _, checkpoint=self.command('POST','/sources',body,
                content_type='multipart/form-data; boundary='+boundary)
            self.assertEqual(response.status_code,200,response.text)
            values={'name':'Tehran monthly sales','sources':{'history':uploaded['id']},'settings':dataset['settings'],
                'classification':'synthetic_sample','request_id':'cloud-input-mapping'}
            response, review, _, checkpoint=self.command('POST','/datasets/preview',values,checkpoint)
            self.assertEqual(response.json()['api_status'],200,review)
            response, imported, view, checkpoint=self.command('POST','/datasets',values,checkpoint)
            self.assertEqual(response.json()['api_status'],201,imported)
            starter=view['views']['/datasets/'+imported['id']+'/orders']
            self.assertEqual(len(starter['inputs']['customers']),4)
            from datetime import timedelta
            inputs=starter['inputs'] | {'reviewed':True,'order_feed':'complete_snapshot',
                'valid_until':str(fixture.today+timedelta(days=30)),
                'note':'Reviewed the complete order book: no confirmed orders yet.'}
            path='/datasets/'+imported['id']+'/orders'
            response, book, view, checkpoint=self.command('PUT',path,{
                'version':starter['version'],'as_of':inputs['as_of'],'valid_until':inputs['valid_until'],
                'order_feed':'complete_snapshot','orders':[]},checkpoint)
            self.assertEqual(response.json()['api_status'],200,book)
            values={'inputs':inputs,'request_id':'cloud-orders-review'}
            response, reviewed, _, checkpoint=self.command('POST',path+'/preview',values,checkpoint)
            self.assertEqual(response.json()['api_status'],200,reviewed)
            response, snapshot, view, checkpoint=self.command('POST',path+'/snapshots',values | {'review_token':reviewed['review_token']},checkpoint)
            self.assertEqual(response.json()['api_status'],201,snapshot)
            self.assertIn('/order-snapshots/'+snapshot['id'],view['views'])
        finally: fixture.tearDown()

    def test_approved_reports_independent_review_exports_and_lifecycle_across_cold_starts(self):
        fixture=sales_fixture.PublicSalesTests();fixture.setUp()
        try:
            _,dataset,_=fixture.history();orders=fixture.orders(dataset)
            group,_=fixture.calculate(dataset,orders,['model:Last observed'])
            run_id=group['jobs'][0]['run_id'];run=fixture.ws.load_run(run_id)
            source=self.root/'approved.zip'
            import shutil
            shutil.copytree(fixture.root/'companies',self.root/'input/data/companies')
            capture(self.root/'input','tehran_a',source);checkpoint=source.read_bytes()
            payload={'snapshot_id':run['sales_input_snapshot_id'],'receiver':'Client MRP',
                'mode':'combined_demand','request_id':'cloud-release-review'}
            response,review,view,checkpoint=self.command('POST','/releases/preview',payload,checkpoint)
            self.assertEqual(response.json()['api_status'],200,review)
            self.assertEqual(view['report_views']['/runs']['runs'],[])
            response,record,view,checkpoint=self.command('POST','/releases',payload|{'reviewed':True,'review_token':review['review_token']},checkpoint)
            self.assertEqual(response.json()['api_status'],201,record)
            approval={'reviewed':True,'review_token':review['review_token']}
            own=dict(self.who,role='approver')
            response,_,_,_=self.command('POST','/releases/'+record['id']+'/approve',approval,checkpoint,who=own)
            self.assertEqual(response.json()['api_status'],403)
            approver=dict(own,subject='independent-reviewer')
            response,approved,view,checkpoint=self.command('POST','/releases/'+record['id']+'/approve',approval,checkpoint,who=approver)
            self.assertEqual(response.json()['api_status'],200,approved)
            self.assertEqual(len(view['report_views']['/runs']['runs']),1)
            self.assertIn('/runs/'+run_id,view['report_views'])
            self.assertNotIn('/runs/'+run_id+'/demand',view['report_views'])
            viewer=dict(self.who,subject='reader',role='viewer',permissions=['reports:read','reports:export'])
            response,fresh,read_view,unchanged=self.command('GET','/runs?limit=1000',None,checkpoint,who=viewer)
            self.assertEqual(response.json()['api_status'],200,fresh)
            self.assertEqual(len(fresh['runs']),1)
            self.assertEqual(unchanged,checkpoint)
            self.assertIn('company-view.json',response.json()['artifacts'])
            for kind in ['csv','xlsx','json']:
                response,descriptor,_,unchanged=self.command('GET','/releases/'+record['id']+'/export?kind='+kind,None,checkpoint,who=viewer)
                self.assertEqual(response.json()['api_status'],200,descriptor)
                self.assertEqual(unchanged,checkpoint)
                binary=self.client.get('/output/'+self.attempts[-1]+'/artifact/api-download.bin').content
                self.assertGreater(len(binary),100)
                if kind=='xlsx':self.assertTrue(binary.startswith(b'PK'))
                if kind=='json':self.assertIsInstance(json.loads(binary),list)
            path='/datasets/'+dataset['id']
            response,metadata,view,checkpoint=self.command('PATCH',path+'/metadata',{'name':'Tehran demand inputs','version':0},checkpoint)
            self.assertEqual(response.json()['api_status'],200,metadata)
            self.assertEqual(view['views'][path+'/metadata']['name'],'Tehran demand inputs')
            version=metadata['lifecycle']['version']
            response,archived,view,checkpoint=self.command('POST',path+'/archive',{'version':version},checkpoint)
            self.assertTrue(archived['lifecycle']['archived'])
            response,restored,view,checkpoint=self.command('POST',path+'/restore',{'version':archived['lifecycle']['version']},checkpoint)
            self.assertFalse(restored['lifecycle']['archived'])
            response,_,_,_=self.command('GET','/runs/'+run_id+'/export?mode=combined_demand&kind=csv',None,checkpoint,who=viewer)
            self.assertEqual(response.status_code,422,'Viewer cannot ask for draft exports')
        finally:fixture.tearDown()

    def test_settings_and_personal_views_use_original_permission_and_owner_gates(self):
        admin=dict(self.who,role='admin',permissions=self.who['permissions']+['settings:manage'])
        response,site,view,checkpoint=self.command('PUT','/settings/site',{'name':'Tehran test factory','province':'Tehran','timezone':'Asia/Tehran'},who=admin)
        self.assertEqual(response.json()['api_status'],200,site)
        self.assertEqual(view['views']['/workspace']['site']['name'],'Tehran test factory')
        response,_,_,_=self.command('PUT','/settings/site',{'name':'Wrong','province':'Tehran','timezone':'Asia/Tehran'},checkpoint)
        self.assertEqual(response.status_code,422)
        key=dict(self.who,subject='service:test-key',auth_kind='api_key',key_kind='company',permissions=self.who['permissions']+['views:own'])
        response,value,_,_=self.command('GET','/views?run_id=unknown',None,checkpoint,who=key)
        self.assertIn(response.json()['api_status'],[403,404])

    def test_saved_conversations_remain_personal_and_survive_rename_archive_restore(self):
        from app.company_context import personal_owner
        who=dict(self.who,permissions=self.who['permissions']+['ai:query','chats:own'])
        workspace=CompanyWorkspaces(self.root/'chat/data/companies')
        try:
            w=workspace.for_principal(who)
            chat=w.journal.put(personal_owner(who),{'question':'Check Tehran demand','answer':'Review saved demand.',
                'run_id':None,'snapshot_id':None,'dataset_id':None,'actions':[]})
            archive=self.root/'chat.zip';capture(self.root/'chat','tehran_a',archive)
        finally:workspace.close()
        checkpoint=archive.read_bytes()
        response,_,view,checkpoint=self.command('POST','/ai/conversations/'+chat+'/rename',{'title':'Tehran sales review'},checkpoint,who=who)
        self.assertEqual(response.json()['api_status'],200)
        self.assertFalse(any(path.startswith('/ai') for path in view['views']),'Private chats never enter shared projections')
        response,listed,_,_=self.command('GET','/ai/conversations',None,checkpoint,who=who)
        self.assertEqual(listed['chats'][0]['title'],'Tehran sales review')
        other=dict(who,subject='other-user')
        response,listed,_,_=self.command('GET','/ai/conversations',None,checkpoint,who=other)
        self.assertEqual(listed['chats'],[])
        response,_,_,_=self.command('GET','/ai/conversations/'+chat,None,checkpoint,who=other)
        self.assertEqual(response.json()['api_status'],400)
        response,_,_,checkpoint=self.command('POST','/ai/conversations/'+chat+'/manage',{'operation':'archive'},checkpoint,who=who)
        self.assertEqual(response.json()['api_status'],200)
        response,listed,_,_=self.command('GET','/ai/conversations?status=archived',None,checkpoint,who=who)
        self.assertEqual(len(listed['chats']),1)
        response,_,_,checkpoint=self.command('POST','/ai/conversations/'+chat+'/manage',{'operation':'restore'},checkpoint,who=who)
        self.assertEqual(response.json()['api_status'],200)
        response,descriptor,_,_=self.command('GET','/ai/conversations/'+chat+'/export',None,checkpoint,who=who)
        self.assertEqual(response.json()['api_status'],200,descriptor)
        self.assertIn(b'Review saved demand',self.client.get('/output/'+self.attempts[-1]+'/artifact/api-download.bin').content)
        service=dict(who,subject='service:integration',auth_kind='api_key',key_kind='company')
        response,_,_,_=self.command('GET','/ai/conversations',None,checkpoint,who=service)
        self.assertEqual(response.json()['api_status'],403)

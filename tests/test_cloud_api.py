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
        for entry in CONTRACT: self.assertIn((entry['method'], entry['path']), actual)
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

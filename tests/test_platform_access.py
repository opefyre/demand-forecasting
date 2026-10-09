import hashlib
import hmac
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.security import SecurityConfig, AccessControl, install_access
from app.platform_identity import IdentityServiceConfig
from app.company_workspace import CompanyWorkspaces


class PlatformAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.origin = 'https://planning.example'
        self.secret = 'test-bridge-secret-with-at-least-32-characters'
        self.role, self.company, self.auth_kind, self.mfa = 'admin', 'company_a', 'session', False
        self.calls = []
        self.available = True
        self.permissions = ['members:manage','customers:read','customers:write','reports:read']
        config = SecurityConfig(mode='better_auth', origin=self.origin, auth_service_url='http://127.0.0.1:8011', auth_bridge_secret=self.secret)
        self.access = AccessControl(config, self.root)
        self.access.identity_service.transport = httpx.MockTransport(self.provider)
        self.app = FastAPI()
        install_access(self.app, self.access)
        @self.app.get('/api/customers')
        def unsafe_legacy():
            self.fail('A legacy store must never be reached under company authentication')
        self.client = TestClient(self.app, base_url=self.origin)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_company_source_lifecycle_is_forwarded_to_root_application(self):
        with patch('apscheduler.schedulers.background.BackgroundScheduler') as scheduler:
            with TestClient(self.app, base_url=self.origin):
                self.assertEqual(scheduler.return_value.start.call_count,3)
                self.assertEqual(scheduler.return_value.add_job.call_count,3)
                refresh = scheduler.return_value.add_job.call_args_list[0].args[0]
                self.assertIsInstance(refresh.__self__, CompanyWorkspaces)
                self.assertEqual(scheduler.return_value.add_job.call_args_list[1].kwargs['id'],'company-monthly-drafts')
                self.assertEqual(scheduler.return_value.add_job.call_args_list[2].kwargs['id'],'company-input-captures')
                self.assertEqual(scheduler.return_value.add_job.call_args_list[2].kwargs['max_instances'],1)
            self.assertEqual(scheduler.return_value.shutdown.call_count,3)

    def provider(self, request):
        self.calls.append(request)
        self.assertNotIn('attacker-private-header', request.headers)
        if not self.available:
            raise httpx.ConnectError('provider URL with credentials must not leak', request=request)
        if request.url.path.startswith('/api/login/'):
            return httpx.Response(200, json={'status':True},headers=[
                ('set-cookie','one=1; HttpOnly; Secure'),('set-cookie','two=2; HttpOnly; Secure')])
        self.assertEqual(request.headers['x-demandlab-bridge-key'], self.secret)
        data = json.loads(request.content)
        if request.url.path == '/internal/config':
            return httpx.Response(200, json={'password':True,'google':False})
        if request.url.path == '/internal/identity':
            if not data.get('cookie') and not data.get('key'):
                return httpx.Response(401, json={'detail':'Sign in to continue'})
            if data.get('company_id') and data['company_id'] != self.company:
                return httpx.Response(403, json={'detail':'Company access is unavailable'})
            return httpx.Response(200, json={'issuer':self.origin,'subject':'user1','name':'Test user',
                'company_id':self.company,'role':self.role,'permissions':self.permissions,
                'mfa_required':self.mfa,'auth_kind':self.auth_kind, 'session_id':'test-session-id'})
        self.assertEqual(data['company_id'], self.company)
        self.assertEqual(data['cookie'], 'valid=session')
        return httpx.Response(200, json={'updated':True})

    def signed_in(self):
        self.client.cookies.set('valid','session')

    def csrf(self):
        return {'origin':self.origin, 'x-demandlab-csrf':hmac.new(self.secret.encode(),b'csrf:test-session-id',hashlib.sha256).hexdigest()}

    def test_configuration_requires_loopback_service_and_https_public_origin(self):
        for origin, url, secret in [('http://public.example','http://127.0.0.1:8011',self.secret),
            (self.origin,'https://auth.example',self.secret), (self.origin,'http://127.0.0.1:8011/path',self.secret),
            (self.origin,'http://name:pass@127.0.0.1:8011',self.secret), (self.origin,'http://127.0.0.1:8011','short')]:
            with self.assertRaises(ValueError): IdentityServiceConfig(origin,url,secret).validate()

    def test_public_sales_routes_keep_identity_csrf_and_key_permissions(self):
        self.signed_in()
        self.permissions=['inputs:read','inputs:write']
        files={'file':('sales.csv',b'date,sku,customer,quantity\n2026-01-01,001,Customer,10\n','text/csv')}
        self.assertEqual(self.client.post('/api/v1/sources',files=files).status_code,403)
        response=self.client.post('/api/v1/sources',files=files,headers=self.csrf())
        self.assertEqual(response.status_code,201,response.text)
        key=response.json()['id']
        self.auth_kind='api_key'
        self.client.cookies.clear()
        headers={'authorization':'Bearer test-company-key'}
        self.assertEqual(self.client.get('/api/v1/sources/'+key,headers=headers).status_code,200)
        self.permissions=['reports:read']
        self.assertEqual(self.client.get('/api/v1/sources/'+key,headers=headers).status_code,403)
        self.assertEqual(self.client.post('/api/v1/sources',files=files,headers=headers).status_code,403)
        self.company='company_b';self.permissions=['inputs:read']
        self.assertEqual(self.client.get('/api/v1/sources/'+key,headers=headers).status_code,404)

    def test_anonymous_requests_and_global_legacy_routes_are_blocked(self):
        self.assertEqual(self.client.get('/api/v1/me').status_code,401)
        self.signed_in()
        self.assertEqual(self.client.get('/api/customers').status_code,503)
        self.assertEqual(self.client.get('/openapi.json').status_code,503)
        self.assertFalse((self.root/'companies').exists())

    def test_session_exposes_safe_user_and_per_session_csrf(self):
        self.signed_in()
        response = self.client.get('/api/auth/session')
        self.assertEqual(response.status_code,200)
        data = response.json()
        self.assertEqual(data['mode'],'better_auth')
        self.assertEqual(data['csrf'],self.csrf()['x-demandlab-csrf'])
        self.assertNotIn('session_id',data['user'])
        self.assertEqual(response.headers['cache-control'],'no-store')

    def test_two_factor_gate_blocks_admin_operations_but_allows_session_and_login(self):
        self.signed_in(); self.mfa = True
        self.assertTrue(self.client.get('/api/auth/session').json()['user']['mfa_required'])
        self.assertEqual(self.client.get('/api/v1/members').status_code,403)
        self.assertEqual(self.client.post('/api/login/two-factor/verify-totp',json={'code':'123456'},headers={'origin':self.origin}).status_code,200)

    def test_user_management_requires_session_admin_origin_and_csrf(self):
        self.signed_in()
        body = {'email':'planner@example.test','role':'planner'}
        self.assertEqual(self.client.post('/api/v1/invitations',json=body).status_code,403)
        self.assertEqual(self.client.post('/api/v1/invitations',json=body,headers={**self.csrf(),'origin':'https://attacker.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/v1/invitations',json=body,headers=self.csrf()).status_code,201)
        self.permissions.remove('members:manage'); self.role = 'planner'
        self.assertEqual(self.client.get('/api/v1/members').status_code,403)

    def test_company_cannot_be_overridden_in_request_body_or_header(self):
        self.signed_in()
        self.assertEqual(self.client.get('/api/v1/me',headers={'x-demandlab-company':'company_b'}).status_code,403)
        self.assertEqual(self.client.get('/api/v1/me',headers={'x-demandlab-company':'../company_b'}).status_code,400)
        self.assertEqual(self.client.post('/api/v1/api-keys',json={'kind':'personal','name':'My key','scopes':['reports:read'],'company_id':'company_b'},headers=self.csrf()).status_code,422)

    def test_api_keys_cannot_manage_users_or_mint_other_keys(self):
        self.auth_kind = 'api_key'
        headers = {'authorization':'Bearer test-only-key'}
        self.assertEqual(self.client.get('/api/v1/me',headers=headers).status_code,200)
        for path in ['/api/v1/members','/api/v1/api-keys']:
            self.assertEqual(self.client.get(path,headers=headers).status_code,403)
        self.assertEqual(self.client.post('/api/login/sign-in/email',json={},headers={**headers,'origin':self.origin}).status_code,403)

    def test_identity_outage_fails_closed_without_exposing_provider_errors(self):
        self.signed_in(); self.available = False
        response = self.client.get('/api/v1/me')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('credentials',response.text)
        self.assertNotIn('provider URL',response.text)

    def test_login_proxy_keeps_both_cookies_and_does_not_forward_internal_headers(self):
        response = self.client.post('/api/login/sign-in/email',json={},headers={'origin':self.origin,
            'x-demandlab-bridge-key':'attacker-private-header','x-forwarded-for':'forged-ip'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.headers.get_list('set-cookie')),2)
        self.assertNotIn('x-demandlab-bridge-key',self.calls[-1].headers)
        self.assertNotEqual(self.calls[-1].headers['x-forwarded-for'],'forged-ip')
        self.assertEqual(self.client.post('/api/login/sign-out',json={},headers={'origin':'https://attacker.example'}).status_code,403)

    def test_customer_crud_and_archiving_are_company_scoped(self):
        self.signed_in()
        body = {'customer':'Mehr Packaging','products':[{'sku':'PET-01','unit':'tonnes'}]}
        created = self.client.post('/api/v1/customers',json=body,headers=self.csrf())
        self.assertEqual(created.status_code,201,created.text)
        identifier = created.json()['id']
        self.assertEqual(self.client.get('/api/v1/customers').json()['total'],1)
        self.company = 'company_b'
        self.assertEqual(self.client.get('/api/v1/customers').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/customers/'+identifier).status_code,404)
        self.assertEqual(self.client.put('/api/v1/customers/'+identifier,json=body,headers=self.csrf()).status_code,404)
        self.assertEqual(self.client.delete('/api/v1/customers/'+identifier,headers=self.csrf()).status_code,404)
        self.assertEqual(self.client.post('/api/v1/customers',json=body,headers=self.csrf()).status_code,201)
        self.company = 'company_a'
        changed = {**body,'customer':'Mehr Tehran'}
        self.assertEqual(self.client.put('/api/v1/customers/'+identifier,json=changed,headers=self.csrf()).status_code,200)
        self.assertEqual(self.client.delete('/api/v1/customers/'+identifier,headers=self.csrf()).status_code,200)
        self.assertEqual(self.client.get('/api/v1/customers').json()['total'],0)
        self.assertEqual(self.client.get('/api/v1/customers?include_archived=true').json()['total'],1)

    def test_customer_product_validation_and_role_restrictions(self):
        self.signed_in()
        created = self.client.post('/api/v1/customers',json={'customer':'Aftab Printing'},headers=self.csrf()).json()
        path = '/api/v1/customers/'+created['id']+'/products'
        product = {'sku':'BAT','unit':'tonnes'}
        self.assertEqual(self.client.put(path,json=[product],headers=self.csrf()).status_code,200)
        self.assertEqual(self.client.put(path,json=[product,product],headers=self.csrf()).status_code,422)
        self.permissions = ['reports:read']; self.role = 'viewer'
        self.assertEqual(self.client.get('/api/v1/customers').status_code,403)
        self.assertEqual(self.client.get(path).status_code,403)
        self.assertEqual(self.client.post('/api/v1/customers',json={'customer':'Denied'},headers=self.csrf()).status_code,403)

    def test_openapi_documents_bearer_and_session_only_administration(self):
        self.signed_in()
        response = self.client.get('/api/v1/openapi.json')
        self.assertEqual(response.status_code,200)
        schema = response.json()
        self.assertEqual(schema['paths']['/api-keys']['post']['security'],[{'BrowserSession':[]}])
        self.assertIn({'ApiKey':[]},schema['paths']['/customers']['post']['security'])
        self.assertEqual(schema['components']['securitySchemes']['ApiKey']['scheme'],'bearer')
        self.assertEqual(schema['servers'],[{'url':'/api/v1'}])
        self.assertEqual(schema['components']['securitySchemes']['BrowserSession']['name'],'__Secure-better-auth.session_token')

    def test_company_factory_rejects_missing_identity_traversal_and_symlink(self):
        factory = CompanyWorkspaces(self.root/'companies')
        for company in ['',None,'../other','a/b']:
            with self.assertRaises(ValueError): factory.for_principal({'company_id':company})
        folder = self.root/'companies'; folder.mkdir()
        (folder/'escaped').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): factory.for_principal({'company_id':'escaped'})


if __name__ == '__main__': unittest.main()

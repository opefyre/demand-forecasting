from dataclasses import replace
import hashlib
import base64
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
# Authlib selects httpx2 when installed (also required by the OpenAI SDK).
# Its mock response/stream must come from the same transport implementation.
import httpx2 as httpx
from joserfc import jwt
from joserfc.jwk import RSAKey

import app.main as main
from app.planning import PlanStore
from app.security import AccessControl, SecurityConfig, install_access


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.members = self.root/'members.json'
        self.members.write_text(json.dumps({'planner':'planner', 'reviewer':'reviewer', 'admin':'admin', 'viewer':'viewer'}))
        self.config = SecurityConfig(mode='oidc', origin='https://planning.example', issuer='https://identity.example',
            client_id='planning', client_secret='test-client-secret', session_secret='test-only-session-key-32-characters', members_path=self.members)
        self.access = AccessControl(self.config, self.root)
        self.app = FastAPI()
        install_access(self.app,self.access)
        # Exercise actual app endpoints behind the same production middleware.
        for route in main.app.routes:
            if getattr(route,'path','').startswith('/api/') and not route.path.startswith('/api/auth/'):
                self.app.router.routes.append(route)
        self.store = PlanStore(self.root/'plans.json')
        self.run = {'run_id':'run','site':{'id':'site'},'source_classification':'user_provided', 'unit':'kg',
                    'metrics':{'evidence_level':'strong'}, 'series':{'A':{'forecast':[{'timestamp':'2026-10-01','mean':100}]}}}
        self.patches = [patch.object(main,'PLAN_STORE',self.store), patch.object(main,'_load_run',return_value=self.run)]
        for patcher in self.patches: patcher.start()
        self.key = RSAKey.generate_key(2048)
        self.subject, self.nonce, self.challenge = 'planner', '', ''
        self.claim_changes = {}
        self.access.oauth.company.client_kwargs['transport'] = httpx.MockTransport(self.provider)

    def tearDown(self):
        for patcher in reversed(self.patches): patcher.stop()
        self.access.store.engine.dispose()
        self.tmp.cleanup()

    def provider(self, request):
        if request.url.path == '/.well-known/openid-configuration':
            return httpx.Response(200,json={'issuer':self.config.issuer,
                'authorization_endpoint':self.config.issuer+'/authorize', 'token_endpoint':self.config.issuer+'/token',
                'jwks_uri':self.config.issuer+'/jwks','id_token_signing_alg_values_supported':['RS256']})
        if request.url.path == '/jwks': return httpx.Response(200,json={'keys':[self.key.as_dict(private=False)]})
        if request.url.path == '/token':
            form = parse_qs(request.content.decode())
            digest = base64.urlsafe_b64encode(hashlib.sha256(form['code_verifier'][0].encode()).digest()).decode().rstrip('=')
            self.assertEqual(digest,self.challenge)
            claims = {'iss':self.config.issuer,'aud':'planning','sub':self.subject,'name':'Verified '+self.subject,
                      'iat':int(time.time()),'exp':int(time.time())+300,'nonce':self.nonce, **self.claim_changes}
            signed = jwt.encode({'alg':'RS256'}, claims, getattr(self,'signing_key',self.key))
            return httpx.Response(200,json={'access_token':'test-provider-token','token_type':'Bearer','expires_in':300,'id_token':signed})
        raise AssertionError(str(request.url))

    def client(self): return TestClient(self.app,base_url=self.config.origin)

    def login(self, client, subject='planner'):
        self.subject = subject
        response = client.get('/api/auth/login',follow_redirects=False)
        self.assertEqual(response.status_code,302,response.text)
        query = parse_qs(urlsplit(response.headers['location']).query)
        self.nonce, self.challenge = query['nonce'][0], query['code_challenge'][0]
        self.assertEqual(query['code_challenge_method'],['S256'])
        response = client.get('/api/auth/callback',params={'code':'local-test-code','state':query['state'][0]},follow_redirects=False)
        return response

    def csrf(self, client):
        token=client.get('/api/auth/session').json()['csrf']
        return {'X-DemandLab-CSRF':token} if token else {}

    def test_demand_release_approval_is_reviewer_admin_only(self):
        path='/api/sales/releases/example/approve'
        for role,expected in [('viewer',False),('planner',False),('reviewer',True),('admin',True)]:
            self.assertEqual(self.access.allowed({'role':role},'POST',path),expected)
        self.assertFalse(self.access.allowed({'role':'reviewer'},'POST','/api/sales/releases'))
        self.assertTrue(self.access.allowed({'role':'planner'},'POST','/api/sales/releases'))

    def test_monthly_schedules_require_admin_and_csrf(self):
        from unittest.mock import MagicMock
        from app.recurring_forecasts import install_recurring_forecasts
        # Included routers are lazy in this FastAPI version; mount the actual
        # router explicitly behind the isolated production security middleware.
        install_recurring_forecasts(self.app,MagicMock(),MagicMock())
        for role in ('viewer','reviewer','planner','admin'):
            with self.client() as client:
                self.assertEqual(self.login(client,role).status_code,303)
                response=client.post('/api/recurring-forecasts',json={})
                self.assertEqual(response.status_code,403)
                response=client.post('/api/recurring-forecasts',json={},headers=self.csrf(client))
                self.assertEqual(response.status_code,422 if role=='admin' else 403)

    def test_factor_profile_routes_require_write_role_and_csrf(self):
        from app.customers import Customer, CustomerStore
        from app.factor_profiles import FactorProfiles, install_profile_routes
        customers=CustomerStore(self.root/'customers.sqlite')
        identifier=customers.save([Customer(customer='Synthetic profile customer')])['ids'][0]
        profiles=FactorProfiles(customers)
        # Profile routes intentionally close over their store. Replace only these
        # routes in the isolated app, not the running workspace's directory.
        self.app.router.routes=[r for r in self.app.router.routes
                                if getattr(r,'path','')!='/api/customers/{customer_id}/factor-profiles']
        install_profile_routes(self.app,profiles)
        path=f'/api/customers/{identifier}/factor-profiles'
        payload={'context':{'currency_exposure':True},'expected_revision':0}
        for role in ('viewer','reviewer'):
            with self.client() as client:
                self.login(client,role)
                self.assertEqual(client.get(path).status_code,200)
                self.assertEqual(client.put(path,json=payload,headers=self.csrf(client)).status_code,403)
        with self.client() as client:
            self.login(client,'planner')
            self.assertEqual(client.put(path,json=payload).status_code,403)
            self.assertEqual(profiles.rows(identifier),[])
            self.assertEqual(client.put(path,json=payload,headers=self.csrf(client)).status_code,200)
            self.assertEqual(profiles.rows(identifier)[0]['revision'],1)

    def create(self, client):
        response=client.post('/api/plans',json={'name':'Company plan','run_id':'run','site_id':'site','owner':'Impersonated'},headers=self.csrf(client))
        self.assertEqual(response.status_code,200,response.text)
        return response.json()

    def status(self, client, plan, status):
        return client.patch(f"/api/plans/{plan['id']}/status",json={'status':status,'actor':'Someone else'},headers=self.csrf(client))

    def test_valid_oidc_pkce_session_signed_cookie_and_logout_revokes_replay(self):
        with self.client() as client:
            self.assertEqual(client.get('/api/plans').status_code,401)
            response=self.login(client)
            self.assertEqual(response.headers['location'],'/today')
            cookie = client.cookies.get('demandlab_session')
            self.assertIn('httponly',response.headers['set-cookie'].lower())
            self.assertIn('secure',response.headers['set-cookie'].lower())
            self.assertNotIn('test-provider-token',cookie)
            self.assertEqual(client.get('/api/auth/session').json()['user']['subject'],'planner')
            self.assertEqual(client.post('/api/auth/logout',headers=self.csrf(client)).status_code,200)
            client.cookies.set('demandlab_session',cookie)
            self.assertEqual(client.get('/api/plans').status_code,401)

    def test_wrong_state_nonce_issuer_audience_expiry_and_unknown_member_fail_closed(self):
        for changes in ({'nonce':'wrong'}, {'nonce':'wrong','nonce_supported':False}, {'iss':'https://other.example'}, {'aud':'other'}, {'exp':1}, {'sub':'unassigned'}):
            with self.subTest(changes=changes), self.client() as client:
                self.claim_changes=changes
                self.assertEqual(self.login(client).headers['location'],'/?signin=failed')
                self.assertEqual(client.get('/api/plans').status_code,401)
        with self.client() as client:
            self.assertEqual(client.get('/api/auth/callback?code=x&state=bad',follow_redirects=False).headers['location'],'/?signin=failed')

    def test_csrf_cross_origin_and_wrong_host_rejected(self):
        with self.client() as client:
            self.login(client)
            self.assertEqual(client.post('/api/plans',json={}).status_code,403)
            self.assertEqual(client.post('/api/plans',json={},headers={**self.csrf(client),'Origin':'https://evil.example'}).status_code,403)
            self.assertEqual(client.get('/api/plans',headers={'Host':'evil.example'}).status_code,400)

    def test_viewer_and_reviewer_cannot_create_and_planner_cannot_administer(self):
        for role in ('viewer','reviewer'):
            with self.client() as client:
                self.login(client,role)
                self.assertEqual(client.get('/api/plans').status_code,200)
                self.assertEqual(client.post('/api/plans',json={},headers=self.csrf(client)).status_code,403)
                self.assertEqual(client.post('/api/decisions',json={},headers=self.csrf(client)).status_code,403)
                self.assertEqual(client.post('/api/inventory/snapshot/receipts',json={},headers=self.csrf(client)).status_code,403)
        with self.client() as client:
            self.login(client)
            self.assertEqual(client.put('/api/site',json={},headers=self.csrf(client)).status_code,403)
            self.assertEqual(client.post('/api/integrations',json={},headers=self.csrf(client)).status_code,403)
            self.assertEqual(client.post('/api/integrations/folders',json={},headers=self.csrf(client)).status_code,403)
            self.assertEqual(client.post('/api/integrations/folders/example/check',json={},headers=self.csrf(client)).status_code,403)

    def test_membership_removal_and_expired_session_take_effect_without_restart(self):
        with self.client() as client:
            self.login(client)
            self.members.write_text('{}')
            self.assertEqual(client.get('/api/plans').status_code,401)
        self.members.write_text('{"planner":"planner"}')
        with self.client() as client:
            self.login(client)
            with self.access.store.engine.begin() as connection:
                connection.execute(self.access.store.table.update().values(expires=1))
            self.assertEqual(client.get('/api/plans').status_code,401)

    def test_server_binds_actor_and_independent_reviewer_approves(self):
        with self.client() as planner, self.client() as reviewer:
            self.login(planner)
            plan=self.create(planner)
            self.assertEqual(plan['owner'],'Verified planner')
            self.assertEqual(plan['created_by']['subject'],'planner')
            response=planner.post(f"/api/plans/{plan['id']}/overrides",json={'item_id':'A','period':'2026-10-01','value':120,'reason':'New order','actor':'Reviewer'},headers=self.csrf(planner))
            self.assertEqual(response.json()['overrides'][0]['identity']['subject'],'planner')
            self.assertEqual(self.status(planner,plan,'review').status_code,200)
            self.assertEqual(self.status(planner,plan,'approved').status_code,403)
            self.login(reviewer,'reviewer')
            response=self.status(reviewer,plan,'approved')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['history'][-1]['identity']['subject'],'reviewer')
            self.assertEqual(self.status(reviewer,plan,'published').status_code,200)

    def test_admin_cannot_approve_own_or_previously_adjusted_plan(self):
        with self.client() as admin, self.client() as planner:
            self.login(admin,'admin')
            own=self.create(admin)
            self.status(admin,own,'review')
            self.assertEqual(self.status(admin,own,'approved').status_code,400)
            self.login(planner)
            other=self.create(planner)
            response=admin.post(f"/api/plans/{other['id']}/overrides",json={'item_id':'A','period':'2026-10-01','value':110,'reason':'Confirmed order'},headers=self.csrf(admin))
            change=response.json()['overrides'][0]
            admin.post(f"/api/plans/{other['id']}/overrides/{change['id']}/revert",json={'reason':'Cancelled'},headers=self.csrf(admin))
            self.status(planner,other,'review')
            self.assertEqual(self.status(admin,other,'approved').status_code,400)

    def test_invalid_configuration_cannot_fall_back_to_anonymous_access(self):
        for config in (replace(self.config,origin='http://planning.example'), replace(self.config,session_secret='short'),
                       replace(self.config,mode='local'), replace(self.config,issuer='https://user:secret@identity.example')):
            with self.assertRaises(ValueError): config.validate()
        with self.client() as client:
            self.login(client)
            self.members.write_text('broken')
            self.assertEqual(client.get('/api/plans').status_code,503)

    def test_wrong_signing_key_and_modified_session_cookie_are_rejected(self):
        self.signing_key = RSAKey.generate_key(2048)
        with self.client() as client:
            self.assertEqual(self.login(client).headers['location'],'/?signin=failed')
            self.assertEqual(client.get('/api/plans').status_code,401)
        self.signing_key=self.key
        with self.client() as client:
            self.login(client)
            value=client.cookies.get('demandlab_session')
            client.cookies.clear()
            client.cookies.set('demandlab_session','tampered'+value)
            self.assertEqual(client.get('/api/plans').status_code,401)

    def test_local_mode_cannot_approve_real_plans_but_labelled_samples_still_work(self):
        with TestClient(main.app) as client:
            plan=self.create(client)
            self.status(client,plan,'review')
            self.assertEqual(self.status(client,plan,'approved').status_code,403)
            self.run['source_classification']='synthetic_sample'
            sample=self.create(client)
            self.status(client,sample,'review')
            self.assertEqual(self.status(client,sample,'approved').status_code,200)

    def test_legacy_creator_and_unverified_adjustments_cannot_receive_authenticated_approval(self):
        legacy=self.store.create(name='Legacy',run_id='run',site_id='site',owner='Typed name',settings={},metrics={'evidence_level':'strong'})
        self.store.transition(legacy['id'],status='review',actor='Typed name')
        with self.client() as reviewer, self.client() as planner:
            self.login(reviewer,'reviewer')
            self.assertEqual(self.status(reviewer,legacy,'approved').status_code,400)
            self.login(planner)
            plan=self.create(planner)
            self.store.add_override(plan['id'],item_id='A',period='2026-10-01',value=110,reason='Old local change',actor='Typed name')
            self.status(planner,plan,'review')
            self.assertEqual(self.status(reviewer,plan,'approved').status_code,400)


if __name__ == '__main__': unittest.main()

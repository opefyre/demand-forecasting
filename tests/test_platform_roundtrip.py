"""Opt-in real Node/PostgreSQL → Python HTTP bridge acceptance test.

Started by auth-service's isolated integration suite. No local client data or
existing secret files are read. All company stores live in a temporary directory.
"""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.security import AccessControl, SecurityConfig, install_access


@unittest.skipUnless(os.getenv('DEMANDLAB_PLATFORM_ROUNDTRIP'), 'Started by isolated authentication integration suite')
class PlatformRoundtripTests(unittest.TestCase):
    def test_real_cookies_keys_and_cross_company_storage(self):
        with TemporaryDirectory() as folder:
            app = FastAPI()
            config = SecurityConfig(mode='better_auth', origin=os.environ['DEMANDLAB_PUBLIC_ORIGIN'],
                auth_service_url=os.environ['DEMANDLAB_AUTH_SERVICE_URL'], auth_bridge_secret=os.environ['DEMANDLAB_AUTH_BRIDGE_SECRET'])
            install_access(app, AccessControl(config, Path(folder)))
            with TestClient(app, base_url=config.origin) as browser:
                browser.headers['x-demandlab-company'] = os.environ['DEMANDLAB_PLATFORM_TEST_COMPANY']
                for key,value in json.loads(os.environ['DEMANDLAB_PLATFORM_TEST_COOKIE']).items():
                    browser.cookies.set(key,value)
                session = browser.get('/api/auth/session')
                self.assertEqual(session.status_code,200,session.text)
                self.assertEqual(session.json()['user']['company_id'],os.environ['DEMANDLAB_PLATFORM_TEST_COMPANY'])
                csrf = {'origin':config.origin,'x-demandlab-csrf':session.json()['csrf']}
                self.assertEqual(browser.get('/api/v1/members').status_code,200)
                created = browser.post('/api/v1/api-keys',json={'name':'Roundtrip integration','kind':'company',
                    'role':'planner','scopes':['customers:read','customers:write'],'days':1},headers=csrf)
                self.assertEqual(created.status_code,201,created.text)
                key = created.json()
                headers = {'authorization':'Bearer '+key['key']}
                body = {'customer':'Tehran Packaging','products':[{'sku':'PET-80','unit':'tonnes'}]}
                customer = browser.post('/api/v1/customers',json=body,headers=headers)
                self.assertEqual(customer.status_code,201,customer.text)
                self.assertEqual(browser.get('/api/v1/customers',headers=headers).json()['total'],1)
                self.assertEqual(browser.get('/api/v1/customers',headers={**headers,
                    'x-demandlab-company':os.environ['DEMANDLAB_PLATFORM_TEST_OTHER']}).status_code,403)
                # A valid session can switch only to a company it belongs to.
                other = {'x-demandlab-company':os.environ['DEMANDLAB_PLATFORM_TEST_OTHER']}
                self.assertEqual(browser.get('/api/v1/customers',headers=other).json()['total'],0)
                self.assertEqual(browser.get('/api/v1/customers/'+customer.json()['id'],headers=other).status_code,404)
                # Bearer authentication cannot silently use a simultaneous browser
                # cookie to gain access-management privileges.
                self.assertEqual(browser.post('/api/v1/api-keys',json={'name':'Nested','scopes':['reports:read']},headers=headers).status_code,403)
                self.assertEqual(browser.delete('/api/v1/api-keys/'+key['id'],headers=csrf).status_code,200)
                self.assertEqual(browser.get('/api/v1/customers',headers=headers).status_code,401)


if __name__ == '__main__': unittest.main()

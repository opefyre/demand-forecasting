"""Four-role API acceptance using the identity service's real permission catalogue.

Disposable company stores; no credentials, live identity service or provider calls.
"""
from pathlib import Path
import json
import subprocess
import unittest
from tests import test_platform_sales as sales_fixture


class DeploymentRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node','--import','tsx','--input-type=module','-e',
            "import { permissions } from './src/policy.ts'; console.log(JSON.stringify(permissions));"],
            cwd=root/'auth-service',capture_output=True,text=True,check=True,timeout=30)
        cls.permissions = json.loads(result.stdout)

    def setUp(self):
        self.fixture=sales_fixture.PublicSalesTests();self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.kind='session'

    def role(self,role):
        self.fixture.role=role;self.fixture.subject=role+'_tehran_a'
        self.fixture.permissions=self.permissions[role].copy()

    def test_read_navigation_matches_all_four_deployment_roles(self):
        matrix = {
            '/customers':{'admin','planner'}, '/datasets':{'admin','planner'},
            '/forecasts':{'admin','planner','approver'}, '/releases':set(self.permissions),
            '/connections/inputs':{'admin','planner'}, '/units':{'admin','planner'},
        }
        for role in self.permissions:
            self.role(role)
            for path,allowed in matrix.items():
                with self.subTest(role=role,path=path):
                    response=self.fixture.client.get('/api/v1'+path)
                    self.assertEqual(response.status_code,200 if role in allowed else 403,response.text)

    def test_only_admin_and_planner_can_create_customer_or_start_forecast(self):
        f=self.fixture
        self.role('planner');_,dataset,_=f.history();snapshot=f.orders(dataset)
        for role in self.permissions:
            self.role(role)
            with self.subTest(role=role):
                response=f.client.post('/api/v1/customers',json={'customer':'Customer '+role})
                self.assertEqual(response.status_code,201 if role in {'admin','planner'} else 403,response.text)
                response=f.client.post('/api/v1/forecasts',json={'name':'Role acceptance '+role,
                    'dataset_id':dataset['id'],'sales_input_id':snapshot['id'],
                    'methods':['model:Last observed'],'request_id':'role-forecast-'+role})
                self.assertEqual(response.status_code,202 if role in {'admin','planner'} else 403,response.text)
        self.assertEqual(len(f.dispatched),2)

    def test_notification_controls_are_not_granted_to_non_admin_roles(self):
        for role in ('planner','approver','viewer'):
            self.role(role)
            for method,path,body in [('GET','/notifications/destinations',None),
                    ('GET','/notifications/deliveries',None),('POST','/notifications/check',{})]:
                with self.subTest(role=role,path=path):
                    response=self.fixture.client.request(method,'/api/v1'+path,json=body)
                    self.assertEqual(response.status_code,403,response.text)

    def test_second_company_never_reads_first_company_inputs_even_as_admin(self):
        f=self.fixture;self.role('admin');_,dataset,_=f.history()
        first=f.client.get('/api/v1/datasets/'+dataset['id']);self.assertEqual(first.status_code,200)
        f.company='tehran_b'
        self.assertEqual(f.client.get('/api/v1/datasets/'+dataset['id']).status_code,404)
        self.assertEqual(f.client.get('/api/v1/customers').json()['customers'],[])


if __name__=='__main__': unittest.main()

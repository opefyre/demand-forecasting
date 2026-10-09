import tempfile
import unittest
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.customers import CustomerStore, Customer, parse_customers, install_customer_routes


class CustomerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = CustomerStore(Path(self.temp.name) / 'customers.db')

    def test_save_edit_persist(self):
        key = self.store.save([Customer(customer='  Tehran buyer  ')])['ids'][0]
        self.store.save([Customer(customer='Tehran buyer', active=False, products=[{'sku':'P1','unit':'tonnes'}])],key)
        found = CustomerStore(self.store.path).list()[0]
        self.assertEqual(found['customer'], 'Tehran buyer')
        self.assertFalse(found['active'])
        self.assertEqual(found['products'][0]['sku'],'P1')

    def test_bulk_duplicate_rolls_back(self):
        self.store.save([Customer(customer='Existing')])
        with self.assertRaises(HTTPException):
            self.store.save([Customer(customer='New'),Customer(customer='Existing')])
        self.assertEqual(len(self.store.list()),1)

    def test_import_keeps_customer_without_products_and_deduplicates_links(self):
        batch = parse_customers([{'customer':'A','sku':'P','unit':'kg'},{'customer':'A','sku':'P','unit':'kg'},{'customer':'B'}])
        self.assertEqual(len(batch.customers),2)
        self.assertEqual(len(batch.customers[0].products),1)
        self.assertEqual(batch.customers[1].products,[])
        self.assertEqual(parse_customers([{'customer':'C','sku':None,'unit':None}]).customers[0].products,[])
        with self.assertRaises(ValueError):
            parse_customers([{'customer':'A','sku':'P'}])

    def test_routes_preview_does_not_save(self):
        app=FastAPI();install_customer_routes(app,self.store)
        client=TestClient(app)
        preview=client.post('/api/customers/preview',files={'file':('customers.csv',b'customer,sku,unit\nA,P,kg\nB,,','text/csv')})
        self.assertEqual(preview.status_code,200)
        self.assertEqual(client.get('/api/customers').json()['customers'],[])
        self.assertEqual(client.post('/api/customers',json=preview.json()).status_code,200)
        self.assertEqual(len(client.get('/api/customers').json()['customers']),2)
        self.assertEqual(client.post('/api/customers/preview',files={'file':('bad.csv',b'name\nNobody','text/csv')}).status_code,422)

    def test_empty_and_duplicate_products_invalid(self):
        with self.assertRaises(ValueError): Customer(customer=' ')
        with self.assertRaises(ValueError): Customer(customer='A',products=[{'sku':'P','unit':'kg'}]*2)

    def test_aliases_and_external_ids_are_reviewed_and_unique(self):
        batch=parse_customers([{'customer':'Tehran buyer','external_id':'001','aliases':'مشتری تهران|Old buyer'}])
        key=self.store.save(batch.customers)['ids'][0]
        self.assertEqual(self.store.list()[0]['external_id'],'001')
        for entry in [Customer(customer='Other',aliases=['old BUYER']),Customer(customer='Other',external_id='001'),
                      Customer(customer='001'),Customer(customer='Other',external_id='Old buyer')]:
            with self.assertRaises(HTTPException):
                self.store.save([Customer(customer='Temporary'),entry])
            self.assertEqual(len(self.store.list()),1)
        self.store.save([Customer(customer='Tehran buyer',external_id='001',aliases=['New alias'])],key)
        self.assertEqual(self.store.list()[0]['id'],key)

    def test_customer_file_id_conflict_and_alias_lengths_are_blocked(self):
        with self.assertRaisesRegex(ValueError,'repeat the same'):
            parse_customers([{'customer':'A','external_id':'001'},{'customer':'A','external_id':'002'}])
        with self.assertRaises(ValueError):Customer(customer='A',aliases=['A'])
        with self.assertRaises(ValueError):Customer(customer='A',aliases=['x'*201])


if __name__ == '__main__':
    unittest.main()

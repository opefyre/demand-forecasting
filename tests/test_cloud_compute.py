from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sqlite3
import unittest
import uuid

from fastapi.testclient import TestClient
from app.cloud_state import EncryptedCompanyVault, capture, restore


class CloudStateTests(unittest.TestCase):
    def test_sqlite_wal_files_and_encrypted_credentials_survive_a_company_only_checkpoint(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / 'scratch'
            company = root / 'data/companies/tehran_a'
            company.mkdir(parents=True)
            with closing(sqlite3.connect(company / 'customers.sqlite3')) as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('CREATE TABLE customers(name TEXT)')
                db.executemany('INSERT INTO customers VALUES(?)', [(name,) for name in ['Mehr','Aftab','Pars','Negin']])
                db.commit()
                vault = EncryptedCompanyVault(company, 'tehran_a', 'sources', 'ab' * 32)
                vault.set('synthetic-secret-never-real')
                self.assertNotIn(b'synthetic-secret-never-real', vault.path('servix').read_bytes())
                output = Path(temp) / 'checkpoint.zip'
                capture(root, 'tehran_a', output)
            fresh = Path(temp) / 'restarted'
            manifest = restore(output, fresh, 'tehran_a')
            self.assertFalse(any(row['path'].endswith('-wal') for row in manifest['files']))
            recovered = fresh / 'data/companies/tehran_a'
            with closing(sqlite3.connect(recovered / 'customers.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM customers').fetchone()[0], 4)
            self.assertEqual(EncryptedCompanyVault(recovered, 'tehran_a', 'sources', 'ab' * 32).get(), 'synthetic-secret-never-real')
            with self.assertRaises(ValueError): restore(output, Path(temp) / 'wrong-company', 'tehran_b')
            # Wrong purpose/key cannot decrypt even a copied ciphertext.
            ciphertext = vault.path('servix').read_bytes()
            wrong = EncryptedCompanyVault(recovered, 'tehran_a', 'connections', 'ab' * 32)
            wrong.path('servix').write_bytes(ciphertext)
            with self.assertRaises(ValueError): wrong.get()
            with self.assertRaises(ValueError): EncryptedCompanyVault(recovered,'tehran_a','sources','cd'*32).get()

    def test_checkpoint_rejects_globals_symlinks_and_path_changes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / 'scratch'
            company = root / 'data/companies/tehran_a'
            company.mkdir(parents=True)
            (company / 'site.json').write_text('{}')
            (root / 'data/global.json').write_text('{}')
            with self.assertRaises(ValueError): capture(root,'tehran_a',Path(temp)/'bad.zip')
            (root / 'data/global.json').unlink()
            (company / 'link').symlink_to(root / 'data')
            with self.assertRaises(ValueError): capture(root,'tehran_a',Path(temp)/'bad.zip')
            with self.assertRaises(ValueError): EncryptedCompanyVault(company,'../other','sources','ab'*32)

    def test_real_four_customer_order_forecast_survives_two_stateless_engine_wakes(self):
        from tests.test_platform_sales import PublicSalesTests
        from app.cloud_compute import app
        fixture = PublicSalesTests(); fixture.setUp()
        try:
            _, dataset, _ = fixture.history()
            orders = fixture.orders(dataset)
            with TemporaryDirectory() as temp:
                # Existing fixture contains only company storage, no demo state.
                import shutil
                root = Path(temp) / 'source'
                shutil.copytree(fixture.root / 'companies', root / 'data/companies')
                archive = Path(temp) / 'source.zip'
                capture(root, 'tehran_a', archive)
                payload = {'dataset_id': dataset['id'], 'sales_input_id': orders['id'], 'method': 'model:Last observed'}
                with patch.dict('os.environ', {'DEMANDLAB_CLOUD_RUNTIME':'true','DEMANDLAB_COMPANY_VAULT_KEY':'ab'*32}), TestClient(app) as client:
                    for method in ['model:Last observed', 'model:Recent average']:
                        job = uuid.uuid4().hex
                        response = client.post('/forecast', content=archive.read_bytes(), headers={'x-forecast-job':json.dumps(
                            {'company_id':'tehran_a','job_id':job,'payload':{**payload,'method':method}})})
                        self.assertEqual(response.status_code,200,response.text)
                        metadata = response.json()
                        result = client.get('/output/'+job+'/artifact/result.json').json()
                        self.assertEqual(result['site']['province'],'Tehran')
                        self.assertTrue(result.get('sales_input_snapshot_id'))
                        next_archive = Path(temp) / (job+'.zip')
                        next_archive.write_bytes(client.get('/output/'+job+'/snapshot').content)
                        recovered = Path(temp) / ('recovered-'+job)
                        restore(next_archive,recovered,'tehran_a')
                        from app.company_workspace import CompanyWorkspaces
                        state=CompanyWorkspaces(recovered/'data/companies')
                        try:
                            ws=state.for_principal({'company_id':'tehran_a'})
                            self.assertEqual(len(ws.customers.list()),4)
                            self.assertEqual(len(ws.list_runs()),1 if method.endswith('Last observed') else 2)
                            from app.sales_demand import demand_outlook
                            snapshot=ws.sales.get(result['sales_input_snapshot_id'])
                            outlook=demand_outlook(snapshot['inputs'],result)
                            current=[row for row in outlook['rows'] if row['period']==str(fixture.today.replace(day=1))]
                            self.assertEqual(sum(row['total'] for row in current),49)
                        finally: state.close()
                        archive=next_archive
                        self.assertEqual(client.delete('/output/'+job).status_code,200)
                        self.assertEqual(client.get('/output/'+job+'/snapshot').status_code,404)
        finally: fixture.tearDown()

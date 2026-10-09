from copy import deepcopy
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from fastapi.testclient import TestClient
import openpyxl

from app.datasets import DatasetStore
from app.factors import FactorStore, observations_available_at
from app.factor_imports import review_import, save_import


class FactorImportTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.datasets = DatasetStore(self.root / 'datasets')
        self.factors = FactorStore(self.root / 'factors')
        self.payload = self.upload('period,value,published\n2025-01-31,100,2025-02-05\n2025-01-31,105,2025-04-01\n2025-03-31,-2,2025-04-05\n')

    def tearDown(self):
        self.folder.cleanup()

    def upload(self, content):
        source = self.datasets.upload('factor.csv', content.encode(), 'factor_observations')
        return dict(source_id=source['id'], name='Test factor', unit='percent', geography='Iran · national',
                    provider='Synthetic test source', frequency='monthly', classification='synthetic_sample',
                    mapping=dict(period='A',value='B',available_at='C'), header_row=1)

    def save(self, payload=None):
        payload = deepcopy(payload or self.payload)
        payload.update(reviewed=True,request_id=str(uuid.uuid4()),review_token=review_import(self.datasets,payload)['review_token'])
        return save_import(self.datasets,self.factors,payload), payload

    def test_revision_cutoff_gaps_and_negative_values(self):
        review = review_import(self.datasets,self.payload,today=date(2026,9,24))
        self.assertEqual(review['issue_count'],0)
        self.assertEqual(review['summary']['revisions'],1)
        self.assertEqual(review['summary']['gaps'],['2025-02-28'])
        saved,_ = self.save()
        self.assertTrue(observations_available_at(saved,'2025-02-05T12:00:00Z').empty)
        self.assertEqual(observations_available_at(saved,'2025-02-06').value.tolist(),[100])
        self.assertEqual(observations_available_at(saved,'2025-04-02').value.tolist(),[105])
        self.assertEqual(observations_available_at(saved,'2025-04-06').value.tolist(),[105,-2])
        self.assertFalse(saved['release_dates_verified'])
        self.assertEqual(saved['use'],'context_only')
        self.assertEqual(self.datasets.list(),[])

    def test_invalid_rows_cannot_save(self):
        invalid = [
            '2025-01-01,1,2025-02-01', '2025-01-31,nan,2025-02-01',
            '2025-01-31,inf,2025-02-01', '2025-01-31,,2025-02-01',
            '2025-01-31,1,2025-01-01', '2999-01-31,1,2999-02-01',
            '1404-01-31,1,1404-02-01', '01/31/2025,1,2025-02-01',
            '2025-01-31,1,', '2025-01-31,1,2025-02-01\n2025-01-31,2,2025-02-01',
        ]
        for row in invalid:
            with self.subTest(row=row):
                payload = self.upload('period,value,published\n'+row+'\n')
                self.assertGreater(review_import(self.datasets,payload)['issue_count'],0)
                with self.assertRaises(ValueError): self.save(payload)
        self.assertEqual(self.factors.list(),[])

    def test_required_metadata_and_mapping(self):
        for change in ({'unit':''},{'geography':''},{'provider':''},{'frequency':'weekly'},
                       {'classification':'guess'},{'mapping':{'period':'A','value':'A','available_at':'C'}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                review_import(self.datasets,{**self.payload,**change})

    def test_save_requires_current_review_and_is_idempotent(self):
        saved, payload = self.save()
        self.assertEqual(save_import(self.datasets,self.factors,payload)['id'],saved['id'])
        with self.assertRaises(ValueError): save_import(self.datasets,self.factors,{**payload,'reviewed':False})
        changed = {**payload,'unit':'tonnes'}
        with self.assertRaisesRegex(ValueError,'exact inputs'): save_import(self.datasets,self.factors,changed)
        changed['review_token'] = review_import(self.datasets,changed)['review_token']
        with self.assertRaisesRegex(ValueError,'already used'): save_import(self.datasets,self.factors,changed)
        self.assertEqual(len(self.factors.list()),1)

    def test_source_hash_checked_again_on_save(self):
        review = review_import(self.datasets,self.payload)
        (self.datasets.root / f"{self.payload['source_id']}.bin").write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed since import'):
            save_import(self.datasets,self.factors,{**self.payload,'reviewed':True,'review_token':review['review_token'],'request_id':str(uuid.uuid4())})

    def test_replacement_reuses_contract_and_preserves_original(self):
        original,_ = self.save()
        updated = self.upload('period,value,published\n2025-04-30,110,2025-05-05\n')
        updated['parent_id'] = original['id']
        saved,_ = self.save(updated)
        self.assertEqual(saved['factor_id'],original['factor_id'])
        self.assertEqual(len(self.factors.get(original['id'])['points']),3)
        self.assertEqual(len(saved['points']),1)  # Full replacement, not an inferred merge.
        with self.assertRaisesRegex(ValueError,'same factor'): self.save({**updated,'unit':'toman'})
        renamed = self.upload('period,other_value,published\n2025-04-30,110,2025-05-05\n')
        with self.assertRaisesRegex(ValueError,'headings changed'): self.save({**renamed,'parent_id':original['id']})

    def test_excel_dates_and_formula_block(self):
        book = openpyxl.Workbook(); sheet = book.active
        sheet.append(['period','value','published'])
        sheet.append([date(2025,1,31),5,date(2025,2,5)])
        buf = BytesIO(); book.save(buf)
        source = self.datasets.upload('factor.xlsx',buf.getvalue(),'factor_observations')
        self.assertEqual(review_import(self.datasets,{**self.payload,'source_id':source['id']})['issue_count'],0)
        sheet['B2'] = '=2+3'; buf = BytesIO();book.save(buf)
        source = self.datasets.upload('formula.xlsx',buf.getvalue(),'factor_observations')
        self.assertEqual(review_import(self.datasets,{**self.payload,'source_id':source['id']})['issue_count'],1)

    def test_api_review_save_and_cutoff(self):
        import app.main as main
        with patch.object(main,'DATASET_STORE',self.datasets), patch.object(main,'FACTOR_STORE',self.factors), TestClient(main.app) as client:
            preview = client.post('/api/factor-imports/preview',json=self.payload)
            self.assertEqual(preview.status_code,200,preview.text)
            payload = {**self.payload,'review_token':preview.json()['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())}
            saved = client.post('/api/factor-imports',json=payload)
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertNotIn('points',saved.json())
            result = client.get(f"/api/factor-imports/{saved.json()['id']}/available?cutoff=2025-02-05")
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['points'][0]['value'],100)
            self.assertEqual(client.post('/api/factor-imports',json={**payload,'reviewed':False}).status_code,400)
            self.assertNotIn('points',client.get('/api/factors').json()['snapshots'][0])


if __name__ == '__main__': unittest.main()

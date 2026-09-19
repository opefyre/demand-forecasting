from io import BytesIO
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

import app.main as main
from app.datasets import DatasetStore


class WorkflowApiTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.store=DatasetStore(Path(self.folder.name))
        self.patcher=patch.object(main,'DATASET_STORE',self.store)
        self.patcher.start()
        self.client=TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        self.folder.cleanup()

    def test_selected_excel_sheet_is_saved_and_reopened(self):
        buffer=BytesIO()
        dates=pd.date_range('2024-01-01',periods=24,freq='MS')
        with pd.ExcelWriter(buffer,engine='openpyxl') as writer:
            pd.DataFrame({'date':dates,'quantity':[10]*24}).to_excel(writer,sheet_name='First',index=False)
            pd.DataFrame({'date':dates,'quantity':[20]*24}).to_excel(writer,sheet_name='Chosen',index=False)
        upload=self.client.post('/api/sources',files={'file':('history.xlsx',buffer.getvalue())},data={'role':'history','sheet':'Chosen'})
        self.assertEqual(upload.status_code,200,upload.text)
        source=upload.json()
        self.assertEqual(source['sheet'],'Chosen')
        body={'name':'Saved sheet test','sources':{'history':source['id']},'settings':{'date_col':'date','target_col':'quantity','frequency':'monthly','horizon':3,'unit':'units'}}
        check=self.client.post('/api/datasets/validate',json=body)
        self.assertEqual(check.status_code,200,check.text)
        self.assertTrue(all(r['target']==20 for r in check.json()['preview']))
        saved=self.client.post('/api/datasets',json=body)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.client.get('/api/sources/'+source['id']).json()['sheet'],'Chosen')
        self.assertEqual(self.client.get('/api/datasets').json()['datasets'][0]['id'],saved.json()['id'])

    def test_invalid_file_fails_without_a_dataset(self):
        upload=self.client.post('/api/sources',files={'file':('bad.csv',b'date,quantity\n2024-01-01,-1\n')},data={'role':'history'})
        body={'name':'Invalid','sources':{'history':upload.json()['id']},'settings':{'date_col':'date','target_col':'quantity'}}
        check=self.client.post('/api/datasets/validate',json=body)
        self.assertEqual(check.status_code,400)
        self.assertEqual(self.client.get('/api/datasets').json()['datasets'],[])

    def test_site_settings_reject_unknown_timezone(self):
        response=self.client.put('/api/site',json={'name':'Test site','province':'Qazvin','timezone':'Not/A_Zone'})
        self.assertEqual(response.status_code,400)


if __name__=='__main__': unittest.main()

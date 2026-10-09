from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from app.assumptions import preview_assumptions, save_assumptions
from app.datasets import DatasetStore
from app.data import read_table


class AssumptionTests(unittest.TestCase):
    def test_api_preview_save_and_queue_keep_scenario_baseline(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        import app.main as main
        with patch.object(main,'DATASET_STORE',self.store), patch.object(main,'_load_run',return_value=self.base), TestClient(main.app) as client:
            self.assertEqual(client.get('/api/runs/base/assumptions').status_code,200)
            response=client.post('/api/runs/base/assumptions',json=self.payload)
            self.assertEqual(response.status_code,200,response.text)
            saved=response.json()
            self.assertEqual(client.post('/api/runs/base/assumptions',json=self.payload).json()['id'],saved['id'])
            with patch.object(main.jobs,'submit',side_effect=lambda values,name,key:values):
                job=client.post('/api/jobs',json={'dataset_id':saved['id'],'request_id':'test-assumption-job'})
                self.assertEqual(job.status_code,202,job.text)
                self.assertEqual(job.json()['base_run_id'],'base')
                for options in ({'base_run_id':'other'},{'method':'recommended'},{'adjustment':10}):
                    self.assertEqual(client.post('/api/jobs',json={'dataset_id':saved['id'],'request_id':'test-invalid-job',**options}).status_code,400)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = DatasetStore(Path(self.tmp.name))
        history = 'date,item,quantity,fx\n' + ''.join(f'2025-{m:02}-01,{item},{10+m},{100+m}\n' for m in range(1,13) for item in ('A','B'))
        future = b'date,item,fx\n2026-01-01,A,120\n2026-02-01,A,125\n2026-01-01,B,130\n2026-02-01,B,135\n'
        sources = {'history': self.store.upload('history.csv', history.encode(), 'history')['id'], 'future': self.store.upload('future.csv', future, 'future')['id']}
        settings = {'date_col':'date', 'item_col':'item', 'target_col':'quantity', 'unit':'units', 'future_date_col':'date','future_item_col':'item','frequency':'monthly','horizon':2,'drivers':['fx'],'method_selection':'recommended','calendar_country':None}
        self.dataset = self.store.save('Synthetic baseline', sources, settings, 'synthetic_sample', True)
        self.base = {'run_id':'base','dataset_id':self.dataset['id'],'source_classification':'synthetic_sample','method_selection':'model:Ridge + drivers',
                     'run_settings':{'method_selection':'model:Ridge + drivers'}, 'series':{item:{'forecast':[{'timestamp':f'2026-{m:02}-01','mean':10} for m in (1,2)]} for item in ('A','B')},
                     'input_manifest':{'settings':deepcopy(settings),'sources':[{'role':r,'id':i,'sha256':self.store.source(i)[0]['sha256']} for r,i in sources.items()]}}
        self.payload = {'name':'Higher exchange rate','owner':'Test planner','reason':'Synthetic assumption test','reviewed':True,'request_id':str(uuid.uuid4()),
                        'definitions':[{'factor':'fx','unit':'IRR per USD','geography':'Iran national, test market','source':'Invented sample assumption'}],
                        'changes':[{'item_id':'A','period':'2026-01-01','factor':'fx','value':150}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_preview_reconciles_original_future_values(self):
        preview = preview_assumptions(self.base,self.store)
        self.assertEqual(preview['factors'],['fx'])
        self.assertEqual(len(preview['rows']),4)
        self.assertEqual(preview['rows'][0]['fx'],120)

    def test_saved_scenario_is_immutable_scoped_and_preserves_method(self):
        original = deepcopy(self.base)
        result = save_assumptions(self.base,self.store,self.payload)
        self.assertEqual(result['sources']['history'],self.dataset['sources']['history'])
        self.assertNotEqual(result['sources']['future'],self.dataset['sources']['future'])
        self.assertEqual(result['settings']['method_selection'],'model:Ridge + drivers')
        source, content = self.store.source(result['sources']['future'])
        frame = read_table(source['name'],content)
        self.assertEqual(frame.fx.tolist(),[150,125,130,135])
        change = result['scenario_provenance']['changes'][0]
        self.assertEqual((change['baseline_value'],change['value']),(120,150))
        self.assertEqual(self.store.get(self.dataset['id']), self.dataset)
        self.assertEqual(self.base,original)
        self.assertEqual(result['classification'],'synthetic_sample')

    def test_idempotent_retry_and_conflicting_request(self):
        first = save_assumptions(self.base,self.store,self.payload)
        self.assertEqual(save_assumptions(self.base,self.store,self.payload)['id'],first['id'])
        self.payload['changes'][0]['value'] = 151
        with self.assertRaisesRegex(ValueError,'different assumptions'):
            save_assumptions(self.base,self.store,self.payload)

    def test_missing_review_source_unit_or_owner_blocks(self):
        for field, value in [('reviewed',False),('owner',''),('request_id','bad')]:
            payload = {**deepcopy(self.payload),field:value}
            with self.assertRaises(ValueError): save_assumptions(self.base,self.store,payload)
        for field in ('unit','geography','source'):
            payload = deepcopy(self.payload)
            payload['definitions'][0][field]=''
            with self.assertRaises(ValueError): save_assumptions(self.base,self.store,payload)

    def test_bad_keys_duplicate_and_nonfinite_values_block(self):
        for field,value in [('item_id','unknown'),('period','2025-01-01'),('factor','inflation'),('value',None),('value',True),('value',float('inf')),('value',float('nan'))]:
            payload = deepcopy(self.payload)
            payload['changes'][0][field] = value
            with self.assertRaises(ValueError): save_assumptions(self.base,self.store,payload)
        payload = deepcopy(self.payload)
        payload['changes'] *= 2
        with self.assertRaisesRegex(ValueError,'unique'): save_assumptions(self.base,self.store,payload)

    def test_no_change_and_unmatched_metadata_block(self):
        self.payload['changes'][0]['value'] = 120
        with self.assertRaisesRegex(ValueError,'unchanged'): save_assumptions(self.base,self.store,self.payload)
        self.base['source_classification'] = 'user_provided'
        with self.assertRaisesRegex(ValueError,'classification'): preview_assumptions(self.base,self.store)

    def test_changed_source_or_settings_and_nested_scenarios_block(self):
        for alteration in ('settings','hash','scenario'):
            base = deepcopy(self.base)
            if alteration=='settings': base['input_manifest']['settings']['horizon']=3
            if alteration=='hash': base['input_manifest']['sources'][0]['sha256']='changed'
            if alteration=='scenario': base['scenario_name']='Previous scenario'
            with self.assertRaises(ValueError): preview_assumptions(base,self.store)

    def test_baseline_missing_factors_or_wrong_periods_blocks(self):
        self.base['series']['A']['forecast'][0]['timestamp']='2026-03-01'
        with self.assertRaisesRegex(ValueError,'periods'): preview_assumptions(self.base,self.store)

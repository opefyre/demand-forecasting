"""History replacement → grouped revision → independent approval, no live calls."""
from copy import deepcopy
from io import BytesIO
import csv
import json
import unittest
import uuid

import openpyxl
import pandas as pd

from app.company_jobs import execute_company_job
from tests import test_platform_sales as fixtures
from tests.test_company_context import VIEW


class RevisionJourneyTests(unittest.TestCase):
    def test_both_calendars_revision_approval_exports_and_isolation(self):
        for calendar in ('gregorian', 'jalali'):
            with self.subTest(calendar=calendar):
                f = fixtures.PublicSalesTests(); f.setUp()
                try:
                    self.verify(f, calendar)
                finally:
                    f.tearDown()

    def verify(self, f, calendar):
        _, dataset, payload = f.history(calendar=calendar)
        original_source = f.ws.datasets.source(dataset['sources']['history'])[1]
        base, _ = f.calculate(dataset, f.orders(dataset))
        originals = {j['run_id']: deepcopy(f.ws.load_run(j['run_id'])) for j in base['jobs']}
        update = f.post('/forecast-updates', {'run_id':base['jobs'][0]['run_id'],
            'workflow':'grouped', 'request_id':str(uuid.uuid4())}, 201)
        frame = pd.read_csv(BytesIO(original_source), dtype={'sku':str})
        last = frame.loc[frame.customer.eq('Aftab')].index[-1]
        frame.loc[last, 'quantity'] = 26
        uploaded = f.client.post('/api/v1/sources', data={'role':'history'},
            files={'file':('corrected.csv',frame.to_csv(index=False).encode(),'text/csv')})
        self.assertEqual(uploaded.status_code, 201, uploaded.text)
        body = {**payload, 'name':'Corrected history', 'sources':{'history':uploaded.json()['id']},
            'parent_dataset_id':dataset['id'], 'request_id':str(uuid.uuid4()), 'accept_warnings':False}
        preview = f.post('/datasets/preview', body)
        self.assertEqual(preview['repeat_upload']['changed_groups'], 1)
        self.assertEqual(preview['repeat_upload']['after_total']-preview['repeat_upload']['before_total'], 6)
        self.assertEqual(f.client.post('/api/v1/datasets',json=body).status_code,400)
        corrected = f.post('/datasets', {**body,'accept_warnings':True}, 201)
        snapshot = f.orders(corrected)
        request = {'action':'calculate_group','revision':update['revision'],'reviewed':True,
            'dataset_id':corrected['id'],'sales_input_id':snapshot['id'],
            'name':'Reviewed October revision','methods':['model:Last observed','model:Recent average'],
            'request_id':str(uuid.uuid4())}
        path = '/forecast-updates/'+update['id']+'/steps'
        result = f.post(path, request)
        self.assertEqual(f.post(path, request)['group']['id'], result['group']['id'])
        for job in result['group']['jobs']:
            execute_company_job(f.ws,job['id'])
            job=f.get('/jobs/'+job['id'])
            self.assertEqual(job['state'],'succeeded',job)
            run = f.get('/runs/'+job['run_id'])
            self.assertEqual(run['run_settings']['calendar_profile']['month_basis'],calendar)
            outlook = f.get('/runs/'+job['run_id']+'/demand')
            self.assertEqual(len(outlook['rows']),12)
            self.assertTrue(all(r['remaining']>0 for r in outlook['rows'] if r['customer']=='Pars'))
            filtered = f.client.get('/api/v1/runs/'+job['run_id']+'/export',
                params={'kind':'json','mode':'combined_demand','customer':'Aftab','sku':'001'})
            self.assertEqual(filtered.status_code,200,filtered.text)
            self.assertEqual(len(filtered.json()),3)
            self.assertEqual({r['sku'] for r in filtered.json()},{'001'})
            self.assertEqual({r['customer'] for r in filtered.json()},{'Aftab'})
            release_body = {'snapshot_id':run['sales_input_snapshot_id'],'receiver':'Client ERP',
                'mode':'combined_demand','request_id':str(uuid.uuid4())}
            review = f.post('/releases/preview',release_body)
            release = f.post('/releases',{**release_body,'reviewed':True,'review_token':review['review_token']},201)
            approval = {'reviewed':True,'review_token':release['report']['review_token']}
            self.assertEqual(f.client.post('/api/v1/releases/'+release['id']+'/approve',json=approval).status_code,403)
            f.role='admin'; f.subject='independent-reviewer'
            f.post('/releases/'+release['id']+'/approve',approval)
            exports={kind:f.client.get('/api/v1/releases/'+release['id']+'/export',params={'kind':kind})
                for kind in ('csv','xlsx','json')}
            self.assertTrue(all(r.status_code==200 for r in exports.values()))
            rows=exports['json'].json()
            csv_rows=list(csv.DictReader(exports['csv'].content.decode('utf-8-sig').splitlines()))
            workbook=openpyxl.load_workbook(BytesIO(exports['xlsx'].content),data_only=False)
            headers=[cell.value for cell in workbook.active[1]]
            excel_rows=[dict(zip(headers,r)) for r in workbook.active.iter_rows(min_row=2,values_only=True)]
            workbook.close()
            for other in (csv_rows,excel_rows):
                self.assertEqual([float(r['quantity']) for r in other],[r['quantity'] for r in rows])
                self.assertEqual({r['sku'] for r in other},{'001','002'})
            self.assertEqual(len(rows),12)
            self.assertAlmostEqual(sum(r['quantity'] for r in rows),sum(r['still_to_serve'] for r in outlook['rows']))
            f.company='tehran_b'
            self.assertEqual(f.client.get('/api/v1/releases/'+release['id']).status_code,404)
            self.assertEqual(f.client.get('/api/v1/runs/'+job['run_id']).status_code,404)
            f.company='tehran_a'; f.role='viewer'; f.permissions=VIEW.copy()
            self.assertEqual(f.client.get('/api/v1/releases/'+release['id']+'/export?kind=json').status_code,200)
            self.assertEqual(f.client.post('/api/v1'+path,json=request).status_code,403)
            f.role='planner'; f.subject='planner_a'; f.permissions=fixtures.ALL.copy()
        self.assertEqual(f.ws.datasets.get(dataset['id']),dataset)
        self.assertEqual(f.ws.datasets.source(dataset['sources']['history'])[1],original_source)
        for key,original in originals.items():
            self.assertEqual(f.ws.load_run(key),original)

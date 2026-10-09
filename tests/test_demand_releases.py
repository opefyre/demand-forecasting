from copy import deepcopy
from datetime import date,timedelta
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from fastapi import FastAPI,Request
from fastapi.testclient import TestClient

from app.demand_comparison import digest
from app.demand_releases import DemandReleases,ReleaseConflict,identity,install_demand_releases
from app.sales_demand import DemandStore
from tests.test_sales_demand import fixture,order


class DemandReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        self.run,self.inputs=fixture()
        self.inputs['orders']=[order(quantity=16),order('C',3)]
        self.orders=DemandStore(self.root/'sales.sqlite3')
        self.snapshot=self.save_orders()
        self.store=DemandReleases(self.orders,lambda key:deepcopy(self.run))
        self.planner=identity({'issuer':'company','subject':'planner'})
        self.reviewer=identity({'issuer':'company','subject':'reviewer'})
        self.demo=identity(None)
        self.payload={'snapshot_id':self.snapshot['id'],'receiver':'Client ERP','mode':'remaining_forecast'}

    def tearDown(self):self.tmp.cleanup()
    def save_orders(self):
        return self.orders.save(self.inputs,self.run,str(uuid.uuid4()),'Planner',[{'run_sha256':digest(self.run)}])
    def submit(self,actor=None,changes=None):
        payload={**self.payload,**(changes or {})}
        report=self.store.preview(payload)[0]
        body={**payload,'review_token':report['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())}
        return self.store.request(body,actor or self.planner),body
    def approve(self,record,actor=None):
        return self.store.approve(record['id'],{'reviewed':True,'review_token':record['report']['review_token']},actor or self.reviewer,'reviewer')

    def test_customer_matching_and_receiver_modes_reconcile(self):
        report=self.store.preview(self.payload)[0]
        self.assertEqual(report['months'][0]['booked'],19)
        self.assertEqual(report['months'][0]['remaining'],10)
        self.assertEqual(report['months'][0]['quantity'],10)
        combined=self.store.preview({**self.payload,'mode':'combined_demand'})[0]
        self.assertEqual(combined['months'][0]['quantity'],29)
        record,_=self.submit(changes={'mode':'combined_demand'})
        approved=self.approve(record)
        rows=json.loads(self.store.export(record['id'],'json')[0])
        self.assertEqual(sum(r['quantity'] for r in rows),29)
        self.assertEqual(rows[1]['quantity'],8)
        self.assertEqual(rows[0]['approval'],'approved')
        self.assertEqual(rows[0]['release_id'],approved['id'])
        self.assertEqual(self.orders.get(self.snapshot['id']),self.snapshot)

    def test_fulfilled_is_not_sent_to_receiver(self):
        self.inputs['orders']=[order(quantity=8,fulfilled=3)]
        self.snapshot=self.save_orders();self.payload['snapshot_id']=self.snapshot['id']
        r,_=self.submit(changes={'mode':'combined_demand'});self.approve(r)
        rows=json.loads(self.store.export(r['id'],'json')[0])
        self.assertEqual(rows[0]['quantity'],7)
        self.assertEqual(rows[0]['total'],10)
        self.assertEqual(rows[0]['fulfilled'],3)

    def test_independent_company_review_and_exact_retries(self):
        record,body=self.submit()
        self.assertEqual(self.store.request(body,self.planner),record)
        self.assertEqual(len(self.store.list(self.run['run_id'])),1)
        with self.assertRaises(PermissionError):self.approve(record,self.planner)
        with self.assertRaises(PermissionError):self.store.approve(record['id'],{'reviewed':True},self.reviewer,'planner')
        with self.assertRaises(ReleaseConflict):self.store.export(record['id'],'csv')
        approved=self.approve(record)
        self.assertEqual(self.approve(record),approved)
        with self.assertRaises(ReleaseConflict):self.store.request({**body,'mode':'combined_demand'},self.planner)
        with self.assertRaises(ReleaseConflict):self.store.request(body,self.reviewer)
        with self.assertRaises(ReleaseConflict):self.store.approve(record['id'],{'reviewed':True,'review_token':'stale'},self.reviewer,'reviewer')

    def test_demo_signoff_cannot_claim_company_approval(self):
        record,_=self.submit(self.demo)
        with self.assertRaises(ValueError):self.approve(record,self.demo)
        with self.assertRaises(PermissionError):self.approve(record)
        self.store.approve(record['id'],{'reviewed':True,'demo_confirmed':True,'review_token':record['report']['review_token']},self.demo,'local')
        self.assertEqual(json.loads(self.store.export(record['id'],'json')[0])[0]['approval'],'demo_approved')
        company,_=self.submit()
        with self.assertRaises(ValueError):self.store.approve(company['id'],{'reviewed':True,'demo_confirmed':True},self.demo,'local')

    def test_changed_sources_block_stale_review_approval_and_download(self):
        report=self.store.preview(self.payload)[0]
        record,_=self.submit();self.approve(record)
        self.inputs['orders'][0]['ordered']=18
        self.save_orders()
        with self.assertRaisesRegex(ReleaseConflict,'newer order'):self.store.preview(self.payload)
        with self.assertRaises(ReleaseConflict):self.store.export(record['id'],'json')
        self.assertFalse(self.store.detail(record['id'],self.reviewer,'reviewer')['can_export'])
        self.assertEqual(self.store.get(record['id'])['outlook']['rows'][0]['booked'],16)

    def test_forecast_change_or_expiry_blocks_signoff(self):
        record,_=self.submit()
        self.run['series']['A']['forecast'][0]['mean']=25
        with self.assertRaisesRegex(ReleaseConflict,'forecast changed'):self.approve(record)
        self.run['series']['A']['forecast'][0]['mean']=10
        import app.demand_releases as releases
        engine=releases.demand_outlook
        with patch.object(releases,'demand_outlook',side_effect=lambda inputs,run:engine(inputs,run,today=date.today()+timedelta(days=8))):
            with self.assertRaises(ReleaseConflict):self.approve(record)

    def test_invalid_contract_approval_and_changed_preview_rejected(self):
        for patch in ({'receiver':''},{'mode':'add_both'},{'receiver':'x'*121}):
            with self.assertRaises(ValueError):self.store.preview({**self.payload,**patch})
        report=self.store.preview(self.payload)[0]
        body={**self.payload,'reviewed':True,'request_id':str(uuid.uuid4()),'review_token':report['review_token']}
        with self.assertRaises(ValueError):self.store.request({**body,'reviewed':False},self.planner)
        with self.assertRaises(ReleaseConflict):self.store.request({**body,'mode':'combined_demand'},self.planner)
        with self.assertRaises(ReleaseConflict):self.store.request({**body,'review_token':'stale'},self.planner)

    def test_source_exceptions_require_resolution_not_silent_acceptance(self):
        self.inputs['commitments']=[{'customer':'B','sku':'001','unit':'tonnes','period':date.today().replace(day=1).isoformat(),
            'quantity':6,'owner':'Planner','reason':'Old complete commitment','valid_until':(date.today()-timedelta(days=1)).isoformat()}]
        self.snapshot=self.save_orders()
        with self.assertRaisesRegex(ReleaseConflict,'expired'):self.store.preview({**self.payload,'snapshot_id':self.snapshot['id']})

    def test_new_approved_version_replaces_download_not_original_record(self):
        first,_=self.submit();first=self.approve(first)
        second,_=self.submit();self.assertEqual(second['version'],2)
        self.assertEqual(self.store.export(first['id'],'json')[0],self.store.export(first['id'],'json')[0])
        self.approve(second)
        with self.assertRaisesRegex(ReleaseConflict,'newer approved'):self.store.export(first['id'],'json')
        self.assertTrue(self.store.detail(first['id'],self.reviewer,'reviewer')['superseded'])
        self.assertEqual(self.store.get(first['id']),first)

    def test_policy_change_replaces_old_mode_and_older_drafts_cannot_replace_new(self):
        older,_=self.submit()
        newer,_=self.submit(changes={'mode':'combined_demand'})
        self.assertEqual(newer['version'],2)
        self.approve(newer)
        with self.assertRaisesRegex(ReleaseConflict,'newer version'):self.approve(older)
        self.assertFalse(self.store.detail(older['id'],self.reviewer,'reviewer')['can_approve'])

    def test_old_months_require_current_order_review_before_handoff(self):
        old=(date.today().replace(day=1)-timedelta(days=1)).replace(day=1).isoformat()
        self.inputs['as_of']=old
        self.run['series']['A']['forecast'].insert(0,{'timestamp':old,'mean':10})
        self.snapshot=self.save_orders()
        with self.assertRaisesRegex(ReleaseConflict,'closed month'):self.store.preview({**self.payload,'snapshot_id':self.snapshot['id']})

    def test_csv_excel_json_have_same_quantities_and_safe_identifiers(self):
        import csv,openpyxl
        record,_=self.submit(changes={'receiver':'=unsafe formula'})
        self.approve(record)
        j=json.loads(self.store.export(record['id'],'json')[0])
        c=list(csv.DictReader(self.store.export(record['id'],'csv')[0].decode('utf-8-sig').splitlines()))
        w=openpyxl.load_workbook(BytesIO(self.store.export(record['id'],'xlsx')[0]),data_only=False)
        headers=[x.value for x in w.active[1]];x=[dict(zip(headers,r)) for r in w.active.iter_rows(min_row=2,values_only=True)]
        self.assertEqual([float(r['quantity']) for r in c],[r['quantity'] for r in j])
        self.assertEqual([r['quantity'] for r in x],[r['quantity'] for r in j])
        self.assertEqual(x[0]['receiver'],"'=unsafe formula")
        self.assertEqual(c[0]['receiver'],"'=unsafe formula")
        w.close()

    def test_persistence_and_api_guarded_approval_and_exports(self):
        app=FastAPI();principal={'issuer':'company','subject':'planner','role':'planner'}
        @app.middleware('http')
        async def authenticated(request:Request,next):
            request.state.principal=principal
            return await next(request)
        reopened=DemandReleases(self.orders,lambda key:self.run);install_demand_releases(app,reopened)
        with TestClient(app) as client:
            url='/api/sales/releases'
            preview=client.post(url+'/preview',json=self.payload)
            self.assertEqual(preview.status_code,200,preview.text)
            body={**self.payload,'review_token':preview.json()['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())}
            submitted=client.post(url,json=body);self.assertEqual(submitted.status_code,200,submitted.text)
            record=submitted.json();key=url+'/'+record['id'];approval={'reviewed':True,'review_token':body['review_token']}
            self.assertEqual(client.post(key+'/approve',json=approval).status_code,403)
            principal={'issuer':'company','subject':'reviewer','role':'reviewer'}
            self.assertTrue(client.get(key).json()['can_approve'])
            self.assertEqual(client.post(key+'/approve',json=approval).status_code,200)
            self.assertEqual(client.get(key+'/export?kind=json').status_code,200)
            self.assertEqual(client.get(key+'/export?kind=exe').status_code,400)
            self.assertEqual(len(client.get(url,params={'run_id':self.run['run_id']}).json()['releases']),1)
            inbox=client.get(url)
            self.assertEqual(inbox.status_code,200,inbox.text)
            self.assertEqual(inbox.json()['releases'][0]['id'],record['id'])
            self.assertTrue(inbox.json()['releases'][0]['can_export'])
            self.assertEqual(client.get(url,params={'run_id':'other-run'}).json()['releases'],[])
            self.inputs['orders'][0]['ordered']=30
            self.save_orders()
            stale=client.get(url).json()['releases'][0]
            self.assertFalse(stale['can_export'])
            self.assertIn('newer order review',stale['blocked'])


if __name__=='__main__':unittest.main()

"""Synthetic vintage matrix, real adapter/engine/order-matching paths."""
from copy import deepcopy
from datetime import date, timedelta
from io import BytesIO
import csv
import io
import unittest
from unittest.mock import patch
import uuid

import httpx
import pandas as pd
from fastapi.testclient import TestClient

from tests import test_factor_links as fixtures
from app.factor_links import choices, preview_link, save_link
from app.supply_pressure import archived_points
from app.sales_demand import demand_outlook


def matrix():
    vintages = pd.period_range('2023-12', '2026-02', freq='M')
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(['Date', *[v.strftime('%b-%y') for v in vintages]])
    for i, period in enumerate(pd.period_range('2023-11', '2026-01', freq='M')):
        writer.writerow([period.end_time.strftime('%d-%b-%Y'), *[
            '#N/A' if period >= v else 999 if i == 0 and v >= pd.Period('2024-02',freq='M') else i + j / 10
            for j,v in enumerate(vintages)]])
    return output.getvalue().encode()


class PublicFactorLinkTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.FactorLinkTests(); self.f.setUp()
        self.snapshot = self.f.factors.refresh('global_supply_pressure', transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=matrix())))
        self.payload = {'snapshot_id':self.snapshot['id'], 'lag_months':2, 'future_value':1,
                        'availability_policy':'vintage_month_end'}

    def tearDown(self): self.f.tearDown()

    def preview(self, payload=None):
        return preview_link(self.f.base,self.f.store,self.f.factors,payload or self.payload)

    def test_public_choice_keeps_real_provenance_in_sample_comparison(self):
        rows = choices(self.f.base,self.f.store,self.f.factors)['snapshots']
        self.assertEqual(len(rows),2)
        self.assertTrue(next(r for r in rows if r['id']==self.snapshot['id'])['public_vintage'])
        review=self.preview()
        self.assertEqual(review['factor_classification'],'real')
        self.assertTrue(any('synthetic sales' in w for w in review['warnings']))
        self.assertEqual(self.f.factors.get(self.snapshot['id'])['use'],'context_only')

    def test_acknowledgment_required_and_first_vintage_excludes_later_revision(self):
        with self.assertRaisesRegex(ValueError,'Accept'):
            self.preview({**self.payload,'availability_policy':None})
        review=self.preview();self.assertEqual(review['missing'],0)
        first=review['rows'][0]
        self.assertEqual(first['value'],0)  # Not the later 999 correction.
        self.assertEqual(first['vintage_month'],'2023-12')
        self.assertEqual(first['availability_date'],'2023-12-31')
        self.assertIsNone(first['publication_date'])
        future=[r for r in review['rows'] if r['kind']=='future']
        self.assertEqual(future[0]['vintage_month'],'2025-12')
        self.assertEqual(future[1]['treatment'],'planning_assumption')
        self.assertEqual(future[1]['value'],1)

    def test_current_vintage_not_available_before_its_month_end(self):
        from app.supply_pressure import parse_supply_pressure
        result=parse_supply_pressure(matrix(),'2026-02-15T00:00:00Z',include_archive=True)
        self.assertNotIn('2026-02',{p['vintage_month'] for p in result['archive_points']})
        self.assertIn('2026-01',{p['vintage_month'] for p in result['archive_points']})

    def test_missing_early_archive_and_unknown_future_block_save(self):
        for changes in ({'lag_months':1},{'future_value':None}):
            payload={**self.payload,**changes};report=self.preview(payload)
            self.assertGreater(report['missing'],0)
            with self.assertRaisesRegex(ValueError,'missing or unpublished'):
                save_link(self.f.base,self.f.store,self.f.factors,{**payload,'reviewed':True,
                    'review_token':report['review_token'],'request_id':str(uuid.uuid4())})

    def test_raw_tampering_blocks_preview_and_save(self):
        report=self.preview()
        path=self.f.factors.root/'raw'/f"{self.snapshot['id']}.csv"
        path.write_bytes(matrix().replace(b'999',b'998'))
        with self.assertRaisesRegex(ValueError,'no longer matches'):self.preview()
        with self.assertRaises(ValueError):
            save_link(self.f.base,self.f.store,self.f.factors,{**self.payload,'reviewed':True,
                'review_token':report['review_token'],'request_id':str(uuid.uuid4())})

    def test_cannot_trust_snapshot_path_or_points_instead_of_retained_file(self):
        altered={**self.snapshot,'raw_response':'../../anything','points':[]}
        self.assertTrue(archived_points(self.f.factors,altered))

    def test_real_engine_export_and_orders_above_below_and_absent(self):
        import app.main as main
        runs=self.f.root/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.f.store),patch.object(main,'FACTOR_STORE',self.f.factors),patch.object(main,'RUNS_DIR',runs),TestClient(main.app) as client:
            baseline=client.post('/api/run-saved',json={'dataset_id':self.f.dataset['id']})
            self.assertEqual(baseline.status_code,200,baseline.text); base=baseline.json()
            url=f"/api/runs/{base['run_id']}/factor-links"
            review=client.post(url+'/preview',json=self.payload)
            self.assertEqual(review.status_code,200,review.text)
            body={**self.payload,'reviewed':True,'review_token':review.json()['review_token'],'request_id':str(uuid.uuid4())}
            saved=client.post(url,json=body); self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(saved.json()['settings']['driver_roles'][review.json()['column']], 'external')
            self.assertEqual(saved.json(),client.post(url,json=body).json())
            response=client.post('/api/run-saved',json={'dataset_id':saved.json()['id']})
            self.assertEqual(response.status_code,200,response.text); linked=response.json()
            self.assertEqual(base['metrics']['evaluation_signature'],linked['metrics']['evaluation_signature'])
            self.assertEqual(base['items'],linked['items'])
            self.assertFalse(linked['scenario']['orders_changed'])
            self.assertFalse(linked['scenario']['release_dates_verified'])
            for item in base['items']:
                self.assertEqual(base['series'][item]['history'],linked['series'][item]['history'])
            for row in linked['series']['__all__']['forecast']:
                self.assertAlmostEqual(row['mean'],sum(p['mean'] for key in linked['items']
                    for p in linked['series'][key]['forecast'] if p['timestamp']==row['timestamp']))
            with pd.ExcelFile(runs/linked['run_id']/'forecast_package.xlsx') as book:
                alignment=pd.read_excel(book,sheet_name='Factor alignment')
                self.assertIn('vintage_month',alignment.columns)
                self.assertTrue(alignment.publication_date.isna().all())
                sources=pd.read_excel(book,sheet_name='Factor sources')
                self.assertIn('attribution',sources.columns)
            orders={'name':'Synthetic orders','run_id':linked['run_id'],'classification':'synthetic_sample',
                'as_of':'2026-01-01','valid_until':'2026-02-28','order_feed':'complete_snapshot',
                'customers':[{'customer':item,'sku':'SKU','unit':'tonnes','series_id':item} for item in ['A','B']],
                'orders':[{'reference':'A-1','customer':'A','sku':'SKU','unit':'tonnes','due_date':'2026-01-15',
                    'ordered':10000,'fulfilled':0,'cancelled':0,'status':'confirmed'},
                    {'reference':'B-1','customer':'B','sku':'SKU','unit':'tonnes','due_date':'2026-01-15',
                    'ordered':1,'fulfilled':0,'cancelled':0,'status':'confirmed'}],
                'reviewed':True,'commitments':[],'note':'Test only'}
            before=deepcopy(orders)
            result=demand_outlook(orders,linked,today=date(2026,1,1))
            self.assertEqual(before,orders)
            jan=[r for r in result['rows'] if r['period']=='2026-01-01']
            self.assertEqual(jan[0]['total'],10000)
            self.assertEqual(jan[0]['remaining'],0)
            self.assertAlmostEqual(jan[1]['total'],jan[1]['baseline'])
            feb=[r for r in result['rows'] if r['period']=='2026-02-01']
            self.assertTrue(all(r['booked']==0 and r['total']==r['baseline'] for r in feb))


if __name__=='__main__': unittest.main()

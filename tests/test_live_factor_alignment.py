"""Live inputs are sensitivity evidence, not retrospectively validated accuracy."""
from copy import deepcopy
from datetime import date
from io import BytesIO
import json
import unittest
from unittest.mock import patch
import uuid

import openpyxl
import pandas as pd
from fastapi.testclient import TestClient

from app.commodity_prices import SERIES, parse_prices
from app.factor_links import choices, preview_link, save_link, accuracy_comparison
from app.live_factor_alignment import monthly_points
from app.live_sources import LiveSources
from app.sales_demand import demand_outlook, export_demand
from tests import test_factor_links as fixtures

CAPTURE = '2026-10-03T12:00:00+00:00'


def prices(end='2026-09'):
    book = openpyxl.Workbook(); sheet = book.active; sheet.title = 'Monthly Prices'
    sheet.append([None] + [v[0] for v in SERIES.values()])
    sheet.append([None] + [v[1] for v in SERIES.values()])
    for i, month in enumerate(pd.period_range('2023-11', end, freq='M')):
        sheet.append([month.strftime('%YM%m')] + [80 + i + j for j in range(len(SERIES))])
    content = BytesIO(); book.save(content); book.close()
    return content.getvalue()


class LiveFactorAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.FactorLinkTests(); self.f.setUp()
        self.feeds = LiveSources(self.f.root / 'feeds.sqlite', self.f.factors)
        raw = prices(); definitions = {'worldbank_' + key: {**row, 'provider':'World Bank',
            'frequency':'monthly', 'geography':'Global reference'} for key, row in parse_prices(raw, CAPTURE).items()}
        with patch('app.live_sources.now', return_value=CAPTURE):
            self.snapshot = self.feeds.save('commodities', definitions, raw, 'xlsx', 'https://example.invalid')[0]
        self.payload = {'snapshot_id':self.snapshot['id'], 'lag_months':2,
            'future_value':150, 'availability_policy':'reviewed_what_if'}

    def tearDown(self): self.f.tearDown()

    def preview(self, payload=None, base=None):
        return preview_link(base or self.f.base, self.f.store, self.f.factors, payload or self.payload)

    def test_live_choice_and_acknowledgment_and_fixed_method(self):
        offered = choices(self.f.base, self.f.store, self.f.factors)['snapshots']
        self.assertTrue(next(s for s in offered if s['id']==self.snapshot['id'])['live_what_if'])
        with self.assertRaisesRegex(ValueError, 'Accept'):
            self.preview({**self.payload, 'availability_policy':None})
        for method in ['recommended', 'seasonal', 'model:Seasonal naive']:
            base = {**self.f.base, 'method_selection':method}
            with self.assertRaisesRegex(ValueError, 'factor-aware'):
                self.preview(base=base)

    def test_history_is_explicitly_retrospective_but_future_capture_gate_remains(self):
        report = self.preview()
        self.assertTrue(report['retrospective']); self.assertEqual(report['missing'],0)
        self.assertEqual(report['rows'][0]['value'],80)
        self.assertEqual(report['rows'][0]['treatment'],'downloaded_history')
        self.assertEqual(report['rows'][0]['availability_date'],CAPTURE)
        # January 2026 forecast may not use observations first captured in October.
        future = [r for r in report['rows'] if r['kind']=='future']
        self.assertTrue(all(r['treatment']=='planning_assumption' for r in future))
        self.assertTrue(all(r['value']==150 for r in future))
        self.assertGreater(self.preview({**self.payload,'future_value':None})['missing'],0)

    def test_integrity_and_original_inputs_unchanged(self):
        review = self.preview(); original = deepcopy(self.f.dataset)
        body = {**self.payload, 'reviewed':True, 'review_token':review['review_token'], 'request_id':str(uuid.uuid4())}
        saved = save_link(self.f.base,self.f.store,self.f.factors,body)
        self.assertEqual(saved['settings']['driver_roles'][review['column']], 'external')
        self.assertEqual(saved['settings']['evidence_policy'],'reviewed_what_if')
        self.assertFalse(saved['scenario_provenance']['orders_changed'])
        self.assertEqual(self.f.store.get(original['id']),original)
        self.assertEqual(saved,save_link(self.f.base,self.f.store,self.f.factors,body))
        (self.f.factors.root / self.snapshot['raw_response']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'no longer matches'): self.preview()

    def test_future_capture_gate_uses_tehran_midnight_not_utc_midnight(self):
        raw = prices('2025-11')
        for hour, expected in [(20,104),(22,150)]:
            captured = f'2025-12-31T{hour}:00:00+00:00'
            definition = {**parse_prices(raw,captured)['brent'],'provider':'World Bank',
                          'frequency':'monthly','geography':'Global reference'}
            with patch('app.live_sources.now',return_value=captured):
                snapshot = self.feeds.save('commodities',{'worldbank_brent':definition},raw,'xlsx','https://example.invalid')[0]
            report = self.preview({**self.payload,'snapshot_id':snapshot['id']})
            first = next(r for r in report['rows'] if r['kind']=='future')
            self.assertEqual(first['value'],expected)
            self.assertEqual(first['release_cutoff'],'2026-01-01T00:00:00+03:30')

    def test_complete_observed_day_fx_means_no_intraday_bias_or_gap_fill(self):
        quotes = []
        for day in pd.date_range('2025-01-01', '2025-01-31'):
            quotes.append({'quote_time':day.isoformat()+'+03:30', 'period':day.date().isoformat(),
                           'value':100, 'available_at':CAPTURE})
        # Last quote on January 1 replaces that day's first quote, not another vote.
        quotes.append({**quotes[0], 'quote_time':'2025-01-01T20:00:00+03:30','value':410})
        quotes.append({'quote_time':'2025-02-01T20:00:00+03:30','period':'2025-02-01','value':900,'available_at':CAPTURE})
        quotes.append({'quote_time':'2026-10-01T20:00:00+03:30','period':'2026-10-01','value':900,'available_at':CAPTURE})
        raw = json.dumps({'retained_quotes':quotes}).encode()
        with patch('app.live_sources.now',return_value=CAPTURE):
            snapshot = self.feeds.save('servix', {'servix_usd_rls':{'name':'USD / Iranian rial',
                'provider':'Servix','geography':'Iran reference','frequency':'quotes',
                'unit':'IRR per USD','points':quotes}}, raw,'json','https://example.invalid')[0]
        points, quality = monthly_points(self.f.factors,snapshot)
        self.assertEqual(len(points),1)
        self.assertEqual(points[0]['value'],110)
        self.assertEqual(points[0]['observed_days'],31)
        self.assertIn('80%',quality['coverage_policy'])
        payload = {**self.payload,'snapshot_id':snapshot['id']}
        report = self.preview(payload)
        self.assertGreater(report['missing'],0)
        with self.assertRaisesRegex(ValueError,'missing or unpublished'):
            save_link(self.f.base,self.f.store,self.f.factors,{**payload,'reviewed':True,
                'review_token':report['review_token'],'request_id':str(uuid.uuid4())})
        with self.assertRaisesRegex(ValueError,'greater than zero'):
            self.preview({**payload,'future_value':0})

    def test_persian_sales_uses_completed_gregorian_observation_not_relabelled_average(self):
        settings = {**self.f.dataset['settings'],'month_basis':'jalali'}
        from app.sales_conventions import shift_month
        dates = [shift_month('2024-03-20',i,'jalali').date().isoformat() for i in range(6)]
        rows = pd.DataFrame([{'date':d,'item':'A','sku':'SKU','customer':'A','qty':20+i}
            for i,d in enumerate(dates)])
        source = self.f.store.upload('persian.csv',rows.to_csv(index=False).encode(),'history')
        dataset = self.f.store.save('Persian sales',{'history':source['id']},settings,'synthetic_sample',True)
        base = {**self.f.base,'dataset_id':dataset['id'],
                'series':{'A':{'forecast':[{'timestamp':shift_month('2024-03-20',i,'jalali').date().isoformat()} for i in [6,7]]}},
                'input_manifest':{'settings':settings,'sources':[{'role':'history','id':source['id'],'sha256':source['sha256']}]}}
        report = self.preview(base=base)
        self.assertEqual(report['rows'][0]['observation_period'],'2024-01-31')
        self.assertEqual(report['rows'][0]['sales_month'],'2024-03-20')

    def test_engine_api_exports_scope_and_orders_keep_policy(self):
        import app.main as main
        runs = self.f.root / 'runs'; runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.f.store), patch.object(main,'FACTOR_STORE',self.f.factors), patch.object(main,'RUNS_DIR',runs), patch.object(main.LIVE_SOURCES,'tick'), TestClient(main.app) as client:
            response = client.post('/api/run-saved',json={'dataset_id':self.f.dataset['id']})
            self.assertEqual(response.status_code,200,response.text); base = response.json()
            url = f"/api/runs/{base['run_id']}/factor-links"
            payload = self.payload
            response = client.post(url+'/preview',json=payload)
            self.assertEqual(response.status_code,200,response.text)
            response = client.post(url,json={**payload,'review_token':response.json()['review_token'],
                'reviewed':True,'request_id':str(uuid.uuid4())})
            self.assertEqual(response.status_code,200,response.text)
            response = client.post('/api/run-saved',json={'dataset_id':response.json()['id']})
            self.assertEqual(response.status_code,200,response.text); result = response.json()
            self.assertEqual(result['metrics']['evidence_policy'],'reviewed_what_if')
            self.assertIsNone(result['metrics']['wape_pct'])
            self.assertFalse(result['metrics']['independent_accuracy_verified'])
            self.assertFalse(result['factor_validation']['available'])
            self.assertTrue(all(r['p10'] is None for r in result['series']['A']['forecast']))
            self.assertEqual(result['series']['A']['history'],base['series']['A']['history'])
            for row in result['series']['__all__']['forecast']:
                self.assertAlmostEqual(row['mean'],sum(r['mean'] for key in ['A','B'] for r in result['series'][key]['forecast'] if r['timestamp']==row['timestamp']))
            with pd.ExcelFile(runs/result['run_id']/'forecast_package.xlsx') as book:
                self.assertFalse(pd.read_excel(book,'Factor accuracy').iloc[0]['available'])
                self.assertTrue(pd.read_excel(book,'Factor test evidence').empty)
                self.assertIn('Factor alignment',book.sheet_names)
                self.assertTrue(pd.read_excel(book,'Models').wape_pct.isna().all())
                self.assertTrue(pd.read_excel(book,'Range parameters').empty)
                self.assertTrue(pd.read_excel(book,'Range fitting').empty)
                self.assertTrue(pd.read_excel(book,'Range check').empty)
            self.assertTrue(pd.read_csv(runs/result['run_id']/'model_leaderboard.csv').wape_pct.isna().all())
            self.assertTrue(pd.read_csv(runs/result['run_id']/'forecast.csv').forecast_use.eq('what_if_unvalidated').all())
            self.assertTrue(all(r['wape_pct'] is None for r in result['leaderboard']))
            self.assertFalse(accuracy_comparison(base,result)['available'])
            from app.factor_scope import apply_factor_scope
            apply_factor_scope(result,base,['A'],runs/result['run_id'])
            self.assertEqual(result['series']['B'],base['series']['B'])
            # Existing order-aware combination must still honor orders above,
            # below, and absent, without a forecast+order double count.
            orders = {'name':'Sample orders','run_id':result['run_id'],'classification':'synthetic_sample',
                'as_of':'2026-01-01','valid_until':'2026-02-28','order_feed':'complete_snapshot',
                'customers':[{'customer':key,'sku':'SKU','unit':'tonnes','series_id':key} for key in ['A','B']],
                'orders':[{'reference':'A-1','customer':'A','sku':'SKU','unit':'tonnes','due_date':'2026-01-15',
                           'ordered':10000,'fulfilled':0,'cancelled':0,'status':'confirmed'},
                          {'reference':'B-1','customer':'B','sku':'SKU','unit':'tonnes','due_date':'2026-01-15',
                           'ordered':1,'fulfilled':0,'cancelled':0,'status':'confirmed'}],
                'commitments':[],'reviewed':True,'note':'Synthetic test only'}
            before=deepcopy(orders)
            outlook = demand_outlook(orders,result,today=date(2026,1,1))
            self.assertEqual(outlook['forecast_use'],'what_if_unvalidated')
            self.assertTrue(all(r['forecast_use']=='what_if_unvalidated' for r in json.loads(export_demand(outlook,'combined_demand','json')[0])))
            self.assertEqual(orders,before)
            january=[r for r in outlook['rows'] if r['period']=='2026-01-01']
            self.assertEqual(january[0]['total'],10000)
            self.assertEqual(january[0]['remaining'],0)
            self.assertEqual(january[1]['total'],january[1]['baseline'])
            february=[r for r in outlook['rows'] if r['period']=='2026-02-01']
            self.assertTrue(all(r['booked']==0 and r['total']==r['baseline'] for r in february))

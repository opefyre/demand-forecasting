"""Isolated public-route acceptance: real file parsers and forecasting engine.

No live feeds, OpenAI requests, client records or persistent demo writes.
"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.data import read_table, preview_table
from app.datasets import DatasetStore
from app.factors import FactorStore
from app.sales_api import install_sales_routes
from app.sales_demand import DemandStore
from app.demand_releases import DemandReleases, install_demand_releases


class IdentifierImportTests(unittest.TestCase):
    def test_delimited_identifiers_and_numeric_preview(self):
        for suffix, sep in [('csv', ','), ('tsv', '\t')]:
            raw = sep.join(['date', 'series', 'customer', 'sku', 'quantity']) + '\n'
            raw += sep.join(['2026-01-01', '0007', 'NA', '001', '10.5']) + '\n'
            frame = read_table('sales.' + suffix, raw.encode())
            self.assertEqual(frame.iloc[0][['series', 'customer', 'sku']].tolist(), ['0007', 'NA', '001'])
            self.assertEqual(frame.quantity.iloc[0], 10.5)
            self.assertIn('quantity', preview_table('sales.' + suffix, raw.encode())['numeric_columns'])

    def test_excel_text_codes_and_json_strings(self):
        rows = [{'date': '2026-01-01', 'series': '0007', 'customer': 'NULL', 'sku': '001', 'quantity': 10}]
        buffer = BytesIO()
        pd.DataFrame(rows).to_excel(buffer, index=False)
        payloads = [('xlsx', buffer.getvalue()), ('json', json.dumps(rows).encode()),
                    ('jsonl', json.dumps(rows[0]).encode())]
        for suffix, raw in payloads:
            frame = read_table('history.' + suffix, raw)
            self.assertEqual(frame.iloc[0][['series', 'customer', 'sku']].tolist(), ['0007', 'NULL', '001'])

    def test_long_codes_and_nullable_numeric_codes(self):
        frame = read_table('sales.csv', b'customer,sku,quantity\n12345678901234567890,123,10\n12345678901234567891,,20\n')
        self.assertEqual(frame.customer.tolist(), ['12345678901234567890', '12345678901234567891'])
        self.assertEqual(frame.sku.iloc[0], '123')
        self.assertTrue(pd.isna(frame.sku.iloc[1]))


class SalesImportJourneyTests(unittest.TestCase):
    def setUp(self):
        import app.main as main
        self.main = main
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(TemporaryDirectory()))
        self.datasets = DatasetStore(root / 'datasets')
        self.factors = FactorStore(root / 'factors')
        self.orders = DemandStore(root / 'sales.sqlite3')
        runs = root / 'runs'
        runs.mkdir()
        for name, value in [('DATASET_STORE', self.datasets), ('FACTOR_STORE', self.factors), ('RUNS_DIR', runs)]:
            self.stack.enter_context(patch.object(main, name, value))
        # Actual route handlers, isolated stores and no background worker lifespan.
        app = FastAPI()
        @app.middleware('http')
        async def principal(request: Request, call_next):
            request.state.principal = None
            return await call_next(request)
        routes = {'/api/sources', '/api/datasets', '/api/datasets/validate', '/api/run-saved',
                  '/api/factor-imports/preview', '/api/factor-imports',
                  '/api/runs/{run_id}/factor-links/preview', '/api/runs/{run_id}/factor-links'}
        app.router.routes.extend(r for r in main.app.routes if getattr(r, 'path', None) in routes)
        install_sales_routes(app, self.orders, self.datasets, main._load_run)
        install_demand_releases(app, DemandReleases(self.orders,main._load_run))
        self.client = self.stack.enter_context(TestClient(app))

    def post(self, path, body):
        response = self.client.post(path, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def upload(self, frame, role, sales=False):
        response = self.client.post('/api/sales/sources' if sales else '/api/sources',
            data={'role': role}, files={'file': (role + '.csv', frame.to_csv(index=False).encode(), 'text/csv')})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_plain_sales_file_to_exact_customer_orders_and_signed_demo_exports(self):
        from app.sales_conventions import local_today
        from app.ai_workspace import input_context
        from app.assumptions import scenario_inputs
        today=local_today(); start=pd.Timestamp(today.replace(day=1))
        dates=pd.date_range(end=start-pd.offsets.MonthBegin(),periods=36,freq='MS')
        # Normal business file: no composite identifier, one SKU shared by customers.
        history=pd.DataFrame([dict(date=str(d.date()),customer=c,sku='001',quantity=q)
            for c,q in [('A',10),('B',20),('C',5)] for d in dates])
        source=self.upload(history,'history')
        settings=dict(date_col='date',target_col='quantity',customer_col='customer',sku_col='sku',
            series_mode='customer_product',unit='tonnes',frequency='monthly',horizon=2,profile='fast',
            drivers=[],method_selection='model:Last observed',calendar_country='IR',weekend_days=[4])
        config=dict(name='Synthetic plain-column journey',sources={'history':source['id']},settings=settings,
            classification='synthetic_sample',accept_warnings=True)
        review=self.post('/api/datasets/validate',config)
        self.assertEqual(review['summary']['series'],3)
        dataset=self.post('/api/datasets',config)
        context=input_context(self.datasets,dataset)
        self.assertEqual({m['customer'] for m in context['metadata'].values()},{'A','B','C'})
        baseline=self.post('/api/run-saved',{'dataset_id':dataset['id']})
        self.assertEqual(len([k for k in baseline['series'] if k!='__all__']),3)
        _,_,future,_,_=scenario_inputs(baseline,self.datasets,allow_empty_drivers=True)
        self.assertEqual(set(future.item_id),set(baseline['metadata']))
        expected={'A':10,'B':20,'C':5}
        for key,meta in baseline['metadata'].items():
            self.assertEqual(meta['sku'],'001')
            for point in baseline['series'][key]['forecast']:
                self.assertAlmostEqual(point['mean'],expected[meta['customer']],places=7)
        starter=self.client.get('/api/sales/runs/'+baseline['run_id']+'/starter').json()
        self.assertEqual({r['customer'] for r in starter['customers']},{'A','B','C'})
        starter.update(reviewed=True,note='Synthetic complete book including customer C without orders',
            order_feed='complete_snapshot',valid_until=str(today+timedelta(days=7)))
        orders=pd.DataFrame([dict(reference='A-01',customer='A',sku='001',unit='tonnes',due_date=str(today),
            ordered=16,fulfilled=2,cancelled=0,status='confirmed'),
            dict(reference='B-01',customer='B',sku='001',unit='tonnes',due_date=str(today),
            ordered=6,fulfilled=0,cancelled=0,status='confirmed')])
        upload=self.upload(orders,'orders',sales=True)
        payload={'inputs':starter,'imports':{'orders':{'source_id':upload['id'],
            'mapping':dict(zip(orders.columns,'ABCDEFGHIJ'))}},'request_id':'plain-journey-orders'}
        outlook=self.post('/api/sales/validate',payload)
        self.assertTrue(outlook['can_export'])
        first=[r for r in outlook['rows'] if r['period']==str(start.date())]
        self.assertEqual(sum(r['total'] for r in first),41)
        self.assertEqual(sum(r['still_to_serve'] for r in first),39)
        self.assertEqual(sum(r['remaining'] for r in first),19)
        self.assertEqual(next(r for r in first if r['customer']=='C')['remaining'],5)
        saved=self.post('/api/sales/inputs',payload)
        for mode,quantity in [('combined_demand',74),('remaining_forecast',54)]:
            body=dict(snapshot_id=saved['id'],receiver='Synthetic MRP receiver',mode=mode)
            report=self.post('/api/sales/releases/preview',body)
            submitted=self.post('/api/sales/releases',{**body,'reviewed':True,
                'review_token':report['review_token'],'request_id':'plain-release-'+mode})
            approved=self.post('/api/sales/releases/'+submitted['id']+'/approve',
                {'reviewed':True,'demo_confirmed':True,'review_token':report['review_token']})
            self.assertEqual(approved['state'],'approved')
            for kind in ('json','csv','xlsx'):
                response=self.client.get('/api/sales/releases/'+submitted['id']+'/export?kind='+kind)
                self.assertEqual(response.status_code,200)
                if kind=='json':frame=pd.DataFrame(response.json())
                elif kind=='csv':frame=pd.read_csv(BytesIO(response.content),dtype={'sku':str},keep_default_na=False)
                else:frame=pd.read_excel(BytesIO(response.content),dtype={'sku':str},keep_default_na=False)
                self.assertEqual(len(frame),6)
                self.assertEqual(set(frame.customer),{'A','B','C'})
                self.assertEqual(set(frame.sku),{'001'})
                self.assertEqual(set(frame.approval),{'demo_approved'})
                self.assertAlmostEqual(frame.quantity.sum(),quantity,places=7)
        self.assertEqual(self.datasets.get(dataset['id']),dataset)
        self.assertEqual(self.datasets.source(source['id'])[1],history.to_csv(index=False).encode())

        # The factor scenario keeps the exact pairs, without requiring users to
        # create or edit the internal keys. No external provider is contacted.
        factor_dates=pd.date_range(start=dates[0]-pd.offsets.MonthEnd(2),
            end=start-pd.offsets.MonthEnd(2),freq='ME')
        factor_source=self.upload(pd.DataFrame([dict(period=str(d.date()),value=100+i,
            published=str((d+pd.Timedelta(days=5)).date())) for i,d in enumerate(factor_dates)]),'factor_observations')
        factor_config=dict(source_id=factor_source['id'],mapping={'period':'A','value':'B','available_at':'C'},
            name='Synthetic context for customer pairs',unit='index points',geography='Iran',
            provider='Synthetic acceptance fixture',frequency='monthly',classification='synthetic_sample')
        factor_review=self.post('/api/factor-imports/preview',factor_config)
        factor=self.post('/api/factor-imports',{**factor_config,'review_token':factor_review['review_token'],
            'reviewed':True,'request_id':'55555555-5555-4555-8555-555555555555'})
        url='/api/runs/'+baseline['run_id']+'/factor-links'
        link=dict(snapshot_id=factor['id'],lag_months=2,future_value=150)
        link_review=self.post(url+'/preview',link)
        self.assertEqual(link_review['missing'],0)
        linked=self.post(url,{**link,'review_token':link_review['review_token'],'reviewed':True,
            'request_id':'66666666-6666-4666-8666-666666666666'})
        linked_run=self.post('/api/run-saved',{'dataset_id':linked['id']})
        self.assertEqual(linked_run['metadata'],baseline['metadata'])
        self.assertEqual(linked_run['metrics']['evaluation_signature'],baseline['metrics']['evaluation_signature'])

    def test_history_customers_orders_factors_to_all_export_formats(self):
        today = datetime.now(timezone.utc).date()
        start = pd.Timestamp(today.replace(day=1))
        dates = pd.date_range(end=start - pd.offsets.MonthBegin(), periods=36, freq='MS')
        rows = [dict(date=str(d.date()), series=series, customer=customer, sku='001', quantity=qty)
                for series, customer, qty in [('0001', 'NA', 10), ('0002', '002', 20), ('0003', '003', 30)]
                for d in dates]
        source = self.upload(pd.DataFrame(rows), 'history')
        settings = dict(date_col='date', target_col='quantity', item_col='series', customer_col='customer',
            sku_col='sku', unit='tonnes', frequency='monthly', horizon=3, profile='fast',
            drivers=[], method_selection='model:Ridge + drivers', missing_strategy='auto', outlier_strategy='none',
            future_driver_policy='require', calendar_country='IR', weekend_days=[4], shutdown_dates=[])
        config = dict(name='Synthetic import acceptance', sources={'history': source['id']}, settings=settings,
                      classification='synthetic_sample', accept_warnings=True)
        self.post('/api/datasets/validate', config)
        dataset = self.post('/api/datasets', config)
        baseline = self.post('/api/run-saved', {'dataset_id': dataset['id']})
        self.assertEqual(set(baseline['series']) - {'__all__'}, {'0001', '0002', '0003'})
        self.assertEqual(baseline['metadata']['0001']['sku'], '001')
        self.assertEqual(baseline['metadata']['0001']['customer'], 'NA')

        customers = pd.DataFrame([dict(customer=c, sku='001', unit='tonnes', series_id=s)
                                  for s, c in [('0001', 'NA'), ('0002', '002'), ('0003', '003')]])
        order_rows = [dict(reference=ref, customer=c, sku='001', unit='tonnes', due_date=str(today),
                          ordered=q, fulfilled=f, cancelled=x, status=status)
                      for ref, c, q, f, x, status in [('00001','NA',16,2,1,'confirmed'),
                          ('00002','002',8,0,0,'confirmed'), ('00003','002',100,0,100,'cancelled'),
                          ('00004','003',999,0,0,'unconfirmed')]]
        order_frame = pd.DataFrame(order_rows)
        imports = {}
        for role, frame in [('customers', customers), ('orders', order_frame)]:
            upload = self.upload(frame, role, sales=True)
            self.post(f'/api/sales/sources/{upload["id"]}/preview', {})
            imports[role] = {'source_id': upload['id'], 'mapping': dict(zip(frame.columns, 'ABCDEFGHIJ'))}
        inputs = dict(name='Synthetic demand', run_id=baseline['run_id'], as_of=str(today),
            valid_until=str(today+timedelta(days=7)), classification='synthetic_sample',
            order_feed='complete_snapshot', reviewed=True, note='Synthetic full-workflow acceptance')
        payload = {'inputs': inputs, 'imports': imports, 'request_id': 'journey-orders-01'}
        preview = self.post('/api/sales/validate', payload)
        self.assertTrue(preview['can_export'])
        saved = self.post('/api/sales/inputs', payload)
        self.assertEqual(saved['inputs']['orders'][0]['reference'], '00001')
        self.assertEqual(self.post('/api/sales/inputs', payload)['id'], saved['id'])
        self.assertEqual(len(saved['evidence'][0]['cells']), 3)

        # Recompute from model outputs + known fixture orders, not demand_outlook.
        # A has 2 delivered, 13 open; B has 8 open. Cancelled/unconfirmed add zero.
        def expected_rows(run):
            expected = {}
            for key, customer in [('0001','NA'), ('0002','002'), ('0003','003')]:
                for row in run['series'][key]['forecast']:
                    period = row['timestamp'][:10]
                    current = period == str(start.date())
                    fulfilled = 2 if current and customer == 'NA' else 0
                    booked = {'NA':13, '002':8, '003':0}[customer] if current else 0
                    remaining = max(0, row['mean'] - fulfilled - booked)
                    expected[customer, period] = dict(booked=booked, fulfilled=fulfilled, remaining=remaining,
                        total=fulfilled+booked+remaining, still_to_serve=booked+remaining)
            return expected
        expected = expected_rows(baseline)
        for row in preview['rows']:
            for field, value in expected[row['customer'], row['period']].items():
                self.assertAlmostEqual(row[field], value, places=7)
        self.assertAlmostEqual(sum(r['booked'] for r in preview['rows']), 21, places=5)
        for kind in ['json', 'csv', 'xlsx']:
            for mode, field in [('combined_demand', 'still_to_serve'), ('remaining_forecast', 'remaining')]:
                response = self.client.get(f'/api/sales/inputs/{saved["id"]}/export?kind={kind}&mode={mode}')
                self.assertEqual(response.status_code, 200, response.text[:200] if kind != 'xlsx' else '')
                if kind == 'json':
                    frame = pd.DataFrame(response.json())
                elif kind == 'csv':
                    frame = pd.read_csv(BytesIO(response.content), dtype={'customer':str, 'sku':str}, keep_default_na=False)
                else:
                    frame = pd.read_excel(BytesIO(response.content), dtype={'customer':str, 'sku':str}, keep_default_na=False)
                self.assertEqual(len(frame), 9)
                self.assertEqual(set(frame.customer), {'NA','002','003'})
                self.assertEqual(set(frame.sku), {'001'})
                self.assertAlmostEqual(frame.quantity.sum(), sum(r[field] for r in expected.values()), places=7)

        # Monthly synthetic Iran context, explicitly not a real inflation/FX feed.
        factor_dates = pd.date_range(start=dates[0]-pd.offsets.MonthEnd(2), end=start-pd.offsets.MonthEnd(2), freq='ME')
        factor_rows = [dict(period=str(d.date()), value=100+i, published=str((d+pd.Timedelta(days=5)).date()))
                       for i,d in enumerate(factor_dates)]
        factor_source = self.upload(pd.DataFrame(factor_rows), 'factor_observations')
        factor_config = dict(source_id=factor_source['id'], mapping={'period':'A','value':'B','available_at':'C'},
            name='Synthetic Iran context', unit='index points', geography='Iran', provider='Synthetic acceptance fixture',
            frequency='monthly', classification='synthetic_sample')
        factor_review = self.post('/api/factor-imports/preview', factor_config)
        factor = self.post('/api/factor-imports', {**factor_config, 'review_token':factor_review['review_token'],
            'reviewed':True, 'request_id':'33333333-3333-4333-8333-333333333333'})
        url = f'/api/runs/{baseline["run_id"]}/factor-links'
        link = {'snapshot_id':factor['id'], 'lag_months':2, 'future_value':150}
        review = self.post(url+'/preview', link)
        self.assertEqual(review['missing'], 0)
        linked = self.post(url, {**link, 'review_token':review['review_token'], 'reviewed':True,
                               'request_id':'44444444-4444-4444-8444-444444444444'})
        target = self.post('/api/run-saved', {'dataset_id':linked['id']})
        self.assertEqual(target['metrics']['evaluation_signature'], baseline['metrics']['evaluation_signature'])
        reuse_url = f'/api/sales/runs/{target["run_id"]}/order-comparison'
        compared = self.post(reuse_url+'/preview', {'snapshot_id':saved['id']})
        copied = self.post(reuse_url, {'snapshot_id':saved['id'], 'review_token':compared['review_token'],
            'reviewed':True, 'request_id':'journey-copy-01'})
        self.assertEqual(copied['inputs']['orders'], saved['inputs']['orders'])
        self.assertEqual(self.orders.get(saved['id']), saved)
        self.assertEqual(self.datasets.get(dataset['id']), dataset)
        final = self.client.get(f'/api/sales/inputs/{copied["id"]}/export?mode=combined_demand&kind=json').json()
        target_expected = expected_rows(target)
        self.assertEqual(len(final), 9)
        for row in final:
            self.assertAlmostEqual(row['quantity'], target_expected[row['customer'],row['period']]['still_to_serve'], places=7)

        for change in [{'order_feed':'unknown'}, {'valid_until':str(today-timedelta(days=1)), 'as_of':str(today-timedelta(days=2))}]:
            blocked = self.post('/api/sales/validate', {**payload, 'inputs':{**inputs, **change}})
            self.assertFalse(blocked['can_export'])


if __name__ == '__main__':
    unittest.main()

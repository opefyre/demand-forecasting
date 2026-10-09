from copy import deepcopy
import asyncio
from datetime import date
import json
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.commodity_prices import parse_prices
from app.factor_links import preview_link,save_link
from app.factor_preparation import FactorContext,prepare_sources,validate_preparation
from app.live_sources import LiveSources
from app.sales_demand import demand_outlook,export_demand
from tests import test_factor_links as fixtures
from tests.test_live_factor_alignment import prices,CAPTURE


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.FactorLinkTests();self.f.setUp()
        self.f.base['leaderboard']=[{'model':'Ridge + drivers'}]
        self.live=LiveSources(self.f.root/'live.sqlite',self.f.factors)
        self.capture=patch('app.live_sources.now',return_value=CAPTURE);self.capture.start();self.addCleanup(self.capture.stop)
        self.addCleanup(self.f.tearDown)
        self.make_prices()

    def make_prices(self,end='2026-09'):
        raw=prices(end)
        definitions={'worldbank_'+key:{**row,'provider':'World Bank','frequency':'monthly','geography':'Global reference'}
                     for key,row in parse_prices(raw,CAPTURE).items()}
        self.snapshots=self.live.save('commodities',definitions,raw,'xlsx','https://example.invalid')

    def report(self,context=None):
        return prepare_sources(self.f.base,self.f.store,self.f.factors,self.live,context or {'materials':['aluminum']})

    def prepared(self):
        report=self.report();row=report['recommendations'][-1]
        return {'links':[{**row['link'],'future_value':150}],'method':row['method'],
                'preparation':{'context':report['context'],'review_token':report['review_token'],
                               'snapshot_ids':[row['snapshot_id']]}}

    def test_explicit_exposure_only_no_sku_name_inference(self):
        report=self.report({'currency_exposure':True,'global_supply':True,'hormuz_route':True,'materials':['aluminum','lead']})
        self.assertEqual([r['source_id'] for r in report['recommendations']],
                         ['iran_cpi','servix','supply','hormuz','commodities','commodities'])
        empty=prepare_sources(self.f.base,self.f.store,self.f.factors,self.live,{})
        self.assertEqual(len(empty['recommendations']),1)
        self.assertEqual(empty['recommendations'][0]['status'],'permission_needed')
        self.assertIn('Annual',empty['context_only'][0])
        self.assertEqual(self.f.base['series'].keys(),{'A','B'})

    def test_context_is_strict_bounded_and_cannot_inject_url(self):
        for value in ({'url':'https://bad.invalid'},{'currency_exposure':'true'},
                      {'materials':['unknown']},{'materials':['lead','lead']},
                      {'materials':['lead','zinc','copper','aluminum','nickel','brent']}):
            with self.subTest(value=value),self.assertRaises(ValueError):FactorContext.model_validate(value)

    def test_complete_history_missing_future_is_explicit_and_no_network_or_write(self):
        before=sorted(p.name for p in self.f.root.rglob('*'))
        with patch.object(self.live,'refresh',side_effect=AssertionError('No network refresh')):
            report=self.report()
        row=report['recommendations'][-1]
        self.assertTrue(row['can_prepare']);self.assertEqual(row['status'],'assumptions_needed')
        self.assertEqual((row['history_months'],row['history_missing'],row['future_missing']),(24,0,2))
        self.assertTrue(all(r['known_value'] is None for r in row['future_months']))
        self.assertEqual(row['method'],'model:Ridge + drivers');self.assertTrue(row['what_if'])
        self.assertEqual(sorted(p.name for p in self.f.root.rglob('*')),before)

    def test_stale_observations_overdue_capture_and_raw_corruption_not_ready(self):
        with patch('app.live_sources.now',return_value='2027-01-03T12:00:00+00:00'):
            self.assertEqual(self.report()['recommendations'][-1]['status'],'refresh_needed')
        self.live.write('commodities',{'enabled':True,'status':'success','last_success':'2026-09-01T00:00:00Z'})
        self.assertFalse(self.report()['recommendations'][-1]['can_prepare'])
        self.live.write('commodities',{'enabled':False,'status':'success'})
        row=self.report()['recommendations'][-1]
        snapshot=self.f.factors.get(row['snapshot_id'])
        (self.f.factors.root/snapshot['raw_response']).write_bytes(b'corrupt')
        self.assertEqual(self.report()['recommendations'][-1]['status'],'unavailable')

    def test_recent_capture_never_hides_short_history(self):
        with patch('app.live_sources.now',return_value='2026-10-04T12:00:00+00:00'):
            self.make_prices('2024-08')
            report=self.report()['recommendations'][-1]
        self.assertFalse(report['can_prepare']);self.assertGreater(report['history_missing'],0)

    def test_review_and_save_retain_context_and_leave_original_unchanged(self):
        original=deepcopy(self.f.dataset);body=self.prepared()
        report=preview_link(self.f.base,self.f.store,self.f.factors,body,self.live)
        self.assertEqual(report['missing'],0);self.assertIn('preparation',report)
        saved=save_link(self.f.base,self.f.store,self.f.factors,
            {**body,'reviewed':True,'review_token':report['review_token'],'request_id':str(uuid.uuid4())},self.live)
        self.assertEqual(saved['settings']['factor_context']['materials'],['aluminum'])
        self.assertEqual(saved['settings']['evidence_policy'],'reviewed_what_if')
        self.assertFalse(saved['scenario_provenance']['orders_changed'])
        self.assertEqual(self.f.store.get(original['id']),original)

    def test_changed_context_tokens_ids_or_refresh_require_new_review(self):
        body=self.prepared()
        for change in ({'context':{'materials':['lead']}},{'review_token':'bad'},
                       {'snapshot_ids':[]},{'snapshot_ids':[body['preparation']['snapshot_ids'][0]]*2}):
            changed={**body,'preparation':{**body['preparation'],**change}}
            with self.subTest(change=change),self.assertRaises(ValueError):
                validate_preparation(self.f.base,self.f.store,self.f.factors,self.live,changed)
        self.live.write('commodities',{'enabled':True,'last_success':'2026-09-01T00:00:00Z'})
        with self.assertRaises(ValueError):validate_preparation(self.f.base,self.f.store,self.f.factors,self.live,body)

    def test_live_download_never_becomes_automatic_factor_selection(self):
        body=self.prepared();body['method']='factor_test'
        with self.assertRaisesRegex(ValueError,'what-if'):
            preview_link(self.f.base,self.f.store,self.f.factors,body,self.live)

    def test_subset_model_names_are_normalized_for_followup_preparation(self):
        self.f.base.update(method_selection='factor_test',leaderboard=[{'model':'Ridge + drivers [fx]'}])
        self.assertEqual(self.report()['recommendations'][-1]['method'],'model:Ridge + drivers')

    def test_route_returns_local_evidence_and_rejects_unknown_context(self):
        from app import main
        with patch.object(main,'DATASET_STORE',self.f.store),patch.object(main,'FACTOR_STORE',self.f.factors),\
             patch.object(main,'LIVE_SOURCES',self.live),patch.object(main,'_load_run',return_value=self.f.base),\
             TestClient(main.app) as client:
            response=client.post('/api/runs/base/factor-preparation',json={'materials':['aluminum']})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['recommendations'][-1]['future_missing'],2)
            self.assertEqual(client.post('/api/runs/base/factor-preparation',json={'url':'x'}).status_code,400)

    def test_prepared_source_runs_existing_engine_orders_and_all_export_formats(self):
        from app import main
        from io import BytesIO
        import csv
        import openpyxl
        runs=self.f.root/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.f.store),patch.object(main,'FACTOR_STORE',self.f.factors),\
             patch.object(main,'RUNS_DIR',runs):
            base=asyncio.run(main.run_saved(main.SavedRunConfig(dataset_id=self.f.dataset['id'])))
            report=prepare_sources(base,self.f.store,self.f.factors,self.live,{'materials':['aluminum']})
            source=report['recommendations'][-1]
            body={'links':[{**source['link'],'future_value':150}],'method':source['method'],
                  'preparation':{'context':report['context'],'snapshot_ids':[source['snapshot_id']],
                                 'review_token':report['review_token']}}
            preview=preview_link(base,self.f.store,self.f.factors,body,self.live)
            dataset=save_link(base,self.f.store,self.f.factors,{**body,'reviewed':True,
                'review_token':preview['review_token'],'request_id':str(uuid.uuid4())},self.live)
            run=asyncio.run(main.run_saved(main.SavedRunConfig(dataset_id=dataset['id'],base_run_id=base['run_id'])))
            self.assertIsNone(run['metrics']['wape_pct'])
            self.assertEqual(run['scenario']['alignment']['preparation']['context']['materials'],['aluminum'])
            orders={'name':'Synthetic test','classification':'synthetic_sample','run_id':run['run_id'],
                'as_of':'2026-01-01','valid_until':'2026-02-01','order_feed':'complete_snapshot',
                'customers':[{'customer':key,'sku':'SKU','unit':'tonnes','series_id':key} for key in ('A','B')],
                'orders':[{'reference':'A1','customer':'A','sku':'SKU','unit':'tonnes','due_date':'2026-01-15',
                           'ordered':200,'fulfilled':20,'cancelled':0,'status':'confirmed'}],
                'commitments':[],'reviewed':True,'note':'Artificial scenario only.'}
            original=deepcopy(orders);outlook=demand_outlook(orders,run,today=date(2026,1,1))
            a=next(r for r in outlook['rows'] if r['customer']=='A' and r['period']=='2026-01-01')
            self.assertEqual(a['booked'],180)
            for r in outlook['rows']:
                self.assertAlmostEqual(r['remaining'],max(r['baseline']-r['booked']-r['fulfilled'],0))
                self.assertAlmostEqual(r['still_to_serve'],r['booked']+r['remaining'])
            self.assertEqual(orders,original)
            for mode in ('combined_demand','remaining_forecast'):
                totals=[]
                for kind in ('csv','xlsx','json'):
                    content,_=export_demand(outlook,mode,kind)
                    if kind=='json':rows=json.loads(content)
                    elif kind=='csv':rows=list(csv.DictReader(content.decode('utf-8-sig').splitlines()))
                    else:
                        book=openpyxl.load_workbook(BytesIO(content),read_only=True,data_only=True)
                        values=list(book.worksheets[0].values);rows=[dict(zip(values[0],r)) for r in values[1:]];book.close()
                    self.assertEqual(len(rows),4);totals.append(sum(float(r['quantity']) for r in rows))
                self.assertAlmostEqual(totals[0],totals[1]);self.assertAlmostEqual(totals[1],totals[2])

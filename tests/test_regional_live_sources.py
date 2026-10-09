from copy import deepcopy
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from unittest.mock import patch

import httpx
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.factors import FactorStore, observations_available_at
from app.hormuz_traffic import parse_traffic, monthly_traffic, ENDPOINT as SHIPS, UNIT as SHIP_UNIT
from app.iran_cpi import parse_cpi, data_url, ENDPOINT as CPI, UNIT as CPI_UNIT
from app.live_factor_alignment import monthly_points, is_live_monthly
from app.live_sources import LiveSources, SourceError, install_live_sources
from app.factor_links import preview_link, save_link
from tests import test_factor_links as fixtures

CAPTURE = '2026-10-03T12:00:00+00:00'


def traffic():
    return {'definition': 'Distinct commercial vessels crossing the Musandam line per UTC day, per direction.',
            'generatedAt': int(pd.Timestamp(CAPTURE).timestamp()*1000),
            'license': 'CC BY 4.0 — hormuz.now; PortWatch data © IMF PortWatch',
            'days': [{'date':d.date().isoformat(),'in':2,'out':3,'total':5,'tankers':1,
                      'source':'legacy' if d.month==8 else 'live','portwatch':900,'avg7':987}
                     for d in pd.date_range('2026-08-01','2026-10-03')]}


def cpi(first='2023-11',last='2026-09'):
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=['DATAFLOW','COUNTRY','INDEX_TYPE','COICOP_1999',
        'TYPE_OF_TRANSFORMATION','FREQUENCY','TIME_PERIOD','OBS_VALUE','SCALE','REFERENCE_PERIOD','COMMON_REFERENCE_PERIOD'])
    writer.writeheader()
    for i,month in enumerate(pd.period_range(first,last,freq='M')):
        writer.writerow({'DATAFLOW':'IMF.STA:CPI(5.0.0)','COUNTRY':'IRN','INDEX_TYPE':'CPI','COICOP_1999':'_T',
            'TYPE_OF_TRANSFORMATION':'IX','FREQUENCY':'M','TIME_PERIOD':month.strftime('%Y-M%m'),
            'OBS_VALUE':100+i,'SCALE':'0','REFERENCE_PERIOD':'2021A','COMMON_REFERENCE_PERIOD':'2021A'})
    return output.getvalue().encode()


class RegionalSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name);self.factors=FactorStore(self.root/'factors')
        self.feeds=LiveSources(self.root/'feeds.sqlite',self.factors)
    def tearDown(self):self.tmp.cleanup()

    def shipping(self,payload=None):
        self.feeds.transport=httpx.MockTransport(lambda r:httpx.Response(200,json=payload or traffic()))
        with patch('app.live_sources.now',return_value=CAPTURE):self.feeds.refresh('hormuz')
        return self.factors.list()[0]

    def test_shipping_uses_own_counts_and_discards_bundled_imf_and_averages(self):
        snapshot=self.shipping();raw=(self.factors.root/snapshot['raw_response']).read_bytes()
        self.assertNotIn(b'portwatch',raw.lower());self.assertNotIn(b'avg7',raw);self.assertNotIn(b'900',raw)
        self.assertTrue(snapshot['upstream_response_sha256']);self.assertTrue(snapshot['retention_basis'])
        self.assertEqual(snapshot['points'][-1]['period'],'2026-10-02');self.assertEqual(snapshot['unit'],SHIP_UNIT)
        points,quality=monthly_points(self.factors,snapshot)
        self.assertEqual([(p['period'],p['value']) for p in points],[('2026-08-31',5),('2026-09-30',5)])
        self.assertEqual(points[0]['reconstructed_days'],31);self.assertEqual(points[1]['reconstructed_days'],0)
        self.assertEqual(quality['incomplete_months'][0]['observed_days'],2)
        self.assertTrue(observations_available_at(snapshot,'2026-09-30').empty)
        self.assertTrue(is_live_monthly(snapshot))

    def test_missing_shipping_day_excludes_whole_month_not_zero_filling(self):
        payload=traffic();payload['days']=[r for r in payload['days'] if r['date']!='2026-09-06']
        snapshot=self.shipping(payload);points,quality=monthly_points(self.factors,snapshot)
        self.assertEqual(len(points),1);self.assertTrue(any(r['month']=='2026-09' for r in quality['incomplete_months']))

    def test_shipping_schema_dates_counts_flags_and_definition_rejected(self):
        for change in ('duplicate','future','count','boolean','partial','source','definition','licence','generated'):
            p=traffic()
            if change=='duplicate':p['days'].append(p['days'][0])
            if change=='future':p['days'][0]['date']='2026-10-04'
            if change=='count':p['days'][0]['total']=4
            if change=='boolean':p['days'][0]['total']=True
            if change=='partial':p['days'][0]['partial']='false'
            if change=='source':p['days'][0]['source']='unknown'
            if change=='definition':p['definition']='estimated cargo volume'
            if change=='licence':p['license']='All rights reserved'
            if change=='generated':p['generatedAt']=True
            with self.subTest(change=change),self.assertRaises(ValueError):parse_traffic(json.dumps(p).encode(),CAPTURE)
        with self.assertRaises(ValueError):parse_traffic(b'{"days":[],"days":[]}',CAPTURE)

    def test_shipping_integrity_and_tampered_monthly_cache_not_trusted(self):
        snapshot=self.shipping();snapshot['monthly'][0]['value']=999
        self.assertEqual(monthly_points(self.factors,snapshot)[0][0]['value'],5)
        changed=deepcopy(snapshot);changed['points'][0]['value']=6
        with self.assertRaises(ValueError):monthly_points(self.factors,changed)
        (self.factors.root/snapshot['raw_response']).write_bytes(b'changed')
        with self.assertRaises(ValueError):monthly_points(self.factors,snapshot)

    def test_shipping_failure_preserves_last_good_and_scheduled_pause_persists(self):
        snapshot=self.shipping();self.feeds.configure('hormuz',True)
        self.feeds.transport=httpx.MockTransport(lambda r:httpx.Response(503,text='unsafe-body'))
        with self.assertRaises(SourceError):self.feeds.refresh('hormuz',force=True)
        self.assertEqual(len(self.factors.list()),1);self.assertEqual(self.feeds.state('hormuz')['snapshot_ids'],[snapshot['id']])
        self.assertNotIn('unsafe-body',json.dumps(self.feeds.listing()))
        self.feeds.configure('hormuz',False)
        self.assertFalse(LiveSources(self.feeds.path,self.factors).state('hormuz')['enabled'])

    def test_shipping_stale_update_is_visible_even_if_fetch_succeeds(self):
        p=traffic();p['generatedAt']=int(pd.Timestamp('2026-10-02T10:00:00Z').timestamp()*1000)
        p['days']=[r for r in p['days'] if r['date']<='2026-10-02'];self.shipping(p)
        with patch('app.live_sources.now',return_value=CAPTURE):
            self.assertTrue(next(r for r in self.feeds.listing()['sources'] if r['id']=='hormuz')['data_behind'])

    def test_cpi_requires_permission_before_configure_queue_or_network(self):
        self.feeds.transport=httpx.MockTransport(lambda r:self.fail('Unpermitted network call'))
        for operation in [lambda:self.feeds.configure('iran_cpi',True),lambda:self.feeds.queue_refresh('iran_cpi'),lambda:self.feeds.refresh('iran_cpi'),lambda:self.feeds.monthly_inflation()]:
            with self.assertRaises(SourceError):operation()
        with self.assertRaises(SourceError):self.feeds.permission('iran_cpi',True,'')
        self.assertEqual(self.factors.list(),[])

    def test_cpi_fixed_endpoint_permission_persistence_withdrawal_and_missing_values(self):
        calls=[]
        def respond(request):
            calls.append(request);self.assertTrue(str(request.url).startswith(CPI+'?'))
            self.assertEqual(request.url.params['startPeriod'],'2010-01')
            self.assertIsNone(request.headers.get('X-API-Key'))
            return httpx.Response(200,content=cpi().replace(b',134,0,',b',,0,'))
        self.feeds.transport=httpx.MockTransport(respond)
        self.feeds.permission('iran_cpi',True,'Synthetic test permission reference, not a real grant')
        self.feeds.configure('iran_cpi',True)
        with patch('app.live_sources.now',return_value=CAPTURE):self.feeds.refresh('iran_cpi')
        snapshot=self.factors.list()[0];self.assertEqual(len(calls),1);self.assertEqual(snapshot['unit'],CPI_UNIT)
        self.assertEqual(snapshot['points'][-1]['period'],'2026-08-31');self.assertEqual(len(snapshot['points']),34)
        self.assertEqual(len(monthly_points(self.factors,snapshot)[0]),34)
        self.assertTrue(LiveSources(self.feeds.path,self.factors).state('iran_cpi')['permission_confirmed'])
        self.feeds.permission('iran_cpi',False,'');self.assertFalse(self.feeds.state('iran_cpi')['enabled'])
        with self.assertRaises(SourceError):self.feeds.refresh('iran_cpi',force=True)
        self.assertEqual(len(calls),1)

    def test_cpi_schema_country_measure_scale_base_and_dates_fail_closed(self):
        raw=cpi('2026-01','2026-02')
        for bad in [raw.replace(b'IRN',b'USA'),raw.replace(b',IX,',b',YOY_PCH_PA_PT,'),raw.replace(b'2021A',b'2010A'),
                    raw.replace(b',0,2021A',b',3,2021A'),raw.replace(b',100,',b',nan,'),raw.replace(b'2026-M01',b'2026-M02'),
                    raw.replace(b'2026-M02',b'2026-M10'),raw.replace(b'TIME_PERIOD',b'UNKNOWN')]:
            with self.assertRaises(ValueError):parse_cpi(bad,CAPTURE)
        self.assertIn('endPeriod=2026-09',data_url(datetime(2026,10,3).date()))

    def test_permission_revoked_during_fetch_does_not_save(self):
        self.feeds.permission('iran_cpi',True,'Synthetic fixture permission')
        def respond(request):
            self.feeds.permission('iran_cpi',False,'');return httpx.Response(200,content=cpi())
        self.feeds.transport=httpx.MockTransport(respond)
        with self.assertRaisesRegex(SourceError,'withdrawn'):self.feeds.refresh('iran_cpi')
        self.assertEqual(self.factors.list(),[]);self.assertFalse(self.feeds.state('iran_cpi')['enabled'])

    def test_permission_api_strict_and_no_implicit_enable(self):
        app=FastAPI();install_live_sources(app,self.feeds,type('Schedule',(),{'add_job':lambda *a,**kw:None})())
        with TestClient(app) as client:
            url='/api/live-sources/iran_cpi/permission'
            self.assertEqual(client.put(url,json={'confirmed':'true','reference':'Synthetic reference'}).status_code,422)
            self.assertEqual(client.put(url,json={'confirmed':True,'reference':'Synthetic reference','extra':1}).status_code,422)
            self.assertEqual(client.put(url,json={'confirmed':True,'reference':'Synthetic reference'}).status_code,200)
            self.assertFalse(self.feeds.state('iran_cpi')['enabled'])

    def test_cpi_reviewed_link_real_source_sample_history_and_missing_shipping_blocks(self):
        f=fixtures.FactorLinkTests();f.setUp()
        try:
            feeds=LiveSources(f.root/'regional.sqlite',f.factors)
            feeds.permission('iran_cpi',True,'Synthetic fixture permission')
            feeds.transport=httpx.MockTransport(lambda r:httpx.Response(200,content=cpi()))
            with patch('app.live_sources.now',return_value=CAPTURE):feeds.refresh('iran_cpi')
            snap=next(s for s in f.factors.list() if s.get('live_source')=='iran_cpi')
            payload={'snapshot_id':snap['id'],'lag_months':2,'future_value':700,'availability_policy':'reviewed_what_if'}
            review=preview_link(f.base,f.store,f.factors,payload)
            self.assertEqual(review['missing'],0);self.assertTrue(review['retrospective'])
            before=deepcopy(f.dataset)
            saved=save_link(f.base,f.store,f.factors,{**payload,'reviewed':True,'review_token':review['review_token'],'request_id':str(uuid.uuid4())})
            self.assertEqual(saved['settings']['evidence_policy'],'reviewed_what_if');self.assertEqual(f.store.get(before['id']),before)
            feeds.transport=httpx.MockTransport(lambda r:httpx.Response(200,json=traffic()))
            with patch('app.live_sources.now',return_value=CAPTURE):feeds.refresh('hormuz')
            ship=next(s for s in f.factors.list() if s.get('live_source')=='hormuz')
            payload={**payload,'snapshot_id':ship['id'],'future_value':5}
            review=preview_link(f.base,f.store,f.factors,payload)
            self.assertGreater(review['missing'],0)
            with self.assertRaisesRegex(ValueError,'missing or unpublished'):
                save_link(f.base,f.store,f.factors,{**payload,'reviewed':True,'review_token':review['review_token'],'request_id':str(uuid.uuid4())})
        finally:f.tearDown()

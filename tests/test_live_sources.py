from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx
import openpyxl
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.commodity_prices import SERIES, LANDING, workbook_url, parse_prices
from app.factors import FactorStore, observations_available_at
from app.live_sources import LiveSources, SourceError, quote, install_live_sources
from app.security import AccessControl

URL = 'https://thedocs.worldbank.org/en/doc/example/related/CMO-Historical-Data-Monthly.xlsx'


def workbook(unit_override=None, duplicate=False):
    book = openpyxl.Workbook()
    book.active.title = 'Mismatch Details'  # A real upstream workbook has this first.
    sheet = book.create_sheet('Monthly Prices')
    sheet.append(['World Bank Commodity Price Data'])
    sheet.append(['Updated on October 02, 2026'])
    sheet.append([None] + [x[0] for x in SERIES.values()])
    sheet.append([None] + [unit_override or x[1] for x in SERIES.values()])
    sheet.append(['2025M01'] + list(range(1, len(SERIES) + 1)))
    sheet.append(['2025M01' if duplicate else '2025M02'] + ['…'] + list(range(2, len(SERIES) + 1)))
    content = BytesIO()
    book.save(content)
    return content.getvalue()


class Vault:
    value = None
    def get(self): return self.value
    def set(self, value): self.value = value


class Scheduler:
    def add_job(self, *args, **kwargs): self.job = (args, kwargs)


class LiveSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.factors = FactorStore(self.root / 'factors')
        self.vault = Vault()
        self.store = LiveSources(self.root / 'feeds.sqlite3', self.factors, vault=self.vault)

    def tearDown(self): self.tmp.cleanup()

    def commodity_transport(self, content=None, status=200):
        def respond(request):
            self.assertIsNone(request.headers.get('X-API-Key'))
            self.assertFalse(request.url.query)
            if str(request.url) == LANDING:
                return httpx.Response(200, text=f'<a href="{URL}">Monthly prices</a>')
            self.assertEqual(str(request.url), URL)
            return httpx.Response(status, content=content or workbook())
        return httpx.MockTransport(respond)

    def test_monthly_download_named_sheet_units_and_missing_values(self):
        self.store.transport = self.commodity_transport()
        self.store.refresh('commodities')
        rows = self.factors.list()
        self.assertEqual(len(rows), len(SERIES))
        brent = next(r for r in rows if r['factor_id'] == 'worldbank_brent')
        self.assertEqual(brent['unit'], '$/bbl')
        self.assertEqual(len(brent['points']), 1)  # Missing month is not filled.
        self.assertEqual(brent['points'][0]['period'], '2025-01-31')
        self.assertTrue(observations_available_at(brent, '2025-02-28').empty)
        self.assertEqual(brent['use'], 'context_only')
        self.assertTrue((self.factors.root / brent['raw_response']).exists())
        self.assertTrue(self.store.listing()['sources'][1]['data_behind'])

    def test_unit_change_and_duplicate_month_block_before_saving(self):
        for content in [workbook(unit_override='toman'), workbook(duplicate=True)]:
            with self.subTest():
                with self.assertRaises(ValueError): parse_prices(content, '2026-10-03T00:00:00+00:00')
        self.assertEqual(self.factors.list(), [])

    def test_only_official_worldbank_download_host(self):
        for url in [URL.replace('thedocs.worldbank.org', 'localhost'), URL.replace('https:', 'http:'), URL.replace('thedocs.worldbank.org', 'evil.example')]:
            with self.assertRaises(ValueError): workbook_url(url)
        self.assertEqual(workbook_url(URL), URL)

    def test_failed_refresh_keeps_previous_and_redacts_errors(self):
        self.store.transport = self.commodity_transport()
        self.store.refresh('commodities')
        count = len(self.factors.list())
        self.store.transport = httpx.MockTransport(lambda r: (_ for _ in ()).throw(RuntimeError('private-key-must-not-leak')))
        with self.assertRaises(SourceError): self.store.refresh('commodities', force=True)
        self.assertEqual(len(self.factors.list()), count)
        state = self.store.state('commodities')
        self.assertEqual(state['status'], 'failed')
        self.assertIsNotNone(state['last_success'])
        self.assertNotIn('private-key', json.dumps(state))
        with self.assertRaisesRegex(SourceError, 'Refresh is paused until'): self.store.refresh('commodities', force=True)
        with self.assertRaises(SourceError) as failure: self.store.queue_refresh('commodities')
        self.assertIn(state['cooldown_until'],str(failure.exception))
        self.assertIn(state['error'],str(failure.exception))
        self.assertNotIn('private-key',str(failure.exception))

    def test_http_redirect_is_not_followed(self):
        requests = []
        def respond(request):
            requests.append(request)
            return httpx.Response(302, headers={'location': 'http://127.0.0.1/private'})
        self.store.transport = httpx.MockTransport(respond)
        with self.assertRaises(SourceError): self.store.refresh('commodities')
        self.assertEqual(len(requests), 1)

    def test_response_size_is_bounded(self):
        self.store.transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 4_000_001))
        with self.assertRaisesRegex(SourceError, 'size'): self.store.refresh('commodities')

    def test_key_verified_and_only_vault_receives_it(self):
        def respond(request):
            self.assertEqual(request.headers['X-API-Key'], 'private-test-key')
            self.assertNotIn('private-test-key', str(request.url))
            return httpx.Response(200, json={'assets': [{'code':'USD_RLS','quoteUnit':'RLS','providerSupported':True,'providers':['SERVIX']}]})
        self.store.transport = httpx.MockTransport(respond)
        result = self.store.setup_key('private-test-key')
        self.assertTrue(result['saved'])
        self.assertEqual(self.vault.get(), 'private-test-key')
        self.assertNotIn('private-test-key', json.dumps(self.store.listing()))
        self.assertNotIn(b'private-test-key', self.store.path.read_bytes())

    def test_wrong_unit_rejected_and_existing_key_preserved(self):
        self.vault.set('previous')
        self.store.transport = httpx.MockTransport(lambda r: httpx.Response(200, json={'assets':[{'code':'USD_RLS','quoteUnit':'toman','providerSupported':True}]}))
        with self.assertRaises(SourceError): self.store.setup_key('new-private-key')
        self.assertEqual(self.vault.get(), 'previous')

    def test_vault_failure_does_not_save_plaintext(self):
        self.store.transport = httpx.MockTransport(lambda r: httpx.Response(200, json={'assets':[{'code':'USD_RLS','quoteUnit':'RLS','providerSupported':True}]}))
        with patch.object(self.vault, 'set', side_effect=RuntimeError('secret key text')):
            with self.assertRaisesRegex(SourceError, 'verify'): self.store.setup_key('new-private-key')
        self.assertNotIn(b'new-private-key', self.store.path.read_bytes())

    def test_daily_quota_survives_recreation(self):
        for _ in range(40): self.store.reserve()
        another = LiveSources(self.store.path, self.factors, vault=self.vault)
        with self.assertRaisesRegex(SourceError, 'daily source limit'): another.reserve()

    def test_429_stops_and_cools_down(self):
        self.vault.set('test-key')
        calls = []
        def respond(request):
            calls.append(request)
            return httpx.Response(429, text='secret-provider-body')
        self.store.transport = httpx.MockTransport(respond)
        with self.assertRaisesRegex(SourceError, 'limit'): self.store.refresh('servix')
        self.assertEqual(len(calls), 1)
        self.assertNotIn('secret-provider-body', json.dumps(self.store.listing()))
        self.assertTrue(self.store.state('servix')['cooldown_until'])

    def test_quote_values_units_and_timestamps(self):
        row = {'code':'USD_RLS','quoteUnit':'RLS','value':900000,'businessTime':'2026-10-01T10:00:00+03:30'}
        self.assertEqual(quote(row, '2026-10-03T00:00:00+00:00')['value'], 900000)
        for changes in [{'quoteUnit':'IRT'}, {'value':True}, {'value':-1}, {'value':float('nan')}, {'businessTime':'2026-10-01'}, {'businessTime':'2027-01-01T00:00:00Z'}]:
            with self.assertRaises(SourceError): quote({**row, **changes}, '2026-10-03T00:00:00+00:00')

    def test_history_bootstrap_bounded_then_incremental_and_no_fabricated_months(self):
        self.vault.set('test-key')
        calls = []
        quote_time = datetime.now(timezone.utc).isoformat()
        def respond(request):
            calls.append(request)
            if request.url.path.endswith('/history'):
                start = datetime.fromisoformat(request.url.params['from'])
                end = datetime.fromisoformat(request.url.params['to'])
                self.assertLessEqual((end-start).days, 30)
                return httpx.Response(200, json=[])
            return httpx.Response(200, json={'code':'USD_RLS','quoteUnit':'RLS','value':900000,'businessTime':quote_time})
        self.store.transport = httpx.MockTransport(respond)
        self.store.refresh('servix')
        self.assertLessEqual(len(calls), 26)
        snapshot = self.factors.list()[0]
        self.assertEqual(len(snapshot['points']), 1)
        self.assertEqual(snapshot['frequency'], 'quotes')
        before = len(calls)
        self.store.refresh('servix', force=True)
        self.assertLessEqual(len(calls) - before, 3)

    def test_unknown_source_and_missing_key_blocked(self):
        with self.assertRaises(SourceError): self.store.configure('http://localhost', True)
        with self.assertRaisesRegex(SourceError, 'account'): self.store.configure('servix', True)
        with self.assertRaisesRegex(SourceError, 'account'): self.store.refresh('servix')

    def test_pause_and_schedule_survive_restart_without_refreshing_paused_sources(self):
        self.store.configure('commodities', True)
        restored = LiveSources(self.store.path, self.factors, vault=self.vault)
        with patch.object(restored, 'refresh') as refresh:
            restored.tick()
            refresh.assert_called_once_with('commodities')
        restored.configure('commodities', False)
        with patch.object(restored, 'refresh') as refresh:
            restored.tick()
            refresh.assert_not_called()

    def test_admin_only_mutations(self):
        for role in ['planner', 'viewer', 'reviewer']:
            for method in ['POST', 'PUT', 'PATCH', 'DELETE']:
                self.assertFalse(AccessControl.allowed(None, {'role':role}, method, '/api/live-sources/servix/credential'))
        self.assertTrue(AccessControl.allowed(None, {'role':'admin'}, 'PUT', '/api/live-sources/servix/credential'))

    def test_invalid_credential_never_echoes_key_in_validation_response(self):
        app = FastAPI()
        install_live_sources(app, self.store, Scheduler())
        with TestClient(app) as client:
            for payload in [{'key':'private-key','unexpected':True}, {'key':['private-key']}, {'key':'private-key'+'x'*9000}]:
                response = client.put('/api/live-sources/servix/credential', json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertNotIn('private-key', response.text)

    def test_click_throttle_and_due_refresh(self):
        self.store.transport = self.commodity_transport()
        self.store.refresh('commodities')
        with self.assertRaisesRegex(SourceError, '15 minutes'): self.store.refresh('commodities')
        self.store.configure('commodities', True)
        with patch.object(self.store, 'refresh') as refresh:
            self.store.tick()
            refresh.assert_not_called()

    def test_queued_refresh_coalesces_and_restart_marks_interruption(self):
        self.assertTrue(self.store.queue_refresh('commodities'))
        self.assertFalse(self.store.queue_refresh('commodities'))
        restored = LiveSources(self.store.path, self.factors, vault=self.vault)
        self.assertEqual(restored.state('commodities')['status'], 'failed')
        self.assertIn('interrupted', restored.state('commodities')['error'])

    def test_pause_during_refresh_survives_completion(self):
        self.store.configure('commodities', True)
        def fetch():
            self.store.configure('commodities', False)
            return []
        with patch.object(self.store, 'commodities', side_effect=fetch):
            self.store.refresh('commodities')
        self.assertFalse(self.store.state('commodities')['enabled'])

    def test_background_failure_is_saved_without_raising(self):
        self.store.transport = self.commodity_transport(status=503)
        self.store.queue_refresh('commodities')
        self.store.background_refresh('commodities')
        self.assertEqual(self.store.state('commodities')['status'], 'failed')

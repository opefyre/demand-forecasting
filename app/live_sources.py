"""Opt-in fixed-endpoint feeds, immutable captures and server-only credentials."""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import sys
from threading import RLock
import uuid

import httpx
import pandas as pd
from fastapi import BackgroundTasks, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from .commodity_prices import LANDING, workbook_url, parse_prices
from .hormuz_traffic import (ENDPOINT as HORMUZ_ENDPOINT, DOCS as HORMUZ_DOCS,
    FACTOR_ID as HORMUZ_FACTOR, NAME as HORMUZ_NAME, UNIT as HORMUZ_UNIT,
    LIMITATION as HORMUZ_LIMITATION, parse_traffic, monthly_traffic)
from .iran_cpi import (DOCS as CPI_DOCS, TERMS as IMF_TERMS, FACTOR_ID as CPI_FACTOR,
    NAME as CPI_NAME, UNIT as CPI_UNIT, LIMITATION as CPI_LIMITATION, data_url as cpi_url, parse_cpi)

SOURCES = {
    'supply': {'name': 'Global supply pressure', 'provider': 'New York Fed', 'url': 'https://www.newyorkfed.org/research/policy/gscpi', 'hours': 24,
               'description': 'Monthly shipping and supply-chain pressure worldwide.'},
    'commodities': {'name': 'Energy & materials', 'provider': 'World Bank', 'url': LANDING, 'hours': 24,
                    'description': 'Monthly global prices. Choose the materials relevant to your business.'},
    'inflation': {'name': 'Iran inflation', 'provider': 'World Bank', 'url': 'https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG?locations=IR', 'hours': 168,
                  'description': 'Annual Iranian inflation. Background context, not current monthly inflation.'},
    'industry': {'name': 'Iran industry', 'provider': 'World Bank', 'url': 'https://data.worldbank.org/indicator/NV.IND.TOTL.KD.ZG?locations=IR', 'hours': 168,
                 'description': 'Annual national industry growth. Not factory-level demand.'},
    'servix': {'name': 'Iran exchange rate', 'provider': 'Servix', 'url': 'https://servix.cc/free-api', 'hours': 24, 'key_required': True,
               'description': 'USD quoted in Iranian rials. Verify the quote basis before using it for your business.'},
    'hormuz': {'name': HORMUZ_NAME, 'provider': 'hormuz.now', 'url': HORMUZ_DOCS, 'hours': 6,
               'description': 'Observed ship crossings through the Strait of Hormuz. Relevant only if your customers or supplies use this route.'},
    'iran_cpi': {'name': CPI_NAME, 'provider': 'IMF', 'url': CPI_DOCS, 'hours': 24,
                 'permission_required': True, 'terms_url': IMF_TERMS,
                 'description': 'Official monthly Iranian household price index. Commercial reuse needs IMF permission; not an automatic sales multiplier.'},
}
FACTOR_IDS = {'supply': 'global_supply_pressure', 'inflation': 'iran_inflation', 'industry': 'iran_industry_growth'}


def now():
    return datetime.now(timezone.utc).isoformat()


class SourceError(ValueError):
    """Only deliberately safe messages can leave the provider adapter."""


class KeyVault:
    def __init__(self, workspace):
        self.service = 'DemandLab.live-sources.' + hashlib.sha256(str(workspace.resolve()).encode()).hexdigest()[:16]

    def backend(self):
        # Never silently use a plaintext or third-party fallback backend.
        if sys.platform != 'darwin':
            raise SourceError('Secure source setup currently requires macOS Keychain on this local app.')
        from keyring.backends.macOS import Keyring
        return Keyring()

    def get(self):
        try:
            return self.backend().get_password(self.service, 'servix')
        except Exception:
            raise SourceError('macOS Keychain is unavailable or locked. Unlock it and try again.') from None

    def set(self, key):
        try:
            self.backend().set_password(self.service, 'servix', key)
        except Exception:
            raise SourceError('The key could not be saved in macOS Keychain. No plaintext fallback was used.') from None


def get_bytes(client, url, limit, **kwargs):
    with client.stream('GET', url, **kwargs) as response:
        if response.status_code == 429:
            raise SourceError('The provider request limit was reached. Wait until tomorrow before retrying.')
        if response.status_code in (401, 403):
            raise SourceError('The provider refused access. Check your account and API key.')
        if response.status_code != 200:
            raise SourceError('The provider is unavailable. The last saved data is kept.')
        chunks, size = [], 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > limit:
                raise SourceError('The source response exceeded the expected size.')
            chunks.append(chunk)
    return b''.join(chunks)


def quote(row, captured):
    if not isinstance(row, dict) or row.get('code') != 'USD_RLS' or row.get('quoteUnit') != 'RLS':
        raise SourceError('The exchange-rate symbol or rial unit did not match. No new values were saved.')
    value = row.get('value')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise SourceError('The provider returned an invalid exchange rate.')
    try:
        timestamp = pd.Timestamp(row['businessTime'])
        if timestamp.tzinfo is None or timestamp > pd.Timestamp(captured) + pd.Timedelta(minutes=5):
            raise ValueError()
        timestamp = timestamp.tz_convert('UTC')
    except (KeyError, TypeError, ValueError):
        raise SourceError('The exchange-rate quote time is missing or invalid.') from None
    return {'period': timestamp.date().isoformat(), 'value': float(value), 'quote_time': timestamp.isoformat(), 'available_at': captured}


class LiveSources:
    def __init__(self, path: Path, factors, *, vault=None, transport=None):
        self.path, self.factors = path, factors
        self.vault = vault or KeyVault(path.parent)
        self.transport = transport
        self.lock = RLock()
        self.refresh_locks = {key: RLock() for key in SOURCES}
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, state TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS quotas (day TEXT PRIMARY KEY, calls INTEGER NOT NULL)')
            for key, serialized in db.execute('SELECT id,state FROM sources').fetchall():
                state = json.loads(serialized)
                if state.get('status') in {'queued', 'refreshing'}:
                    state.update(status='failed', error='The last refresh was interrupted. Automatic refresh will retry.')
                    db.execute('UPDATE sources SET state=? WHERE id=?', (json.dumps(state), key))

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.path, timeout=20)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def state(self, key):
        if key not in SOURCES:
            raise SourceError('Choose a supported live source.')
        with self.db() as db:
            row = db.execute('SELECT state FROM sources WHERE id=?', (key,)).fetchone()
        return json.loads(row[0]) if row else {'enabled': False, 'status': 'not_connected'}

    def write(self, key, state):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO sources VALUES (?,?)', (key, json.dumps(state, allow_nan=False)))

    def listing(self):
        snapshots = self.factors.list()
        result = []
        for key, definition in SOURCES.items():
            state = self.state(key)
            matches = [r for r in snapshots if r.get('live_source') == key or r.get('factor_id') == FACTOR_IDS.get(key)]
            latest = {}
            for row in matches:
                latest.setdefault(row['factor_id'], row)
            series = []
            for row in latest.values():
                points = row.get('points', [])
                series.append({k: row.get(k) for k in ('id', 'factor_id', 'name', 'unit', 'geography', 'frequency', 'captured_at', 'use', 'limitation')}
                              | {'first_period': points[0]['period'] if points else None,
                                 'latest_period': points[-1]['period'] if points else None, 'count': len(points)})
                latest_time = row.get('latest_quote_time') or (points[-1]['period'] if points else None)
                max_age = {'quotes': pd.Timedelta(hours=1), 'daily': pd.Timedelta(days=3), 'monthly': pd.Timedelta(days=75), 'annual': pd.Timedelta(days=730)}.get(row.get('frequency'))
                stamp = pd.Timestamp(latest_time) if latest_time else None
                if stamp is not None and stamp.tzinfo is None:
                    stamp = stamp.tz_localize('UTC')
                series[-1]['data_behind'] = bool(stamp is not None and max_age is not None and stamp + max_age < pd.Timestamp(now()))
                if key == 'hormuz' and row.get('provider_updated_at'):
                    series[-1]['data_behind'] |= pd.Timestamp(now()) - pd.Timestamp(row['provider_updated_at']) > pd.Timedelta(hours=12)
            last = state.get('last_success')
            due = bool(state.get('enabled') and (not last or
                       pd.Timestamp(last) + pd.Timedelta(hours=definition['hours'] * 2) < pd.Timestamp(now())))
            result.append({'id': key, **definition, **state, 'refresh_overdue': due, 'data_behind': any(s['data_behind'] for s in series), 'series': series})
        return {'sources': result, 'automatic_refresh': 'While this local app is running. Refresh resumes on restart.'}

    def reserve(self):
        # Conservatively reserve 40 of the documented free 50/day. Other apps can
        # still exhaust the shared provider quota, in which case we stop on 429.
        day = datetime.now(timezone.utc).date().isoformat()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT calls FROM quotas WHERE day=?', (day,)).fetchone()
            count = row[0] if row else 0
            if count >= 40:
                raise SourceError('This app’s daily source limit was reached. Retry tomorrow.')
            db.execute('INSERT OR REPLACE INTO quotas VALUES (?,?)', (day, count + 1))

    def servix_json(self, client, path, key, **params):
        self.reserve()
        raw = get_bytes(client, 'https://servix.cc/api/v1/assets/' + path, 2_000_000,
                        headers={'X-API-Key': key}, params=params)
        return json.loads(raw)

    def validate_key(self, key):
        if not key or len(key) > 2048 or any(c.isspace() for c in key):
            raise SourceError('Paste a valid Servix API key without spaces.')
        with httpx.Client(timeout=25, follow_redirects=False, trust_env=False, transport=self.transport) as client:
            payload = self.servix_json(client, 'supported', key)
        asset = next((r for r in payload.get('assets', []) if r.get('code') == 'USD_RLS'), None)
        if not asset or asset.get('quoteUnit') != 'RLS' or not asset.get('providerSupported'):
            raise SourceError('This account does not offer the required USD/rial series.')
        return asset

    def setup_key(self, key):
        with self.lock:
            try:
                asset = self.validate_key(key)
                self.vault.set(key)
            except SourceError:
                raise
            except Exception:
                raise SourceError('Could not verify this key. Check your account and try again.') from None
            state = self.state('servix')
            state.update(credential_configured=True, status='ready', error=None,
                         quote_basis='Servix USD_RLS reference quote; local settlement basis unverified',
                         providers=asset.get('providers', []), verified_at=now())
            self.write('servix', state)
            return {'saved': True, 'storage': 'macOS Keychain', 'key_returned': False}

    def configure(self, key, enabled):
        with self.lock:
            state = self.state(key)
            if key == 'servix' and enabled and not state.get('credential_configured'):
                raise SourceError('Connect your Servix account first.')
            if key == 'iran_cpi' and enabled and not state.get('permission_confirmed'):
                raise SourceError('Record permission covering automated commercial IMF data use before connecting.')
            state.update(enabled=enabled)
            self.write(key, state)
            return state

    def permission(self, key, confirmed, reference):
        if key != 'iran_cpi':
            raise SourceError('This source does not use the IMF permission workflow.')
        if confirmed and (not isinstance(reference, str) or not 8 <= len(reference.strip()) <= 300):
            raise SourceError('Enter a permission reference (8–300 characters), not an API key.')
        with self.lock:
            state = self.state(key)
            state.update(permission_confirmed=confirmed, permission_reference=reference.strip() if confirmed else None,
                         permission_recorded_at=now(), permission_basis='Admin declaration; not independently verified')
            if not confirmed:
                state['enabled'] = False
            self.write(key, state)
            return state

    def save(self, key, definitions, raw, suffix, data_url):
        captured = now()
        raw_id = uuid.uuid4().hex
        raw_dir = self.factors.root / 'raw'
        raw_dir.mkdir(exist_ok=True)
        raw_name = f'raw/{raw_id}.{suffix}'
        (self.factors.root / raw_name).write_bytes(raw)
        snapshots = []
        for factor_id, definition in definitions.items():
            row = {**definition, 'id': uuid.uuid4().hex, 'factor_id': factor_id,
                   'live_source': key, 'kind': 'public_observations', 'classification': 'real',
                   'captured_at': captured, 'sha256': hashlib.sha256(raw).hexdigest(),
                   'raw_response': raw_name, 'data_url': data_url,
                   'availability_basis': 'first_local_capture_not_original_release', 'use': 'context_only',
                   'limitation': definition.get('limitation', 'Original historical publication times are not verified. No automatic forecast changes or past-test joins.')}
            with self.factors.lock:
                target = self.factors.root / f"{row['id']}.json"
                temp = target.with_suffix('.tmp')
                temp.write_text(json.dumps(row, ensure_ascii=False, allow_nan=False))
                temp.replace(target)
            snapshots.append(row)
        return snapshots

    def commodities(self):
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False, transport=self.transport) as client:
            html = get_bytes(client, LANDING, 4_000_000).decode('utf-8')
            url = workbook_url(html)
            content = get_bytes(client, url, 5_000_000)
        captured = now()
        parsed = parse_prices(content, captured)
        definitions = {'worldbank_' + key: {**row, 'provider': 'World Bank', 'source_url': LANDING,
                       'license': 'CC BY 4.0; check dataset-specific third-party terms',
                       'frequency': 'monthly', 'geography': 'Global reference market'} for key, row in parsed.items()}
        return self.save('commodities', definitions, content, 'xlsx', url)

    def shipping(self):
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False, transport=self.transport) as client:
            content = get_bytes(client, HORMUZ_ENDPOINT, 2_000_000)
        captured = now()
        try:
            points, retained, updated = parse_traffic(content, captured)
        except ValueError as exc:
            raise SourceError(str(exc)) from None
        monthly, quality = monthly_traffic(points)
        projection = json.dumps(retained, ensure_ascii=False, allow_nan=False).encode()
        return self.save('hormuz', {HORMUZ_FACTOR: {
            'name': HORMUZ_NAME, 'provider': 'hormuz.now', 'unit': HORMUZ_UNIT,
            'source_url': HORMUZ_DOCS, 'license': 'CC BY 4.0 — provider-owned counts only',
            'license_url': HORMUZ_DOCS, 'attribution': 'Source: hormuz.now (CC BY 4.0), https://hormuz.now',
            'frequency': 'daily', 'calendar': 'gregorian', 'time_standard': 'UTC',
            'geography': 'Strait of Hormuz · regional shipping route, not Tehran site demand',
            'points': points, 'provider_updated_at': updated, 'monthly': monthly,
            'monthly_quality': quality, 'limitation': HORMUZ_LIMITATION,
            'upstream_response_sha256': hashlib.sha256(content).hexdigest(),
            'retention_basis': 'Exact selected provider-owned fields; bundled IMF fields discarded',
        }}, projection, 'json', HORMUZ_ENDPOINT)

    def monthly_inflation(self):
        if not self.state('iran_cpi').get('permission_confirmed'):
            raise SourceError('IMF commercial-use permission has not been recorded. No request was sent.')
        url = cpi_url(datetime.now(timezone.utc).date())
        with httpx.Client(timeout=30, follow_redirects=False, trust_env=False, transport=self.transport) as client:
            content = get_bytes(client, url, 2_000_000,
                                headers={'Accept': 'application/vnd.sdmx.data+csv;version=1.0.0'})
        captured = now()
        try:
            points = parse_cpi(content, captured)
        except ValueError as exc:
            raise SourceError(str(exc)) from None
        # Permission could be revoked while the source request is in flight.
        if not self.state('iran_cpi').get('permission_confirmed'):
            raise SourceError('IMF permission was withdrawn. No new snapshot was saved.')
        return self.save('iran_cpi', {CPI_FACTOR: {
            'name': CPI_NAME, 'provider': 'IMF', 'unit': CPI_UNIT, 'frequency': 'monthly',
            'geography': 'Iran · national households, not Tehran-only', 'calendar': 'gregorian',
            'source_url': CPI_DOCS, 'license_url': IMF_TERMS,
            'license': 'IMF terms; commercial-use permission declared by workspace admin',
            'attribution': f'Source: International Monetary Fund, Consumer Price Index, {CPI_DOCS}',
            'normalization': {'measure': 'cpi_index', 'base_year': '2021', 'multiplier': 1},
            'permission_recorded_at': self.state('iran_cpi')['permission_recorded_at'],
            'limitation': CPI_LIMITATION, 'points': points,
        }}, content, 'csv', url)

    def exchange(self):
        key = self.vault.get()
        if not key:
            raise SourceError('Connect your Servix account first.')
        captured = now()
        previous = next((r for r in self.factors.list() if r.get('live_source') == 'servix'), None)
        # Initial bootstrap is bounded to 24 months; subsequent captures fetch the
        # last seven days. Month completeness/history depth is never assumed.
        end = datetime.now(timezone.utc).date()
        start = (pd.Timestamp(previous['latest_quote_time']).date() - timedelta(days=7)) if previous else end - timedelta(days=730)
        start = max(start, end - timedelta(days=730))
        points = {p['quote_time']: p for p in previous.get('points', [])} if previous else {}
        raw_rows = []
        with httpx.Client(timeout=25, follow_redirects=False, trust_env=False, transport=self.transport) as client:
            current = quote(self.servix_json(client, 'USD_RLS', key), captured)
            raw_rows.append(current)
            points[current['quote_time']] = current
            while start <= end:
                until = min(start + timedelta(days=30), end)
                payload = self.servix_json(client, 'USD_RLS/history', key, **{'from': str(start), 'to': str(until)})
                if not isinstance(payload, list) or len(payload) > 20_000:
                    raise SourceError('The exchange-rate history format changed.')
                for row in payload:
                    point = quote(row, captured)
                    # Provider dates are Gregorian, quote days use Asia/Tehran.
                    local_day = pd.Timestamp(point['quote_time']).tz_convert('Asia/Tehran').date()
                    if not start <= local_day <= until:
                        raise SourceError('The provider returned a quote outside the requested date range.')
                    old = points.get(point['quote_time'])
                    if old and old['value'] == point['value']:
                        point['available_at'] = old['available_at']
                    points[point['quote_time']] = point
                    raw_rows.append(point)
                start = until + timedelta(days=1)
        ordered = sorted(points.values(), key=lambda p: p['quote_time'])
        raw = json.dumps({'returned_quotes': raw_rows, 'retained_quotes': ordered}, allow_nan=False).encode()
        return self.save('servix', {'servix_usd_rls': {
            'name': 'USD / Iranian rial', 'provider': 'Servix', 'unit': 'IRR per USD',
            'source_url': 'https://servix.cc/docs/current-prices', 'frequency': 'quotes',
            'geography': 'Iran · provider reference quote', 'points': ordered,
            'quote_basis': 'Servix USD_RLS; official/open-market/settlement basis unverified',
            'latest_quote_time': current['quote_time'], 'calendar': 'gregorian',
            'normalization': {'original_unit': 'RLS', 'canonical_unit': 'IRR', 'multiplier': 1},
        }}, raw, 'json', 'https://servix.cc/api/v1/assets/USD_RLS/history')

    def refresh(self, key, *, force=False):
        if key not in SOURCES:
            raise SourceError('Choose a supported live source.')
        with self.refresh_locks[key]:
            state = self.state(key)
            if key == 'iran_cpi' and not state.get('permission_confirmed'):
                raise SourceError('Record IMF commercial-use permission before fetching. No request was sent.')
            if state.get('cooldown_until') and pd.Timestamp(state['cooldown_until']) > pd.Timestamp(now()):
                raise SourceError(self.cooldown_message(state))
            # Repeated clicks cannot burn the account quota or hammer public APIs.
            if state.get('last_attempt') and pd.Timestamp(state['last_attempt']) + pd.Timedelta(minutes=15) > pd.Timestamp(now()):
                if not force:
                    raise SourceError('This source was just checked. Please wait 15 minutes before refreshing again.')
            state.update(last_attempt=now(), status='refreshing')
            self.write(key, state)
            try:
                if key in FACTOR_IDS:
                    rows = [self.factors.refresh(FACTOR_IDS[key], transport=self.transport)]
                elif key == 'commodities':
                    rows = self.commodities()
                elif key == 'hormuz':
                    rows = self.shipping()
                elif key == 'iran_cpi':
                    rows = self.monthly_inflation()
                elif key == 'servix':
                    rows = self.exchange()
                else:
                    raise SourceError('This live source has no configured adapter.')
                state = self.state(key)  # Retain pause/resume changes made during fetch.
                state.update(status='healthy', last_success=now(), error=None, cooldown_until=None,
                             snapshot_ids=[r['id'] for r in rows])
            except Exception as exc:
                message = str(exc) if isinstance(exc, SourceError) else 'Could not refresh this source. The last saved data is kept.'
                tomorrow = datetime.combine(datetime.now(timezone.utc).date() + timedelta(days=1), datetime.min.time(), timezone.utc)
                cooldown = tomorrow.isoformat() if 'limit' in message else (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
                state = self.state(key)
                state.update(status='failed', error=message, cooldown_until=cooldown)
                self.write(key, state)
                raise SourceError(message) from None
            self.write(key, state)
            return state

    def queue_refresh(self, key):
        with self.lock:
            state = self.state(key)
            if key == 'iran_cpi' and not state.get('permission_confirmed'):
                raise SourceError('Record IMF commercial-use permission before fetching. No request was sent.')
            if state.get('status') in {'queued', 'refreshing'}:
                return False
            if state.get('cooldown_until') and pd.Timestamp(state['cooldown_until']) > pd.Timestamp(now()):
                raise SourceError(self.cooldown_message(state))
            if state.get('last_attempt') and pd.Timestamp(state['last_attempt']) + pd.Timedelta(minutes=15) > pd.Timestamp(now()):
                raise SourceError('This source was just checked. Please wait 15 minutes before refreshing again.')
            state.update(status='queued', error=None)
            self.write(key, state)
            return True

    @staticmethod
    def cooldown_message(state):
        return (f'Refresh is paused until {state["cooldown_until"]}. '
                f'Last check: {state.get("error") or "source unavailable"} '
                'Saved data is unchanged.')

    def background_refresh(self, key):
        try:
            self.refresh(key)
        except SourceError:
            pass  # Failure is saved, not exposed in background exception logs.

    def tick(self):
        for key, definition in SOURCES.items():
            state = self.state(key)
            last = state.get('last_success')
            if state.get('enabled') and (not last or pd.Timestamp(last) + pd.Timedelta(hours=definition['hours']) <= pd.Timestamp(now())):
                try:
                    self.refresh(key)
                except SourceError:
                    pass  # Visible saved error; preserve last good capture.


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    enabled: bool


class SourcePermission(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    confirmed: bool
    reference: str = ''


def install_live_sources(app, store, scheduler):
    @app.on_event('startup')
    def schedules():
        scheduler.add_job(store.tick, 'interval', minutes=15, id='live-sources', replace_existing=True,
                          max_instances=1, coalesce=True, next_run_time=datetime.now(timezone.utc))

    @app.get('/api/live-sources')
    def listing():
        return store.listing()

    @app.put('/api/live-sources/servix/credential')
    async def credential(request: Request):
        # Key entry is local-only or authenticated HTTPS. The regular access layer
        # restricts all live-source mutations to admins and checks request origin.
        local = request.client and request.client.host in {'127.0.0.1', '::1', 'testclient'}
        if not local and request.url.scheme != 'https':
            raise HTTPException(400, 'Use the local app or HTTPS to save a private key.')
        try:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 8192:
                    raise SourceError('The credential request is too large.')
            try:
                payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                raise SourceError('Provide a valid private key request.') from None
            if not isinstance(payload, dict) or set(payload) != {'key'} or not isinstance(payload['key'], str):
                raise SourceError('Provide one private API key.')
            return await run_in_threadpool(store.setup_key, payload['key'])
        except SourceError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.put('/api/live-sources/{key}')
    def configure(key: str, payload: SourceConfig):
        try:
            return store.configure(key, payload.enabled)
        except SourceError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.put('/api/live-sources/{key}/permission')
    def permission(key: str, payload: SourcePermission):
        try:
            return store.permission(key, payload.confirmed, payload.reference)
        except SourceError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.post('/api/live-sources/{key}/refresh')
    def refresh(key: str, background: BackgroundTasks):
        try:
            if store.queue_refresh(key):
                background.add_task(store.background_refresh, key)
            return store.state(key)
        except SourceError as exc:
            raise HTTPException(400, str(exc)) from None

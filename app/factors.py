"""Public factor snapshots with conservative availability-time provenance.

The catalog describes sources, never fabricated measurements. Newly downloaded
revised history is context, not point-in-time backtest data.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import RLock
import uuid

import httpx
import numpy as np
import pandas as pd
from app.supply_pressure import DATA_URL, DEFINITION, parse_supply_pressure


CATALOG = {
    DEFINITION['id']: DEFINITION,
    'iran_inflation': {
        'id': 'iran_inflation', 'name': 'Iran inflation', 'provider': 'World Bank',
        'indicator': 'FP.CPI.TOTL.ZG', 'country': 'IRN', 'geography': 'Iran · national',
        'frequency': 'annual', 'unit': '% annual change',
        'source_url': 'https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG?locations=IR',
        'license': 'CC BY 4.0',
        'description': 'Annual consumer-price inflation. Not a monthly price feed or a future inflation forecast.',
    },
    'iran_industry_growth': {
        'id': 'iran_industry_growth', 'name': 'Iran industry growth', 'provider': 'World Bank',
        'indicator': 'NV.IND.TOTL.KD.ZG', 'country': 'IRN', 'geography': 'Iran · national',
        'frequency': 'annual', 'unit': '% annual change',
        'source_url': 'https://data.worldbank.org/indicator/NV.IND.TOTL.KD.ZG?locations=IR',
        'description': 'Annual industry value-added growth, including construction. Context, not a factory-level demand measure.',
    },
}


class FactorStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def list(self) -> list[dict]:
        with self.lock:
            return sorted([json.loads(path.read_text()) for path in self.root.glob('*.json')], key=lambda row: row['captured_at'], reverse=True)

    def get(self, identifier: str) -> dict:
        if len(identifier) != 32 or any(char not in '0123456789abcdef' for char in identifier):
            raise ValueError('Invalid factor snapshot.')
        path = self.root / f'{identifier}.json'
        if not path.exists():
            raise ValueError('Factor snapshot was not found.')
        return json.loads(path.read_text())

    def refresh(self, factor_id: str, *, transport=None) -> dict:
        if factor_id not in CATALOG:
            raise ValueError('Choose a supported public data source.')
        definition = CATALOG[factor_id]
        if factor_id == DEFINITION['id']:
            return self._refresh_supply_pressure(transport=transport)
        # Fixed public endpoints: no client file, item, revenue or site location
        # is included in a request, and no credentials are needed.
        url = f"https://api.worldbank.org/v2/country/{definition['country']}/indicator/{definition['indicator']}"
        with httpx.Client(timeout=30, transport=transport, follow_redirects=False, trust_env=False) as client:
            # Only completed years: far-future ranges are needlessly expensive for
            # the upstream API, and incomplete annual values aren't monthly data.
            # The upstream gateway rejects the percent-encoded range separator
            # on some routes. All query values here are fixed or server-generated.
            query = f'?format=json&per_page=100&date=1990:{datetime.now(timezone.utc).year - 1}'
            with client.stream('GET', url + query) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError('The public response exceeded the expected size.')
                    chunks.append(chunk)
            content = b''.join(chunks)
            payload = json.loads(content)
        if not isinstance(payload, list) or len(payload) != 2 or not isinstance(payload[1], list):
            raise ValueError('The source did not return an indicator series. No snapshot was saved.')
        captured = datetime.now(timezone.utc).isoformat()
        points = []
        for row in payload[1]:
            if row.get('value') is None:
                continue
            if row.get('countryiso3code') != definition['country'] or row.get('indicator', {}).get('id') != definition['indicator']:
                raise ValueError('The response country or indicator did not match the requested source.')
            year = int(row['date'])
            value = float(row['value'])
            if not 1990 <= year <= datetime.now(timezone.utc).year or not np.isfinite(value):
                raise ValueError('The source returned an invalid year or value.')
            points.append({'period': f'{year}-12-31', 'value': value, 'available_at': captured})
        if not points or len({row['period'] for row in points}) != len(points):
            raise ValueError('The source returned no observations or duplicate years.')
        identifier = uuid.uuid4().hex
        snapshot = {**definition, 'id': identifier, 'factor_id': factor_id, 'captured_at': captured,
                    'sha256': hashlib.sha256(content).hexdigest(),
                    'raw_response': f'raw/{identifier}.json',
                    'provider_updated_at': payload[0].get('lastupdated'),
                    'points': sorted(points, key=lambda row: row['period']),
                    'availability_basis': 'first_local_capture_not_original_release',
                    'use': 'context_only',
                    'limitation': 'This is revised historical data downloaded now. Original publication dates are not supplied. It is not silently joined to earlier backtests or forecasts.'}
        with self.lock:
            raw_dir = self.root / 'raw'
            raw_dir.mkdir(exist_ok=True)
            (raw_dir / f'{identifier}.json').write_bytes(content)
            target = self.root / f"{snapshot['id']}.json"
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(target)
        return snapshot

    def _refresh_supply_pressure(self, *, transport=None) -> dict:
        # Fixed public URL, bounded streaming, no customer data or credentials.
        with httpx.Client(timeout=20, transport=transport, follow_redirects=False, trust_env=False) as client:
            with client.stream('GET', DATA_URL) as response:
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 2_000_000:
                        raise ValueError('The public response exceeded the expected size.')
                    chunks.append(chunk)
        content = b''.join(chunks)
        captured = datetime.now(timezone.utc).isoformat()
        parsed = parse_supply_pressure(content, captured)
        identifier = uuid.uuid4().hex
        snapshot = {**DEFINITION, **parsed, 'id': identifier,
                    'kind': 'public_observations', 'classification': 'real',
                    'factor_id': DEFINITION['id'], 'captured_at': captured,
                    'sha256': hashlib.sha256(content).hexdigest(),
                    'raw_response': f'raw/{identifier}.csv', 'data_url': DATA_URL,
                    'availability_basis': 'first_local_capture_not_original_release',
                    'use': 'context_only',
                    'limitation': 'Vintage month labels are retained, but exact historical publication dates are not verified. This download does not automatically enter forecasts or earlier backtests.'}
        with self.lock:
            raw = self.root / 'raw'
            raw.mkdir(exist_ok=True)
            raw_file = raw / f'{identifier}.csv'
            with raw_file.open('xb') as handle:
                handle.write(content)
            temporary = self.root / f'{identifier}.tmp'
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(self.root / f'{identifier}.json')
        return snapshot


def observations_available_at(snapshot: dict, cutoff: str) -> pd.DataFrame:
    """A point-in-time gate; a recent download must not leak into old backtests."""
    frame = pd.DataFrame(snapshot.get('points', []))
    if frame.empty:
        return frame
    as_of = pd.Timestamp(cutoff)
    as_of = as_of.tz_localize('UTC') if as_of.tzinfo is None else as_of.tz_convert('UTC')
    mask = pd.to_datetime(frame.available_at, utc=True).le(as_of) & pd.to_datetime(frame.period, utc=True).le(as_of)
    # A revision replaces the earlier value only after its own release date.
    eligible = frame.loc[mask].copy()
    eligible['_release'] = pd.to_datetime(eligible.available_at, utc=True)
    return (eligible.sort_values('_release').drop_duplicates('period', keep='last')
            .sort_values('period').drop(columns='_release'))

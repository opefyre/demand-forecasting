"""Versioned NASA POWER context. Never substitute reanalysis for future weather."""
from __future__ import annotations

import calendar
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
from threading import RLock
import uuid

import httpx

ENDPOINT = 'https://power.larc.nasa.gov/api/temporal/daily/point'
DOCS = 'https://power.larc.nasa.gov/docs/services/api/temporal/daily/'
PARAMETERS = {'T2M': ('Temperature at 2 metres', 'C'), 'PRECTOTCORR': ('Daily precipitation', 'mm/day')}


def request_definition(payload, today=None):
    today = today or datetime.now(timezone.utc).date()
    if payload.get('share_coordinates') is not True:
        raise ValueError('Confirm that these coordinates may be sent to NASA POWER.')
    location = payload.get('location_name', '')
    if not isinstance(location, str) or not 3 <= len(location.strip()) <= 120:
        raise ValueError('Enter a location name (3–120 characters).')
    coords = {}
    for key, limit in [('latitude', 90), ('longitude', 180)]:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -limit <= value <= limit:
            raise ValueError(f'Enter a valid {key} between {-limit} and {limit}.')
        coords[key] = float(value)
    try:
        start, end = (date.fromisoformat(payload[key]) for key in ('start', 'end'))
    except (TypeError, ValueError, KeyError):
        raise ValueError('Enter the first and last historical dates.')
    if start < date(1981, 1, 1) or end >= today or start > end or (end-start).days > 3660:
        raise ValueError('Choose up to 10 years from 1981 through yesterday. This source does not supply future weather.')
    return {**coords, 'location_name': location.strip(), 'start': start.isoformat(), 'end': end.isoformat(),
            'time_standard': 'UTC', 'coordinate_permission': 'explicit_request_confirmation'}


def normalize_response(payload, definition, captured):
    try:
        header = payload['header']
        coordinates = payload['geometry']['coordinates']
        if payload['geometry']['type'] != 'Point' or any(
            not math.isfinite(float(actual)) or abs(float(actual)-definition[key]) > 0.0001
            for actual, key in zip(coordinates[:2], ('longitude', 'latitude'))
        ) or len(coordinates) < 2:
            raise ValueError('The response location does not match the requested coordinates.')
        if header['time_standard'] != 'UTC':
            raise ValueError('The provider returned a different daily time standard.')
        values = payload['properties']['parameter']
        start, end = date.fromisoformat(definition['start']), date.fromisoformat(definition['end'])
        expected = [start + timedelta(days=n) for n in range((end-start).days+1)]
        allowed = {d.strftime('%Y%m%d') for d in expected}
        fill = float(header['fill_value'])
        if isinstance(header['fill_value'], bool) or fill != -999:
            raise ValueError('The provider returned an invalid missing-value marker.')
        for key, (_, unit) in PARAMETERS.items():
            if payload['parameters'][key]['units'] != unit:
                raise ValueError('The provider changed the weather units. No values were converted silently.')
            if not isinstance(values[key], dict) or not set(values[key]).issubset(allowed):
                raise ValueError('Weather observations contain dates outside the requested period.')
        points = []
        for day in expected:
            point = {'period': day.isoformat(), 'available_at': captured}
            for key in PARAMETERS:
                raw = values[key].get(day.strftime('%Y%m%d'))
                if raw is None or raw == fill:
                    point[key] = None
                else:
                    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
                        raise ValueError('The provider returned a non-numeric or non-finite weather reading.')
                    if key == 'PRECTOTCORR' and raw < 0:
                        raise ValueError('The provider returned negative precipitation.')
                    point[key] = float(raw)
            points.append(point)
        if not any(p[key] is not None for p in points for key in PARAMETERS):
            raise ValueError('No weather readings are available for these dates. No snapshot was saved.')
        quality = {key: {'valid_days': sum(p[key] is not None for p in points),
                         'missing_days': sum(p[key] is None for p in points),
                         'latest_reading': next((p['period'] for p in reversed(points) if p[key] is not None), None)} for key in PARAMETERS}
        return points, quality
    except (KeyError, TypeError, IndexError) as exc:
        raise ValueError('The provider response schema changed. No snapshot was saved.') from exc


def monthly_weather(points):
    """No partial-month means/totals disguised as complete monthly features."""
    months = {}
    for point in points:
        months.setdefault(point['period'][:7], []).append(point)
    output = []
    for month, rows in sorted(months.items()):
        year, number = map(int, month.split('-'))
        days = calendar.monthrange(year, number)[1]
        row = {'period': month+'-01', 'expected_days': days}
        for key in PARAMETERS:
            valid = [p[key] for p in rows if p[key] is not None]
            row[key+'_valid_days'] = len(valid)
            row[key] = (math.fsum(valid)/days if key == 'T2M' else math.fsum(valid)) if len(valid) == days else None
        output.append(row)
    return output


class WeatherStore:
    def __init__(self, root: Path):
        self.root = root
        self.snapshots = root / 'snapshots'
        self.responses = root / 'responses'
        self.snapshots.mkdir(parents=True, exist_ok=True)
        self.responses.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def list(self):
        return sorted([json.loads(p.read_text()) for p in self.snapshots.glob('*.json')], key=lambda x: x['captured_at'], reverse=True)

    def get(self, identifier):
        if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
            raise ValueError('Invalid weather snapshot.')
        path = self.snapshots / f'{identifier}.json'
        if not path.exists():
            raise ValueError('Weather snapshot was not found.')
        snapshot = json.loads(path.read_text())
        raw_path = self.responses / f'{identifier}.json'
        if not raw_path.exists() or hashlib.sha256(raw_path.read_bytes()).hexdigest() != snapshot['sha256']:
            raise ValueError('The saved weather source changed. Re-fetch before using it.')
        return snapshot

    def refresh(self, payload, *, transport=None, now=None):
        fixed_clock = now is not None
        now = now or datetime.now(timezone.utc)
        definition = request_definition(payload, now.date())
        request_hash = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
        # Avoid repeated provider calls for the same location/date range in one day.
        # Serializes local requests only; distributed deployments need a shared lock.
        with self.lock:
            for old in self.list():
                if old['request_hash'] == request_hash and timedelta(0) <= now-datetime.fromisoformat(old['captured_at']) < timedelta(hours=24):
                    return {**self.get(old['id']), 'cache_reused': True}
            params = {'parameters': ','.join(PARAMETERS), 'community': 'AG', 'format': 'JSON', 'time-standard': 'UTC',
                      'latitude': definition['latitude'], 'longitude': definition['longitude'],
                      'start': definition['start'].replace('-', ''), 'end': definition['end'].replace('-', '')}
            with httpx.Client(timeout=30, transport=transport or httpx.HTTPTransport(retries=2), follow_redirects=False) as client:
                with client.stream('GET', ENDPOINT, params=params) as response:
                    response.raise_for_status()
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 4_000_000:
                            raise ValueError('The weather response exceeded the allowed size.')
                        chunks.append(chunk)
            content = b''.join(chunks)
            def unique_keys(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('The weather response contains duplicate keys or dates.')
                    result[key] = value
                return result
            try:
                response_data = json.loads(content, object_pairs_hook=unique_keys)
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise ValueError('The weather source did not return readable data.')
            captured = (now if fixed_clock else datetime.now(timezone.utc)).isoformat()
            points, quality = normalize_response(response_data, definition, captured)
            identifier = uuid.uuid4().hex
            snapshot = {'id': identifier, 'provider': 'NASA POWER', 'source_url': DOCS,
                'request': definition, 'request_hash': request_hash, 'captured_at': captured,
                'sha256': hashlib.sha256(content).hexdigest(), 'source_header': response_data['header'],
                'parameters': response_data['parameters'], 'points': points, 'quality': quality,
                'monthly': monthly_weather(points), 'use': 'context_only',
                'availability_basis': 'first_local_capture_not_original_release',
                'limitation': 'Gridded historical estimates, not a plant sensor or future forecast. UTC days are not Tehran local days. Revised history is not automatically joined to backtests.',
                'attribution': 'NASA POWER Project, NASA Langley Research Center',
                'license_url': 'https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy'}
            # Keep the exact source response for reproducibility before publication.
            (self.responses / f'{identifier}.json').write_bytes(content)
            target = self.snapshots / f'{identifier}.json'
            temporary = target.with_suffix('.tmp')
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temporary.replace(target)
            return {**snapshot, 'cache_reused': False}


def weather_csv(snapshot):
    buffer = io.StringIO()
    columns = ['period', 'temperature_c', 'precipitation_mm_per_day', 'available_at', 'time_standard', 'latitude', 'longitude', 'snapshot_id', 'source_sha256', 'use']
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for point in snapshot['points']:
        writer.writerow({'period': point['period'], 'temperature_c': point['T2M'], 'precipitation_mm_per_day': point['PRECTOTCORR'],
            'available_at': point['available_at'], 'time_standard': 'UTC', 'latitude': snapshot['request']['latitude'],
            'longitude': snapshot['request']['longitude'], 'snapshot_id': snapshot['id'], 'source_sha256': snapshot['sha256'], 'use': 'context_only'})
    return buffer.getvalue()

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.weather import WeatherStore, request_definition, normalize_response, monthly_weather, weather_csv
from app.factors import observations_available_at

NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)
REQUEST = {'location_name': 'Public documentation example; not a client site', 'latitude': 0, 'longitude': 0,
           'start': '2025-01-01', 'end': '2025-01-03', 'share_coordinates': True}


def response():
    return {'geometry': {'type': 'Point', 'coordinates': [0, 0, 0]},
            'header': {'time_standard': 'UTC', 'fill_value': -999, 'sources': ['MERRA2']},
            'parameters': {'T2M': {'units': 'C'}, 'PRECTOTCORR': {'units': 'mm/day'}},
            'properties': {'parameter': {'T2M': {'20250101': 27.53, '20250102': 27.81, '20250103': 27.79},
                                         'PRECTOTCORR': {'20250101': 0.58, '20250102': 4.75, '20250103': 0.53}}}}


class WeatherTests(unittest.TestCase):
    def transport(self, payload=None, calls=None):
        def handle(request):
            if calls is not None: calls.append(request)
            return httpx.Response(200, json=payload if payload is not None else response())
        return httpx.MockTransport(handle)

    def test_validated_request_and_explicit_coordinate_permission(self):
        self.assertEqual(request_definition(REQUEST, NOW.date())['latitude'], 0)
        for changes in ({'share_coordinates': False}, {'latitude': None}, {'latitude': True}, {'latitude': 91},
                        {'longitude': float('nan')}, {'longitude': '0'}, {'location_name': ''},
                        {'start': '1980-01-01'}, {'end': '2026-09-21'}, {'end': 'bad'},
                        {'start': '2025-02-01'}, {'start': '2000-01-01'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                request_definition({**REQUEST, **changes}, NOW.date())

    def test_saved_source_restarts_export_and_request_privacy(self):
        with TemporaryDirectory() as folder:
            calls = []; store = WeatherStore(Path(folder))
            snapshot = store.refresh(REQUEST, transport=self.transport(calls=calls), now=NOW)
            saved = WeatherStore(Path(folder)).get(snapshot['id'])
            self.assertEqual(saved['points'][0]['T2M'], 27.53)
            self.assertEqual(saved['quality']['PRECTOTCORR']['valid_days'], 3)
            self.assertIsNone(saved['monthly'][0]['T2M'])
            self.assertEqual(saved['availability_basis'], 'first_local_capture_not_original_release')
            self.assertEqual(saved['points'][0]['available_at'], NOW.isoformat())
            self.assertTrue(observations_available_at(saved, '2025-02-01').empty)
            self.assertEqual(set(calls[0].url.params), {'parameters', 'community', 'format', 'time-standard', 'latitude', 'longitude', 'start', 'end'})
            self.assertNotIn('location_name', str(calls[0].url))
            rows = list(csv.DictReader(io.StringIO(weather_csv(saved))))
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]['temperature_c'], '27.53')
            self.assertEqual(rows[0]['source_sha256'], saved['sha256'])
            self.assertEqual(rows[0]['use'], 'context_only')

    def test_cache_avoids_repeat_calls_but_retains_later_vintages(self):
        with TemporaryDirectory() as folder:
            calls = []; store = WeatherStore(Path(folder))
            first = store.refresh(REQUEST, transport=self.transport(calls=calls), now=NOW)
            second = store.refresh(REQUEST, transport=self.transport(calls=calls), now=NOW+timedelta(hours=2))
            self.assertTrue(second['cache_reused']); self.assertEqual(second['id'], first['id']); self.assertEqual(len(calls), 1)
            changed = response(); changed['properties']['parameter']['T2M']['20250101'] = 28
            third = store.refresh(REQUEST, transport=self.transport(changed, calls), now=NOW+timedelta(hours=25))
            self.assertNotEqual(third['id'], first['id']); self.assertEqual(len(calls), 2)
            self.assertEqual(store.get(first['id'])['points'][0]['T2M'], 27.53)

    def test_missing_sentinel_and_absent_days_remain_unknown(self):
        data = response(); data['properties']['parameter']['T2M']['20250101'] = -999
        del data['properties']['parameter']['PRECTOTCORR']['20250102']
        points, quality = normalize_response(data, request_definition(REQUEST), NOW.isoformat())
        self.assertIsNone(points[0]['T2M']); self.assertIsNone(points[1]['PRECTOTCORR'])
        self.assertEqual(quality['T2M']['missing_days'], 1)
        self.assertEqual(quality['PRECTOTCORR']['missing_days'], 1)

    def test_schema_geography_time_units_and_invalid_values_block(self):
        cases = []
        item = response(); item['geometry']['coordinates'] = [1, 0]; cases.append(item)
        item = response(); item['header']['time_standard'] = 'LST'; cases.append(item)
        item = response(); item['header']['fill_value'] = 0; cases.append(item)
        item = response(); item['parameters']['T2M']['units'] = 'F'; cases.append(item)
        item = response(); del item['properties']; cases.append(item)
        for value in (True, 'warm', float('inf')):
            item = response(); item['properties']['parameter']['T2M']['20250101'] = value; cases.append(item)
        item = response(); item['properties']['parameter']['PRECTOTCORR']['20250101'] = -2; cases.append(item)
        item = response(); item['properties']['parameter']['T2M']['20250104'] = 10; cases.append(item)
        item = response(); item['properties']['parameter'] = {'T2M': {}, 'PRECTOTCORR': {}}; cases.append(item)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                normalize_response(data, request_definition(REQUEST), NOW.isoformat())

    def test_monthly_mean_and_total_require_every_calendar_day(self):
        points = [{'period': f'2024-02-{d:02}', 'T2M': float(d), 'PRECTOTCORR': 2.0} for d in range(1, 30)]
        month = monthly_weather(points)[0]
        self.assertEqual(month['expected_days'], 29); self.assertEqual(month['T2M'], 15); self.assertEqual(month['PRECTOTCORR'], 58)
        points[0]['T2M'] = None
        month = monthly_weather(points)[0]
        self.assertIsNone(month['T2M']); self.assertEqual(month['PRECTOTCORR'], 58)
        self.assertIsNone(monthly_weather(points[1:])[0]['PRECTOTCORR'])

    def test_failure_does_not_replace_previous_snapshot_and_hash_checks(self):
        with TemporaryDirectory() as folder:
            store = WeatherStore(Path(folder)); first = store.refresh(REQUEST, transport=self.transport(), now=NOW)
            failure = httpx.MockTransport(lambda _: httpx.Response(503))
            with self.assertRaises(httpx.HTTPStatusError): store.refresh(REQUEST, transport=failure, now=NOW+timedelta(days=2))
            self.assertEqual(len(store.list()), 1)
            self.assertEqual(store.get(first['id'])['id'], first['id'])
            (store.responses / f"{first['id']}.json").write_text('{}')
            with self.assertRaisesRegex(ValueError, 'source changed'): store.get(first['id'])
            with self.assertRaises(ValueError): store.get('../etc')

    def test_duplicate_keys_and_oversized_response_block(self):
        with TemporaryDirectory() as folder:
            store = WeatherStore(Path(folder))
            for content in (b'{"header": {}, "header": {}}', b'x'*4_000_001):
                with self.assertRaises(ValueError):
                    store.refresh(REQUEST, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content)), now=NOW)
            self.assertEqual(store.list(), [])

    def test_api_empty_validation_and_export(self):
        from app import main
        with TemporaryDirectory() as folder, patch.object(main, 'WEATHER_STORE', WeatherStore(Path(folder))):
            client = TestClient(main.app)
            self.assertEqual(client.get('/api/weather').json(), {'snapshots': []})
            self.assertEqual(client.post('/api/weather/refresh', json={}).status_code, 400)
            snapshot = main.WEATHER_STORE.refresh(REQUEST, transport=self.transport(), now=NOW)
            result = client.get('/api/weather/'+snapshot['id']+'/export')
            self.assertEqual(result.status_code, 200); self.assertIn('27.53', result.text)
            self.assertIn('attachment;', result.headers['content-disposition'])
            self.assertEqual(client.get('/api/weather/unknown/export').status_code, 400)


if __name__ == '__main__': unittest.main()

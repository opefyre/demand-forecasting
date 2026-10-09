"""Read-only reconciliation of the public example saved through the weather UI."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import sys

import httpx

root = Path(__file__).resolve().parents[1]
identifier = sys.argv[1] if len(sys.argv) > 1 else '7c1c62d3f56d4e34adb5836638ecd407'
if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
    raise SystemExit('Use a saved weather snapshot identifier.')
snapshot = json.loads((root / 'data/weather/snapshots' / f'{identifier}.json').read_text())
raw_bytes = (root / 'data/weather/responses' / f'{identifier}.json').read_bytes()
raw = json.loads(raw_bytes)
assert hashlib.sha256(raw_bytes).hexdigest() == snapshot['sha256']
assert snapshot['request']['latitude'] == snapshot['request']['longitude'] == 0
values = raw['properties']['parameter']
temperature = list(values['T2M'].values())
rainfall = list(values['PRECTOTCORR'].values())
assert len(temperature) == len(rainfall) == 31
assert all(v != -999 for v in temperature + rainfall)
mean = math.fsum(temperature) / 31
total = math.fsum(rainfall)
assert snapshot['monthly'][0]['T2M'] == mean
assert snapshot['monthly'][0]['PRECTOTCORR'] == total
response = httpx.get(f'http://127.0.0.1:8010/api/weather/{identifier}/export')
response.raise_for_status()
export = list(csv.DictReader(io.StringIO(response.text)))
assert len(export) == 31
for row in export:
    key = row['period'].replace('-', '')
    assert float(row['temperature_c']) == values['T2M'][key]
    assert float(row['precipitation_mm_per_day']) == values['PRECTOTCORR'][key]
    assert row['use'] == 'context_only' and row['time_standard'] == 'UTC'
    assert row['available_at'] == snapshot['captured_at']
print(json.dumps({'snapshot_id': identifier, 'location': 'public 0°, 0° example; not the client',
                  'daily_rows_reconciled': 31, 'mean_temperature_c': mean, 'total_rainfall_mm': total,
                  'source_hash_matches': True, 'export_matches': True}))

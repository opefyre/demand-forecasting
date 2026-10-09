"""Create a separately reviewed synthetic version; verify exports and preservation."""
import argparse
import copy
import csv
import io
import json
import math
from datetime import date, timedelta

from verify_order_comparison import api, URL
import httpx


def verify(snapshot_id):
    original = api('/api/sales/inputs/' + snapshot_id)
    inputs = copy.deepcopy(original['inputs'])
    assert inputs['classification'] == 'synthetic_sample', 'Synthetic inputs only'
    today = date.today()
    inputs.update(name='Synthetic demo · renewed order review', as_of=str(today),
                  valid_until=str(today + timedelta(days=7)), reviewed=True,
                  note='Synthetic acceptance only: unchanged sample orders checked; no client data.')
    payload = dict(inputs=inputs, base_snapshot_id=snapshot_id, order_mode='changes',
                   request_id=f'synthetic-review-{snapshot_id}-{today}')
    preview = api('/api/sales/validate', payload)
    assert preview['can_export'], preview['warnings']
    saved = api('/api/sales/inputs', payload)
    assert api('/api/sales/inputs', payload)['id'] == saved['id']
    assert api('/api/sales/inputs/' + snapshot_id) == original
    outlook = api('/api/sales/inputs/' + saved['id'] + '/outlook')
    assert outlook['can_export']
    assert saved['inputs']['orders'] == original['inputs']['orders']
    for row in outlook['rows']:
        assert math.isclose(row['total'], row['fulfilled'] + row['booked'] + row['remaining'], abs_tol=1e-8)
    for kind in ['json', 'csv']:
        for mode, field in [('combined_demand', 'still_to_serve'), ('remaining_forecast', 'remaining')]:
            response = httpx.get(f'{URL}/api/sales/inputs/{saved["id"]}/export', params={'mode':mode, 'kind':kind})
            response.raise_for_status()
            rows = response.json() if kind == 'json' else list(csv.DictReader(io.StringIO(response.text)))
            assert len(rows) == len(outlook['rows'])
            assert math.isclose(sum(float(r['quantity']) for r in rows), sum(r[field] for r in outlook['rows']), abs_tol=1e-8)
    print(json.dumps(dict(snapshot=saved['id'], source_unchanged=True, exports_checked=4,
                          rows=len(outlook['rows']), valid_until=inputs['valid_until'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot_id')
    verify(parser.parse_args().snapshot_id)

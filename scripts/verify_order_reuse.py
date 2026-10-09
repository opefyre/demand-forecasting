"""Read-only acceptance check for the approved synthetic ten-month demo."""
import json
import math
from io import BytesIO

import httpx
import pandas as pd

from verify_order_comparison import URL, api


def verify(run_id):
    key = api(f'/api/sales/runs/{run_id}/inputs')['snapshots'][0]['id']
    saved = api(f'/api/sales/inputs/{key}')
    assert saved['inputs']['classification'] == 'synthetic_sample'
    proof = next(e for e in saved['evidence'] if e.get('type') == 'horizon_order_reuse')
    source = api('/api/sales/inputs/' + proof['source_snapshot_id'])
    assert proof['source_sha256'] == source['sha256']
    assert not proof['publication_approval_carried'] and proof['coverage_confirmed']
    for field in ['customers', 'orders', 'commitments', 'as_of', 'valid_until', 'order_feed']:
        assert saved['inputs'][field] == source['inputs'][field]
    outlook = api(f'/api/sales/inputs/{key}/outlook')
    original = api(f'/api/sales/inputs/{source["id"]}/outlook')
    assert outlook['can_export'] and len(outlook['rows']) == 60
    assert len({r['period'] for r in outlook['rows']}) == 10
    assert len(proof['added_months']) == 4
    index = lambda r: (r['customer'], r['sku'], r['unit'], r['period'])
    old = {index(r): r for r in original['rows']}
    for row in outlook['rows']:
        if index(row) in old:
            assert row['booked'] == old[index(row)]['booked']
        else:
            assert row['booked'] == 0 and row['remaining'] > 0
        assert math.isclose(row['total'], row['fulfilled'] + row['booked'] + row['remaining'], abs_tol=1e-8)
    for kind in ['json', 'csv', 'xlsx']:
        for mode, field in [('combined_demand', 'still_to_serve'), ('remaining_forecast', 'remaining')]:
            response = httpx.get(f'{URL}/api/sales/inputs/{key}/export', params={'mode': mode, 'kind': kind})
            response.raise_for_status()
            if kind == 'json':
                frame = pd.DataFrame(response.json())
            elif kind == 'csv':
                frame = pd.read_csv(BytesIO(response.content))
            else:
                frame = pd.read_excel(BytesIO(response.content))
            assert len(frame) == 60 and set(frame.approval) == {'draft'}
            assert math.isclose(frame.quantity.sum(), sum(r[field] for r in outlook['rows']), abs_tol=1e-8)
    print(json.dumps({'run': run_id, 'snapshot': key, 'months': 10, 'rows': 60,
                      'booked': sum(r['booked'] for r in outlook['rows']),
                      'total': sum(r['total'] for r in outlook['rows']),
                      'source_unchanged': True, 'six_exports_reconciled': True}))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    verify(parser.parse_args().run_id)

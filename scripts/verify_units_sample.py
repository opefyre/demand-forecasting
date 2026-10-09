"""Create explicitly synthetic stock and independently check the selected conversion."""
from pathlib import Path
import json
import httpx

root = Path(__file__).resolve().parents[1]
with httpx.Client(base_url='http://127.0.0.1:8010', timeout=30) as client:
    versions = client.get('/api/units').raise_for_status().json()['versions']
    version = next(v for v in versions if v['name'] == 'Synthetic pallet definition' and v['classification'] == 'synthetic_sample')
    content = (root / 'sample_data/inventory_units_demo.csv').read_bytes()
    source = client.post('/api/inventory/sources', files={'file': ('inventory_units_demo.csv', content, 'text/csv')}).raise_for_status().json()
    config = {'source_id': source['id'], 'name': 'Synthetic mixed-unit stock', 'classification': 'synthetic_sample',
              'mapping': {'sku': 'A', 'quantity': 'B', 'unit': 'C', 'quality': 'D', 'record_key': 'E'},
              'quality_mode': 'column', 'quality_map': {'OK': 'available', 'HOLD': 'hold'},
              'as_of': '2026-08-31', 'reviewed': True}
    stock = client.post('/api/inventory', json=config).raise_for_status().json()
    url = f'/api/inventory/{stock["id"]}/projection'
    params = {'run_id': '01e6aa772eba'}
    unresolved = client.get(url, params=params).raise_for_status().json()
    assert next(r for r in unresolved['rows'] if r['sku'] == 'COA-ART-135')['opening'] is None
    report = client.get(url, params={**params, 'unit_version_id': version['id']}).raise_for_status().json()
    row = next(r for r in report['rows'] if r['sku'] == 'COA-ART-135')
    kraft = next(r for r in report['rows'] if r['sku'] == 'PKG-KRAFT-120')
    assert row['opening'] == 1000 * 2
    assert row['held_stock'] == 125 * 2
    assert row['closing'] == 2000 - row['demand']
    assert kraft['opening'] == 50000 / 1000
    print(json.dumps({'snapshot_id': stock['id'], 'unit_version_id': version['id'], 'opening_tonnes': row['opening'],
                      'held_tonnes': row['held_stock'], 'closing_tonnes': row['closing'],
                      'kraft_opening_tonnes': kraft['opening'], 'source_rows': len(report['conversions'])}))

"""Save/run or reconcile the explicitly synthetic routed-production fixture."""
import argparse
import json
import math
from pathlib import Path
import sys
import uuid

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = 'http://127.0.0.1:8010'


def api(path, payload=None):
    response = httpx.get(BASE + path) if payload is None else httpx.post(BASE + path, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def upload(path, role):
    with path.open('rb') as content:
        response = httpx.post(BASE + '/api/sources', data={'role': role}, files={'file': (path.name, content)}, timeout=30)
    response.raise_for_status()
    return response.json()


def start():
    history = upload(ROOT / 'sample_data/routed_history_demo.csv', 'history')
    operations = upload(ROOT / 'outputs/01a0a5ce-routing/synthetic_routed_production.xlsx', 'operations')
    mapping = operations['preview']['suggested_mapping']
    assert mapping['mode'] == 'routed'
    mapping.update(stock_as_of='2026-08-31', reviewed=True)
    config = {'name': 'Synthetic multi-step production sample', 'classification': 'synthetic_sample', 'accept_warnings': True,
              'sources': {'history': history['id'], 'operations': operations['id']},
              'settings': {'date_col': 'date', 'item_col': 'item_id', 'sku_col': 'sku', 'customer_col': 'customer', 'target_col': 'quantity', 'unit': 'KBlank',
                           'frequency': 'monthly', 'horizon': 3, 'profile': 'fast', 'method_selection': 'model:Last observed',
                           'operations_mapping': mapping, 'calendar_country': 'IR', 'weekend_days': [4], 'drivers': [], 'outlier_strategy': 'none'}}
    api('/api/datasets/validate', config)
    dataset = api('/api/datasets', config)
    job = api('/api/jobs', {'dataset_id': dataset['id'], 'request_id': str(uuid.uuid4())})
    print(json.dumps({'dataset_id': dataset['id'], 'job': job}))


def verify(run_id):
    run = api('/api/runs/' + run_id)
    output = run['operations']
    assert run['unit'] == 'KBlank'
    assert run['source_classification'] == 'synthetic_sample'
    assert run['input_manifest']['settings']['operations_mapping']['mode'] == 'routed'
    # Independent arithmetic: sum customers before rounding batches.
    for period in ('2026-09-01', '2026-10-01', '2026-11-01'):
        quantities = {'A': 0, 'B': 0}
        for item, series in run['series'].items():
            if item == '__all__':
                continue
            point = next(p for p in series['forecast'] if p['timestamp'][:10] == period)
            quantities[run['metadata'][item]['sku']] += point['mean']
        a, b = quantities['A'], quantities['B']
        assert (a, b) == (150, 40)
        required = a * .5 + b * 100 / 1000
        cutter = a * .2 + math.ceil(a / 100) * 2 + b * .5 + math.ceil(b / 100)
        press = a * .1 + math.ceil(a / 100)
        material = next(r for r in output['materials'] if r['period'] == period)
        assert material['gross_requirement'] == required == 79
        for machine, expected in [('Cutter', cutter), ('Press', press)]:
            row = next(r for r in output['capacity'] if r['production_line'] == machine and r['period'] == period)
            assert row['required_quantity'] == expected
            assert row['capacity_unit'] == 'hours'
    assert output['materials'][0]['opening'] == 90
    assert output['materials'][0]['projected_balance'] == 11
    assert output['materials'][0]['recommended_order'] == 10
    assert len(output['workload_details']) == 9
    assert output['workload_details'][0]['source_cells']['hours_per_unit'] == 'Routing!F2'
    print(json.dumps({'run_id': run_id, 'monthly_material_kg': 79, 'cutter_hours': 55, 'press_hours': 17, 'source_cells_preserved': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run')
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    if args.start:
        start()
    elif args.run:
        verify(args.run)
    else:
        parser.error('Choose --start or --run RUN_ID')

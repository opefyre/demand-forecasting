"""Reconcile one live mapped sample without using the supply calculation function."""
import json
import math
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.datasets import DatasetStore
from app.operations import read_operations_workbook

root = Path(__file__).resolve().parents[1]
identifier = sys.argv[1] if len(sys.argv) > 1 else 'e847b7a5adf5'
if len(identifier) != 12 or any(c not in '0123456789abcdef' for c in identifier):
    raise SystemExit('Use a saved forecast run identifier.')
run = json.loads((root / 'runs' / identifier / 'result.json').read_text())
manifest = run['input_manifest']
source = next(s for s in manifest['sources'] if s['role'] == 'operations')
stored, content = DatasetStore(root / 'data/datasets').source(source['id'])
assert stored['sha256'] == source['sha256']
tables = read_operations_workbook(stored['name'], content, manifest['settings']['operations_mapping'])
period = '2026-09-01'
material = 'PULP-HW'
recipe = {r.sku: float(r.quantity_per_tonne) * (1 + float(r.scrap_pct) / 100)
          for r in tables['bom'].itertuples() if r.material_id == material}
parts = []
for item, series in run['series'].items():
    if item == '__all__':
        continue
    sku = run['metadata'][item]['sku']
    for point in series['forecast']:
        if point['timestamp'][:10] == period and sku in recipe:
            parts.append(point['mean'] * recipe[sku])
required = math.fsum(parts)
row = next(r for r in run['operations']['materials'] if r['material_id'] == material and r['period'] == period)
master = next(r for r in tables['materials'].itertuples() if r.material_id == material)
opening = float(master.inventory_on_hand) - float(master.quality_hold_qty)
receipts = math.fsum(float(r.quantity) for r in tables['open_pos'].itertuples()
                     if r.material_id == material and str(r.due_date)[:7] == period[:7]
                     and r.status in ('open', 'confirmed'))
assert row['gross_requirement'] == round(required, 3)
assert row['opening'] == opening
assert row['projected_balance'] == round(opening + receipts - required, 3)
assert run['operations']['input_lineage']['materials']['stock_as_of'] == '2026-08-31'
print(json.dumps({'run_id': run['run_id'], 'material': material, 'period': period,
                  'independent_requirement': required, 'saved_requirement': row['gross_requirement'],
                  'opening': opening, 'receipts': receipts, 'closing': row['projected_balance'],
                  'mapping_preserved': True}))

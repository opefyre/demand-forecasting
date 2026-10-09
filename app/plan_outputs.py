"""Resolve one plan version once for both exports and supply calculations."""
from copy import deepcopy
from io import BytesIO
import math

import pandas as pd


def resolve_plan(run: dict, plan: dict) -> tuple[dict, list[dict]]:
    if plan['run_id'] != run['run_id']:
        raise ValueError('The plan and forecast do not match.')
    result = deepcopy(run)
    overrides = {}
    available = {(item, str(row['timestamp'])[:10])
                 for item, series in run['series'].items() if item != '__all__'
                 for row in series.get('forecast', [])}
    for change in plan.get('overrides', []):
        if change.get('reverted_at'):
            continue
        key = (change['item_id'], change['period'][:10])
        value = float(change['value'])
        if key not in available or not math.isfinite(value) or value < 0:
            raise ValueError('This plan contains an invalid adjustment. Review it before export.')
        overrides[key] = change  # Latest active adjustment wins, as in plan review.
    previous = {}
    snapshot = plan.get('revision_baseline')
    if snapshot:
        if snapshot['run_id'] != run['run_id']:
            raise ValueError('The previous plan version uses a different forecast.')
        for change in snapshot['overrides']:
            key = (change['item_id'], change['period'][:10])
            value = float(change['value'])
            if key not in available or not math.isfinite(value) or value < 0:
                raise ValueError('The previous plan snapshot contains an invalid quantity.')
            previous[key] = value
    rows, totals = [], {}
    for item, series in result['series'].items():
        if item == '__all__':
            continue
        for row in series.get('forecast', []):
            period = str(row['timestamp'])[:10]
            change = overrides.get((item, period))
            statistical = row['mean']
            quantity = float(change['value']) if change else statistical
            if not math.isfinite(quantity) or quantity < 0:
                raise ValueError('The forecast contains an invalid quantity.')
            rows.append({'item_id': item, 'sku': run.get('metadata', {}).get(item, {}).get('sku', item),
                         'period': period, 'unit': run.get('unit', 'units'),
                         'forecast_quantity': statistical, 'plan_quantity': quantity,
                         'adjustment': quantity - statistical,
                         'reason': change.get('reason', '') if change else '',
                         'actor': change.get('actor', '') if change else ''})
            if snapshot:
                prior = previous.get((item, period), statistical)
                rows[-1].update(previous_plan_quantity=prior, revision_change=quantity-prior)
            row['mean'] = quantity
            # Statistical ranges are not ranges around a human-adjusted plan.
            for key in ('p10', 'p50', 'p90'):
                row.pop(key, None)
            totals[period] = totals.get(period, 0) + quantity
    if '__all__' in result['series']:
        result['series']['__all__']['forecast'] = [
            {'timestamp': period, 'mean': value} for period, value in sorted(totals.items())]
    result['plan'] = {'id': plan['id'], 'name': plan['name'], 'status': plan['status'],
                      'updated_at': plan['updated_at'], 'run_id': run['run_id']}
    result.pop('operations', None)  # Never reuse baseline supply for an adjusted plan.
    result.pop('forecast_rows', None)
    return result, rows


def plan_workbook(plan: dict, rows: list[dict], operations: dict | None = None) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name='Plan quantities', index=False)
        pd.DataFrame([{'field': key, 'value': str(plan.get(key, ''))}
                      for key in ('id', 'name', 'status', 'run_id', 'owner', 'updated_at', 'root_plan_id', 'parent_plan_id', 'version', 'revision_reason', 'created_by')]).to_excel(
                          writer, sheet_name='Plan version', index=False)
        pd.DataFrame(plan.get('overrides', [])).to_excel(writer, sheet_name='Adjustment history', index=False)
        pd.DataFrame([{**{k:v for k,v in event.items() if k != 'identity'},
                       'identity_basis':'company_sign_in' if event.get('identity') else 'self_declared',
                       'issuer':event.get('identity', {}).get('issuer'),
                       'subject':event.get('identity', {}).get('subject')}
                      for event in plan.get('history', [])]).to_excel(writer, sheet_name='Plan activity', index=False)
        if operations:
            for key, title in [('materials', 'Materials'), ('capacity', 'Capacity'), ('workload_details', 'Production steps')]:
                pd.DataFrame(operations.get(key, [])).to_excel(writer, sheet_name=title, index=False)
        # Imported names and free-text reasons must remain text, never Excel formulas.
        for sheet in writer.book:
            for row in sheet:
                for cell in row:
                    if cell.data_type == 'f':
                        cell.data_type = 's'
    return buffer.getvalue()

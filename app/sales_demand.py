"""Customer-scoped demand consumption. No inventory or production calculations."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from io import BytesIO
import csv
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .inventory import raw_table, text_value
from .sales_conventions import local_today, period_start, month_label, shift_month
from .factor_normalization import input_date, numeric


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, validate_default=True)


class CustomerProduct(StrictRecord):
    customer: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=60)
    series_id: str = Field(default='', max_length=300)


class SalesOrder(StrictRecord):
    reference: str = Field(min_length=1, max_length=160)
    customer: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=60)
    due_date: date
    ordered: Decimal = Field(ge=0, allow_inf_nan=False)
    fulfilled: Decimal = Field(default=0, ge=0, allow_inf_nan=False)
    cancelled: Decimal = Field(default=0, ge=0, allow_inf_nan=False)
    status: Literal['confirmed', 'unconfirmed', 'cancelled']

    @model_validator(mode='after')
    def quantities(self):
        if self.fulfilled + self.cancelled > self.ordered:
            raise ValueError(f'{self.reference}: fulfilled + cancelled exceeds ordered quantity.')
        if self.status == 'cancelled' and self.fulfilled + self.cancelled != self.ordered:
            raise ValueError(f'{self.reference}: a cancelled line must account for every unit as fulfilled or cancelled.')
        if self.status == 'unconfirmed' and self.fulfilled:
            raise ValueError(f'{self.reference}: an unconfirmed line cannot have fulfilled quantities.')
        return self


class Commitment(StrictRecord):
    customer: str = Field(min_length=1, max_length=160)
    sku: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=60)
    period: date
    quantity: Decimal = Field(ge=0, allow_inf_nan=False)
    owner: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=3, max_length=500)
    valid_until: date


class DemandInputs(StrictRecord):
    name: str = Field(min_length=1, max_length=160)
    run_id: str = Field(min_length=1, max_length=80)
    as_of: date
    valid_until: date
    classification: Literal['user_provided', 'synthetic_sample']
    order_feed: Literal['complete_snapshot', 'unknown']
    customers: list[CustomerProduct] = Field(min_length=1, max_length=10000)
    orders: list[SalesOrder] = Field(default_factory=list, max_length=50000)
    commitments: list[Commitment] = Field(default_factory=list, max_length=10000)
    reviewed: bool = False
    note: str = Field(min_length=3, max_length=1000)


def month(value, basis='gregorian'):
    return period_start(value, basis).date().isoformat()


def month_basis(run):
    return run.get('run_settings', {}).get('calendar_profile', {}).get('month_basis', 'gregorian')


def run_today(run):
    return local_today(run.get('site', {}).get('timezone', 'Asia/Tehran'))


def number(value):
    return Decimal(str(value))


def match_key(row):
    return row.customer, row.sku, row.unit


def validate_inputs(payload, run):
    data = DemandInputs.model_validate(payload)
    if not data.reviewed:
        raise ValueError('Confirm the full customer list, order status meanings and quantities before saving.')
    if data.run_id != run['run_id']:
        raise ValueError('These inputs belong to a different forecast.')
    if data.classification != run.get('source_classification'):
        raise ValueError('Sample and real inputs cannot be mixed.')
    if run.get('run_settings', {}).get('frequency') != 'monthly':
        raise ValueError('Customer order matching currently supports monthly forecasts only.')
    if data.valid_until < data.as_of:
        raise ValueError('Freshness expiry must be on or after the source date.')
    basis = month_basis(run)
    if data.as_of > run_today(run):
        raise ValueError('The source date cannot be in the future.')
    keys = [match_key(row) for row in data.customers]
    customer_keys = set(keys)
    if len(customer_keys) != len(keys):
        raise ValueError('Duplicate customer / SKU / unit relationships.')
    ids = [row.series_id for row in data.customers if row.series_id]
    if len(set(ids)) != len(ids):
        raise ValueError('A historical series cannot supply the forecast for multiple customers.')
    for customer in data.customers:
        if customer.series_id:
            if customer.series_id == '__all__' or customer.series_id not in run.get('series', {}):
                raise ValueError(f'{customer.customer}: choose an individual saved forecast series.')
            meta = run.get('metadata', {}).get(customer.series_id, {})
            if meta.get('customer') and str(meta['customer']) != customer.customer:
                raise ValueError(f'{customer.series_id}: the recorded customer does not match.')
            if meta.get('sku') and str(meta['sku']) != customer.sku:
                raise ValueError(f'{customer.series_id}: the recorded SKU does not match.')
            if customer.unit != run.get('unit'):
                raise ValueError('Customer units must match the forecast; no implicit conversion is made.')
    refs = [row.reference for row in data.orders]
    if len(set(refs)) != len(refs):
        raise ValueError('Duplicate order-line references. Split deliveries need unique schedule references.')
    for order in data.orders:
        if match_key(order) not in customer_keys:
            raise ValueError(f'{order.reference}: add this customer / SKU / unit to the customer list first.')
        if month(order.due_date, basis) > month(data.as_of, basis) and order.fulfilled:
            raise ValueError(f'{order.reference}: future-period fulfilled quantities need a corrected demand date.')
    commitment_keys = []
    for row in data.commitments:
        if match_key(row) not in customer_keys or str(row.period) != month(row.period, basis):
            raise ValueError('Commitments require a listed customer / SKU / unit and the first day of the month.')
        commitment_keys.append((*match_key(row), str(row.period)))
    if len(set(commitment_keys)) != len(commitment_keys):
        raise ValueError('Duplicate complete commitments for a customer / SKU / month.')
    return data


def demand_outlook(payload, run, today=None):
    data = validate_inputs(payload, run)
    today = today or run_today(run)
    basis = month_basis(run)
    fresh = data.order_feed == 'complete_snapshot' and data.valid_until >= today
    periods = sorted({str(r['timestamp'])[:10] for s, group in run['series'].items()
                      if s != '__all__' for r in group['forecast']})
    by_order = defaultdict(list)
    schedule = []
    for order in data.orders:
        bucket = month(order.due_date, basis)
        reason = ('Not confirmed' if order.status == 'unconfirmed' else
                  'Cancelled' if order.status == 'cancelled' and not order.fulfilled else
                  'Outside forecast periods' if bucket not in periods else
                  'Closed period' if bucket < month(data.as_of, basis) else '')
        schedule.append({**order.model_dump(mode='json'), 'period': bucket,
                         'outstanding': float(order.ordered - order.fulfilled - order.cancelled),
                         'included': not reason, 'reason': reason})
        if not reason:
            by_order[(*match_key(order), bucket)].append(order)
    commitments = {(*match_key(c), str(c.period)): c for c in data.commitments}
    rows = []
    for customer in data.customers:
        forecasts = {str(r['timestamp'])[:10]: r['mean'] for r in
                     run.get('series', {}).get(customer.series_id, {}).get('forecast', [])}
        for period in periods:
            if period < month(data.as_of, basis):
                continue
            orders = by_order[(*match_key(customer), period)]
            fulfilled = sum((o.fulfilled for o in orders), Decimal(0))
            booked = sum((o.ordered - o.fulfilled - o.cancelled for o in orders), Decimal(0))
            baseline = number(forecasts[period]) if period in forecasts else None
            if baseline is not None and (not baseline.is_finite() or baseline < 0):
                raise ValueError('The selected baseline contains an invalid quantity.')
            commitment = commitments.get((*match_key(customer), period))
            current_commitment = commitment and commitment.valid_until >= today
            issue = ''
            status = 'Partly booked' if booked else 'Expected only'
            if not fresh:
                remaining, status, issue = None, 'Orders unknown', 'Refresh and review the order source.'
            elif current_commitment:
                if commitment.quantity < fulfilled + booked:
                    remaining, status, issue = None, 'Conflict', 'Complete commitment is below booked/fulfilled quantity.'
                else:
                    remaining = commitment.quantity - fulfilled - booked
                    status = 'Complete commitment'
            elif baseline is None:
                remaining, status, issue = None, 'More history needed', 'Additional demand is unknown; known orders are retained.'
            else:
                remaining = max(Decimal(0), baseline - fulfilled - booked)
                if booked and not remaining:
                    status = 'Covered by orders'
            if commitment and not current_commitment:
                issue = 'Complete commitment expired; partial-order policy applied.'
            matched = min(baseline, fulfilled + booked) if baseline is not None else None
            rows.append({'customer': customer.customer, 'sku': customer.sku, 'unit': customer.unit,
                'series_id': customer.series_id, 'period': period,
                'period_label':month_label(period,basis), 'planning_calendar':basis,
                'period_end':(shift_month(period,1,basis).date()-timedelta(days=1)).isoformat(),
                'baseline': float(baseline) if baseline is not None else None,
                'booked': float(booked), 'fulfilled': float(fulfilled),
                'matched': float(matched) if matched is not None else None,
                'remaining': float(remaining) if remaining is not None else None,
                'total': float(fulfilled + booked + remaining) if remaining is not None else None,
                'still_to_serve': float(booked + remaining) if remaining is not None else None,
                'status': status, 'issue': issue, 'order_references': [o.reference for o in orders],
                'commitment': commitment.model_dump(mode='json') if commitment else None})
    used = {c.series_id for c in data.customers if c.series_id}
    unmapped = sorted(set(run['series']) - used - {'__all__'})
    warnings = []
    what_if = run.get('metrics',{}).get('evidence_policy') == 'reviewed_what_if'
    if what_if:
        warnings.append('What-if forecast: external historical release dates are unverified. Quantities are planning assumptions, not validated accuracy evidence.')
    if not fresh:
        warnings.append('Order source is unknown or expired. Final totals and demand exports are blocked.')
    if unmapped:
        warnings.append(f'{len(unmapped)} forecast series are not mapped to the customer list. Exports are blocked.')
    if any(r['reason'] == 'Outside forecast periods' and r['status'] == 'confirmed' for r in schedule):
        warnings.append('Some confirmed orders fall outside this forecast. Review the order schedule.')
    overdue = [r for r in schedule if r['status'] == 'confirmed' and r['outstanding'] > 0
               and r['period'] < month(data.as_of, basis)]
    if overdue:
        warnings.append('Past-due open orders need reviewed delivery dates. Exports are blocked; these orders were not silently moved.')
    return {'run_id': run['run_id'], 'name': data.name, 'as_of': str(data.as_of),
            'valid_until': str(data.valid_until), 'fresh': fresh, 'rows': rows,
            'orders': schedule, 'unmapped_series': unmapped, 'warnings': warnings,
            'can_export': bool(rows) and fresh and not unmapped and not overdue and all(r['total'] is not None for r in rows),
            'classification': data.classification, 'planning_calendar':basis,
            'forecast_use':'what_if_unvalidated' if what_if else 'model_estimate',
            'policy': 'exact_customer_sku_month_v1'}


class StaleOrderRevision(ValueError):
    """An order revision must be based on the current saved version."""


def revise_orders(previous, incoming, mode, as_of):
    """Upsert complete line values, never quantity deltas. No implicit deletes."""
    if mode not in {'replace', 'changes'}:
        raise ValueError('Choose a full order book or changed lines.')
    def indexed(rows):
        result = {}
        for raw in rows:
            row = SalesOrder.model_validate(raw).model_dump(mode='json')
            if row['reference'] in result:
                raise ValueError('Duplicate order reference: ' + row['reference'])
            result[row['reference']] = row
        return result
    old, supplied = indexed(previous), indexed(incoming)
    merged = {**old, **supplied} if mode == 'changes' else supplied
    changes = []
    for reference in sorted(old.keys() | merged.keys()):
        before, after = old.get(reference), merged.get(reference)
        if before == after:
            continue
        if before and after:
            if any(before[k] != after[k] for k in ('customer', 'sku', 'unit')):
                raise ValueError(f'{reference}: this reference already belongs to another customer, SKU or unit. Use a unique source / order / delivery-line reference.')
            if number(after['fulfilled']) < number(before['fulfilled']):
                raise ValueError(f'{reference}: fulfilled quantity cannot decrease in an order update.')
            if number(before['fulfilled']) and month(before['due_date']) != month(after['due_date']):
                raise ValueError(f'{reference}: keep fulfilled quantities in their original month. Split the remaining delivery into a new reference.')
        if before and not after and number(before['fulfilled']) and month(before['due_date']) >= month(as_of):
            raise ValueError(f'{reference}: the full order book must retain this month’s fulfilled quantities.')
        changes.append({'reference': reference, 'change': 'added' if not before else 'removed' if not after else 'updated',
                        'before': before, 'after': after})
    return list(merged.values()), changes


class DemandStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as con:
            con.execute('CREATE TABLE IF NOT EXISTS sales_inputs (id TEXT PRIMARY KEY, request_id TEXT UNIQUE, payload TEXT NOT NULL)')
            con.commit()

    def list(self, run_id):
        with closing(sqlite3.connect(self.path)) as con:
            rows = [json.loads(r[0]) for r in con.execute('SELECT payload FROM sales_inputs ORDER BY rowid DESC')]
        return [r for r in rows if r['inputs']['run_id'] == run_id]

    def get(self, key):
        with closing(sqlite3.connect(self.path)) as con:
            row = con.execute('SELECT payload FROM sales_inputs WHERE id=?', (key,)).fetchone()
        if not row:
            raise ValueError('Customer/order snapshot not found.')
        return json.loads(row[0])

    def save(self, payload, run, request_id, actor, evidence=None, base_snapshot_id=None, comparison_guard=None):
        data = validate_inputs(payload, run).model_dump(mode='json')
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
            raise ValueError('A retry identifier is required.')
        canonical = json.dumps({'inputs': data, 'evidence': evidence or []}, sort_keys=True, ensure_ascii=False)
        if base_snapshot_id:
            canonical += '\nbase:' + base_snapshot_id
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        key = hashlib.sha256(request_id.encode()).hexdigest()[:32]
        row = {'id': key, 'request_id': request_id, 'sha256': digest, 'inputs': data,
               'evidence': evidence or [], 'actor': actor, 'created_at': datetime.now(timezone.utc).isoformat()}
        if base_snapshot_id:
            row['base_snapshot_id'] = base_snapshot_id
        with closing(sqlite3.connect(self.path, timeout=30)) as con:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute('SELECT payload FROM sales_inputs WHERE request_id=?', (request_id,)).fetchone()
            if old:
                old = json.loads(old[0])
                if old['sha256'] != digest:
                    raise ValueError('This retry identifier was already used for different inputs.')
                return old
            if comparison_guard:
                versions=[json.loads(r[0]) for r in con.execute('SELECT payload FROM sales_inputs ORDER BY rowid DESC')]
                source=next((r for r in versions if r['id']==comparison_guard['source_id']),None)
                latest_source=next((r for r in versions if source and r['inputs']['run_id']==source['inputs']['run_id']),None)
                latest_target=next((r for r in versions if r['inputs']['run_id']==data['run_id']),None)
                if (not source or source['sha256']!=comparison_guard['source_sha256'] or latest_source['id']!=source['id']
                        or (latest_target['id'] if latest_target else None)!=comparison_guard['target_latest_id']):
                    raise StaleOrderRevision('Orders changed while you were reviewing. Reopen the comparison.')
            if base_snapshot_id:
                latest = next((json.loads(r[0]) for r in con.execute('SELECT payload FROM sales_inputs ORDER BY rowid DESC')
                               if json.loads(r[0])['inputs']['run_id'] == data['run_id']), None)
                if not latest or latest['id'] != base_snapshot_id:
                    raise StaleOrderRevision('A newer order version is available. Open the latest version and apply your changes there.')
            con.execute('INSERT INTO sales_inputs VALUES (?,?,?)', (key, request_id, json.dumps(row, ensure_ascii=False)))
            con.commit()
        return row


SCHEMAS = {'customers': CustomerProduct, 'orders': SalesOrder, 'commitments': Commitment}


def import_rows(sources, role, config):
    source, content = sources.source(config['source_id'])
    if source['role'] != 'sales_' + role:
        raise ValueError('Wrong source type for this input.')
    table = raw_table(source['name'], content, config.get('sheet'), config.get('header_row', 1))
    mapping = config.get('mapping', {})
    allowed = set(SCHEMAS[role].model_fields)
    if set(mapping) - allowed:
        raise ValueError('Unknown mapped fields.')
    columns = {col['id'] for col in table['columns']}
    if any(col not in columns for col in mapping.values() if col):
        raise ValueError('A mapped column no longer exists.')
    selected = [col for col in mapping.values() if col]
    if len(set(selected)) != len(selected):
        raise ValueError('Each input field needs its own source column.')
    records, cells = [], []
    calendar = config.get('calendar','gregorian')
    matches=config.get('customer_matches') or {}
    if not isinstance(matches,dict) or len(matches)>10000 or any(not isinstance(k,str) or not isinstance(v,str) or not k.strip() or not v.strip() for k,v in matches.items()):
        raise ValueError('Customer matches must map reviewed source names to customer names.')
    matched_names={}
    for item in table['rows']:
        record = {}
        for field, col in mapping.items():
            if not col:
                continue
            value = text_value(item['values'].get(col))
            if value:
                record[field] = value[:10] if isinstance(item['values'].get(col), (date, datetime)) else value
                annotation = SCHEMAS[role].model_fields[field].annotation
                if annotation is date:
                    record[field] = input_date(item['values'].get(col), calendar).isoformat()
                elif annotation is Decimal:
                    record[field] = str(numeric(value))
        if record.get('customer') in matches:
            original=record['customer'];record['customer']=matches[original]
            if original!=record['customer']:matched_names[original]=record['customer']
        try:
            records.append(SCHEMAS[role].model_validate(record).model_dump(mode='json'))
        except ValueError as exc:
            raise ValueError(f'Row {item["source_row"]}: {str(exc)[:450]}') from exc
        cells.append({'row': item['source_row'], 'cells': {field: f'{col}{item["source_row"]}' for field,col in mapping.items() if col}})
    if table['formulas']:
        raise ValueError('Export values, not Excel formulas, for reviewed customer and order inputs.')
    return records, {'source': {k: source[k] for k in ('id', 'name', 'sha256')}, 'role': role,
                      'mapping': mapping, 'calendar':calendar, 'customer_matches':matched_names,'sheet': table['sheet'], 'header_row': table['header_row'], 'cells': cells}


def export_demand(outlook, mode, kind, *, release_metadata=None):
    if mode not in {'remaining_forecast', 'combined_demand'} or kind not in {'csv', 'xlsx', 'json'}:
        raise ValueError('Select remaining forecast or combined demand, and CSV, Excel or JSON.')
    if not outlook['can_export']:
        raise ValueError('Resolve missing history, unmapped series and source freshness before exporting final demand.')
    rows = [{**{k: r[k] for k in ('customer','sku','unit','period','baseline','booked','fulfilled','matched','remaining','total','still_to_serve','status')},
             'quantity': r['remaining'] if mode == 'remaining_forecast' else r['still_to_serve'],
             'export_mode': mode, 'snapshot_id': outlook.get('snapshot_id'), 'run_id': outlook['run_id'],
             'as_of': outlook['as_of'], 'policy': outlook['policy'], 'approval': 'draft',
             'planning_calendar':outlook.get('planning_calendar','gregorian'),
             'period_label':r.get('period_label',r['period'][:7]),
             'period_end':r.get('period_end'),
             'forecast_use':outlook.get('forecast_use','model_estimate'),
             **(release_metadata or {})} for r in outlook['rows']]
    if kind == 'json':
        return json.dumps(rows, ensure_ascii=False).encode(), 'application/json'
    # Neutralise spreadsheet formula strings; underlying saved identifiers are unchanged.
    safe = [{k: ("'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v)
             for k,v in r.items()} for r in rows]
    if kind == 'csv':
        from io import StringIO
        output = StringIO(); writer = csv.DictWriter(output, fieldnames=list(safe[0]))
        writer.writeheader(); writer.writerows(safe)
        return ('\ufeff'+output.getvalue()).encode(), 'text/csv'
    import pandas as pd
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame(safe).to_excel(writer, sheet_name='Demand', index=False)
    return output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

"""Immutable, reviewed closed-period actuals and paired forecast evaluation."""
from collections import defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import uuid
from io import StringIO
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import Column, JSON, MetaData, String, Table, create_engine, select
from sqlalchemy.exc import IntegrityError

from .inventory import raw_table, text_value
from .plan_outputs import resolve_plan
from .sales_conventions import period_start, shift_month, month_label
from .sales_demand import month_basis
from .factor_normalization import input_date, numeric


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def period_end(start, frequency, basis='gregorian'):
    start = date.fromisoformat(start)
    if frequency == 'monthly':
        if period_start(start, basis).date() != start:
            raise ValueError('Monthly forecast dates must be the first day of each month.')
        return shift_month(start, 1, basis).date() - timedelta(days=1)
    if frequency not in {'weekly', 'daily'}:
        raise ValueError('The forecast frequency is not supported for actual-results comparison.')
    return start + timedelta(days=6 if frequency == 'weekly' else 0)


def before_period(value, period, zone):
    """No timestamp means no proof of a prospective forecast or approval."""
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return instant.tzinfo is not None and instant.astimezone(zone).date() < date.fromisoformat(period)
    except (AttributeError, TypeError, ValueError):
        return False


def score(rows, predicted='forecast'):
    n = len(rows)
    if not n:
        return {'observations': 0, 'actual_total': None, 'predicted_total': None, 'absolute_error': None,
                'wape_pct': None, 'bias_pct': None, 'mae': None}
    try:
        actual = math.fsum(r['actual'] for r in rows)
        total = math.fsum(r[predicted] for r in rows)
        error = math.fsum(abs(r[predicted] - r['actual']) for r in rows)
    except OverflowError as exc:
        raise ValueError('Quantity totals are too large. Check the unit and source quantities.') from exc
    return {'observations': n, 'actual_total': actual, 'predicted_total': total, 'absolute_error': error,
            'wape_pct': error / actual * 100 if actual else None,
            'bias_pct': (total - actual) / actual * 100 if actual else None, 'mae': error / n}


def export_actuals(report):
    stream = StringIO()
    columns = ['item_id', 'period', 'period_label', 'planning_calendar', 'actual', 'forecast', 'approved', 'unit', 'horizon_step',
               'prospective', 'plan_eligible', 'source_row', 'source_cell', 'comparison_id', 'run_id', 'plan_id', 'classification']
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for row in report['rows']:
        values = {**row, 'unit': report['unit'], 'comparison_id': report['id'], 'run_id': report['run_id'],
                  'plan_id': (report.get('plan') or {}).get('id'), 'classification': report['classification']}
        writer.writerow({key: "'" + value if isinstance(value, str) and value.startswith(('=', '+', '-', '@', '\t', '\r')) else value
                         for key, value in values.items() if key in columns})
    return stream.getvalue().encode('utf-8-sig')


def evaluate_actuals(run, table, config, plan=None, today=None):
    unit = run.get('unit')
    if not unit or config.get('unit') != unit:
        raise ValueError('Confirm the same quantity unit as this forecast. Renaming a unit does not convert it.')
    classification = config.get('classification')
    expected_class = run.get('source_classification', 'user_provided')
    if classification not in {'user_provided', 'synthetic_sample'} or classification != expected_class:
        raise ValueError('Sample forecasts must use sample actuals; real forecasts must use real actuals.')
    zone = ZoneInfo(run.get('site', {}).get('timezone', 'Asia/Tehran'))
    today = today or datetime.now(zone).date()
    try:
        closed = date.fromisoformat(config.get('closed_through', ''))
    except (ValueError, TypeError):
        raise ValueError('Enter the last fully closed date covered by these actuals.')
    if classification != 'synthetic_sample' and closed >= today:
        raise ValueError('Only completed dates can be closed. Today and future dates are not actual results.')
    mapping = config.get('mapping', {})
    cols = {c['id'] for c in table['columns']}
    fields = [mapping.get(key) for key in ('item_id', 'timestamp', 'actual')]
    if len(set(fields)) != 3 or any(field not in cols for field in fields):
        raise ValueError('Match three different columns: item, period start, and actual quantity.')
    frequency = run.get('run_settings', {}).get('frequency', 'monthly')
    basis = month_basis(run)
    calendar = config.get('calendar', 'gregorian')
    if calendar not in ('gregorian', 'jalali'):
        raise ValueError('Choose Gregorian or Persian dates for the actual-results file.')
    forecast = {}
    for item, series in run.get('series', {}).items():
        if item == '__all__':
            continue
        for step, row in enumerate(series.get('forecast', []), 1):
            key = (item, str(row['timestamp'])[:10])
            quantity = float(row['mean'])
            if key in forecast or not math.isfinite(quantity) or quantity < 0:
                raise ValueError('The forecast contains duplicate or invalid quantities.')
            forecast[key] = {'forecast': quantity, 'step': step, 'end': period_end(key[1], frequency, basis)}
    expected = {key for key, row in forecast.items() if row['end'] <= closed}
    if not expected:
        raise ValueError('No forecast period has ended by the selected closed date.')
    if closed not in {row['end'] for row in forecast.values()}:
        raise ValueError('Choose the ending date of a forecast period, not a partially completed period.')
    resolved = {}
    approval = None
    if plan:
        if plan.get('status') not in {'approved', 'published'}:
            raise ValueError('Choose an approved or published plan for this forecast.')
        adjusted, _ = resolve_plan(run, plan)
        resolved = {(item, str(row['timestamp'])[:10]): float(row['mean'])
                    for item, series in adjusted['series'].items() if item != '__all__'
                    for row in series.get('forecast', [])}
        # Latest approval is authoritative after a plan was reopened/re-approved.
        approvals = [h.get('at') for h in plan.get('history', []) if h.get('status') == 'approved']
        approval = approvals[-1] if approvals else None
    rows, issues, seen = [], [], set()
    for source in table['rows']:
        values, number = source['values'], source['source_row']
        item = text_value(values.get(mapping['item_id']))
        raw_date = values.get(mapping['timestamp'])
        # Explicit calendar only; numeric Excel date guesses are unsafe.
        try:
            period = input_date(raw_date, calendar).isoformat()
        except (ValueError, TypeError):
            issues.append({'row': number, 'cell': f'{mapping["timestamp"]}{number}', 'message': 'Use a period-start date in YYYY-MM-DD format.'})
            continue
        key = (item, period)
        if key in seen:
            issues.append({'row': number, 'cell': f'{mapping["item_id"]}{number}', 'message': 'This item and period are repeated. Supply one actual total per item and period.'})
            continue
        seen.add(key)
        if key not in expected:
            issues.append({'row': number, 'cell': f'{mapping["item_id"]}{number}', 'message': 'Item or period does not match a closed period in this forecast. Use exact item IDs and period-start dates.'})
            continue
        try:
            value = values.get(mapping['actual'])
            if isinstance(value, bool):
                raise ValueError()
            actual = float(numeric(value))
            if not math.isfinite(actual) or actual < 0:
                raise ValueError()
        except (ValueError, TypeError):
            issues.append({'row': number, 'cell': f'{mapping["actual"]}{number}', 'message': 'Actual quantity must be finite and nonnegative. Missing values and returns are not zero demand.'})
            continue
        item_meta = run.get('metadata', {}).get(item, {})
        rows.append({'item_id': item, 'period': period, 'period_label': month_label(period, basis) if frequency=='monthly' else period,
                     'planning_calendar': basis, 'actual': actual,
                     'forecast': forecast[key]['forecast'], 'approved': resolved.get(key),
                     'horizon_step': forecast[key]['step'], 'source_row': number,
                     'source_cell': f'{mapping["actual"]}{number}',
                     'prospective': before_period(run.get('issued_at'), period, zone),
                     'plan_eligible': bool(plan and before_period(approval, period, zone)),
                     'category': item_meta.get('category') or 'Unspecified',
                     'customer': item_meta.get('customer') or 'Unspecified'})
    missing = sorted(expected - {(r['item_id'], r['period']) for r in rows})
    prospective = [r for r in rows if r['prospective']]
    # A paired plan comparison must use only periods approved before they started.
    paired = [r for r in prospective if r['plan_eligible']]
    baseline, approved = score(paired), score(paired, 'approved')
    improvement = None if baseline['wape_pct'] is None or approved['wape_pct'] is None else baseline['wape_pct'] - approved['wape_pct']
    breakdowns = {}
    for dimension in ('item_id', 'period', 'horizon_step', 'category', 'customer'):
        groups = defaultdict(list)
        for row in rows:
            groups[row[dimension]].append(row)
        breakdowns[dimension] = [{'key': key, **score(group)} for key, group in sorted(groups.items())]
    warnings = []
    formula_count = sum(row['source_cell'] in table.get('formulas', {}) for row in rows)
    if formula_count:
        warnings.append(f'{formula_count} actual quantities use saved Excel formula results. Confirm the workbook was recalculated before export.')
    if missing:
        warnings.append(f'{len(missing)} item-period results are missing. They are excluded, not treated as zero.')
    if len(prospective) != len(rows):
        warnings.append('Some forecasts were issued after a period began, or have no recorded issue time. Their errors are diagnostic only, not forward-looking accuracy evidence.')
    if plan and len(paired) != len(rows):
        warnings.append('Plan improvement is measured only where both forecast issue and plan approval predate the period. Late or undated approvals are excluded.')
    if classification == 'synthetic_sample':
        warnings.append('Sample results demonstrate the workflow, not operational forecast accuracy.')
    return {'run_id': run['run_id'], 'unit': unit, 'frequency': frequency, 'planning_calendar': basis, 'closed_through': closed.isoformat(),
            'classification': classification, 'rows': rows, 'issues': issues[:100], 'issue_count': len(issues),
            'coverage': {'expected': len(expected), 'matched': len(rows), 'missing': len(missing),
                         'pct': len(rows) / len(expected) * 100, 'missing_keys': [{'item_id': i, 'period': p} for i, p in missing[:100]]},
            'diagnostic': score(rows), 'prospective': score(prospective),
            'paired_baseline': baseline, 'paired_approved': approved, 'improvement_points': improvement,
            'breakdowns': breakdowns, 'warnings': warnings,
            'plan': {'id': plan['id'], 'name': plan['name'], 'approved_at': approval} if plan else None}


class ActualsStore:
    def __init__(self, path, sources):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.sources = sources
        self.engine = create_engine(f'sqlite:///{path}')
        metadata = MetaData()
        self.table = Table('actual_evaluations', metadata, Column('id', String, primary_key=True),
                           Column('run_id', String, index=True), Column('created_at', String), Column('payload', JSON))
        metadata.create_all(self.engine)

    def inspect(self, config, run, plan=None):
        source, content = self.sources.source(config['source_id'])
        if source['role'] != 'actuals':
            raise ValueError('Choose an actual-results source, not a training or stock file.')
        table = raw_table(source['name'], content, config.get('sheet'), config.get('header_row', 1))
        report = evaluate_actuals(run, table, config, plan)
        report['source'] = {key: source[key] for key in ('id', 'name', 'sha256')}
        report['source'].update(sheet=table['sheet'], header_row=table['header_row'])
        return report

    def save(self, config, run, plan=None):
        report = self.inspect(config, run, plan)
        if report['issue_count'] or not report['rows']:
            raise ValueError('Resolve the actual-results issues before saving.')
        if not config.get('reviewed') or not str(config.get('owner', '')).strip():
            raise ValueError('Name the reviewer and confirm the closed dates, units and quantities.')
        if report['coverage']['missing'] and not config.get('accept_partial'):
            raise ValueError('Confirm the missing results before saving a partial comparison.')
        try:
            key = uuid.UUID(config['request_id']).hex if config.get('request_id') else uuid.uuid4().hex
        except (ValueError, AttributeError) as exc:
            raise ValueError('Invalid save request identifier. Reopen the import before retrying.') from exc
        now = datetime.now(timezone.utc).isoformat()
        row = {'id': key, 'created_at': now, 'config': config, 'run_sha256': digest(run),
               'plan_sha256': digest(plan) if plan else None, **report}
        try:
            with self.engine.begin() as conn:
                conn.execute(self.table.insert().values(id=key, run_id=run['run_id'], created_at=now, payload=row))
        except IntegrityError:
            existing = self.get(key)
            if any(existing.get(field) != row.get(field) for field in ('config', 'run_sha256', 'plan_sha256')):
                raise ValueError('That save request already belongs to different inputs. Review and save a new version.')
            return existing
        return row

    def list(self, run_id):
        with self.engine.connect() as conn:
            rows = conn.execute(select(self.table.c.payload).where(self.table.c.run_id == run_id).order_by(self.table.c.created_at.desc())).scalars()
            return [{key: value for key, value in row.items() if key not in {'rows', 'breakdowns', 'config'}} for row in rows]

    def get(self, key):
        with self.engine.connect() as conn:
            row = conn.execute(select(self.table.c.payload).where(self.table.c.id == key)).scalar()
        if row is None:
            raise ValueError('Saved actual-results comparison not found.')
        return row

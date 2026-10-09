"""Read-only daily decisions derived from saved evidence, not invented scores."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import math
import hashlib
import json


def build_today(run, plans, site, *, plan=None, operations=None, operations_error=None, now=None):
    today = (now or datetime.now(ZoneInfo(site.get('timezone', 'Asia/Tehran')))).date()
    result = {'date': today.isoformat(), 'site': site, 'decisions': [], 'activity': [],
              'context': None, 'metrics': {}}
    if not run:
        result['decisions'] = [{'id':'start', 'title':'Add your sales or demand history',
            'detail':'Import actual quantities to create the first forecast.', 'kind':'data',
            'action':{'page':'data', 'import':True}, 'priority':0}]
        return result
    classification = run.get('source_classification', 'unknown')
    if run.get('site', {}).get('id') != site.get('id'):
        raise ValueError('Choose a forecast for the current site.')
    scoped = [p for p in plans if p.get('run_id') == run['run_id']
              and p.get('site_id') == site.get('id')
              and p.get('settings', {}).get('source_classification', 'unknown') == classification]
    if plan and plan not in scoped:
        raise ValueError('Choose a plan from this forecast, site and data source.')
    if plan and plan['status'] not in {'approved', 'published'}:
        raise ValueError('Daily supply decisions need an approved or published plan.')
    frequency = run.get('run_settings', {}).get('frequency')
    result['context'] = {'run_id':run['run_id'], 'name':plan['name'] if plan else run.get('dataset_name', 'Forecast'),
        'plan_id':plan['id'] if plan else None, 'status':plan['status'] if plan else 'forecast',
        'frequency':frequency, 'unit':run.get('unit'), 'source_classification':classification,
        'last_actual_period':run.get('summary', {}).get('end'), 'issued_at':run.get('issued_at')}
    decisions = result['decisions']
    def add(key, title, detail, kind, action, priority=1, **extra):
        decisions.append(dict(id=key, title=title, detail=detail, kind=kind, action=action, priority=priority, **extra))
    metrics = run.get('metrics', {})
    verified = metrics.get('independent_accuracy_verified') is True
    error = metrics.get('wape_pct')
    result['metrics']['historical_error_pct'] = error if verified and isinstance(error, (int,float)) and math.isfinite(error) else None
    if not verified or metrics.get('evidence_level') == 'limited':
        add('evidence', 'Check forecast evidence', 'No reliable separate accuracy check is available for this outlook.',
            'forecast', {'page':'forecast', 'tab':'accuracy'}, 0)
    if frequency == 'monthly' and run.get('summary', {}).get('end'):
        last = date.fromisoformat(run['summary']['end'][:10])
        missing = (today.year-last.year)*12+today.month-last.month-1
        if missing > 0:
            add('history', f'{missing} completed month{"s" if missing != 1 else ""} after the last actual',
                'Check whether newer actual quantities are available. This does not use a factory reporting deadline.',
                'data', {'page':'data'}, 0)
    for saved in scoped:
        if saved['status'] == 'review':
            add('review:'+saved['id'], 'Review '+saved['name'], 'Check quantities and change reasons before approving.',
                'review', {'page':'plans', 'plan_id':saved['id']}, 0, owner=saved.get('owner'))
        for event in saved.get('history', []):
            result['activity'].append({'plan_id':saved['id'], 'plan_name':saved['name'],
                'actor':event.get('actor'), 'note':event.get('note'), 'at':event.get('at')})
    result['activity'] = sorted(result['activity'], key=lambda row:row.get('at') or '', reverse=True)[:5]
    if not scoped:
        add('save', 'Save a plan for review', 'Keep this forecast with an owner and a review history.',
            'review', {'page':'forecast', 'tab':'outlook', 'save':True}, 2)
    if operations is None or not operations.get('source'):
        result['metrics'].update(materials_at_risk=None, constrained_lines=None)
        add('operations', 'Supply checks unavailable', operations_error or 'Add production and material inputs to check this outlook.',
            'data', {'page':'data'}, 1)
    else:
        material_risks = [r for r in operations.get('materials', []) if r.get('status') == 'shortage']
        capacity_risks = [r for r in operations.get('capacity', []) if r.get('status') == 'bottleneck']
        result['metrics'].update(materials_at_risk=len({r['material_id'] for r in material_risks}) if operations.get('materials') else None,
                                 constrained_lines=len({r['production_line'] for r in capacity_risks}) if operations.get('capacity') else None)
        for kind in ('materials', 'capacity'):
            if not operations.get(kind):
                add('missing:'+kind, f'{kind.capitalize()} checks unavailable',
                    'The selected inputs contain no calculated rows for this check.', 'data', {'page':'data'})
        for kind, rows, key, name in [('materials',material_risks,'material_id','material_name'),
                                     ('capacity',capacity_risks,'production_line','production_line')]:
            # One decision per material/line, pointing at the earliest affected period.
            groups = {}
            for row in sorted(rows, key=lambda r:r['period']):
                groups.setdefault(row[key], []).append(row)
            for identifier, group in groups.items():
                row = group[0]
                quantity = row['shortage'] if kind == 'materials' else -row['gap_quantity']
                unit = row.get('unit') if kind == 'materials' else row.get('capacity_unit')
                detail = (f'{quantity:,.1f} {unit} below the stock target' if kind == 'materials'
                          else f'{quantity:,.1f} {unit} above available capacity')
                add(kind+':'+identifier, row[name], detail, kind,
                    {'page':'supply', 'tab':kind, 'period':row['period'], 'search':row[name]},
                    1, period=row['period'], affected_periods=len(group),
                    source_signature=hashlib.sha256(json.dumps(group,sort_keys=True,default=str).encode()).hexdigest())
    for item, diagnostic in run.get('series_diagnostics', {}).items():
        reasons = []
        if diagnostic.get('structural_break_suspected'): reasons.append('The recent demand pattern changed.')
        if diagnostic.get('stockout_or_lost_sales_suspected'): reasons.append('Zero-sales periods may need checking; lost sales are not confirmed.')
        if reasons:
            add('pattern:'+item, 'Check '+item, ' '.join(reasons), 'forecast',
                {'page':'forecast', 'tab':'outlook', 'item':item}, 2)
    decisions.sort(key=lambda row:(row['priority'], row.get('period', ''), row['id']))
    return result

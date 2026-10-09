"""Reviewed factor observations. Importing never changes a forecast or order book."""
from datetime import date, datetime, timezone
import hashlib
import json
import os
import tempfile
import uuid

from .inventory import raw_table, inventory_preview
from . import factor_normalization as normalization


LIMITATION = ('Publication dates are supplied by the uploader, not independently verified. '
              'Saved for review only; linking to forecasts requires a separate reviewed step.')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def iso_date(value):
    if isinstance(value, datetime):
        if value.time().isoformat() != '00:00:00':
            raise ValueError('Use dates without times.')
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or len(value.strip()) != 10:
        raise ValueError('Use Gregorian YYYY-MM-DD dates or Excel date cells.')
    return date.fromisoformat(value.strip())


def source_table(datasets, payload, *, preview=False):
    source, content = datasets.source(payload.get('source_id'))
    if source['role'] != 'factor_observations':
        raise ValueError('Upload this file as factor observations, not sales history.')
    parser = inventory_preview if preview else raw_table
    table = parser(source['name'], content, payload.get('sheet') or source.get('sheet'), payload.get('header_row', 1))
    return source, table


def review_import(datasets, payload, *, today=None):
    today = today or datetime.now(timezone.utc).date()
    source, table = source_table(datasets, payload)
    config = {key: payload.get(key) for key in ('source_id', 'sheet', 'header_row', 'mapping', 'name',
              'unit', 'geography', 'provider', 'frequency', 'classification', 'parent_id')}
    config.update(normalization.convention(payload))
    calendar=config.get('calendar','gregorian')
    config['unit']=normalization.unit(config)
    for key in ('name', 'unit', 'geography', 'provider'):
        value = config[key]
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError(f'Enter {key} (up to 200 characters).')
        config[key] = value.strip()
    frequency = config['frequency']
    if frequency not in {'daily', 'monthly', 'annual'}:
        raise ValueError('Choose daily, monthly or annual observations.')
    if config['classification'] not in {'user_provided', 'synthetic_sample'}:
        raise ValueError('Identify real data or a demonstration sample.')
    mapping = config['mapping']
    columns = {col['id']: col['label'] for col in table['columns']}
    if (not isinstance(mapping, dict) or set(mapping) != {'period', 'value', 'available_at'}
            or any(not isinstance(v, str) or v not in columns for v in mapping.values())
            or len(set(mapping.values())) != 3):
        raise ValueError('Match three different columns: period, value and publication date.')
    points, issues, seen = [], [], set()
    for row in table['rows']:
        number, values = row['source_row'], row['values']
        try:
            period = normalization.input_date(values[mapping['period']],calendar)
            released = normalization.input_date(values[mapping['available_at']],calendar)
            if period > today or released > today:
                raise ValueError('Future dates belong in scenario assumptions, not historical observations.')
            if released < period:
                raise ValueError('Publication date cannot precede the observation period end.')
            start=normalization.period_bounds(period,frequency,calendar)
            raw = values[mapping['value']]
            value = normalization.normalized_value(raw,config)
            identity = (period, released)
            if identity in seen:
                raise ValueError('Repeated period and publication date. Keep one value for each release.')
            seen.add(identity)
            if any(f'{column}{number}' in table['formulas'] for column in mapping.values()):
                raise ValueError('Export mapped formulas as confirmed values before importing.')
            # Date-only releases become eligible at the end of the declared local day.
            points.append({'period': period.isoformat(), 'value': value,
                           'period_start':start.isoformat(),
                           'available_at':normalization.released_at(released,config.get('publication_timezone','UTC')),
                           'publication_date': released.isoformat(), 'source_row': number,
                           'original_period':str(values[mapping['period']]),
                           'original_publication_date':str(values[mapping['available_at']]),
                           'original_value':str(raw)})
        except (ValueError, TypeError, OverflowError) as exc:
            issues.append({'row': number, 'message': str(exc) or 'Enter a valid date and numeric value.'})
    if not table['rows']:
        issues.append({'row': None, 'message': 'No observations found.'})
    points.sort(key=lambda row: (row['period'], row['available_at']))
    periods = sorted({point['period'] for point in points})
    gaps = normalization.period_gaps(periods,frequency,calendar)
    fingerprint = digest({'config': config, 'source_hash': source['sha256'], 'columns': columns})
    return {'config': config, 'source': {key: source[key] for key in ('id', 'name', 'sha256', 'created_at')},
            'columns': columns, 'points': points, 'issues': issues[:100], 'issue_count': len(issues),
            'review_token': fingerprint, 'limitation': LIMITATION, 'normalization':normalization.summary(config),
            'summary': {'observations': len(periods), 'revisions': len(points) - len(periods),
                        'first_period': periods[0] if periods else None, 'last_period': periods[-1] if periods else None,
                        'days_since_last_period': (today - date.fromisoformat(periods[-1])).days if periods else None,
                        'gap_count': len(gaps), 'gaps': gaps[:24], 'checked_on': today.isoformat()}}


def save_import(datasets, factors, payload):
    if payload.get('reviewed') is not True:
        raise ValueError('Review the observations and source details before saving.')
    try:
        request_id = str(uuid.UUID(payload.get('request_id', '')))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Use a valid save request identifier.')
    review = review_import(datasets, payload)
    if review['issue_count'] or payload.get('review_token') != review['review_token']:
        raise ValueError('Review these exact inputs again and resolve all row errors before saving.')
    config = review['config']
    parent = factors.get(config['parent_id']) if config.get('parent_id') else None
    if parent:
        if parent.get('kind') != 'imported_observations':
            raise ValueError('Choose an imported factor version to update.')
        for key in ('name', 'unit', 'geography', 'provider', 'frequency', 'classification'):
            if parent.get(key) != config[key]:
                raise ValueError('Updates must keep the same factor, unit, location, source and frequency. Import a separate factor instead.')
        old=parent['import_config']
        if (old.get('calendar','gregorian')!=config.get('calendar','gregorian') or
                old.get('publication_timezone','UTC')!=config.get('publication_timezone','UTC') or
                old.get('factor_details')!=config.get('factor_details')):
            raise ValueError('Updates must keep the same calendar, release timezone and factor definition. Import separately.')
        # Position alone is not proof of the same field after a file replacement.
        for field, column in config['mapping'].items():
            old_label = parent['column_labels'][parent['import_config']['mapping'][field]]
            if review['columns'][column] != old_label:
                raise ValueError('The replacement headings changed. Import separately and review its new mapping.')
    key = uuid.uuid5(uuid.NAMESPACE_URL, 'demand-factor-import:' + request_id).hex
    fingerprint = review['review_token']
    snapshot = {**{k: config[k] for k in ('name', 'unit', 'geography', 'provider', 'frequency', 'classification')},
                'id': key, 'factor_id': parent['factor_id'] if parent else 'import:' + key,
                'kind': 'imported_observations', 'captured_at': datetime.now(timezone.utc).isoformat(),
                'sha256': review['source']['sha256'], 'source': review['source'],
                'parent_id': config.get('parent_id'), 'import_config': config, 'column_labels': review['columns'],
                'calendar':config.get('calendar','gregorian'),
                'normalization':review['normalization'],
                'points': review['points'], 'summary': review['summary'], 'save_fingerprint': fingerprint,
                'availability_basis': 'uploader_declared_release_dates', 'release_dates_verified': False,
                'use': 'context_only', 'limitation': LIMITATION}
    target = factors.root / f'{key}.json'
    # Publish without overwriting, including simultaneous requests from workers.
    with factors.lock:
        fd, temporary = tempfile.mkstemp(dir=factors.root, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(snapshot, stream, ensure_ascii=False, allow_nan=False)
            try:
                os.link(temporary, target)
            except FileExistsError:
                existing = factors.get(key)
                if existing.get('save_fingerprint') != fingerprint:
                    raise ValueError('This save request was already used for different inputs.')
                return existing
        finally:
            os.unlink(temporary)
    return snapshot


def freshness(snapshot, *, today=None):
    """Age observations, not download time; thresholds are review guidance only."""
    today=today or datetime.now(timezone.utc).date()
    latest=snapshot.get('summary',{}).get('last_period')
    if not latest:
        return {'status':'unknown','latest_period':None,'checked_on':today.isoformat()}
    day=date.fromisoformat(latest)
    days=(today-day).days
    allowance={'daily':7,'monthly':62,'annual':550}[snapshot['frequency']]
    return {'status':'behind' if days>allowance else 'recent','latest_period':latest,
            'days_since_last_period':days,'checked_on':today.isoformat(),
            'rule':f'Review if the latest observation ended more than {allowance} days ago; not a provider release deadline.'}

"""Read the NY Fed's published vintage matrix; never invent release days."""
import csv
from datetime import datetime
from io import StringIO
import math
import hashlib

import pandas as pd


DATA_URL = 'https://www.newyorkfed.org/medialibrary/research/interactives/data/gscpi/gscpi_interactive_data.csv'
DEFINITION = {
    'id': 'global_supply_pressure',
    'name': 'Global Supply Chain Pressure Index (GSCPI)',
    'provider': 'Federal Reserve Bank of New York',
    'geography': 'Global · not Iran-specific', 'frequency': 'monthly',
    'unit': 'Standard deviations from historical average',
    'source_url': 'https://www.newyorkfed.org/research/policy/gscpi',
    'license': 'NY Fed Terms of Use · attribution required',
    'license_url': 'https://www.newyorkfed.org/privacy/termsofuse',
    'attribution': 'Federal Reserve Bank of New York, Global Supply Chain Pressure Index, https://www.newyorkfed.org/research/policy/gscpi.',
    'description': 'Global shipping and manufacturing pressure. Higher values mean more pressure, not higher sales.',
    'release_schedule': 'Monthly, fourth business day; publication may be delayed.',
}


def parse_supply_pressure(content: bytes, captured: str, *, include_archive=False) -> dict:
    """Strict schema with only the latest vintage exposed as current observations.

    All vintage columns remain in the retained raw response. Their month labels
    do not prove a publication day, so current points use local capture time.
    """
    rows = list(csv.reader(StringIO(content.decode('utf-8-sig'))))
    if not rows or rows[0][0:1] != ['Date'] or len(rows[0]) < 2:
        raise ValueError('The supply-pressure source format changed. No snapshot was saved.')
    headers = rows[0][1:]
    try:
        vintages = [pd.Timestamp(datetime.strptime(value, '%b-%y')) for value in headers]
    except ValueError as exc:
        raise ValueError('Invalid supply-pressure vintage months.') from exc
    now = pd.Timestamp(captured).tz_convert('UTC').tz_localize(None)
    if (len(set(vintages)) != len(vintages) or vintages != sorted(vintages)
            or any(v.year < 1997 or v > now for v in vintages)):
        raise ValueError('Invalid or duplicate supply-pressure vintage months.')
    points, archive = [], []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(rows[0]):
            raise ValueError('The supply-pressure row has unexpected columns.')
        try:
            period = pd.Timestamp(datetime.strptime(row[0], '%d-%b-%Y'))
        except ValueError as exc:
            raise ValueError('Invalid supply-pressure observation date.') from exc
        if not period.is_month_end or period.year < 1997 or period >= vintages[-1]:
            raise ValueError('Invalid or future supply-pressure observation month.')
        for index, cell in enumerate(row[1:]):
            if cell in ('', '#N/A'):
                continue
            try:
                value = float(cell)
            except ValueError as exc:
                raise ValueError('Invalid supply-pressure value.') from exc
            if not math.isfinite(value) or period >= vintages[index]:
                raise ValueError('Invalid value or observation after its vintage month.')
            if include_archive:
                # Explicit conservative assumption, NOT a verified release timestamp.
                available = vintages[index].to_period('M').end_time.floor('us').tz_localize('UTC')
                if available <= pd.Timestamp(captured):
                    archive.append({'period': period.date().isoformat(), 'value': value,
                        'available_at': available.isoformat(), 'publication_date': None,
                        'availability_date': available.date().isoformat(),
                        'vintage_month': vintages[index].strftime('%Y-%m')})
        if row[-1] in ('', '#N/A'):
            raise ValueError('The latest supply-pressure vintage has a missing value.')
        points.append({'period': period.date().isoformat(), 'value': float(row[-1]),
                       'available_at': captured})
    periods = sorted(point['period'] for point in points)
    if not periods or len(set(periods)) != len(periods):
        raise ValueError('No supply-pressure observations or duplicate months.')
    expected = pd.period_range(periods[0], periods[-1], freq='M')
    if len(expected) != len(periods):
        raise ValueError('The supply-pressure source has a gap in its monthly history.')
    if pd.Timestamp(periods[-1]) + pd.offsets.MonthBegin(1) != vintages[-1]:
        raise ValueError('The latest supply-pressure observation does not match its vintage.')
    return {**({'archive_points': archive} if include_archive else {}),
            'points': sorted(points, key=lambda p: p['period']),
            'provider_vintage_month': vintages[-1].strftime('%Y-%m'),
            'vintage_months': [v.strftime('%Y-%m') for v in vintages],
            'provider_updated_at': None}


VINTAGE_POLICY = ('Past NY Fed versions are treated as available after their labelled month ended '
    '(UTC). This is a conservative timing assumption, not independently verified publication '
    'dates. Later revisions and versions after the forecast cutoff are excluded. Historical '
    'test predictions hold the last training factor value; unknown future values require your '
    'explicit assumption. Global supply pressure is not a direct measure of Iranian sales.')


def is_public_vintage(snapshot):
    return (snapshot.get('kind') == 'public_observations'
            and snapshot.get('factor_id') == DEFINITION['id']
            and snapshot.get('frequency') == 'monthly'
            and snapshot.get('classification') == 'real')


def archived_points(store, snapshot):
    """Use the validated retained response, not caller-provided paths or points."""
    identifier = snapshot['id']
    if not is_public_vintage(snapshot) or len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
        raise ValueError('Choose a supported public vintage snapshot.')
    path = store.root / 'raw' / f'{identifier}.csv'
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('The retained public-source response is missing or too large. Fetch it again.')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != snapshot['sha256']:
        raise ValueError('The retained public-source response no longer matches its snapshot.')
    return parse_supply_pressure(content, snapshot['captured_at'], include_archive=True)['archive_points']


def freshness(snapshot: dict, now=None) -> dict:
    """A transparent grace rule, not a claim about the provider's exact release day."""
    current = pd.Timestamp(now or datetime.now().astimezone()).tz_convert('UTC')
    latest = pd.Timestamp(snapshot['points'][-1]['period'])
    age = (current.year - latest.year) * 12 + current.month - latest.month
    return {'status': 'behind' if age > 2 else 'recent', 'latest_period': latest.date().isoformat(),
            'rule': 'Review if the latest observation is more than two calendar months behind today.'}

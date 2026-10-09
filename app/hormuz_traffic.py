"""Licensed provider-owned AIS counts; never use bundled IMF PortWatch fields."""
import calendar
from datetime import date
import json
import math

import pandas as pd

ENDPOINT = 'https://hormuz.now/api/daily.json'
DOCS = 'https://hormuz.now/data'
FACTOR_ID = 'hormuz_visible_crossings'
UNIT = 'AIS-visible commercial crossings/day'
NAME = 'Hormuz ship traffic'
LIMITATION = ('AIS-visible commercial crossings, not cargo tonnes or Iranian customer demand. '
              'Ships without AIS may be missed. Legacy/mixed days use reconstructed tracking; '
              'counts and classifications can be revised. Short history may not cover your sales '
              'periods. Only complete UTC months are averaged; no missing days are filled.')


def parse_traffic(content, captured):
    """Validate original or retained projection, preserving the provider's own counts."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('The shipping response contains duplicate fields.')
            result[key] = value
        return result
    try:
        payload = json.loads(content, object_pairs_hook=unique)
        stamp = pd.Timestamp(captured)
        if stamp.tzinfo is None:
            raise ValueError('The shipping capture time needs a time zone.')
        stamp = stamp.tz_convert('UTC')
        generated = payload['generatedAt']
        if isinstance(generated, bool) or not isinstance(generated, (int, float)) or not math.isfinite(generated):
            raise ValueError('The shipping source update time is invalid.')
        updated = pd.Timestamp(generated, unit='ms', tz='UTC')
        if updated > stamp + pd.Timedelta(minutes=5) or updated < pd.Timestamp('2026-04-20', tz='UTC'):
            raise ValueError('The shipping source update time is invalid.')
        definition = payload['definition']
        if not isinstance(definition, str) or not all(s in definition for s in ('Distinct commercial', 'UTC day', 'per direction', 'Musandam')):
            raise ValueError('The shipping counting definition changed. Review the source before using it.')
        if 'CC BY 4.0' not in payload['license'] or 'hormuz.now' not in payload['license']:
            raise ValueError('The shipping source no longer declares its expected licence.')
        rows = payload['days']
        if not isinstance(rows, list) or not 1 <= len(rows) <= 10_000:
            raise ValueError('The shipping history is missing or too large.')
        selected, points, seen = [], [], set()
        for row in rows:
            period = row['date']
            day = date.fromisoformat(period)
            if day.isoformat() != period or day < date(2026, 4, 20) or day > updated.date() or period in seen:
                raise ValueError('The shipping history contains invalid, future or duplicated days.')
            seen.add(period)
            counts = {}
            for key in ('in', 'out', 'total', 'tankers'):
                value = row[key]
                if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
                    raise ValueError('The shipping history contains invalid vessel counts.')
                counts[key] = value
            if counts['total'] != counts['in'] + counts['out'] or counts['tankers'] > counts['total']:
                raise ValueError('The shipping counts do not reconcile.')
            source = row['source']
            partial = row.get('partial', False)
            if source not in ('live', 'legacy', 'mixed') or not isinstance(partial, bool):
                raise ValueError('The shipping history has an unknown coverage flag.')
            # A UTC day still in progress cannot be treated as complete, even if
            # the upstream partial flag is absent.
            partial = partial or day >= updated.date() or day >= stamp.date()
            selected.append({'date': period, **counts, 'source': source, 'partial': partial})
            if not partial:
                points.append({'period': period, 'value': float(counts['total']),
                               'available_at': captured, 'tracking_basis': source})
        if not points:
            raise ValueError('No complete shipping days are available. No snapshot was saved.')
        points.sort(key=lambda p: p['period'])
        selected.sort(key=lambda p: p['date'])
        # The endpoint bundles IMF fields under separate terms. Discard them,
        # including IMF baselines, calibrated averages and political status.
        retained = {'definition': definition, 'generatedAt': generated,
                    'license': 'CC BY 4.0 — hormuz.now (provider-owned counts only)', 'days': selected}
        return points, retained, updated.isoformat()
    except (KeyError, TypeError, OverflowError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('The shipping response format changed. No snapshot was saved.') from exc


def monthly_traffic(points):
    months = {}
    for point in points:
        months.setdefault(point['period'][:7], []).append(point)
    output, incomplete = [], []
    for month, rows in sorted(months.items()):
        year, number = map(int, month.split('-'))
        days = calendar.monthrange(year, number)[1]
        if len(rows) != days or len({r['period'] for r in rows}) != days:
            incomplete.append({'month': month, 'observed_days': len(rows), 'expected_days': days})
            continue
        reconstructed = sum(p['tracking_basis'] != 'live' for p in rows)
        output.append({'period': f'{month}-{days:02d}', 'value': math.fsum(p['value'] for p in rows) / days,
                       'available_at': max(p['available_at'] for p in rows),
                       'observed_days': days, 'expected_days': days, 'reconstructed_days': reconstructed})
    return output, {'aggregation': 'Mean provider-owned AIS-visible crossings per complete UTC day in a Gregorian month',
                    'coverage_policy': 'All calendar days required; partial days and incomplete months excluded; no gap filling',
                    'calendar': 'gregorian', 'time_standard': 'UTC',
                    'incomplete_months': incomplete, 'limitation': LIMITATION}

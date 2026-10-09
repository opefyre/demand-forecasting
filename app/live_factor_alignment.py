"""Turn retained live observations into complete, auditable monthly inputs.

Downloaded revised history is usable only in an explicitly reviewed sensitivity
scenario, never as proof of historical forecast accuracy.
"""
import hashlib
import json
import math

import pandas as pd

from .commodity_prices import parse_prices, SERIES
from .hormuz_traffic import FACTOR_ID as HORMUZ_FACTOR, UNIT as HORMUZ_UNIT, NAME as HORMUZ_NAME, parse_traffic, monthly_traffic
from .iran_cpi import FACTOR_ID as CPI_FACTOR, UNIT as CPI_UNIT, NAME as CPI_NAME, parse_cpi, LIMITATION as CPI_LIMITATION

WHAT_IF_POLICY = ('What-if only: historical observations were downloaded later, and original '
                  'release dates are unverified. Use a user-chosen factor-aware method; '
                  'accuracy scores and planning ranges are withheld. Future observations '
                  'must have been captured before the forecast starts at Tehran midnight; otherwise provide '
                  'an explicit assumption. No missing months are filled. A change in the '
                  'forecast does not prove that the factor caused a change in demand.')
FACTOR_METHODS = ('Ridge + drivers', 'Elastic Net + drivers', 'Histogram gradient boosting',
                  'LightGBM + drivers', 'Random forest', 'Extra trees')


def is_live_monthly(snapshot):
    return (snapshot.get('kind') == 'public_observations' and
            ((snapshot.get('live_source') == 'commodities' and
              snapshot.get('factor_id') in {'worldbank_' + key for key in SERIES}) or
             (snapshot.get('live_source') == 'servix' and snapshot.get('factor_id') == 'servix_usd_rls') or
             (snapshot.get('live_source') == 'hormuz' and snapshot.get('factor_id') == HORMUZ_FACTOR) or
             (snapshot.get('live_source') == 'iran_cpi' and snapshot.get('factor_id') == CPI_FACTOR)))


def monthly_points(store, snapshot):
    """Verify retained content; use observed-day FX means, not intraday weighting."""
    if not is_live_monthly(snapshot):
        raise ValueError('This live source does not provide supported monthly forecast inputs.')
    path = (store.root / snapshot.get('raw_response', '')).resolve()
    if path.parent != (store.root / 'raw').resolve():
        raise ValueError('Invalid retained live-source file.')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != snapshot.get('sha256'):
        raise ValueError('The retained live-source file no longer matches its snapshot.')
    captured = snapshot['captured_at']
    if snapshot['live_source'] == 'iran_cpi':
        points = parse_cpi(content, captured)
        if ([(p['period'], p['value']) for p in points] != [(p['period'], p['value']) for p in snapshot['points']]
                or snapshot['unit'] != CPI_UNIT or snapshot['name'] != CPI_NAME):
            raise ValueError('The inflation observations, name or units no longer match the retained source.')
        return points, {'aggregation': 'Published headline CPI index, 2021 = 100',
                        'coverage_policy': 'Exact completed Gregorian source months; no interpolation',
                        'calendar': 'gregorian', 'limitation': CPI_LIMITATION}
    if snapshot['live_source'] == 'hormuz':
        points, _, _ = parse_traffic(content, captured)
        if ([(p['period'], p['value'], p['tracking_basis']) for p in points] !=
                [(p['period'], p['value'], p['tracking_basis']) for p in snapshot['points']]
                or snapshot['unit'] != HORMUZ_UNIT or snapshot['name'] != HORMUZ_NAME):
            raise ValueError('The shipping observations, name or units no longer match the retained source.')
        # Snapshot metadata cannot supply unverified monthly values.
        return monthly_traffic(points)
    if snapshot['live_source'] == 'commodities':
        key = snapshot['factor_id'].removeprefix('worldbank_')
        parsed = parse_prices(content, captured)[key]
        if parsed['unit'] != snapshot['unit'] or parsed['name'] != snapshot['name']:
            raise ValueError('The live commodity name or unit changed.')
        expected = [(p['period'], p['value']) for p in parsed['points']]
        if expected != [(p['period'], p['value']) for p in snapshot['points']]:
            raise ValueError('The commodity observations no longer match the retained source.')
        return parsed['points'], {'aggregation': 'Published Gregorian monthly price',
                                 'coverage_policy': 'Exact source months; no interpolation'}
    raw = json.loads(content)
    quotes = raw['retained_quotes']
    if quotes != snapshot['points'] or snapshot['unit'] != 'IRR per USD':
        raise ValueError('The exchange-rate observations or units no longer match the retained source.')
    by_day, seen = {}, set()
    for point in quotes:
        stamp = pd.Timestamp(point['quote_time'])
        available = pd.Timestamp(point['available_at'])
        value = point['value']
        if (stamp.tzinfo is None or available.tzinfo is None or available > pd.Timestamp(captured)
                or stamp > pd.Timestamp(captured) + pd.Timedelta(minutes=5)
                or isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0 or stamp in seen):
            raise ValueError('Invalid or duplicated retained exchange-rate quote.')
        seen.add(stamp)
        day = stamp.tz_convert('Asia/Tehran').date()
        old = by_day.get(day)
        if old is None or stamp > old[0]:
            by_day[day] = (stamp, float(value), available)
    months = {}
    for day, row in by_day.items():
        months.setdefault(pd.Timestamp(day).to_period('M'), []).append(row)
    points = []
    for month, rows in sorted(months.items()):
        end = month.end_time.normalize().date()
        # 80% is an explicit conservative app guardrail, not a provider guarantee.
        coverage = len(rows) / month.days_in_month
        if end >= pd.Timestamp(captured).tz_convert('Asia/Tehran').date() or coverage < .8:
            continue
        points.append({'period': end.isoformat(), 'value': sum(r[1] for r in rows) / len(rows),
                       'available_at': max(r[2] for r in rows).isoformat(),
                       'observed_days': len(rows), 'expected_days': month.days_in_month,
                       'coverage_pct': 100 * coverage})
    return points, {'aggregation': 'Mean of the last quote on each observed Tehran day',
                    'coverage_policy': 'Complete Gregorian months with at least 80% of calendar days observed; missing days are not filled',
                    'quote_basis': snapshot.get('quote_basis'),
                    'calendar': 'gregorian'}

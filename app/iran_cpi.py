"""Pinned official monthly headline CPI; no annual interpolation or mirror fallback."""
import csv
from datetime import date
import io
import math
import re

import pandas as pd

DOCS = 'https://data.imf.org/Datasets/CPI'
TERMS = 'https://www.imf.org/en/About/copyright-and-terms.'
ENDPOINT = 'https://api.imf.org/external/sdmx/2.1/data/IMF.STA,CPI,5.0.0/IRN.CPI._T.IX.M'
FACTOR_ID = 'imf_iran_headline_cpi'
NAME = 'Iran monthly price index'
UNIT = 'CPI index (2021 = 100)'
LIMITATION = ('National household prices, not Tehran-specific prices or physical demand. '
              'Gregorian source months are not Persian months. Original publication times '
              'are unverified; revised history supports reviewed what-if scenarios only. '
              'Permission for automated commercial reuse must be recorded before connection.')


def parse_cpi(content, captured):
    try:
        stamp = pd.Timestamp(captured)
        if stamp.tzinfo is None:
            raise ValueError('The inflation capture time needs a time zone.')
        reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
        required = {'DATAFLOW', 'COUNTRY', 'INDEX_TYPE', 'COICOP_1999', 'TYPE_OF_TRANSFORMATION',
                    'FREQUENCY', 'TIME_PERIOD', 'OBS_VALUE', 'SCALE', 'REFERENCE_PERIOD', 'COMMON_REFERENCE_PERIOD'}
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)) or not required.issubset(reader.fieldnames):
            raise ValueError('The official inflation response format changed.')
        points, seen = [], set()
        for i, row in enumerate(reader):
            if i >= 500 or None in row or any(row[k] is None for k in required):
                raise ValueError('The inflation response has malformed or excessive rows.')
            expected = {'DATAFLOW': 'IMF.STA:CPI(5.0.0)', 'COUNTRY': 'IRN', 'INDEX_TYPE': 'CPI',
                        'COICOP_1999': '_T', 'TYPE_OF_TRANSFORMATION': 'IX', 'FREQUENCY': 'M'}
            if any(row[k] != v for k, v in expected.items()):
                raise ValueError('The provider returned a different country or inflation measure.')
            match = re.fullmatch(r'(20\d{2})-M(0[1-9]|1[0-2])', row['TIME_PERIOD'])
            if not match or row['TIME_PERIOD'] in seen:
                raise ValueError('The inflation series contains invalid or duplicated months.')
            seen.add(row['TIME_PERIOD'])
            month = pd.Period(f'{match[1]}-{match[2]}', freq='M')
            if month.year < 2010 or month.end_time.date() >= stamp.tz_convert('UTC').date():
                raise ValueError('The inflation response includes incomplete or future months.')
            if row['OBS_VALUE'] == '':
                continue  # No forward filling of unreleased observations.
            if row['SCALE'] != '0' or row['REFERENCE_PERIOD'] != '2021A' or row['COMMON_REFERENCE_PERIOD'] not in ('', '2021A'):
                raise ValueError('The inflation scale or base year changed. Review it before using this series.')
            value = float(row['OBS_VALUE'])
            if not math.isfinite(value) or value <= 0:
                raise ValueError('The provider returned an invalid price index.')
            points.append({'period': month.end_time.date().isoformat(), 'value': value, 'available_at': captured})
        if not points:
            raise ValueError('No monthly Iran price-index observations were returned.')
        points.sort(key=lambda p: p['period'])
        return points
    except (UnicodeDecodeError, csv.Error, TypeError, KeyError) as exc:
        raise ValueError('The official inflation response format changed. No snapshot was saved.') from exc


def data_url(today=None):
    today = today or date.today()
    end = (pd.Timestamp(today).to_period('M') - 1).strftime('%Y-%m')
    return f'{ENDPOINT}?startPeriod=2010-01&endPeriod={end}&format=csvfile'

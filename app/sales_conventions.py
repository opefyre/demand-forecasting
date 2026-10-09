"""Reviewed sales meaning and Iran input parsing; source files remain immutable."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from .factor_normalization import input_date, numeric
from persiantools.jdatetime import JalaliDate


def period_start(value, basis='gregorian'):
    value = pd.Timestamp(value).date()
    if basis == 'jalali':
        j = JalaliDate(value)
        return pd.Timestamp(JalaliDate(j.year, j.month, 1).to_gregorian())
    if basis != 'gregorian':
        raise ValueError('Choose Gregorian or Persian planning months.')
    return pd.Timestamp(value.replace(day=1))


def shift_month(value, count=1, basis='gregorian'):
    start = period_start(value, basis)
    if basis == 'gregorian':
        year, month = divmod(start.year * 12 + start.month - 1 + int(count), 12)
        return pd.Timestamp(date(year, month + 1, 1))
    j = JalaliDate(start.date())
    year, month = divmod(j.year * 12 + j.month - 1 + count, 12)
    return pd.Timestamp(JalaliDate(year, month + 1, 1).to_gregorian())


def month_range(start, end=None, periods=None, basis='gregorian'):
    if periods is not None:
        return pd.DatetimeIndex([shift_month(start, i, basis) for i in range(periods)])
    values = []
    point = period_start(start, basis)
    while point <= pd.Timestamp(end):
        values.append(point)
        point = shift_month(point, 1, basis)
    return pd.DatetimeIndex(values)


def month_label(value, basis='gregorian'):
    d = pd.Timestamp(value).date()
    if basis == 'jalali':
        j = JalaliDate(d)
        return f'{j.year:04d}-{j.month:02d}'
    return d.strftime('%Y-%m')


def local_today(zone='Asia/Tehran', now=None):
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError('Use a timezone-aware clock.')
    return instant.astimezone(ZoneInfo(zone)).date()


def dates(values, calendar='gregorian'):
    if calendar not in ('gregorian', 'jalali'):
        raise ValueError('Choose Gregorian or Persian dates.')
    def parse(value):
        try:
            if pd.isna(value):
                return pd.NaT
            # Preserve legacy Excel/ISO Gregorian timestamps, but reject ambiguous
            # timezone-bearing/timed values rather than moving them to another day.
            if calendar == 'gregorian' and isinstance(value, str):
                value = value.strip().replace('/', '-')
                if value.endswith(' 00:00:00') or value.endswith('T00:00:00'):
                    value = value[:10]
            return pd.Timestamp(input_date(value, calendar))
        except (ValueError, TypeError, OverflowError):
            return pd.NaT
    return values.map(parse)


def quantities(values):
    def parse(value):
        try:
            return float(numeric(value))
        except (ValueError, TypeError, OverflowError):
            return float('nan')
    return values.map(parse).astype(float)


def normalize_history(frame, settings):
    """Apply only declared transformations and retain a reconciliation receipt."""
    calendar = settings.get('history_calendar', 'gregorian')
    grain = settings.get('history_grain', 'transactions')
    # The recognized wide client workbook contains monthly totals, not dated
    # transactions. Never distribute those totals across another calendar.
    if frame.attrs.get('wide_forecast_matrix'):
        grain = 'monthly_totals'
    measure = settings.get('sales_measure', 'unspecified')
    policy = settings.get('returns_policy', 'reject')
    if measure not in ('unspecified', 'recorded_sales', 'customer_demand', 'shipped', 'invoiced'):
        raise ValueError('Choose what the sales quantity represents.')
    if grain not in ('transactions', 'monthly_totals'):
        raise ValueError('Choose dated transactions or monthly totals.')
    if policy not in ('reject', 'exclude_returns', 'net_returns'):
        raise ValueError('Choose how reviewed returns should be treated.')
    basis = settings.get('month_basis', 'gregorian')
    if basis not in ('gregorian', 'jalali'):
        raise ValueError('Choose Gregorian or Persian planning months.')
    if settings.get('frequency', 'monthly') != 'monthly' and basis != 'gregorian':
        raise ValueError('Persian planning months apply to monthly forecasts only.')
    if grain == 'monthly_totals' and settings.get('frequency','monthly') != 'monthly':
        raise ValueError('Monthly totals can only support monthly forecasts. Supply dated transactions for daily or weekly forecasts.')
    if grain == 'monthly_totals' and calendar != basis:
        raise ValueError('Monthly totals must use the same calendar as planning months. Import dated transactions to aggregate into another calendar.')
    from .input_corrections import apply_cell_corrections
    out = apply_cell_corrections(frame, settings)
    dc, qc = settings.get('date_col'), settings.get('target_col')
    if dc not in out or qc not in out:
        raise ValueError('Match date and quantity columns first.')
    out[dc] = dates(out[dc], calendar)
    out[qc] = quantities(out[qc])
    if out[dc].isna().any() or out[qc].isna().any():
        raise ValueError('Some dates or quantities are unreadable. Check the selected calendar and numeric values.')
    negative = out[qc] < 0
    receipt = {'sales_measure': measure, 'input_calendar': calendar, 'input_grain': grain,
               'forecast_month_basis': basis, 'returns_policy': policy,
               'source_rows': len(out), 'return_rows': int(negative.sum()),
               'gross_quantity': float(out.loc[~negative, qc].sum()),
               'return_quantity': float(-out.loc[negative, qc].sum()),
               'source_net_quantity': float(out[qc].sum())}
    warnings = []
    if settings.get('history_cell_corrections'):
        warnings.append(f'{len(settings["history_cell_corrections"])} reviewed formatting corrections apply to this input version; original cells are unchanged.')
    if measure == 'unspecified' and 'sales_measure' in settings:
        warnings.append('Sales meaning is not specified. Confirm whether these are requested, shipped or invoiced quantities before operational use.')
    if measure == 'recorded_sales':
        warnings.append('Recorded sales are used as reported. Whether they represent shipments, invoices or unconstrained customer demand is not established.')
    if calendar != basis:
        warnings.append(f'Dated transactions are grouped into {"Persian" if basis == "jalali" else "Gregorian"} planning months; original dates are preserved in the source.')
    if negative.any():
        if policy == 'reject':
            raise ValueError('Review negative quantities and choose a returns policy. They are not silently changed to zero.')
        if measure == 'unspecified':
            raise ValueError('Choose the sales meaning before applying a returns policy.')
        if policy == 'exclude_returns':
            out = out.loc[~negative].copy()
            warnings.append(f'{receipt["return_rows"]} return/correction rows retained in source evidence but excluded from gross sales; demand may differ from net sales.')
        else:
            warnings.append(f'{receipt["return_rows"]} return/correction rows subtract from their own item and period; negative period totals are blocked.')
    if out.empty:
        raise ValueError('No sales remain after the selected returns policy.')
    cc = settings.get('customer_col')
    aliases = settings.get('customer_aliases', {})
    if not isinstance(aliases, dict) or len(aliases)>10000 or any(not isinstance(k, str) or not isinstance(v, str) or not k.strip() or not v.strip() or len(k)>200 or len(v)>200 for k, v in aliases.items()):
        raise ValueError('Customer matches must map a source name to one reviewed customer name.')
    if aliases and cc in out:
        out[cc] = out[cc].map(lambda value: aliases.get(str(value), value))
        receipt['customer_matches'] = aliases
        warnings.append('Reviewed customer-name matches were applied to this input version only.')
    from .sales_groups import customer_product_series, validate_series_identity
    out = customer_product_series(out, settings)
    validate_series_identity(out, settings)
    receipt['series_mode'] = settings.get('series_mode', 'column')
    receipt['model_input_quantity'] = float(out[qc].sum())
    out.attrs.update(frame.attrs)
    out.attrs['sales_conventions'] = receipt
    out.attrs['sales_convention_warnings'] = warnings
    return out, warnings

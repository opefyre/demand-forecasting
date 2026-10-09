"""Unit-aware route loading, not finite-capacity job scheduling."""
from datetime import date, datetime
import math
import pandas as pd
from .units import convert_stock, standard_factor


def product_quantity(quantity, sku, source_unit, target_unit, period, version=None):
    row = {'quantity': quantity, 'sku': sku, 'unit': source_unit, 'source_row': None, 'quality': 'available'}
    converted, evidence = convert_stock(row, target_unit, period, version)
    return converted['quantity'], evidence


def material_factor(source_unit, target_unit):
    if not source_unit or not target_unit:
        raise ValueError('Confirm recipe and material-stock units.')
    factor = 1.0 if source_unit == target_unit else standard_factor(source_unit, target_unit)
    if factor is None:
        raise ValueError(f'Recipe material unit {source_unit} cannot be converted to stock unit {target_unit}. Supply a confirmed common material unit.')
    return factor


def route_workload(demand, routing, forecast_unit, version=None):
    required = {'sku', 'sequence', 'stage', 'production_line', 'product_unit', 'hours_per_unit', 'valid_from'}
    if required - set(routing.columns) or routing.empty:
        raise ValueError('Map the required production-step fields.')
    work = routing.reset_index(drop=True).copy()
    for field in ('sku', 'stage', 'production_line', 'product_unit'):
        if work[field].isna().any() or work[field].astype(str).str.strip().eq('').any():
            raise ValueError(f'Production steps contain a missing {field}.')
        work[field] = work[field].astype(str).str.strip()
    for field in ('sequence', 'hours_per_unit', 'batch_size', 'setup_hours_per_batch'):
        if field not in work:
            continue
        values = pd.to_numeric(work[field], errors='coerce')
        if (values.isna() | values.lt(0) | ~values.map(math.isfinite)).any():
            raise ValueError(f'Production steps: {field} needs finite, nonnegative numbers.')
        if field in {'sequence', 'hours_per_unit', 'batch_size'} and values.le(0).any():
            raise ValueError(f'Production steps: {field} must be greater than zero.')
        if field == 'sequence' and values.mod(1).ne(0).any():
            raise ValueError('Production step numbers must be whole numbers.')
        work[field] = values
    if ('batch_size' in work) != ('setup_hours_per_batch' in work):
        raise ValueError('Match batch size and setup hours together, or leave both unmapped.')
    def route_date(value):
        if value is None or pd.isna(value) or str(value).strip() == '':
            return pd.NaT
        try:
            # Numeric serials and ambiguous regional strings must not become
            # accidental nanosecond timestamps. Excel readers supply dates.
            if isinstance(value, (date, datetime)):
                return pd.Timestamp(value.date() if isinstance(value, datetime) else value)
            return pd.Timestamp(date.fromisoformat(str(value).strip()))
        except (ValueError, TypeError):
            return pd.NaT
    starts = pd.to_datetime(work.valid_from.map(route_date))
    ends = pd.to_datetime(work.get('valid_to', pd.Series(None, index=work.index, dtype=object)).map(route_date))
    if starts.isna().any() or starts.dt.day.ne(1).any():
        raise ValueError('Production routes must start on the first day of a month.')
    if 'valid_to' in work:
        provided = work.valid_to.notna() & work.valid_to.astype(str).str.strip().ne('')
        if (provided & (ends.isna() | ~ends.dt.is_month_end)).any():
            raise ValueError('Route end dates must be valid month-end dates, or blank.')
        if (ends.notna() & ends.lt(starts)).any():
            raise ValueError('A route end date cannot precede its start date.')
    work['start'] = starts.dt.strftime('%Y-%m-%d')
    work['end'] = ends.dt.strftime('%Y-%m-%d').fillna('9999-12-31')
    for _, group in work.groupby(['sku', 'sequence']):
        previous_end = None
        for row in group.sort_values('start').itertuples():
            if previous_end is not None and row.start <= previous_end:
                raise ValueError(f'{row.sku}: overlapping definitions for production step {int(row.sequence)}. Alternatives need a reviewed allocation, not duplicate routes.')
            previous_end = row.end
    missing = set(demand) - set(work.sku)
    if missing:
        raise ValueError('Production routes are missing products: ' + ', '.join(sorted(missing)))
    details = []
    for sku, periods in sorted(demand.items()):
        route = work[work.sku == sku]
        steps = set(route.sequence)
        for period, quantity in sorted(periods.items()):
            active = route[(route.start <= period) & (route.end >= period)]
            if set(active.sequence) != steps:
                raise ValueError(f'{sku}: incomplete production steps for {period}. Confirm the route for every forecast month.')
            for index, row in active.sort_values('sequence').iterrows():
                units, evidence = product_quantity(quantity, sku, forecast_unit, row.product_unit, period, version)
                batches = math.ceil(units / row.batch_size) if 'batch_size' in work and units > 0 else 0
                setup = batches * row.setup_hours_per_batch if 'batch_size' in work else 0.0
                runtime = units * row.hours_per_unit
                total = runtime + setup
                if not math.isfinite(total):
                    raise ValueError('Calculated machine workload is too large.')
                details.append({'sku': sku, 'period': period, 'sequence': int(row.sequence), 'stage': row.stage,
                                'production_line': row.production_line, 'product_quantity': units,
                                'product_unit': row.product_unit, 'hours_per_unit': float(row.hours_per_unit),
                                'run_hours': runtime, 'setup_hours': setup, 'batches': batches,
                                'required_hours': total, 'conversion': evidence,
                                'source_cells': routing.attrs.get('source_cells', [{}] * len(routing))[index]})
    frame = pd.DataFrame(details)
    totals = {} if frame.empty else frame.groupby(['production_line', 'period']).required_hours.sum().to_dict()
    if any(not math.isfinite(value) for value in totals.values()):
        raise ValueError('Total machine workload is too large.')
    return totals, details

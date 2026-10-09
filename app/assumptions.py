"""Reviewed future-factor scenarios; observations and baseline inputs stay immutable."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import uuid

import pandas as pd

from .data import actual_history, read_table, prepare_history, build_future_covariates
from .sales_conventions import normalize_history


def scenario_inputs(base, store, *, allow_empty_drivers=False):
    if base.get('scenario_name') or not base.get('dataset_id'):
        raise ValueError('Choose a saved baseline forecast, not another scenario.')
    dataset = store.get(base['dataset_id'])
    if dataset['classification'] != base.get('source_classification'):
        raise ValueError('The baseline and saved data must have the same real/sample classification.')
    manifest = base.get('input_manifest', {})
    settings = deepcopy(manifest.get('settings', {}))
    if not settings or dataset['settings'] != settings:
        raise ValueError('This forecast does not have matching saved input settings. Run the saved data again first.')
    captured = {row['role']: row for row in manifest.get('sources', [])}
    if set(captured) != set(dataset['sources']):
        raise ValueError('The forecast is missing source provenance. Run the saved data again first.')
    for role, identifier in dataset['sources'].items():
        source, _ = store.source(identifier)
        if captured[role].get('id') != identifier or captured[role].get('sha256') != source['sha256']:
            raise ValueError('The saved source does not match this baseline forecast.')
    drivers = settings.get('drivers', [])
    if not drivers and not allow_empty_drivers:
        raise ValueError('This forecast has no extra factors. Select factors in Data and run a baseline first.')
    # Reuse the exact original preparation and future-value policy.
    source, content = store.source(dataset['sources']['history'])
    raw = read_table(source['name'], content, sheet_name=source.get('sheet'))
    history, _ = actual_history(raw, unit_filter=settings.get('unit_filter'), excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
    history, _ = normalize_history(history, settings)
    from .sales_groups import series_column, customer_product_future
    grouped_history = history
    history, _ = prepare_history(history, date_col=settings['date_col'], target_col=settings['target_col'], item_col=series_column(settings) or None,
        driver_cols=drivers, frequency=settings.get('frequency', 'monthly'), missing_strategy=settings.get('missing_strategy', 'auto'),
        outlier_strategy=settings.get('outlier_strategy', 'none'), calendar_country=settings.get('calendar_country', 'IR') or None,
        weekend_days=tuple(settings.get('weekend_days', [4])), shutdown_dates=tuple(settings.get('shutdown_dates', [])),month_basis=settings.get('month_basis','gregorian'))
    future = None
    if dataset['sources'].get('future'):
        source, content = store.source(dataset['sources']['future'])
        future = read_table(source['name'], content, sheet_name=source.get('sheet'))
    future, future_item = customer_product_future(future, grouped_history, settings)
    future, warnings = build_future_covariates(history, future, future_date_col=settings.get('future_date_col'), future_item_col=future_item,
        known_driver_cols=drivers, frequency=settings.get('frequency', 'monthly'), horizon=settings.get('horizon', 6),
        missing_future_policy=settings.get('future_driver_policy', 'require'),input_calendar=settings.get('future_calendar','gregorian'))
    future = future[['item_id', 'timestamp', *drivers]].copy()
    future['timestamp'] = future.timestamp.dt.strftime('%Y-%m-%d')
    expected = {(str(item), str(point['timestamp'])[:10]) for item, series in base['series'].items() if item != '__all__' for point in series['forecast']}
    if set(zip(future.item_id, future.timestamp)) != expected:
        raise ValueError('The saved data no longer matches the baseline forecast periods.')
    numeric = [key for key in drivers if pd.to_numeric(future[key], errors='coerce').map(lambda value: pd.notna(value) and math.isfinite(value)).all()]
    for key in numeric:
        future[key] = pd.to_numeric(future[key])
    return dataset, settings, future, numeric, warnings


def preview_assumptions(base, store):
    _, _, future, numeric, warnings = scenario_inputs(base, store)
    return {'base_run_id': base['run_id'], 'factors': numeric, 'items': sorted(future.item_id.unique().tolist()),
            'rows': future[['item_id', 'timestamp', *numeric]].to_dict(orient='records'), 'warnings': warnings,
            'limitation': 'These are future assumptions, not observed data or causal estimates. A method that ignores a factor may return the same forecast.'}


def save_assumptions(base, store, payload):
    for key in ('name', 'owner', 'reason'):
        if not isinstance(payload.get(key), str) or not 2 <= len(payload[key].strip()) <= 500:
            raise ValueError(f'Enter a {key} for this scenario.')
    if payload.get('reviewed') is not True:
        raise ValueError('Review the future assumptions before saving.')
    try:
        request_id = str(uuid.UUID(payload.get('request_id', '')))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('A valid scenario request identifier is required.')
    fingerprint = hashlib.sha256(json.dumps({'base': base['run_id'], 'payload': payload}, sort_keys=True, allow_nan=False).encode()).hexdigest()
    identifier = hashlib.sha256(('factor-scenario:' + request_id).encode()).hexdigest()[:32]
    with store.lock:
        if store._path('dataset', identifier).exists():
            previous = store.get(identifier)
            if previous.get('scenario_provenance', {}).get('request_digest') != fingerprint:
                raise ValueError('This request already saved different assumptions. Start a new scenario.')
            return previous
        dataset, settings, future, numeric, warnings = scenario_inputs(base, store)
        changes = payload.get('changes')
        if not isinstance(changes, list) or not 1 <= len(changes) <= 10000:
            raise ValueError('Change at least one future value (maximum 10,000).')
        definitions = payload.get('definitions', [])
        if not isinstance(definitions, list):
            raise ValueError('Supply a unit, geographic scope and source for each changed factor.')
        descriptions = {}
        for definition in definitions:
            if not isinstance(definition, dict):
                raise ValueError('Each factor definition must contain its unit, geography and source.')
            factor = definition.get('factor')
            if factor in descriptions or factor not in numeric:
                raise ValueError('Choose distinct numeric factors from this baseline.')
            if any(not isinstance(definition.get(k), str) or not 1 <= len(definition[k].strip()) <= 500 for k in ('unit', 'geography', 'source')):
                raise ValueError('Confirm the unit, geographic scope and source of each changed factor.')
            descriptions[factor] = {k: definition[k].strip() for k in ('factor', 'unit', 'geography', 'source')}
        indices = {(str(row.item_id), row.timestamp): index for index, row in future.iterrows()}
        evidence, seen = [], set()
        for change in changes:
            if not isinstance(change, dict):
                raise ValueError('Each change must identify an item, period, factor and value.')
            factor = change.get('factor')
            key = (change.get('item_id'), change.get('period'))
            unique = (*key, factor)
            if key not in indices or factor not in descriptions or unique in seen:
                raise ValueError('Each change needs a unique forecast item, period and reviewed factor.')
            seen.add(unique)
            value = change.get('value')
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('Assumption values must be finite numbers; blanks are not zero.')
            index = indices[key]
            previous = float(future.at[index, factor])
            if previous == value:
                continue
            evidence.append({'item_id': key[0], 'period': key[1], 'factor': factor, 'baseline_value': previous, 'value': value})
            future[factor] = future[factor].astype(float)
            future.at[index, factor] = value
        if not evidence:
            raise ValueError('The values are unchanged. Edit an assumption before calculating a scenario.')
        if set(descriptions) != {row['factor'] for row in evidence}:
            raise ValueError('Only describe factors with changed values.')
        settings['future_date_col'], settings['future_item_col'] = 'timestamp', 'item_id'
        settings['future_calendar'] = 'gregorian'  # Generated CSV contains canonical ISO dates.
        # Preserve the baseline's deliberate method choice, including manual reruns.
        settings['method_selection'] = base.get('method_selection') or base['run_settings']['method_selection']
        sources = dict(dataset['sources'])
        source = store.upload('reviewed_future_assumptions.csv', future.to_csv(index=False).encode('utf-8'), 'future')
        sources['future'] = source['id']
        provenance = {'type': 'factor_assumptions', 'base_run_id': base['run_id'], 'base_dataset_id': dataset['id'],
                      'name': payload['name'].strip(), 'owner': payload['owner'].strip(), 'reason': payload['reason'].strip(),
                      'recorded_at': datetime.now(timezone.utc).isoformat(), 'definitions': list(descriptions.values()),
                      'changes': evidence, 'inherited_future_policy': settings.get('future_driver_policy', 'require'),
                      'inherited_warnings': warnings, 'request_digest': fingerprint,
                      'identity_basis': 'self_declared_not_authenticated', 'refitted': True}
        return store.save(payload['name'].strip(), sources, settings, classification=dataset['classification'], accept_warnings=True,
                          provenance=provenance, identifier=identifier)

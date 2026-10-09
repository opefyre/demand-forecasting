"""Dated evidence and a reversible no-extra-factors comparison; no order writes."""
from copy import deepcopy
import uuid
import pandas as pd

from .assumptions import scenario_inputs
from .data import actual_history, read_table
from .forecast_engine import _engine_versions


def review_factors(base, store):
    dataset, settings, future, _, warnings = scenario_inputs(base, store)
    source, content = store.source(dataset['sources']['history'])
    raw, _ = actual_history(read_table(source['name'], content, sheet_name=source.get('sheet')),
        unit_filter=settings.get('unit_filter'), excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
    dates = pd.to_datetime(raw[settings['date_col']])
    future_source = store.source(dataset['sources']['future'])[0] if dataset['sources'].get('future') else None
    definitions = settings.get('factor_definitions', {})
    rows = []
    for factor in settings['drivers']:
        values = raw[factor]
        missing = values.isna() | values.astype(str).str.strip().eq('')
        definition = definitions.get(factor, {})
        coverage = future.attrs.get('driver_coverage', {}).get(factor, {})
        rows.append({'factor':factor, 'history_rows':len(raw), 'history_missing':int(missing.sum()),
            'latest_recorded_period':None if missing.all() else dates[~missing].max().strftime('%Y-%m-%d'),
            'unit':definition.get('unit'), 'geography':definition.get('geography'),
            'source':definition.get('source') or source['name'],
            'future_provided':coverage.get('provided',0), 'future_filled':coverage.get('assumed',0),
            'future_expected':coverage.get('expected',len(future)),
            'future_policy':settings.get('future_driver_policy','require'),
            'historical_kind':'uploaded_history_not_independently_verified', 'future_kind':'planning_assumptions',
            'release_dates_verified':False})
    current = base.get('engine') == _engine_versions() and base.get('metrics',{}).get('factor_test_policy') == 'last_training_value'
    return {'run_id':base['run_id'], 'factors':rows, 'warnings':warnings,
        'history_start':dates.min().strftime('%Y-%m-%d'), 'history_end':dates.max().strftime('%Y-%m-%d'),
        'history_captured_at':source['created_at'], 'future_captured_at':future_source['created_at'] if future_source else None,
        'forecast_start':future.timestamp.min(), 'forecast_end':future.timestamp.max(),
        'source_classification':dataset['classification'], 'can_compare':current,
        'comparison_blocker':None if current else 'Recalculate this baseline first: older forecasts used a different factor-testing rule.',
        'test_note':base.get('metrics',{}).get('factor_test_note') or 'This saved run predates the factor cutoff check. Do not use its test score to judge factor usefulness.',
        'future_note':'Provided future values are assumptions, not observations. Filled values follow the selected missing-value policy.',
        'availability_note':'File import dates are not original publication dates. Historical revisions and release delays remain unverified.'}


def save_factor_comparison(base, store, payload):
    if payload.get('reviewed') is not True:
        raise ValueError('Confirm the comparison before calculating.')
    try:
        request_id = str(uuid.UUID(payload.get('request_id','')))
    except (ValueError,TypeError,AttributeError):
        raise ValueError('A valid comparison request identifier is required.')
    report = review_factors(base,store)
    if not report['can_compare']:
        raise ValueError(report['comparison_blocker'])
    dataset = store.get(base['dataset_id'])
    settings = deepcopy(dataset['settings'])
    removed = list(settings['drivers'])
    settings['drivers'] = []
    settings['driver_roles'] = {}
    settings['method_selection'] = base.get('method_selection') or base['run_settings']['method_selection']
    # Keep the exact files/calendar/target/settings; only remove extra predictors.
    provenance = {'type':'factor_comparison', 'base_run_id':base['run_id'], 'base_dataset_id':dataset['id'],
        'name':'Without extra factors', 'owner':'Planner',
        'reason':'Compare the same sales history and calendar without extra factor inputs. Automatic selection, if chosen, is repeated in each run.',
        'identity_basis':'comparison_request_not_authenticated_signature',
        'definitions':[], 'changes':[], 'removed_factors':removed, 'inherited_warnings':[],
        'refitted':True, 'orders_changed':False, 'limitation':report['availability_note']}
    return store.save('Without extra factors',dataset['sources'],settings,dataset['classification'],True,
        provenance=provenance,parent_dataset_id=dataset['id'],request_id='factor-comparison:'+request_id)

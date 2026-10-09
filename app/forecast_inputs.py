"""Review external inputs before fitting any forecast model.

Reuse the scenario alignment contract without inventing a calculated baseline.
The context contains dates and identities only, never predictions or scores.
"""
from copy import deepcopy

from .data import actual_history, read_table, prepare_history, build_future_covariates
from .sales_conventions import normalize_history
from .sales_groups import series_column, customer_product_future
from .forecast_engine import _engine_versions
from .factor_links import choices, preview_link, save_link


def input_context(store, identifier):
    dataset = store.get(identifier)
    if dataset.get('scenario_provenance') or set(dataset['sources']) - {'history', 'future'}:
        raise ValueError('Choose saved sales history, not a comparison or production dataset.')
    settings = deepcopy(dataset['settings'])
    if settings.get('frequency', 'monthly') != 'monthly':
        raise ValueError('External factor matching currently needs monthly sales.')
    store.inspect(dataset['sources'], settings, dataset['classification'])
    manifest = []
    frames = {}
    for role, key in dataset['sources'].items():
        source, content = store.source(key)
        manifest.append({'role': role, 'id': key, 'sha256': source['sha256']})
        frames[role] = read_table(source['name'], content, sheet_name=source.get('sheet'))
    history, _ = actual_history(frames['history'], unit_filter=settings.get('unit_filter'),
                               excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
    history, _ = normalize_history(history, settings)
    item = series_column(settings)
    clean, _ = prepare_history(history, date_col=settings['date_col'], target_col=settings['target_col'],
        item_col=item or None, driver_cols=settings.get('drivers', []), frequency='monthly',
        missing_strategy=settings.get('missing_strategy', 'auto'), outlier_strategy=settings.get('outlier_strategy', 'none'),
        calendar_country=settings.get('calendar_country', 'IR') or None,
        weekend_days=tuple(settings.get('weekend_days', [4])), shutdown_dates=tuple(settings.get('shutdown_dates', [])),
        month_basis=settings.get('month_basis', 'gregorian'))
    future_frame, future_item = customer_product_future(frames.get('future'), history, settings)
    future, _ = build_future_covariates(clean, future_frame, future_date_col=settings.get('future_date_col'),
        future_item_col=future_item, known_driver_cols=settings.get('drivers', []), frequency='monthly',
        horizon=settings.get('horizon', 6), missing_future_policy=settings.get('future_driver_policy', 'require'),
        input_calendar=settings.get('future_calendar', 'gregorian'))
    series, metadata = {}, {}
    for key, rows in future.groupby('item_id'):
        key = str(key)
        series[key] = {'forecast': [{'timestamp': date.strftime('%Y-%m-%d')} for date in rows.timestamp]}
        original = history[history[item].astype(str).eq(key)] if item else history
        last = original.iloc[-1]
        metadata[key] = {field: str(last[column]) if (column := settings.get(field + '_col')) else ''
                         for field in ('customer', 'sku')}
    return {'run_id': 'inputs:' + identifier, 'dataset_id': identifier,
            'source_classification': dataset['classification'], 'engine': _engine_versions(),
            'input_manifest': {'settings': settings, 'sources': manifest},
            'series': series, 'metadata': metadata, 'method_selection': 'model:Ridge + drivers',
            'leaderboard': [{'model': name} for name in
                            ('Ridge + drivers', 'Elastic Net + drivers', 'Histogram gradient boosting')],
            'input_context_only': True}


def factor_options(store, factors, identifier, live=None):
    context = input_context(store, identifier)
    options = choices(context, store, factors)
    from .factor_preparation import connected_source_readiness
    states = live.listing()['sources'] if live else []
    for snapshot in options['snapshots']:
        if snapshot['live_what_if'] or snapshot['public_vintage']:
            state = connected_source_readiness(snapshot['id'], states=states)
            snapshot.update(can_use=state['ready'], readiness_note=state['note'])
    return options


def preview_inputs(store, factors, identifier, payload, live=None):
    if payload.get('series_ids') is not None or payload.get('preparation') is not None:
        raise ValueError('New forecast factors apply to the selected sales dataset. Use result comparisons for narrower groups.')
    options = factor_options(store, factors, identifier, live)
    requested = payload.get('links') or [{'snapshot_id':payload.get('snapshot_id')}]
    if not isinstance(requested, list) or any(not isinstance(row,dict) for row in requested):
        raise ValueError('Choose a list of forecast factors.')
    for link in requested:
        snapshot = next((s for s in options['snapshots'] if s['id']==link.get('snapshot_id')), None)
        if snapshot is None:
            raise ValueError('Source versions changed. Review the live factors again.')
        if snapshot.get('can_use') is False:
            raise ValueError(snapshot['readiness_note'])
    return preview_link(input_context(store, identifier), store, factors, payload)


def save_inputs(store, factors, identifier, payload, live=None):
    preview_inputs(store, factors, identifier, payload, live)
    return save_link(input_context(store, identifier), store, factors, payload, forecast_input=True)

"""Evidence-backed mapping proposals. Source cells and sales orders are never edited."""
import hashlib
import json
import math
from typing import Literal
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from .data import read_table, actual_history
from .sales_conventions import normalize_history


class MappingChange(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    field: Literal['date_col','target_col','item_col','customer_col','sku_col','future_date_col','future_item_col']
    column: str = Field(min_length=1, max_length=300)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def sources_for(dataset):
    return {k:v for k,v in dataset['sources'].items() if k in {'history','future'} and v}


def input_report(store, dataset, settings=None, *, review=None):
    settings = settings or dataset['settings']
    files, frames, errors, warnings = {}, {}, [], []
    for role, key in sources_for(dataset).items():
        source, content = store.source(key)
        frame = read_table(source['name'], content, sheet_name=source.get('sheet'))
        frames[role] = frame
        files[role] = {'id':key, 'name':source['name'], 'sha256':source['sha256'],
                       'columns':[str(c) for c in frame.columns], 'rows':len(frame)}
    frame = frames.get('history')
    total = None
    if frame is not None:
        try:
            frame, source_warnings = actual_history(frame, unit_filter=settings.get('unit_filter'),
                excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
            warnings.extend(source_warnings)
            frame, convention_warnings = normalize_history(frame, settings)
            warnings.extend(convention_warnings)
            repeated = int(frame.duplicated(keep=False).sum())
            if repeated:
                warnings.append(f'{repeated} identical rows need checking. They may be valid transactions; none were removed.')
            quantity = settings.get('target_col')
            if quantity in frame:
                values = pd.to_numeric(frame[quantity], errors='coerce')
                if values.notna().all() and values.map(math.isfinite).all():
                    total = float(values.sum())
            from .sales_groups import series_column
            item = series_column(settings)
            for field in ('customer_col','sku_col'):
                column = settings.get(field)
                if not column:
                    warnings.append(f'{field.removesuffix("_col").title()} column is not mapped. Customer/SKU output may be incomplete.')
                elif column not in frame:
                    errors.append(f'The mapped {field.removesuffix("_col")} column does not exist.')
                else:
                    missing = frame[column].isna() | frame[column].astype(str).str.strip().eq('')
                    if missing.any(): errors.append(f'{int(missing.sum())} rows have no {field.removesuffix("_col")}.')
                    groups = frame.groupby(item,dropna=False)[column].nunique() if item in frame else pd.Series([frame[column].nunique()])
                    if (groups > 1).any():
                        errors.append(f'The item mapping combines different {field.removesuffix("_col")} values. Use a distinct customer–SKU series identifier.')
        except ValueError as exc:
            errors.append(str(exc))
    try:
        if review is None:
            review = store.inspect(sources_for(dataset),settings,dataset['classification'])
        warnings.extend(review.get('warnings',[]))
        warnings.extend(review.get('source_review',{}).get('warnings',[]))
    except ValueError as exc:
        errors.append(str(exc)); review = {}
    visible_fields = {'date_col','target_col','item_col','series_mode','customer_col','sku_col','future_date_col',
        'future_item_col','drivers','frequency','horizon','unit','unit_filter','missing_strategy',
        'outlier_strategy','future_driver_policy','calendar_country','weekend_days','shutdown_dates',
        'history_calendar','history_grain','month_basis','sales_measure','returns_policy','future_calendar','customer_aliases',
        'history_cell_corrections','history_corrections_sha256'}
    return {'dataset_id':dataset['id'], 'files':files,
            'settings':{k:v for k,v in settings.items() if k in visible_fields},
            'source_quantity_total':total, 'unit':settings.get('unit'),
            'errors':list(dict.fromkeys(errors)), 'warnings':list(dict.fromkeys(warnings)),
            'summary':review.get('summary',{}), 'driver_coverage':review.get('driver_coverage',{}),
            'forecast_start':review.get('forecast_start'), 'forecast_end':review.get('forecast_end'),
            'preview':review.get('preview',[]), 'classification':dataset['classification']}


def validate_import(store, sources, settings, classification='user_provided'):
    """Same checks for manual and assisted imports, before any public save."""
    review = store.inspect(sources, settings, classification)
    if sources.get('operations'):  # Preserve legacy datasets, outside the sales workflow.
        return review
    report = input_report(store, {'id':'draft', 'sources':sources, 'settings':settings,
                                  'classification':classification}, review=review)
    if report['errors']:
        raise ValueError('; '.join(report['errors']))
    return {**review, 'warnings':report['warnings']}


def mapping_proposal(store, dataset_id, changes, reason):
    source = store.get(dataset_id)
    if source.get('scenario_provenance'):
        raise ValueError('Review mappings on the original dataset, not an assumption scenario.')
    if not 1 <= len(changes) <= 7 or len(reason.strip()) < 3 or len(reason) > 1000:
        raise ValueError('Propose 1–7 mapping changes and explain why.')
    before = input_report(store,source)
    settings = dict(source['settings']); parsed = [MappingChange.model_validate(c) for c in changes]
    if len({c.field for c in parsed}) != len(parsed): raise ValueError('Each mapping can be changed only once.')
    diff = []
    for change in parsed:
        role = 'future' if change.field.startswith('future_') else 'history'
        if change.column not in before['files'].get(role,{}).get('columns',[]):
            raise ValueError(f'{change.column}: choose a column from the {role} file.')
        if settings.get(change.field) != change.column:
            diff.append({'field':change.field,'before':settings.get(change.field),'after':change.column})
            settings[change.field] = change.column
    if not diff: raise ValueError('These mappings are already selected.')
    after = input_report(store,source,settings)
    if after['errors']: raise ValueError('Resolve these input problems first: '+'; '.join(after['errors']))
    return {'kind':'input_mapping','dataset_id':dataset_id,'dataset_sha256':digest(source),
            'source_hashes':{k:f['sha256'] for k,f in before['files'].items()},
            'changes':[c.model_dump() for c in parsed], 'reason':reason.strip(), 'diff':diff,
            'before_total':before['source_quantity_total'],'after_total':after['source_quantity_total'],
            'before_prepared_total':before['summary'].get('total_demand'),
            'after_prepared_total':after['summary'].get('total_demand'),
            'unit':after['unit'], 'warnings':after['warnings'], 'preview':after['preview'],
            'validation_sha256':digest(after)}


def apply_mapping(store, proposal, actor, request_id):
    source = store.get(proposal['dataset_id'])
    if digest(source) != proposal['dataset_sha256']:
        raise ValueError('Inputs changed. Ask for a new mapping review.')
    fresh = mapping_proposal(store,source['id'],proposal['changes'],proposal['reason'])
    if fresh != proposal:
        raise ValueError('Input evidence changed. Ask for a new mapping review.')
    settings = {**source['settings'], **{c['field']:c['column'] for c in proposal['changes']}}
    return store.save(source['name']+' · Reviewed mappings',sources_for(source),settings,
        source['classification'],True,parent_dataset_id=source['id'],request_id=request_id,
        import_provenance={'kind':'assistant_mapping_review','actor':actor,'proposal':proposal})

"""Compare repeated history at its declared customer/SKU/period grain."""
from .data import read_table, actual_history, period_dates
from .sales_conventions import normalize_history


def history_groups(store, dataset):
    settings = dataset['settings']
    file, raw = store.source(dataset['sources']['history'])
    frame = read_table(file['name'], raw, sheet_name=file.get('sheet'))
    frame, _ = actual_history(frame, unit_filter=settings.get('unit_filter'),
        excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
    frame, _ = normalize_history(frame, settings)
    frame = frame.copy()
    frame['_period'] = period_dates(frame[settings['date_col']],settings.get('frequency','monthly'),settings.get('month_basis','gregorian'))
    item = settings.get('item_col') if settings.get('series_mode','column') == 'column' else None
    keys = [c for c in (settings.get('customer_col'),settings.get('sku_col'),item) if c]
    keys = list(dict.fromkeys(keys))
    if any(c not in frame for c in keys): raise ValueError('Match the customer/product columns before comparing uploads.')
    groups = frame.groupby(keys+['_period'],dropna=False)[settings['target_col']].sum()
    values = {tuple(str(v)[:10] if i==len(keys) else str(v) for i,v in enumerate(k if isinstance(k,tuple) else (k,))):float(q)
              for k,q in groups.items()}
    return values, len(frame), keys


def repeat_review(store, parent_id, sources, settings, classification):
    parent = store.get(parent_id)
    if parent.get('scenario_provenance') or parent['sources'].get('operations'):
        raise ValueError('Repeat uploads need original sales inputs, not a factor or production scenario.')
    if sources.get('history') == parent['sources'].get('history'):
        return None
    if any(settings.get(k,default)!=parent['settings'].get(k,default) for k,default in
        [('unit',None),('history_calendar','gregorian'),('month_basis','gregorian'),('frequency','monthly'),
         ('sales_measure','unspecified'),('history_grain','transactions'),('returns_policy','reject'),('series_mode','column')]):
        raise ValueError('Keep the same unit, calendar, sales meaning and returns policy for a repeat comparison. Start a separate import to change them.')
    current = {'id':'draft','sources':sources,'settings':settings,'classification':classification}
    before, old_rows, old_keys = history_groups(store,parent)
    after, new_rows, new_keys = history_groups(store,current)
    if len(old_keys) != len(new_keys):
        raise ValueError('Keep equivalent customer/product grouping for a repeat upload.')
    removed, added = set(before)-set(after), set(after)-set(before)
    changed = {k for k in before.keys() & after.keys() if before[k] != after[k]}
    periods_old, periods_new = {k[-1] for k in before}, {k[-1] for k in after}
    old, _ = store.source(parent['sources']['history'])
    new, _ = store.source(sources['history'])
    rows = [{'scope':list(k[:-1]),'period':k[-1], 'before':before.get(k), 'after':after.get(k)}
            for k in sorted(removed|added|changed)]
    return {'parent_dataset_id':parent_id,'mode':'replacement_not_append',
        'same_file_contents':old['sha256']==new['sha256'], 'unit':settings.get('unit'),
        'before_rows':old_rows,'after_rows':new_rows,'before_total':sum(before.values()),'after_total':sum(after.values()),
        'added_groups':len(added),'removed_groups':len(removed),'changed_groups':len(changed),
        'added_periods':sorted(periods_new-periods_old),'removed_periods':sorted(periods_old-periods_new),
        'scope_labels':new_keys,'changes':rows[:120], 'change_count':len(rows),'truncated':len(rows)>120,
        'retained_factors':sources.get('future') is not None and sources.get('future')==parent['sources'].get('future'),
        'message':'This file replaces the full history for the new version; it is not appended. Original history and orders stay unchanged.'}

"""Exact customer/product series built from reviewed mappings, never fuzzy names."""
import json

import pandas as pd

PAIR_COLUMN = '__demandlab_customer_product__'


def series_column(settings):
    mode = settings.get('series_mode', 'column')
    if mode not in {'column', 'customer_product'}:
        raise ValueError('Choose customer/product grouping or a reviewed group column.')
    return PAIR_COLUMN if mode == 'customer_product' else settings.get('item_col')


def customer_product_series(frame, settings):
    """Preserve original identifiers and quantities; add one reproducible key."""
    if settings.get('series_mode', 'column') != 'customer_product':
        series_column(settings)  # Reject unknown contracts, including API inputs.
        return frame
    customer, sku = settings.get('customer_col'), settings.get('sku_col')
    if not customer or not sku or customer == sku or customer not in frame or sku not in frame:
        raise ValueError('Choose separate customer and product columns for customer/product forecasts.')
    if {customer, sku} & {settings.get('date_col'), settings.get('target_col')}:
        raise ValueError('Customer and product columns must be different from the date and quantity columns.')
    for column in (customer, sku):
        missing = frame[column].isna() | frame[column].astype(str).str.strip().eq('')
        if missing.any():
            raise ValueError(f'{int(missing.sum())} rows have no {"customer" if column == customer else "product"}. Review these before forecasting.')
    keys = pd.Series([json.dumps([str(c), str(s)], ensure_ascii=False, separators=(',', ':'))
                      for c, s in zip(frame[customer], frame[sku])], index=frame.index)
    if PAIR_COLUMN in frame and not frame[PAIR_COLUMN].equals(keys):
        raise ValueError('The saved customer/product keys do not match their source columns. Review the input.')
    out = frame.copy()
    out[PAIR_COLUMN] = keys
    out.attrs.update(frame.attrs)
    return out


def validate_series_identity(frame, settings):
    item = series_column(settings)
    for field in ('customer_col', 'sku_col'):
        column = settings.get(field)
        if not column:
            continue  # Explicit unallocated/aggregate history remains supported.
        if column not in frame:
            raise ValueError('The mapped customer or product column does not exist.')
        missing = frame[column].isna() | frame[column].astype(str).str.strip().eq('')
        if missing.any():
            raise ValueError(f'{int(missing.sum())} rows have no {field.removesuffix("_col")}.')
        groups = frame.groupby(item, dropna=False)[column].nunique() if item in frame else pd.Series([frame[column].nunique()])
        if (groups > 1).any():
            raise ValueError(f'A forecast group combines different {field.removesuffix("_col")} values. Choose Customer & product grouping, or a distinct group column.')


def customer_product_future(frame, history, settings):
    """Common factors remain common; scoped factors must identify the exact pair."""
    item = settings.get('future_item_col')
    if frame is None or settings.get('series_mode', 'column') != 'customer_product':
        return frame, item
    customer, sku = settings.get('customer_col'), settings.get('sku_col')
    if customer in frame and sku in frame:
        return customer_product_series(frame, settings), PAIR_COLUMN
    if not item:
        return frame, None
    if item not in frame:
        raise ValueError('The mapped future group column does not exist.')
    keys = set(history[PAIR_COLUMN].astype(str))
    values = frame[item].astype(str)
    if set(values) <= keys:
        return frame, item  # Factor scenarios already carry exact reviewed keys.
    original = settings.get('item_col')
    if not original or original not in history:
        raise ValueError('Future factors need customer and product columns, or exact customer/product group keys. Use no group column only for shared factors.')
    links = history[[original, PAIR_COLUMN]].drop_duplicates()
    if links[original].duplicated().any():
        raise ValueError('The future group column covers multiple customers or products. Supply both customer and product columns.')
    mapping = dict(zip(links[original].astype(str), links[PAIR_COLUMN]))
    if not set(values) <= set(mapping):
        raise ValueError('Future factors contain groups that are not in the reviewed sales history.')
    out = frame.copy()
    out[item] = values.map(mapping)
    out.attrs.update(frame.attrs)
    return out, item

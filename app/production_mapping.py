"""Explicit positional mappings for operational workbook tables."""
from datetime import date
from copy import deepcopy
import pandas as pd
from .inventory import raw_table, text_value

SCHEMA = {
    'bom': {'label': 'Product recipes', 'required': {'sku': 'Product code', 'material_id': 'Material code', 'quantity_per_tonne': 'Material quantity per tonne of product'}, 'optional': {'scrap_pct': 'Extra material allowance (%)'}},
    'materials': {'label': 'Materials and stock', 'required': {'material_id': 'Material code', 'material_name': 'Material name', 'unit': 'Material unit', 'inventory_on_hand': 'Total stock (including holds)', 'safety_stock': 'Minimum stock target', 'lead_time_days': 'Supplier lead time (days)', 'moq': 'Order multiple'}, 'optional': {'quality_hold_qty': 'Stock on hold', 'supplier': 'Supplier'}},
    'capacity': {'label': 'Monthly capacity', 'required': {'production_line': 'Production line', 'period': 'Month', 'available_tonnes': 'Available tonnes'}, 'optional': {'planned_downtime_hours': 'Planned downtime (hours)', 'working_days': 'Working days', 'oee_target': 'Efficiency target (0–1)'}},
    'open_pos': {'label': 'Expected deliveries', 'required': {'material_id': 'Material code', 'due_date': 'Expected date', 'quantity': 'Quantity', 'status': 'Status'}, 'optional': {}},
}


def production_schema(mode='tonnes'):
    if mode not in {'tonnes', 'routed'}:
        raise ValueError('Choose tonne-based lines or product routes and machine hours.')
    schema = deepcopy(SCHEMA)
    if mode == 'routed':
        schema['bom']['required'] = {'sku': 'Product code', 'product_unit': 'Product unit', 'material_id': 'Material code', 'material_unit': 'Recipe material unit', 'quantity_per_unit': 'Material quantity per product unit'}
        schema['capacity']['required'] = {'production_line': 'Machine or work centre', 'period': 'Month', 'available_hours': 'Net available machine hours'}
        schema['routing'] = {'label': 'Production steps', 'required': {'sku': 'Product code', 'sequence': 'Step number', 'stage': 'Step name', 'production_line': 'Machine or work centre', 'product_unit': 'Product unit', 'hours_per_unit': 'Run hours per finished-product unit', 'valid_from': 'Applies from'}, 'optional': {'valid_to': 'Applies through', 'batch_size': 'Units per batch', 'setup_hours_per_batch': 'Setup hours per batch'}}
    return schema


def mapped_operations(name, content, config):
    if not isinstance(config, dict) or config.get('reviewed') is not True:
        raise ValueError('Check and confirm the production column mappings.')
    try:
        as_of = date.fromisoformat(config.get('stock_as_of', ''))
    except (ValueError, TypeError):
        raise ValueError('Confirm the material stock snapshot date.')
    tables = config.get('tables', {})
    result = {}
    for kind, schema in production_schema(config.get('mode', 'tonnes')).items():
        spec = tables.get(kind)
        if not spec or not spec.get('sheet'):
            if kind == 'open_pos':
                continue
            raise ValueError(f'Choose a worksheet for {schema["label"]}.')
        table = raw_table(name, content, spec['sheet'], spec.get('header_row', 1))
        mapping = spec.get('columns', {})
        existing = {c['id'] for c in table['columns']}
        if any(mapping.get(field) not in existing for field in schema['required']):
            raise ValueError(f'Match all required columns in {schema["label"]}.')
        chosen = [value for value in mapping.values() if value]
        if len(set(chosen)) != len(chosen) or any(value not in existing for value in chosen):
            raise ValueError(f'Choose a different existing column for every field in {schema["label"]}.')
        if set(mapping) - (schema['required'].keys() | schema['optional'].keys()):
            raise ValueError('The production mapping contains an unknown field.')
        records, lineage, formula_count = [], [], 0
        for source in table['rows']:
            row = {field: source['values'].get(column) for field, column in mapping.items() if column}
            # Blank unrelated worksheet rows are not operational records.
            if not any(text_value(value) for value in row.values()):
                continue
            for field in ('sku', 'material_id', 'material_name', 'unit', 'product_unit', 'material_unit', 'stage', 'production_line', 'supplier', 'status'):
                if field in row:
                    row[field] = text_value(row[field])
            for field in schema['required']:
                if text_value(row[field]) == '':
                    raise ValueError(f'{spec["sheet"]}!{mapping[field]}{source["source_row"]}: {schema["required"][field]} is missing.')
            records.append(row)
            cells = {field: f'{spec["sheet"]}!{column}{source["source_row"]}' for field, column in mapping.items() if column}
            lineage.append(cells)
            formula_count += sum(f'{column}{source["source_row"]}' in table['formulas'] for column in chosen)
        if not records:
            raise ValueError(f'{schema["label"]} has no mapped records.')
        frame = pd.DataFrame(records)
        frame.attrs = {'source_sheet': spec['sheet'], 'source_cells': lineage, 'stock_as_of': as_of.isoformat(), 'cached_formula_cells': formula_count}
        result[kind] = frame
    return result

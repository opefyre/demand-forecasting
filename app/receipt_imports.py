"""Map exported receipt lines with the existing positional spreadsheet reader."""
from datetime import date, datetime
from .inventory import raw_table, text_value


def import_receipts(sources, config):
    source, content = sources.source(config['source_id'])
    if source['role'] != 'receipts':
        raise ValueError('Choose a receipt export, not a demand or stock file.')
    table = raw_table(source['name'], content, config.get('sheet'), config.get('header_row', 1))
    columns = {row['id'] for row in table['columns']}
    mapping = config.get('mapping', {})
    required = ('reference', 'sku', 'quantity', 'due_date')
    if any(mapping.get(key) not in columns for key in required):
        raise ValueError('Match the reference, product, outstanding quantity and usable date columns.')
    selected = [value for value in mapping.values() if value]
    if len(selected) != len(set(selected)) or any(value not in columns for value in selected):
        raise ValueError('Choose a different existing column for each receipt field.')
    if not mapping.get('unit') and not text_value(config.get('fixed_unit')):
        raise ValueError('Match the unit column or confirm a unit for all lines.')
    if not table['rows'] or len(table['rows']) > 5000:
        raise ValueError('Use an export with 1–5,000 receipt lines.')
    rows, evidence, formula_count = [], [], 0
    for row in table['rows']:
        values, number = row['values'], row['source_row']
        value = lambda key: values.get(mapping.get(key))
        due = value('due_date')
        if isinstance(due, datetime): due = due.date().isoformat()
        elif isinstance(due, date): due = due.isoformat()
        else: due = text_value(due)
        # Unambiguous ISO Gregorian dates only; no locale/day-month guessing.
        try:
            if date.fromisoformat(due).isoformat() != due: raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(f"Row {number}: use a real Excel date or YYYY-MM-DD for the usable date.")
        fields = {key: text_value(value(key)) for key in ('reference', 'sku')}
        for key in ('kind', 'status'):
            if mapping.get(key):
                original = text_value(value(key))
                mapped = config.get(key + '_map', {}).get(original)
                if not mapped: raise ValueError(f'Row {number}: choose what {key} “{original}” means.')
                fields[key] = mapped
            else: fields[key] = config.get('fixed_' + key, '')
        fields.update(quantity=value('quantity'), due_date=due,
                      unit=text_value(value('unit')) if mapping.get('unit') else text_value(config.get('fixed_unit')))
        cells = {key: f'{column}{number}' for key, column in mapping.items() if column}
        formula_count += sum(cell in table['formulas'] for cell in cells.values())
        rows.append(fields)
        evidence.append({'reference': fields['reference'], 'source_row': number, 'cells': cells})
    return {'rows': rows, 'source': {key: source[key] for key in ('id', 'name', 'sha256')},
            'sheet': table['sheet'], 'header_row': table['header_row'], 'mapping': mapping,
            'source_cells': evidence, 'config': config,
            'warnings': ([f'{formula_count} mapped cells use saved Excel formula results. Confirm the workbook was recalculated before export.'] if formula_count else [])}

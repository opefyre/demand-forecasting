"""Bounded formatting overlays; never invent a number or rewrite a source file."""
import unicodedata
from pydantic import BaseModel, ConfigDict, Field
from .data import read_table, actual_history

DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
MAX_CELLS = 100


class CellCorrection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    row: int = Field(ge=1, strict=True)
    column: str = Field(min_length=1, max_length=300)
    before: str = Field(max_length=1000)
    after: str = Field(min_length=1, max_length=1000)


def canonical(value, numeric_or_date=False):
    if not isinstance(value, str):
        return value
    result = unicodedata.normalize('NFC', value).strip()
    return result.translate(DIGITS) if numeric_or_date else result


def columns(settings):
    labels = {settings.get(k) for k in ('item_col', 'customer_col', 'sku_col')}
    measures = {settings.get(k) for k in ('date_col', 'target_col')} | set(settings.get('drivers', []))
    return (labels | measures) - {None, ''}, measures - {None, ''}


def apply_cell_corrections(frame, settings):
    changes = settings.get('history_cell_corrections', [])
    if not isinstance(changes, list) or len(changes) > MAX_CELLS:
        raise ValueError('Review at most 100 formatting corrections per input version.')
    out = frame.copy()
    allowed, measures = columns(settings)
    seen = set()
    for value in changes:
        change = CellCorrection.model_validate(value)
        key = (change.row, change.column)
        if key in seen or change.column not in allowed or change.column not in out:
            raise ValueError('Choose one correction per mapped sales-history cell.')
        seen.add(key)
        # Parsers preserve integer row indexes, including gaps in Excel sheets.
        index = change.row - 1
        if index not in out.index:
            raise ValueError('A corrected row is outside the selected sales scope. Review the input version again.')
        before = out.at[index, change.column]
        if not isinstance(before, str) or before != change.before:
            raise ValueError('A source cell changed. Review formatting again.')
        expected = canonical(before, change.column in measures)
        if change.after != expected or expected == before or not expected:
            raise ValueError('Only outer spaces, Unicode composition and date/quantity digits can be normalized. Values cannot be invented or changed.')
        out.at[index, change.column] = change.after
    out.attrs.update(frame.attrs)
    return out


def correction_evidence(store, dataset):
    from .input_review import digest
    if dataset.get('scenario_provenance') or dataset['sources'].get('operations'):
        raise ValueError('Review original sales inputs, not a factor or production scenario.')
    source, raw = store.source(dataset['sources']['history'])
    settings = dataset['settings']
    frame = read_table(source['name'], raw, sheet_name=source.get('sheet'))
    frame, _ = actual_history(frame, unit_filter=settings.get('unit_filter'),
        excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
    frame = apply_cell_corrections(frame, settings)
    allowed, measures = columns(settings)
    cells, total = [], 0
    for index, row in frame.iterrows():
        for column in sorted(allowed & set(frame.columns)):
            before = row[column]
            if not isinstance(before, str) or len(before) > 1000:
                continue
            after = canonical(before, column in measures)
            if after != before and after:
                total += 1
                if len(cells) < MAX_CELLS:
                    cells.append({'row':int(index)+1, 'column':column, 'before':before, 'after':after})
    return {'dataset_id':dataset['id'], 'source_sha256':source['sha256'],
        'dataset_sha256':digest(dataset), 'cells':cells, 'candidate_count':total,
        'truncated':total > MAX_CELLS,
        'row_reference':'Parsed data-row index, not an Excel cell address.',
        'limits':'Formatting only. No missing values, removed rows, guessed dates, customer merges or quantity changes.'}


def correction_proposal(store, dataset_id, changes, reason):
    from .input_review import digest, input_report
    dataset = store.get(dataset_id)
    evidence = correction_evidence(store, dataset)
    if not 1 <= len(changes) <= MAX_CELLS or not 3 <= len(reason.strip()) <= 1000:
        raise ValueError('Choose 1–100 formatting corrections and explain why.')
    parsed = [CellCorrection.model_validate(c).model_dump() for c in changes]
    if len({(c['row'], c['column']) for c in parsed}) != len(parsed):
        raise ValueError('Each source cell can be corrected only once.')
    candidates = {(c['row'], c['column']):c for c in evidence['cells']}
    if any(candidates.get((c['row'], c['column'])) != c for c in parsed):
        raise ValueError('Choose exact formatting changes from the current evidence; no invented repairs.')
    previous = dataset['settings'].get('history_cell_corrections', [])
    if len(previous) + len(parsed) > MAX_CELLS:
        raise ValueError('This version already has corrections. Resolve larger changes in a fresh source file.')
    settings = {**dataset['settings'], 'history_cell_corrections':previous + parsed,
        'history_corrections_sha256':evidence['source_sha256']}
    before, after = input_report(store, dataset), input_report(store, dataset, settings)
    if after['errors']:
        raise ValueError('Resolve input problems first: ' + '; '.join(after['errors']))
    # Quantities and dates use the same declared parsers; no business-value edit.
    return {'kind':'input_correction', 'dataset_id':dataset_id,
        'dataset_sha256':evidence['dataset_sha256'], 'source_sha256':evidence['source_sha256'],
        'changes':parsed, 'reason':reason.strip(), 'unit':after['unit'],
        'before_total':before['source_quantity_total'], 'after_total':after['source_quantity_total'],
        'before_prepared_total':before['summary'].get('total_demand'),
        'after_prepared_total':after['summary'].get('total_demand'),
        'warnings':after['warnings'], 'validation_sha256':digest(after),
        'row_reference':evidence['row_reference']}


def apply_correction(store, proposal, actor, request_id):
    from .input_review import digest, sources_for
    dataset = store.get(proposal['dataset_id'])
    if digest(dataset) != proposal['dataset_sha256']:
        raise ValueError('Inputs changed. Ask for a new correction review.')
    fresh = correction_proposal(store, dataset['id'], proposal['changes'], proposal['reason'])
    if fresh != proposal:
        raise ValueError('Correction evidence changed. Ask for a new review.')
    settings = {**dataset['settings'], 'history_corrections_sha256':proposal['source_sha256'], 'history_cell_corrections':
        dataset['settings'].get('history_cell_corrections', []) + proposal['changes']}
    return store.save(dataset['name'] + ' · Reviewed formatting', sources_for(dataset), settings,
        dataset['classification'], True, parent_dataset_id=dataset['id'], request_id=request_id,
        import_provenance={'kind':'assistant_formatting_review', 'actor':actor, 'proposal':proposal})

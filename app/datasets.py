"""Saved input snapshots and validation shared by the import flow and forecasting."""
from __future__ import annotations

import json
import uuid
import hashlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

import pandas as pd
from fastapi.encoders import jsonable_encoder

from .data import preview_table, read_table, prepare_history, build_future_covariates, summarize_history, actual_history, source_review
from .operations import operations_preview, read_operations_workbook, calculate_operations
from .sales_conventions import normalize_history


class DatasetStore:
    def __init__(self, root: Path, unit_store=None):
        self.root = root
        self.unit_store = unit_store
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def _path(self, kind, key):
        if not key or len(key) != 32 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Invalid saved data identifier.')
        return self.root / f'{kind}-{key}.json'

    def _write(self, path, data):
        with self.lock:
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(jsonable_encoder(data), ensure_ascii=False, allow_nan=False), encoding='utf-8')
            temp.replace(path)

    def upload(self, name, payload, role, sheet=None):
        if role not in {'history','future','operations','inventory','actuals','receipts','sales_customers','sales_orders','sales_commitments','factor_observations'}:
            raise ValueError('Choose history, future factors, or operations.')
        if role in {'inventory', 'actuals', 'receipts','sales_customers','sales_orders','sales_commitments','factor_observations'}:
            from .inventory import inventory_preview
            preview = inventory_preview(name, payload, sheet)
        else:
            preview = operations_preview(name, payload) if role == 'operations' else preview_table(name, payload, sheet_name=sheet)
        key = uuid.uuid4().hex
        row = {'id':key,'name':Path(name).name,'role':role,'sheet':sheet or preview.get('selected_sheet') or preview.get('sheet'),'preview':preview,'sha256':hashlib.sha256(payload).hexdigest(),'created_at':datetime.now(timezone.utc).isoformat()}
        (self.root / f'{key}.bin').write_bytes(payload)
        self._write(self._path('source',key),row)
        return row

    def source(self, key):
        path = self._path('source',key)
        if not path.exists(): raise ValueError('This saved file was not found. Upload it again.')
        row = json.loads(path.read_text())
        content = (self.root / f'{key}.bin').read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if row.get('sha256') and row['sha256'] != digest:
            raise ValueError('This saved file has changed since import. Upload a new version before continuing.')
        # Older imports had no digest. A new run captures the bytes it actually reads;
        # do not retroactively add provenance to already-saved forecasts.
        row['sha256'] = digest
        return row, content

    def list(self):
        return sorted([json.loads(p.read_text()) for p in self.root.glob('dataset-*.json')], key=lambda x:x['created_at'], reverse=True)

    def list_sources(self):
        return sorted([json.loads(p.read_text()) for p in self.root.glob('source-*.json')],
                      key=lambda row: row['created_at'], reverse=True)

    def get(self, key):
        path = self._path('dataset',key)
        if not path.exists(): raise ValueError('Saved dataset was not found.')
        return json.loads(path.read_text())

    def inspect(self, sources: dict, settings: dict, classification='user_provided'):
        if not sources.get('history'): raise ValueError('Upload historical data first.')
        if set(sources) - {'history', 'future', 'operations'}:
            raise ValueError('Inventory is a separate operational input, not demand history.')
        frames = {}
        for role, key in sources.items():
            if not key: continue
            source, payload = self.source(key)
            if source['role'] != role: raise ValueError(f'The {role} file has the wrong role.')
            if role == 'history' and settings.get('history_cell_corrections') and settings.get('history_corrections_sha256') != source['sha256']:
                raise ValueError('Formatting corrections belong to another history file. Review the new file without the old corrections.')
            frames[role] = read_operations_workbook(source['name'],payload,settings.get('operations_mapping'),self.unit_store) if role=='operations' else read_table(source['name'],payload,sheet_name=source['sheet'])
        frame, source_warnings = actual_history(frames['history'], unit_filter=settings.get('unit_filter'), excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
        if 'unit' in frame and settings.get('unit') != str(frame.unit.iloc[0]).strip():
            raise ValueError('The selected quantity unit does not match the source. Select the source unit; renaming it is not a conversion.')
        date_col, target_col, item_col = settings.get('date_col'), settings.get('target_col'), settings.get('item_col')
        required = [x for x in [date_col,target_col,item_col] if x]
        if not date_col or not target_col or any(x not in frame for x in required): raise ValueError('Match the date and quantity columns to your file.')
        if len(required)!=len(set(required)): raise ValueError('Date, quantity and item must use different columns.')
        frame, convention_warnings = normalize_history(frame, settings)
        from .sales_groups import series_column, customer_product_future
        item_col = series_column(settings)
        invalid_dates=frame[date_col].isna().sum()
        values=frame[target_col]
        invalid_values=(values.isna() | values.eq(float('inf')) | values.eq(float('-inf'))).sum()
        if invalid_dates or invalid_values: raise ValueError(f'Fix {invalid_dates} unreadable date(s) and {invalid_values} missing, negative or invalid quantity value(s) in the source file before continuing.')
        if item_col and (frame[item_col].isna() | frame[item_col].astype(str).str.strip().eq('')).any(): raise ValueError('Some rows have no item identifier. Fill these before continuing.')
        frequency=settings.get('frequency','monthly'); horizon=int(settings.get('horizon',6))
        if frequency not in {'monthly','weekly','daily'} or not 1<=horizon<=24: raise ValueError('Choose a valid frequency and a horizon from 1 to 24.')
        drivers=settings.get('drivers',[])
        if not isinstance(drivers,list) or any(x not in frame for x in drivers): raise ValueError('Selected factors must exist in historical data.')
        if set(drivers)&set(required): raise ValueError('Date, item and target cannot also be forecasting factors.')
        clean,warnings=prepare_history(frame,date_col=date_col,target_col=target_col,item_col=item_col or None,driver_cols=drivers,frequency=frequency,missing_strategy=settings.get('missing_strategy','auto'),outlier_strategy=settings.get('outlier_strategy','none'),calendar_country=settings.get('calendar_country','IR') or None,weekend_days=tuple(settings.get('weekend_days',[4])),shutdown_dates=tuple(settings.get('shutdown_dates',[])),month_basis=settings.get('month_basis','gregorian'))
        future_frame, future_item = customer_product_future(frames.get('future'), frame, settings)
        future,future_warnings=build_future_covariates(clean,future_frame,future_date_col=settings.get('future_date_col') or None,future_item_col=future_item or None,known_driver_cols=drivers,frequency=frequency,horizon=horizon,missing_future_policy=settings.get('future_driver_policy','require'),input_calendar=settings.get('future_calendar','gregorian'))
        # Validate operational schema and references without fitting models.
        if 'operations' in frames:
            line_col = settings.get('production_line_col') or 'production_line'
            if frequency!='monthly': raise ValueError('Operations planning currently needs a monthly forecast. Choose monthly or remove the operations file.')
            routed = 'routing' in frames['operations']
            if not routed and settings.get('unit')!='tonnes': raise ValueError('Tonne-based lines need demand in tonnes. Choose product routes for other demand units.')
            if not routed and (line_col not in frame or frame[line_col].isna().any() or frame[line_col].astype(str).str.strip().eq('').any()):
                raise ValueError('Production data needs a production_line column in history to match each item to its capacity calendar.')
            metadata={}; series={}
            for identifier,group in clean.groupby('item_id'):
                source_rows=frame[frame[item_col].astype(str)==str(identifier)] if item_col else frame
                last=source_rows.iloc[-1]
                sku_col=settings.get('sku_col') or item_col
                if not routed and source_rows[line_col].astype(str).str.strip().nunique() != 1:
                    raise ValueError(f'Item {identifier} has multiple production lines. A reviewed routing is needed before capacity planning.')
                metadata[str(identifier)]={'sku':str(last[sku_col]) if sku_col else str(identifier),'production_line':str(last[line_col]).strip() if not routed else None}
                series[str(identifier)]={'forecast':[{'timestamp':r.timestamp,'mean':0} for r in future[future.item_id.astype(str)==str(identifier)].itertuples()]}
            calculate_operations({'metadata':metadata,'series':series,'unit':settings.get('unit'), 'source_classification':classification},frames['operations'])
            bom=frames['operations']['bom']; materials=frames['operations']['materials']
            unknown=set(bom.material_id.astype(str))-set(materials.material_id.astype(str))
            if unknown: raise ValueError('BOM refers to unknown materials: '+', '.join(sorted(unknown)))
            cached_count = sum(f.attrs.get('cached_formula_cells', 0) for f in frames['operations'].values())
            if cached_count:
                source_warnings.append(f'{cached_count} mapped production cells use saved Excel formula results. Confirm the workbook was recalculated before export.')
        summary=summarize_history(clean)
        return {'summary':summary,'sales_conventions':clean.attrs.get('sales_conventions',{}),'warnings':source_warnings+warnings+future_warnings,'source_review':source_review(frames['history']),'driver_coverage':future.attrs.get('driver_coverage',{}),'forecast_start':future.timestamp.min().strftime('%Y-%m-%d'),'forecast_end':future.timestamp.max().strftime('%Y-%m-%d'),'preview':json.loads(clean[['item_id','timestamp','target']].head(8).to_json(orient='records',date_format='iso'))}

    def save(self, name, sources, settings, classification='user_provided', accept_warnings=False, *, provenance=None, identifier=None, parent_dataset_id=None, import_provenance=None, request_id=None):
        if not name.strip(): raise ValueError('Enter a dataset name.')
        if request_id is not None and (not isinstance(request_id,str) or not 1<=len(request_id)<=200 or identifier):
            raise ValueError('Use one valid save request identifier.')
        fingerprint = hashlib.sha256(json.dumps(jsonable_encoder(dict(name=name.strip(),sources=sources,settings=settings,
            classification=classification,parent_dataset_id=parent_dataset_id,provenance=provenance,
            import_provenance=import_provenance)),sort_keys=True,allow_nan=False).encode()).hexdigest()
        key = uuid.uuid5(uuid.NAMESPACE_URL,'demandlab-dataset:'+request_id).hex if request_id else identifier or uuid.uuid4().hex
        path = self._path('dataset',key)
        def existing():
            row = self.get(key)
            if not request_id or row.get('save_fingerprint') != fingerprint:
                raise ValueError('This save request was already used for different inputs; saved versions cannot be overwritten.')
            return row
        if path.exists(): return existing()
        parent = self.get(parent_dataset_id) if parent_dataset_id else None
        if sources.get('operations') and not settings.get('operations_mapping'):
            raise ValueError('Review the production mappings and stock date before saving this dataset.')
        from .input_review import validate_import
        review=validate_import(self,sources,settings,classification)
        if review['warnings'] and not accept_warnings: raise ValueError('Review and acknowledge the data adjustments before saving.')
        row={'id':key,'name':name.strip(),'sources':sources,'settings':settings,'classification':classification,'review':review,'created_at':datetime.now(timezone.utc).isoformat()}
        if request_id: row['save_fingerprint'] = fingerprint
        if parent:
            row['parent_dataset_id'] = parent['id']
            row['replaced_sources'] = [role for role in sorted(set(parent['sources']) | set(sources))
                                       if parent['sources'].get(role) != sources.get(role)]
        if provenance:
            row['scenario_provenance'] = provenance
        if import_provenance:
            row['import_provenance'] = import_provenance
        # Publish a fully written file without overwriting another process's save.
        # A hard link is atomic on the local filesystem; temporary bytes are never
        # listed as a dataset. The loser of a concurrent retry reads the winner.
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.root,prefix='.dataset-',delete=False) as stream:
            temporary = Path(stream.name)
            try:
                json.dump(jsonable_encoder(row),stream,ensure_ascii=False,allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        try:
            os.link(temporary,path)
        except FileExistsError:
            return existing()
        finally:
            temporary.unlink(missing_ok=True)
        return row

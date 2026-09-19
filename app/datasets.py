"""Saved input snapshots and validation shared by the import flow and forecasting."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

import pandas as pd
from fastapi.encoders import jsonable_encoder

from .data import preview_table, read_table, prepare_history, build_future_covariates, summarize_history
from .operations import operations_preview, read_operations_workbook, calculate_operations


class DatasetStore:
    def __init__(self, root: Path):
        self.root = root
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
        if role not in {'history','future','operations'}:
            raise ValueError('Choose history, future factors, or operations.')
        preview = operations_preview(name, payload) if role == 'operations' else preview_table(name, payload, sheet_name=sheet)
        key = uuid.uuid4().hex
        row = {'id':key,'name':Path(name).name,'role':role,'sheet':sheet or preview.get('selected_sheet'),'preview':preview,'created_at':datetime.now(timezone.utc).isoformat()}
        (self.root / f'{key}.bin').write_bytes(payload)
        self._write(self._path('source',key),row)
        return row

    def source(self, key):
        path = self._path('source',key)
        if not path.exists(): raise ValueError('This saved file was not found. Upload it again.')
        row = json.loads(path.read_text())
        return row, (self.root / f'{key}.bin').read_bytes()

    def list(self):
        return sorted([json.loads(p.read_text()) for p in self.root.glob('dataset-*.json')], key=lambda x:x['created_at'], reverse=True)

    def get(self, key):
        path = self._path('dataset',key)
        if not path.exists(): raise ValueError('Saved dataset was not found.')
        return json.loads(path.read_text())

    def inspect(self, sources: dict, settings: dict):
        if not sources.get('history'): raise ValueError('Upload historical data first.')
        frames = {}
        for role, key in sources.items():
            if not key: continue
            source, payload = self.source(key)
            if source['role'] != role: raise ValueError(f'The {role} file has the wrong role.')
            frames[role] = read_operations_workbook(source['name'],payload) if role=='operations' else read_table(source['name'],payload,sheet_name=source['sheet'])
        frame = frames['history']
        if 'record_type' in frame:
            mask=frame.record_type.astype(str).str.lower().eq('actual')
            if mask.any(): frame=frame[mask].copy()
        date_col, target_col, item_col = settings.get('date_col'), settings.get('target_col'), settings.get('item_col')
        required = [x for x in [date_col,target_col,item_col] if x]
        if not date_col or not target_col or any(x not in frame for x in required): raise ValueError('Match the date and quantity columns to your file.')
        if len(required)!=len(set(required)): raise ValueError('Date, quantity and item must use different columns.')
        invalid_dates=pd.to_datetime(frame[date_col],errors='coerce').isna().sum()
        values=pd.to_numeric(frame[target_col],errors='coerce')
        invalid_values=(values.isna() | ~values.between(0,float('inf')) | values.eq(float('inf'))).sum()
        if invalid_dates or invalid_values: raise ValueError(f'Fix {invalid_dates} unreadable date(s) and {invalid_values} missing, negative or invalid quantity value(s) in the source file before continuing.')
        if item_col and (frame[item_col].isna() | frame[item_col].astype(str).str.strip().eq('')).any(): raise ValueError('Some rows have no item identifier. Fill these before continuing.')
        frequency=settings.get('frequency','monthly'); horizon=int(settings.get('horizon',6))
        if frequency not in {'monthly','weekly','daily'} or not 1<=horizon<=24: raise ValueError('Choose a valid frequency and a horizon from 1 to 24.')
        drivers=settings.get('drivers',[])
        if not isinstance(drivers,list) or any(x not in frame for x in drivers): raise ValueError('Selected factors must exist in historical data.')
        if set(drivers)&set(required): raise ValueError('Date, item and target cannot also be forecasting factors.')
        clean,warnings=prepare_history(frame,date_col=date_col,target_col=target_col,item_col=item_col or None,driver_cols=drivers,frequency=frequency,missing_strategy=settings.get('missing_strategy','auto'),outlier_strategy=settings.get('outlier_strategy','none'))
        future,future_warnings=build_future_covariates(clean,frames.get('future'),future_date_col=settings.get('future_date_col') or None,future_item_col=settings.get('future_item_col') or None,known_driver_cols=drivers,frequency=frequency,horizon=horizon,missing_future_policy=settings.get('future_driver_policy','require'))
        # Validate operational schema and references without fitting models.
        if 'operations' in frames:
            if frequency!='monthly': raise ValueError('Operations planning currently needs a monthly forecast. Choose monthly or remove the operations file.')
            if settings.get('unit')!='tonnes': raise ValueError('The operations workbook uses quantities per tonne. Choose tonnes, or remove this file and convert your quantities before using Supply.')
            if 'production_line' not in frame or frame.production_line.isna().any():
                raise ValueError('Production data needs a production_line column in history to match each item to its capacity calendar.')
            metadata={}; series={}
            for identifier,group in clean.groupby('item_id'):
                source_rows=frame[frame[item_col].astype(str)==str(identifier)] if item_col else frame
                last=source_rows.iloc[-1]
                sku_col=settings.get('sku_col') or item_col
                metadata[str(identifier)]={'sku':str(last[sku_col]) if sku_col else str(identifier),'production_line':str(last.production_line)}
                series[str(identifier)]={'forecast':[{'timestamp':r.timestamp,'mean':0} for r in future[future.item_id.astype(str)==str(identifier)].itertuples()]}
            calculate_operations({'metadata':metadata,'series':series},frames['operations'])
            bom=frames['operations']['bom']; materials=frames['operations']['materials']
            unknown=set(bom.material_id.astype(str))-set(materials.material_id.astype(str))
            if unknown: raise ValueError('BOM refers to unknown materials: '+', '.join(sorted(unknown)))
        summary=summarize_history(clean)
        return {'summary':summary,'warnings':warnings+future_warnings,'driver_coverage':future.attrs.get('driver_coverage',{}),'forecast_start':future.timestamp.min().strftime('%Y-%m-%d'),'forecast_end':future.timestamp.max().strftime('%Y-%m-%d'),'preview':json.loads(clean[['item_id','timestamp','target']].head(8).to_json(orient='records',date_format='iso'))}

    def save(self, name, sources, settings, classification='user_provided', accept_warnings=False):
        if not name.strip(): raise ValueError('Enter a dataset name.')
        review=self.inspect(sources,settings)
        if review['warnings'] and not accept_warnings: raise ValueError('Review and acknowledge the data adjustments before saving.')
        key=uuid.uuid4().hex
        row={'id':key,'name':name.strip(),'sources':sources,'settings':settings,'classification':classification,'review':review,'created_at':datetime.now(timezone.utc).isoformat()}
        self._write(self._path('dataset',key),row)
        return row

"""Explicit quantity scenarios preserve the selected forecast, not a refitted model."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import shutil
import uuid

import pandas as pd

from .operations import calculate_operations, append_operations_export


def quantity_scenario(base: dict, *, name: str, adjustment: float, runs_dir: Path, operations=None, source_runs_dir=None) -> dict:
    if not name.strip():
        raise ValueError('Enter a scenario name.')
    if base.get('scenario_name'):
        raise ValueError('Create scenarios from an unadjusted forecast.')
    if not -90 <= adjustment <= 300:
        raise ValueError('Demand change must be between −90% and 300%.')
    result=deepcopy(base)
    result.update(run_id=uuid.uuid4().hex[:12],base_run_id=base['run_id'],scenario_name=name.strip())
    result['issued_at'] = datetime.now(timezone.utc).isoformat()
    result['run_settings']['scenario_adjustment_pct']=adjustment
    result['scenario']={'type':'quantity_adjustment','percent':adjustment,'base_run_id':base['run_id'],'refitted':False}
    multiplier=1+adjustment/100
    def adjust(row):
        row['baseline_mean']=row['mean']
        for key in ('mean','p50','p10','p90'):
            if row.get(key) is not None: row[key]*=multiplier
        row['scenario_adjustment_pct']=adjustment
    for series in result['series'].values():
        for row in series['forecast']: adjust(row)
    for row in result.get('forecast_rows',[]): adjust(row)
    if operations:
        result['operations']=calculate_operations(result,operations)
    folder=runs_dir/result['run_id']
    folder.mkdir()
    original=(source_runs_dir or runs_dir)/base['run_id']
    for filename in ('history_clean.csv','model_leaderboard.csv','driver_importance.csv','forecast_package.xlsx'):
        if (original/filename).exists(): shutil.copy2(original/filename,folder/filename)
    forecast=pd.DataFrame(result.get('forecast_rows',[]))
    forecast.to_csv(folder/'forecast.csv',index=False)
    book=folder/'forecast_package.xlsx'
    mode='a' if book.exists() else 'w'
    with pd.ExcelWriter(book,engine='openpyxl',mode=mode,**({'if_sheet_exists':'replace'} if mode=='a' else {})) as writer:
        forecast.to_excel(writer,sheet_name='Forecast',index=False)
        pd.DataFrame([result['scenario']]).to_excel(writer,sheet_name='Scenario',index=False)
        pd.DataFrame([{'setting':k,'value':str(v)} for k,v in result['run_settings'].items()]).to_excel(writer,sheet_name='Run Settings',index=False)
    if operations: append_operations_export(book,result['operations'])
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,default=str),encoding='utf-8')
    return result

"""Compose scoped factor forecasts without changing unselected baseline results."""
from copy import deepcopy
import pandas as pd
from .scoped_accuracy import scoped_accuracy


def apply_factor_scope(result, base, selected, folder):
    if selected is None:
        return
    selected = set(selected)
    accuracy = scoped_accuracy(base,result,selected)
    keys = set(base['series']) - {'__all__'}
    if not selected or selected - keys or set(result['series']) != set(base['series']):
        raise ValueError('Factor scenario scope does not match its baseline.')
    for key in keys:
        before = [r['timestamp'] for r in base['series'][key]['forecast']]
        after = [r['timestamp'] for r in result['series'][key]['forecast']]
        if before != after:
            raise ValueError('Factor scenario periods do not match its baseline.')
    for key in keys - selected:
        result['series'][key] = deepcopy(base['series'][key])
    if result.get('factor_evaluation'):
        result['factor_evaluation']['rows']=[row for row in result['factor_evaluation']['rows'] if row['item_id'] in selected]
        result['factor_evaluation']['scope_note']='Unselected customer/products retain their saved baseline; factor tests apply only to the selected scope.'
        import json
        (folder/'factor_evaluation.json').write_text(json.dumps(result['factor_evaluation'],indent=2))
    result['forecast_rows'] = [deepcopy(row) for row in result['forecast_rows'] if str(row['item_id']) in selected] + [
        deepcopy(row) for row in base['forecast_rows'] if str(row['item_id']) not in selected]
    totals = {}
    for key in keys:
        for row in result['series'][key]['forecast']:
            totals[row['timestamp']] = totals.get(row['timestamp'],0.) + row['mean']
    aggregate = deepcopy(base['series']['__all__'])
    aggregate['forecast'] = [dict(item_id='All series',timestamp=period,mean=value,p50=value,
        baseline_mean=value,scenario_adjustment_pct=0,p10=None,p90=None)
        for period,value in sorted(totals.items())]
    aggregate['methods'] = {}
    result['series']['__all__'] = aggregate
    note = ('Selected series use the factor-model calculation; other series retain their saved baseline. '
            'Shared models may learn across all history. Portfolio ranges are not validated '
            'for this mixed scenario. ' + accuracy['reason'])
    result['warnings'] = list(dict.fromkeys([*result.get('warnings',[]),note]))
    # The full refit's scores/ranges must not be advertised as evidence for a mixed plan.
    for key in ('wape_pct','mae','rmse','smape_pct','bias_pct','interval_coverage_pct'):
        result['metrics'][key] = None
    result['metrics']['independent_accuracy_verified'] = False
    result['metrics']['scope_note'] = note
    result['metrics']['horizon_metrics'] = []
    if accuracy['available']:
        result['metrics'].update(accuracy['metrics'])
        result['metrics']['independent_accuracy_verified'] = True
        result['metrics']['horizon_metrics'] = accuracy['horizon_metrics']
    result['scoped_accuracy'] = accuracy
    result['metrics'].pop('range_check',None)
    result['range_model'] = {}
    result['range_fitting_rows'] = []
    result['leaderboard'] = []
    result['drivers'] = []
    result['series_diagnostics'] = {}
    for key in keys - selected:
        if key in base.get('series_ensemble_weights',{}):
            result.setdefault('series_ensemble_weights',{})[key] = deepcopy(base['series_ensemble_weights'][key])
    frame = pd.DataFrame(result['forecast_rows'])
    frame.to_csv(folder/'forecast.csv',index=False)
    pd.DataFrame(columns=['model']).to_csv(folder/'model_leaderboard.csv',index=False)
    pd.DataFrame(columns=['feature']).to_csv(folder/'driver_importance.csv',index=False)
    with pd.ExcelWriter(folder/'forecast_package.xlsx',engine='openpyxl',mode='a',if_sheet_exists='replace') as writer:
        if result.get('factor_evaluation'):
            import json
            rows=result['factor_evaluation']['rows']
            pd.DataFrame([{k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in rows]).to_excel(
                writer,sheet_name='Factor choices',index=False)
        frame.to_excel(writer,sheet_name='Forecast',index=False)
        for sheet in ('Models','Drivers','Series Diagnostics','Range check','Range fitting','Range parameters','Range policy'):
            if sheet in writer.book.sheetnames:
                del writer.book[sheet]
        pd.DataFrame([{'series_id':key,'source':'Factor scenario' if key in selected else 'Saved baseline'}
                      for key in sorted(keys)]).to_excel(writer,sheet_name='Factor scope',index=False)
        pd.DataFrame([{'note':note}]).to_excel(writer,sheet_name='Scope limitations',index=False)
        pd.DataFrame(accuracy['rows']).to_excel(writer,sheet_name='Scoped accuracy evidence',index=False)
        pd.DataFrame([accuracy.get('metrics',{'status':accuracy['reason']})]).to_excel(writer,sheet_name='Scoped accuracy',index=False)
        for sheet in writer.book:
            for row in sheet:
                for cell in row:
                    if cell.data_type == 'f':
                        cell.data_type = 's'

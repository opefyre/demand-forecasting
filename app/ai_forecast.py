"""Shared preflight and bounded evidence for assistant forecast requests."""
import json


def forecast_preflight(store, source, months, method):
    if source.get('scenario_provenance'):
        raise ValueError('Open the original baseline before changing a scenario horizon.')
    settings = {**source['settings'], 'horizon':months, 'method_selection':method}
    sources = {k:v for k,v in source['sources'].items() if k in {'history','future'}}
    review = store.inspect(sources,settings,source['classification'])
    previous = {json.dumps(w,sort_keys=True) for w in source.get('review',{}).get('warnings',[])}
    if any(json.dumps(w,sort_keys=True) not in previous for w in review.get('warnings',[])):
        raise ValueError('The new horizon introduces data warnings. Review it in Data before running.')
    return settings, sources


def method_evidence(run):
    fields = ('model','wape_pct','mae','rmse','smape_pct','bias_pct','status','selection_loss',
              'failure_count','confirmation','stability_pct','weight','recommended_weight')
    leaders = run.get('leaderboard',[])
    metrics = run.get('metrics',{})
    # Keep decisive scalar evidence and separately measured errors; omit bulky row-level traces.
    compact = {k:v for k,v in metrics.items() if v is None or isinstance(v,(str,int,float,bool))}
    return {'leaderboard':[{k:r[k] for k in fields if k in r} for r in leaders[:40]],
            'model_count':len(leaders),'truncated':len(leaders)>40,'metrics':compact,
            'warnings':run.get('warnings',[]),'selected':run.get('method_selection'),
            'classification':run.get('source_classification'),
            'detail_note':'Row-level and horizon-level traces omitted. Use Accuracy for the full evidence; no new models were tested.'}

"""Reproducible artificial sales/factors. Not Iranian market observations."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]/'sample_data'/'factor_testing'
CASES=('useful_signal','irrelevant_factors','mixed_customers','changed_relationship','sparse_demand','short_history')


def generate(case,seed=7301):
    if case not in CASES: raise ValueError('Unknown synthetic case.')
    rng=np.random.default_rng(seed)
    count=24 if case=='short_history' else 84
    dates=pd.date_range(end='2026-09-01',periods=count,freq='MS')
    # Sticky but irregular levels, not handpicked to produce a winning model.
    pressure=np.zeros(count+6)
    for i in range(1,len(pressure)):
        pressure[i]=.85*pressure[i-1]+rng.normal(0,.55)
    fx=800000+np.arange(count+6)*11000+pressure*130000
    noise=rng.normal(0,1,count+6)
    rows=[];truth=[]
    pairs=[('Demo Tehran A','0001',170),('Demo Tehran A','0002',85),('Demo Tehran B','0001',230),('Demo Tehran C','0003',40)]
    for customer,sku,level in pairs:
        for i in range(count+6):
            seasonal=1+.18*np.sin(2*np.pi*i/12)+.06*np.cos(4*np.pi*i/12)
            # Approximate spring dip, not actual Persian holiday/day attribution.
            month=(dates[0]+pd.DateOffset(months=i)).month
            seasonal*=.85 if month==3 else 1.
            sensitivity=.00016 if case in {'useful_signal','changed_relationship','short_history'} else (.00016 if case=='mixed_customers' and customer=='Demo Tehran A' else 0.)
            if case=='changed_relationship' and i>=count-6:sensitivity*=-.7
            qty=max(0,level*seasonal+sensitivity*(fx[i]-1000000)+rng.normal(0,level*.08))
            if case=='sparse_demand' and rng.random()<.7:qty=0.
            day=dates[0]+pd.DateOffset(months=i)
            record={'date':day.date().isoformat(),'series':customer+'/'+sku,'customer':customer,'sku':sku,
                    'quantity':round(qty,2),'exchange_rate':round(float(fx[i]),2),'unrelated_index':round(float(noise[i]),5)}
            (rows if i<count else truth).append(record)
    future=[]
    for customer,sku,_ in pairs:
        for day in pd.date_range('2026-10-01',periods=6,freq='MS'):
            future.append({'date':str(day.date()),'series':customer+'/'+sku,'exchange_rate':round(float(fx[count-1]),2),
                           'unrelated_index':round(float(noise[count-1]),5)})
    return pd.DataFrame(rows),pd.DataFrame(future),pd.DataFrame(truth),pairs


def write_samples():
    ROOT.mkdir(exist_ok=True)
    summaries=[]
    for case in CASES:
        data,future,truth,pairs=generate(case)
        data.to_csv(ROOT/(case+'-history.csv'),index=False)
        future.to_csv(ROOT/(case+'-assumptions.csv'),index=False)
        truth.to_csv(ROOT/(case+'-withheld-actuals.csv'),index=False)
        summaries.append({'case':case,'history_rows':len(data),'months':data.date.nunique(),
            'total_tonnes':round(float(data.quantity.sum()),2),'forecast_months':6,'seed':7301})
    (ROOT/'manifest.json').write_text(json.dumps({'classification':'synthetic_sample','geography':'Tehran-inspired synthetic customer names',
        'unit':'tonnes','calendar':'gregorian','quantity_meaning':'generated_customer_demand',
        'factor_meaning':'generated_IRR_per_USD_and_unrelated_index_not_market_data',
        'future_policy':'last_historical_value_is_an_explicit_synthetic_assumption',
        'warning':'Realistic-scale artificial scenarios, not client or live-market facts. Withheld actuals are not inputs.',
        'cases':summaries},indent=2))
    return summaries


if __name__=='__main__':
    print(json.dumps(write_samples(),indent=2))

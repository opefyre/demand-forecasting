"""Bounded live checks: synthetic demo only, read/propose only, never approve actions."""
import argparse
import json
from pathlib import Path
import time
import requests

CASES = [
    ('lookup', 'For Demo customer A, show the saved monthly demand. Keep it brief. Do not create a forecast or export.', None),
    ('horizon', 'Prepare a forecast for Demo customer A for the next 10 months. Use the recommended method. Do not run until I approve.', None),
    ('followup', 'Actually make that 8 months for the same customer. Do not run yet.', 'horizon'),
    ('ambiguous', 'Prepare a forecast for Demo customer for 6 months. I have not chosen which customer yet.', None),
    ('review', 'Review the selected sales and factor inputs for missing values or mapping problems. Report only verified issues; do not modify anything.', None),
    ('unknown', 'Give me the demand for Customer NeverExists. Do not guess a different customer or invent quantities.', None),
]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true')
    parser.add_argument('--case', choices=[c[0] for c in CASES]);args=parser.parse_args()
    if not args.live:parser.error('Use --live to authorize bounded, billable OpenAI calls with synthetic data.')
    base='http://127.0.0.1:8010'; run_id='58df6ab41b1f'; snapshot='37d0646991260d00a76812640c96d2a4'
    run=requests.get(f'{base}/api/runs/{run_id}',timeout=20).json()
    assert run['source_classification']=='synthetic_sample'
    originals=requests.get(f'{base}/api/sales/inputs/{snapshot}',timeout=20).json()
    assert originals['inputs']['classification']=='synthetic_sample'
    results=[]; ids={}
    for name,question,parent in CASES:
        if args.case and name!=args.case:continue
        if parent and parent not in ids:raise ValueError('Run the full suite for a conversation follow-up.')
        payload={'run_id':run_id,'snapshot_id':snapshot,'question':question,'consent':True}
        if parent:payload['previous_turn_id']=ids[parent]
        start=time.monotonic(); response=requests.post(base+'/api/ai/chat',json=payload,timeout=170)
        result=response.json(); ids[name]=result.get('id')
        record={'case':name,'seconds':round(time.monotonic()-start,2),'status':response.status_code,**result}
        actions=result.get('actions',[])
        if response.status_code==200:
            if name in {'horizon','followup'}:
                expected=10 if name=='horizon' else 8
                record['contract_passed']=len(actions)==1 and all(actions[0].get(k)==v for k,v in
                    {'kind':'forecast','customer':'Demo A','months':expected,'method':'recommended'}.items())
            else:
                record['contract_passed']=not actions and result.get('role')==('review' if name=='review' else 'decision' if name=='ambiguous' else 'query')
        results.append(record);print(json.dumps(record),flush=True)
        if response.status_code!=200:break
    assert originals==requests.get(f'{base}/api/sales/inputs/{snapshot}',timeout=20).json()
    output=Path('outputs/assistant-live');output.mkdir(parents=True,exist_ok=True)
    (output/(args.case or 'suite')).with_suffix('.json').write_text(json.dumps(results,indent=2))
    if any(r['status']!=200 or not r.get('contract_passed') for r in results):raise SystemExit(1)

if __name__=='__main__':main()

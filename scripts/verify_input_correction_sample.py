"""Explicit synthetic local sample. No OpenAI call; original inputs remain intact."""
import json
from pathlib import Path
import requests
from app.input_corrections import correction_evidence, correction_proposal, apply_correction
from app.datasets import DatasetStore


def verify():
    root=Path(__file__).resolve().parents[1]
    store=DatasetStore(root/'data'/'datasets')
    path=root/'sample_data'/'formatting_history_demo.csv'
    file=store.upload(path.name,path.read_bytes(),'history')
    settings={'date_col':'date','target_col':'qty','item_col':'item','customer_col':'customer',
        'sku_col':'sku','frequency':'monthly','horizon':3,'unit':'tonnes','outlier_strategy':'none',
        'history_calendar':'gregorian','history_grain':'transactions','month_basis':'gregorian',
        'sales_measure':'recorded_sales','returns_policy':'reject','profile':'fast','drivers':[]}
    parent=store.save('Demo · formatting review',{'history':file['id']},settings,'synthetic_sample',True)
    evidence=correction_evidence(store,parent)
    proposal=correction_proposal(store,parent['id'],evidence['cells'],'Synthetic sample: trim customer outer spaces only.')
    saved=apply_correction(store,proposal,'Local synthetic verification','sample-format-'+parent['id'])
    response=requests.post('http://127.0.0.1:8010/api/run-saved',json={'dataset_id':saved['id'],'method':'model:Last observed'},timeout=90)
    response.raise_for_status();run=response.json()
    assert run['metadata']['A/P']['customer']=='A'
    assert run['metadata']['A/P']['sku']=='0001'
    assert run['summary']['total_demand']==210
    assert store.get(parent['id'])==parent and store.source(file['id'])[1]==path.read_bytes()
    result={'parent_dataset_id':parent['id'],'corrected_dataset_id':saved['id'],'run_id':run['run_id'],
        'corrections':len(proposal['changes']),'history_total':210,'original_preserved':True,
        'provider_calls':0,'sample_only':True}
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__': verify()

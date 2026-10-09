"""Compose separately reviewed factor groups using existing calculations, not new maths."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import uuid

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from .factor_imports import digest
from .factor_links import inputs, preview_link
from .runtime import checkpoint


class BatchInputs(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    dataset_ids: list[str]=Field(min_length=1,max_length=20)
    require_connected_sources: StrictBool=False


class BatchSave(BatchInputs):
    reviewed: StrictBool
    review_token: str
    request_id: str


def preview_batch(base,datasets,factors,payload,live=None,profiles=None):
    value=BatchInputs.model_validate(payload)
    if base.get('base_run_id') or base.get('scenario_name'):
        raise ValueError('Start a customer/product batch from the original forecast.')
    original,*_=inputs(base,datasets)
    if len(set(value.dataset_ids))!=len(value.dataset_ids):
        raise ValueError('Add each reviewed group once.')
    known=set(base['series'])-{'__all__'};seen=set();groups=[]
    for key in value.dataset_ids:
        child=datasets.get(key);proof=child.get('scenario_provenance',{})
        if proof.get('type')!='factor_link' or proof.get('base_run_id')!=base['run_id']:
            raise ValueError('Every group must be a reviewed factor comparison of this baseline.')
        if proof.get('baseline_sha256')!=digest(base):
            raise ValueError('The baseline changed or this is an older comparison. Review the group again.')
        if proof.get('derived_inputs_sha256')!=digest({'sources':child['sources'],'settings':child['settings']}):
            raise ValueError('A group’s calculation inputs changed after review.')
        selected=proof.get('alignment',{}).get('series_ids')
        if not selected or set(selected)-known:
            raise ValueError('Review an explicit customer/product scope for every group.')
        if seen.intersection(selected):
            raise ValueError('A customer/product appears in more than one group. Remove the overlap.')
        seen.update(selected)
        reviewed=proof.get('reviewed_inputs')
        if not reviewed:raise ValueError('Review this older factor comparison again before adding it to a batch.')
        report=preview_link(base,datasets,factors,reviewed,live,profiles)
        if report['missing'] or report['review_token']!=proof['review_token']:
            raise ValueError('A group’s profile, source or assumptions changed. Review that group again.')
        if value.require_connected_sources:
            from .factor_preparation import connected_source_readiness
            for source in report.get('factors',[report]):
                if not connected_source_readiness(source['snapshot_id'],live)['ready']:
                    raise ValueError('A connected source is no longer ready. Refresh and review it before calculating.')
        for source in child['sources'].values():
            if source:datasets.source(source)
        if child['classification']!=original['classification']:
            raise ValueError('Do not combine real and sample sales inputs.')
        groups.append({'dataset_id':key,'dataset_sha256':digest(child),'series_ids':sorted(selected),
            'series':[{'id':s,**base.get('metadata',{}).get(s,{})} for s in sorted(selected)],
            'method':report['method'],'retrospective':bool(report.get('retrospective')),
            'profile':report.get('preparation',{}).get('profile'),
            'factors':[{'name':r['factor'],'snapshot_id':r['snapshot_id'],'lag_months':r['lag_months'],
                        'unit':r['unit'],'geography':r['geography']} for r in report.get('factors',[report])],
            'alignment':report})
    report={'base_run_id':base['run_id'],'groups':groups,'series_count':len(seen),
            'unchanged_series_ids':sorted(known-seen),'baseline_sha256':digest(base),
            'retrospective':any(g['retrospective'] for g in groups),
            'policy':'Each reviewed group is calculated separately. Other series keep their baseline. '
                     'Orders must be reviewed afterwards; they are not copied or added twice. '
                     'No combined accuracy score or portfolio range is claimed.'}
    if value.require_connected_sources:report['require_connected_sources']=True
    report['review_token']=digest(report)
    return report


def save_batch(base,datasets,factors,payload,live=None,profiles=None):
    value=BatchSave.model_validate(payload)
    if not value.reviewed:raise ValueError('Review the groups and unchanged products before calculating.')
    request=str(uuid.UUID(value.request_id))
    report=preview_batch(base,datasets,factors,{'dataset_ids':value.dataset_ids,'require_connected_sources':value.require_connected_sources},live,profiles)
    if value.review_token!=report['review_token']:raise ValueError('The batch changed. Review the current groups again.')
    identifier=uuid.uuid5(uuid.NAMESPACE_URL,'factor-batch:'+request).hex
    original=datasets.get(base['dataset_id'])
    with datasets.lock:
        if datasets._path('dataset',identifier).exists():
            found=datasets.get(identifier)
            if found.get('scenario_provenance',{}).get('review_token')!=report['review_token']:
                raise ValueError('This request already saved a different batch.')
            return found
        proof={'type':'factor_batch','name':'Customer/product factors · monthly forecast',
               'base_run_id':base['run_id'],'review_token':report['review_token'],
               'dataset_ids':value.dataset_ids,'alignment':report,'require_connected_sources':value.require_connected_sources,
               'orders_changed':False,'recorded_at':datetime.now(timezone.utc).isoformat()}
        return datasets.save(proof['name'],deepcopy(original['sources']),deepcopy(original['settings']),
                             original['classification'],True,identifier=identifier,
                             parent_dataset_id=original['id'],provenance=proof)


def check_saved_batch(base,dataset,datasets,factors,live=None,profiles=None):
    proof=dataset['scenario_provenance']
    report=preview_batch(base,datasets,factors,{'dataset_ids':proof['dataset_ids'],'require_connected_sources':proof.get('require_connected_sources',False)},live,profiles)
    if report['review_token']!=proof['review_token']:
        raise ValueError('Batch evidence changed. Review profiles, sources and assumptions again.')
    return report


def compose_batch(base,dataset,report,children,runs_dir):
    if len(children)!=len(report['groups']):raise ValueError('Every batch group must finish successfully.')
    result=deepcopy(base);keys=set(base['series'])-{'__all__'}
    selected=set();rows=[];evidence=[];evaluation=[];weights={}
    for group,child in zip(report['groups'],children):
        if (child.get('base_run_id')!=base['run_id'] or child.get('dataset_id')!=group['dataset_id']
                or child.get('engine')!=base.get('engine') or child.get('unit')!=base.get('unit')):
            raise ValueError('A calculation does not match its reviewed batch group.')
        if set(child['series'])!=set(base['series']):raise ValueError('Batch series changed during calculation.')
        for key in group['series_ids']:
            if key in selected or key not in keys:raise ValueError('Batch customer/product scope overlaps or changed.')
            before=base['series'][key]['forecast'];after=child['series'][key]['forecast']
            if [r['timestamp'] for r in before]!=[r['timestamp'] for r in after]:
                raise ValueError('Batch groups must have identical forecast months.')
            if any(isinstance(r['mean'],bool) or not math.isfinite(r['mean']) or r['mean']<0 for r in after):
                raise ValueError('A group returned invalid forecast quantities.')
            result['series'][key]=deepcopy(child['series'][key]);selected.add(key)
            weights[key]=deepcopy(child.get('series_ensemble_weights',{}).get(key,{}))
        rows.extend(deepcopy(r) for r in child['forecast_rows'] if r['item_id'] in group['series_ids'])
        evidence.append({'dataset_id':group['dataset_id'],'series_ids':group['series_ids'],
                         'method':group['method'],'validation':child.get('factor_validation'),
                         'model_failures':child.get('model_failures',[])})
        evaluation.extend(deepcopy(r) for r in child.get('factor_evaluation',{}).get('rows',[]) if r['item_id'] in group['series_ids'])
    rows.extend(deepcopy(r) for r in base['forecast_rows'] if r['item_id'] not in selected)
    expected={(k,r['timestamp']) for k in keys for r in base['series'][k]['forecast']}
    actual=[(r['item_id'],r['timestamp']) for r in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:raise ValueError('Batch rows do not reconcile to every customer/product/month.')
    by_key={(k,r['timestamp']):r['mean'] for k in keys for r in result['series'][k]['forecast']}
    if any(not math.isclose(r['mean'],by_key[(r['item_id'],r['timestamp'])],rel_tol=1e-12,abs_tol=1e-9) for r in rows):
        raise ValueError('Batch table quantities differ from the customer/product forecasts.')
    totals={}
    for key in sorted(keys):
        for point in result['series'][key]['forecast']:
            totals[point['timestamp']]=totals.get(point['timestamp'],0.)+point['mean']
    if any(not math.isfinite(v) for v in totals.values()):raise ValueError('Batch total is not finite.')
    result['series']['__all__']=deepcopy(base['series']['__all__'])
    result['series']['__all__']['methods']={}
    result['series']['__all__']['forecast']=[dict(item_id='All series',timestamp=p,mean=v,p50=v,
        baseline_mean=v,scenario_adjustment_pct=0,p10=None,p90=None) for p,v in sorted(totals.items())]
    result.update(run_id=uuid.uuid4().hex[:12],dataset_id=dataset['id'],dataset_name=dataset['name'],
                  base_run_id=base['run_id'],scenario_name=dataset['name'],scenario=dataset['scenario_provenance'],
                  method_selection='factor_batch',best_model='Reviewed customer/product factors',forecast_rows=rows,
                  issued_at=datetime.now(timezone.utc).isoformat(),batch_evidence=evidence,
                  leaderboard=[],drivers=[],series_diagnostics={},range_model={},range_fitting_rows=[],
                  ensemble_weights={},recommended_ensemble_weights={})
    result['evidence_policy']='reviewed_what_if' if report['retrospective'] else 'reviewed_batch'
    result['series_ensemble_weights'].update(weights)
    result['run_settings']['method_selection']='factor_batch'
    result['input_manifest']={**deepcopy(base['input_manifest']),'dataset_id':dataset['id'],
                              'saved_at':dataset['created_at'],'batch_groups':report['groups']}
    result['metrics']={**deepcopy(base['metrics']),**{k:None for k in
        ('wape_pct','mae','rmse','smape_pct','bias_pct','interval_coverage_pct','interval_target_pct')},
        'independent_accuracy_verified':False,'automatic_publish_allowed':False,'horizon_metrics':[],
        'evidence_policy':result['evidence_policy'],'evidence_level':'limited','evidence_reason':report['policy']}
    for k in ('range_check','factor_evaluation'):result['metrics'].pop(k,None)
    result.pop('scoped_accuracy',None);result.pop('factor_validation',None)
    if evaluation:
        result['factor_evaluation']={**deepcopy(base.get('factor_evaluation',{})),'rows':evaluation,
                                    'scope_note':'Only the reviewed groups shown here were tested. Other series retain their baseline.'}
    else:result.pop('factor_evaluation',None)
    result['warnings']=list(dict.fromkeys([*base.get('warnings',[]),report['policy'],
        *(w for child in children for w in child.get('warnings',[]))]))
    folder=runs_dir/result['run_id'];folder.mkdir(parents=True,exist_ok=False)
    frame=pd.DataFrame(rows);frame.to_csv(folder/'forecast.csv',index=False)
    pd.DataFrame(columns=['model']).to_csv(folder/'model_leaderboard.csv',index=False)
    pd.DataFrame(columns=['feature']).to_csv(folder/'driver_importance.csv',index=False)
    alignment=[{**r,'group_dataset_id':g['dataset_id']} for g in report['groups'] for r in g['alignment']['rows']]
    scope=[{'series_id':s,'customer':base.get('metadata',{}).get(s,{}).get('customer'),
            'sku':base.get('metadata',{}).get(s,{}).get('sku'),
            'source_dataset':next((g['dataset_id'] for g in report['groups'] if s in g['series_ids']),base['dataset_id'])}
           for s in sorted(keys)]
    with pd.ExcelWriter(folder/'forecast_package.xlsx',engine='openpyxl') as writer:
        frame.to_excel(writer,sheet_name='Forecast',index=False)
        pd.DataFrame(scope).to_excel(writer,sheet_name='Customer product factors',index=False)
        pd.DataFrame(alignment).to_excel(writer,sheet_name='Factor alignment',index=False)
        pd.DataFrame([{'note':report['policy']}]).to_excel(writer,sheet_name='Limitations',index=False)
        for sheet in writer.book:
            for row in sheet:
                for cell in row:
                    if cell.data_type=='f':cell.data_type='s'
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,default=str))
    return result


async def calculate_batch(base,dataset,datasets,factors,live,profiles,calculate_child,runs_dir):
    report=check_saved_batch(base,dataset,datasets,factors,live,profiles)
    children=[]
    for i,group in enumerate(report['groups']):
        checkpoint(f'Calculating customer/product group {i+1} of {len(report["groups"])}')
        children.append(await calculate_child(group['dataset_id']))
    check_saved_batch(base,dataset,datasets,factors,live,profiles)
    checkpoint('Combining reviewed customer/product forecasts')
    return compose_batch(base,dataset,report,children,runs_dir)

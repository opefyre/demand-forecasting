import {t as uiText,pluralSuffix} from './localization.mjs';
import React,{useState,useRef,useEffect} from 'react';
import {X,PencilSimple} from '@phosphor-icons/react';
import {FactorLink} from './factor-links.jsx';

export function BatchGroupTable({groups,run,ui,onEdit,onRemove,disabled}){
  const {Table}=ui;
  return <div className="factor-batch-groups"><Table headers={[uiText("Customer / product"),uiText("Factors"),uiText("Method"),'']}>
    {groups.map(d=>{const a=d.scenario_provenance.alignment,ids=a.series_ids;
      return <tr key={d.id}><td>{ids.map(id=><div key={id}>{run.metadata?.[id]?.customer} · {run.metadata?.[id]?.sku||id}</div>)}</td>
        <td data-label="Factors">{(a.factors||[a]).map(f=>f.factor).join(' + ')}</td><td data-label="Method">{a.method==='factor_test'?uiText("Test factors"):a.method==='recommended'?uiText("Automatic"):a.method.replace(/^model:/,'')}</td>
        <td>{onEdit&&ids.length===1&&<button className="icon-button" disabled={disabled} aria-label={'Edit factors for '+ids[0]} title={uiText("Edit factors")} onClick={()=>onEdit(ids[0])}><PencilSimple size={18}/></button>}
          {onRemove&&<button className="icon-button" disabled={disabled} aria-label={'Remove group '+ids.join(', ')} title={uiText("Keep baseline instead")} onClick={()=>onRemove(d.id)}><X size={18}/></button>}</td></tr>;})}
  </Table></div>;
}

export function FactorBatch({run,api,ui,canEdit,onSaved,onManageSources,onManageProfiles,buttonLabel='Add forecast factors',autoOpen=false,onDismiss,allowedSeriesIds}){
  const {Modal,Button,Pick,Field,ErrorBox}=ui;
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),
    [profiles,setProfiles]=useState([]),[selected,setSelected]=useState(''),[active,setActive]=useState(''),
    [groups,setGroups]=useState([]),[report,setReport]=useState(null),[approved,setApproved]=useState(false);
  const request=useRef(null),key='demandlab.factorBatch.'+run.run_id+(allowedSeriesIds?'.scope.'+JSON.stringify([...allowedSeriesIds].sort()):'');
  const choices=Object.keys(run.series||{}).filter(id=>id!=='__all__'&&(!allowedSeriesIds||allowedSeriesIds.includes(id))).map(id=>[id,(run.metadata?.[id]?.customer||id)+' · '+(run.metadata?.[id]?.sku||id)]);
  const close=()=>{setOpen(false);onDismiss?.();};
  useEffect(()=>{if(autoOpen)show();},[autoOpen]);
  function change(next){setGroups(next);setReport(null);setApproved(false);request.current=null;
    try{localStorage.setItem(key,JSON.stringify(next.map(d=>d.id)));}catch{setError('The draft could not be kept in this browser. Keep this window open.');}}
  async function show(){setOpen(true);setBusy(true);setError('');setReport(null);setApproved(false);
    try{const [p,library]=await Promise.all([api('/api/runs/'+run.run_id+'/factor-profiles'),api('/api/datasets')]);setProfiles(p.profiles);
      const ids=JSON.parse(localStorage.getItem(key)||'[]');
      if(!Array.isArray(ids)||ids.length>20||ids.some(id=>typeof id!=='string'))throw Error('Saved group list needs review.');
      const saved=ids.map(id=>library.datasets.find(d=>d.id===id&&d.scenario_provenance?.type==='factor_link'&&d.scenario_provenance.base_run_id===run.run_id));
      if(saved.some(d=>!d))throw Error('Some saved groups are unavailable. Review factors again.');
      if(allowedSeriesIds&&saved.some(d=>d.scenario_provenance.alignment.series_ids.some(id=>!allowedSeriesIds.includes(id))))throw Error('Your existing draft includes other products. Open Scenarios to finish it, or ask for those products too.');
      setGroups(saved);setSelected(choices[0]?.[0]||'');
    }catch(e){setError(e.message);}finally{setBusy(false);}}
  async function act(work){setBusy(true);setError('');try{await work();}catch(e){setError(e.message);}finally{setBusy(false);}}
  const unchanged=Object.keys(run.series||{}).filter(id=>id!=='__all__'&&!groups.some(g=>g.scenario_provenance.alignment.series_ids.includes(id))).length;
  return <>
    {!autoOpen&&<Button disabled={!canEdit} onClick={show}>{buttonLabel}</Button>}
    <Modal open={open&&!active} title={uiText("Customer/product factors")} description={uiText("Review each group, then calculate one monthly forecast.")} wide className="factor-link-modal factor-batch-modal" dismissible={!busy} onClose={close}>
      <ErrorBox error={error}/>
      {busy&&!groups.length?<p role="status">{uiText("Loading saved profiles…")}</p>:<>
        {!!choices.length?<div className="factor-add-row"><Field title={uiText("Customer / product")}><Pick label={uiText("Customer/product factors")} disabled={busy||!canEdit} value={selected} options={choices} onChange={setSelected}/></Field>
          <Button disabled={!selected||busy||!canEdit||groups.length>=20&&!groups.some(g=>g.scenario_provenance.alignment.series_ids.includes(selected))} onClick={()=>setActive(selected)}>{uiText("Review factors")}</Button></div>:
          <p>{uiText("No customer/product forecast is available.")}</p>}
        {!!groups.length&&<BatchGroupTable groups={groups} run={run} ui={ui} disabled={busy||!canEdit} onEdit={id=>setActive(id)} onRemove={id=>change(groups.filter(g=>g.id!==id))}/>}
        <p className="table-note">{unchanged}{' '}{uiText("customer/product")}{pluralSuffix(unchanged)}{' '}{uiText("keep their baseline. Orders are reviewed next.")}</p>
        {!!groups.length&&<Button disabled={busy||!canEdit} onClick={()=>act(async()=>{setReport(await api('/api/runs/'+run.run_id+'/factor-batch/preview',{dataset_ids:groups.map(g=>g.id)}));setApproved(false);})}>{uiText("Review batch")}</Button>}
        {report&&<label className="check-line"><input type="checkbox" disabled={busy||!canEdit} checked={approved} onChange={e=>setApproved(e.target.checked)}/>{uiText("I reviewed these groups and the products keeping their baseline.")}</label>}
      </>}
      <div className="dialog-actions"><Button disabled={busy} onClick={close}>{uiText("Close")}</Button>{report&&<Button kind="primary" disabled={!approved||busy||!canEdit} onClick={()=>act(async()=>{
        request.current ||= crypto.randomUUID();const saved=await api('/api/runs/'+run.run_id+'/factor-batch',{
          dataset_ids:groups.map(g=>g.id),review_token:report.review_token,reviewed:true,request_id:request.current});
        await onSaved(saved,request.current);change([]);close();
      })}>{busy?uiText("Starting…"):uiText("Calculate monthly forecast")}</Button>}</div>
      {onManageProfiles&&<details className="help-details"><summary>{uiText("Save reusable factor choices")}</summary><p>{uiText("Set customer defaults or product overrides in Customers.")}</p><Button disabled={busy} onClick={()=>{close();onManageProfiles();}}>{uiText("Open Customers")}</Button></details>}
    </Modal>
    {active&&<FactorLink key={active} run={run} api={api} ui={ui} canEdit={canEdit} autoOpen initialProfileSeriesId={profiles.some(p=>p.series_id===active)?active:undefined} requiredSeriesId={active}
      onDismiss={()=>setActive('')} saveLabel="Add to monthly forecast" onManageSources={()=>{setActive('');close();onManageSources?.();}}
      onSaved={async d=>{const ids=d.scenario_provenance?.alignment?.series_ids;
        if(ids?.length!==1||ids[0]!==active)throw Error('Review the selected customer/product only.');
        change([...groups.filter(g=>!g.scenario_provenance.alignment.series_ids.includes(active)),d]);setActive('');}}/>}
  </>;
}

export function BatchEvidence({scenario,run,ui}){
  if(scenario?.type!=='factor_batch')return null;
  const groups=scenario.alignment.groups.map(g=>({id:g.dataset_id,scenario_provenance:{alignment:g.alignment}}));
  return <details className="surface disclosure"><summary>{uiText("Customer/product factors")}</summary><div className="detail-body">
    <BatchGroupTable groups={groups} run={run} ui={ui}/><p className="table-note">{scenario.alignment.unchanged_series_ids.length}{' '}{uiText("other products retain their baseline. Each group was calculated separately. No combined accuracy score or portfolio range is claimed.")}</p>
  </div></details>;
}

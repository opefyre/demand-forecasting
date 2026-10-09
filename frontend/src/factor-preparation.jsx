import {t as uiText} from './localization.mjs';
import React,{useEffect,useRef,useState} from 'react';
import {preparedSelection} from './factor-preparation.mjs';
import {ExposureFields} from './factor-profile-editor.jsx';

const blank={currency_exposure:false,global_supply:false,hormuz_route:false,materials:[]};
export function PreparationResults({report,selected,onSelect,ui,disabled}) {
  return <div className="source-suggestions" aria-label={uiText("Suggested sources")}>
    {report.recommendations.map(row=><section className="source-suggestion" key={row.factor_id}>
      <div className="source-suggestion-title">
        <label className="check-line"><input type="checkbox" aria-label={uiText('Prepare {{name}}',{name:row.name})}
          disabled={disabled||!row.can_prepare} checked={selected.includes(row.snapshot_id)}
          onChange={e=>onSelect(row.snapshot_id,e.target.checked)}/><strong>{row.name}</strong></label>
        <small>{row.what_if?uiText("What-if only"):row.snapshot_id?uiText("Archived source"):''}</small>
      </div>
      <p>{row.note}</p>
      <details className="help-details"><summary>{uiText("Why this source?")}</summary><p>{row.reason}</p>
        {row.provider&&<p>{row.provider} · {row.geography} · {row.unit}</p>}
        {row.history_missing!=null&&<p>{uiText('{{matched}} of {{total}} required historical months matched at the proposed two-month timing.',{matched:row.history_months-row.history_missing,total:row.history_months})}</p>}
        {row.captured_at&&<p>{uiText('Downloaded {{date}}. A recent download is not necessarily recent observations.',{date:new Date(row.captured_at).toLocaleDateString()})}</p>}
        {row.cooldown_until&&<p>{uiText('Refresh paused until {{date}}. Retained observations are kept.',{date:new Date(row.cooldown_until).toLocaleString()})}</p>}
        {row.policy&&<p>{row.policy}</p>}
      </details>
    </section>)}
    <p className="source-suggestion-note">{uiText("Suggestions are not proof of better accuracy. Future values remain yours to review.")}</p>
  </div>;
}

export function FactorPreparation({run,api,ui,disabled,onPrepared,onReset,onManage,lockedProfile=false,initialProfileSeriesId=''}) {
  const {Button,Field,Pick,ErrorBox}=ui;
  const [context,setContext]=useState(run.input_manifest?.settings?.factor_context||blank),[report,setReport]=useState(null),
    [materials,setMaterials]=useState([]),[selected,setSelected]=useState([]),
    [busy,setBusy]=useState(false),[error,setError]=useState(''),[open,setOpen]=useState(true);
  const [profiles,setProfiles]=useState([]),[profileId,setProfileId]=useState(initialProfileSeriesId);
  const alive=useRef(true),revision=useRef(0);
  async function check(value=context,profile=profileId){
    onReset?.();
    const current=++revision.current;setBusy(true);setError('');setReport(null);setSelected([]);
    try{const next=await api('/api/runs/'+run.run_id+'/factor-preparation',profile?{profile_series_id:profile}:value);
      if(alive.current&&revision.current===current){setReport(next);setMaterials(next.materials);}
    }catch(e){if(alive.current&&revision.current===current)setError(e.message);}
    finally{if(alive.current&&revision.current===current)setBusy(false);}
  }
  useEffect(()=>{alive.current=true;check(context);api('/api/runs/'+run.run_id+'/factor-profiles').then(r=>{if(alive.current)setProfiles(r.profiles);}).catch(e=>{if(alive.current)setError(e.message);});return()=>{alive.current=false;revision.current++;};},[run.run_id]);
  function update(patch){onReset?.();revision.current++;setBusy(false);setContext(v=>({...v,...patch}));setReport(null);setSelected([]);setError('');}
  return <details className="source-preparation" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>{uiText("Find relevant live factors")}</summary>
    <div className="source-preparation-body">
      <ErrorBox error={error}/>
      {!lockedProfile&&(profiles.length>0||profileId)&&<Field title={uiText("Use a saved profile")}><Pick label={uiText("Saved factor profile")} value={profileId} disabled={busy||disabled} options={[["",uiText("Choose factors for this forecast")],...profiles.map(p=>[p.series_id,p.customer+' · '+p.target_sku+' ('+p.target_unit+')'])]} onChange={id=>{setProfileId(id);setContext(id?profiles.find(p=>p.series_id===id).context:blank);check(id?profiles.find(p=>p.series_id===id).context:blank,id);}}/></Field>}
      {profileId?<p className="source-suggestion-note">{uiText("Only this customer/product. Other forecasts stay unchanged. Edit defaults in Customers → Factors.")}</p>:<ExposureFields value={context} ui={ui} materials={materials} disabled={disabled||busy} onChange={value=>update(value)}/>}
      <Button disabled={disabled||busy} onClick={()=>check()}>{busy?uiText("Checking source coverage…"):uiText("Check sources")}</Button>
      {report&&<>
        <PreparationResults report={report} selected={selected} disabled={disabled||busy} ui={ui} onSelect={(id,checked)=>setSelected(ids=>checked?[...ids,id]:ids.filter(i=>i!==id))}/>
        <Button disabled={disabled||busy||!selected.length||selected.length>8} onClick={()=>{try{onPrepared(preparedSelection(report,selected));setOpen(false);}catch(e){setError(e.message);}}}>{uiText("Review selected sources")}</Button>
        {onManage&&report.recommendations.some(r=>!r.can_prepare)&&<Button disabled={busy||disabled} onClick={onManage}>{uiText("Manage connections")}</Button>}
      </>}
    </div>
  </details>;
}

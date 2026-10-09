import React,{useEffect,useRef,useState} from 'react';
import {useSmoothState} from './ui-motion.jsx';
import {t as uiText} from './localization.mjs';
import {FactorSettings} from './factor-links.jsx';
import {futureAssumptions} from './factor-assumptions.mjs';
import {planningMonth} from './planning-calendar.mjs';

export function ForecastFactors({dataset,api,ui,canEdit,onSaved,onReady,navigate}){
  const {Button,ErrorBox,Table,Help,Pick}=ui;
  const [options,setOptions]=useState(null),[error,setError]=useState(null),[busy,setBusy]=useState(false);
  const [selected,setSelected]=useState([]),[expanded,setExpanded]=useSmoothState(''),[review,setReview]=useState(null),[approved,setApproved]=useState(false);
  const [add,setAdd]=useState('');
  const attempt=useRef(null);
  const endpoint='/api/datasets/'+dataset.id+'/forecast-factors';
  useEffect(()=>{let live=true;onReady(true);api(endpoint).then(r=>{if(live)setOptions(r);}).catch(e=>{if(live)setError(e);});return()=>{live=false;};},[dataset.id]);
  function change(rows){setSelected(rows);setReview(null);setApproved(false);attempt.current=null;onReady(!rows.length);}
  function update(id,patch){change(selected.map(row=>row.id===id?{...row,...patch}:row));}
  function body(){return{method:'model:Ridge + drivers',links:selected.map(row=>{
    const snapshot=options.snapshots.find(s=>s.id===row.id);
    return{snapshot_id:row.id,lag_months:Number(row.lag),...futureAssumptions(row.monthly,row.value,row.monthlyValues),
      ...(snapshot.live_what_if&&row.timingAccepted?{availability_policy:'reviewed_what_if'}:{}),
      ...(snapshot.public_vintage&&row.timingAccepted?{availability_policy:'vintage_month_end'}:{}),
      ...(snapshot.calendar==='jalali'&&row.calendarAccepted?{period_alignment:'last_completed_jalali_month'}:{})};
  })};}
  async function act(work){setBusy(true);setError(null);try{await work();}catch(e){setError(e);}finally{setBusy(false);}}
  const snapshots=(options?.snapshots||[]).filter(row=>row.live_what_if||row.public_vintage);
  const available=snapshots.filter(row=>row.can_use!==false&&!selected.some(s=>s.id===row.id));
  const ready=selected.length&&selected.every(row=>{
    const snapshot=snapshots.find(s=>s.id===row.id);
    return snapshot&&row.timingAccepted&&(snapshot.calendar!=='jalali'||row.calendarAccepted);
  });
  const basis=dataset.settings?.month_basis||'gregorian';
  return <div className="forecast-factor-selection">
    <div className="section-heading"><h3>{uiText('External factors')}</h3><Help text={uiText('Sources refresh automatically. Each calculation keeps the exact source version and your future assumptions.')}/></div>
    <ErrorBox error={error}/>
    {!options&&!error&&<p role="status">{uiText('Loading…')}</p>}
    {options&&!snapshots.length&&<p className="table-note">{uiText('No connected monthly factors are available yet.')}</p>}
    {!!available.length&&selected.length<8&&<div className="factor-add-row"><Pick label={uiText('Factor to add')} disabled={!canEdit||busy} value={add} options={[['',uiText('Choose a factor')],...available.map(snapshot=>[snapshot.id,snapshot.name+' · '+snapshot.provider])]} onChange={setAdd}/><Button disabled={!add||!canEdit||busy} onClick={()=>{change([...selected,{id:add,lag:'2',value:'',monthly:false,monthlyValues:{},timingAccepted:false}]);setExpanded(add);setAdd('');}}>{uiText('Add')}</Button></div>}
    {snapshots.some(row=>row.can_use===false)&&<details className="help-details"><summary>{uiText('Unavailable sources')}</summary>{snapshots.filter(row=>row.can_use===false).map(row=><p key={row.id}>{row.name} · {uiText(row.readiness_note)}</p>)}</details>}
    <fieldset disabled={busy||!canEdit} className="forecast-factor-settings">{selected.map(row=><FactorSettings key={row.id} factor={row} chosen={snapshots.find(s=>s.id===row.id)} periods={options.forecast_periods} ui={ui} basis={basis} disabled={busy||!canEdit} expanded={expanded===row.id} onToggle={()=>setExpanded(expanded===row.id?'':row.id)} onChange={patch=>update(row.id,patch)} onRemove={()=>change(selected.filter(r=>r.id!==row.id))}/>)}</fieldset>
    {!!selected.length&&<Button disabled={!ready||busy||!canEdit} onClick={()=>act(async()=>{setReview(await api(endpoint+'/preview',body()));setApproved(false);})}>{uiText('Review factors')}</Button>}
    {review&&<div className="forecast-factor-review">
      {review.missing>0&&<p role="alert">{uiText('Required values are missing. Choose another source or complete future assumptions. Historical values are never invented.')}</p>}
      <Table headers={[uiText('Factor'),uiText('Month'),uiText('Value'),uiText('Source')]}>{review.rows.filter(row=>row.kind==='future').map(row=><tr key={row.snapshot_id+row.sales_month}>
        <td>{row.factor}</td><td>{planningMonth(row.sales_month,basis)}</td><td>{row.value??'—'} {row.unit}</td><td>{uiText(row.treatment==='planning_assumption'?'Your assumption':row.value==null?'Missing':'Saved observation')}</td>
      </tr>)}</Table>
      {review.retrospective&&<p className="table-note">{uiText('Downloaded history supports a what-if forecast, not a claim of past accuracy. Choose a factor-aware method next.')}</p>}
      <details className="help-details"><summary>{uiText('Historical matching')}</summary><Table headers={[uiText('Factor'),uiText('Month'),uiText('Observation'),uiText('Value')]}>{review.rows.filter(row=>row.kind==='history').map(row=><tr key={row.snapshot_id+row.sales_month}><td>{row.factor}</td><td>{planningMonth(row.sales_month,basis)}</td><td>{row.observation_period}</td><td>{row.value??'—'}</td></tr>)}</Table></details>
      <label className="check-line"><input type="checkbox" disabled={busy||!canEdit||review.missing>0} checked={approved} onChange={e=>setApproved(e.target.checked)}/>{uiText('I reviewed locations, dates and future assumptions.')}</label>
      <Button kind="primary" disabled={!approved||busy||!canEdit||review.missing>0} onClick={()=>act(async()=>{
        attempt.current ||= crypto.randomUUID();const saved=await api(endpoint,{...body(),reviewed:true,review_token:review.review_token,request_id:attempt.current});await onSaved(saved);onReady(true);
      })}>{uiText(busy?'Saving…':'Use these factors')}</Button>
    </div>}
    <button className="home-text-link" onClick={()=>navigate('data')}>{uiText('Manage live sources')}</button>
  </div>;
}

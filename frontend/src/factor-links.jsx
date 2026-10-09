import {t as uiText} from './localization.mjs';
import {useSmoothState} from './ui-motion.jsx';
import React, {useState,useRef,useEffect} from 'react';
import {X} from '@phosphor-icons/react';
import {futureAssumptions} from './factor-assumptions.mjs';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {FactorPreparation} from './factor-preparation.jsx';
const factorMethods=new Set(['Ridge + drivers','Elastic Net + drivers','Histogram gradient boosting','LightGBM + drivers','Random forest','Extra trees']);

export function FactorSettings({factor,chosen,periods,ui,expanded,onToggle,onChange,onRemove,disabled,basis}) {
  const {Field,Pick}=ui;
  return <section className="factor-scenario-driver">
    <div className="section-heading">
      <button className="home-text-link" aria-expanded={expanded} onClick={onToggle}><strong>{chosen.name}</strong><small>{chosen.geography} · {chosen.unit}</small>{chosen.normalization?.factor_details?.kind==='exchange_rate'&&<small>{chosen.normalization.factor_details.market.replaceAll('_',' ')} · {chosen.normalization.factor_details.side}</small>}</button>
      <button className="icon-button" aria-label={uiText('Remove {{name}}',{name:chosen.name})} title={uiText("Remove factor")} disabled={disabled} onClick={onRemove}><X size={18}/></button>
    </div>
    {expanded&&<div className="factor-link-fields">
      {chosen.calendar==='jalali'&&<label className="check-line"><input type="checkbox" checked={!!factor.calendarAccepted} onChange={e=>onChange({calendarAccepted:e.target.checked})}/>{uiText("At each lag cutoff, use the last complete Persian month. This is not a Gregorian monthly average.")}</label>}
      {chosen.public_vintage&&<label className="check-line"><input type="checkbox" checked={factor.timingAccepted} onChange={e=>onChange({timingAccepted:e.target.checked})}/>{uiText("Use each historical version after its labelled month ended. Exact release dates are unverified.")}</label>}
      {chosen.live_what_if&&<label className="check-line"><input type="checkbox" checked={factor.timingAccepted} onChange={e=>onChange({timingAccepted:e.target.checked})}/>{uiText("Use downloaded history for a what-if comparison. Past accuracy and forecast ranges will not be shown.")}</label>}
      <div className="form-grid">
        <Field title={uiText("Use observations from")} help={uiText("Two months earlier links October demand to August's factor, only if published before October began.")}><Pick label={uiText('Observation timing for {{name}}',{name:chosen.name})} value={factor.lag} options={Array.from({length:12},(_,i)=>[String(i+1),uiText('{{count}} months earlier',{count:i+1})])} onChange={lag=>onChange({lag})}/></Field>
        {!factor.monthly&&<Field title={uiText("Future assumption")} help={uiText("Used only where the required future observation is unavailable. Published values take priority.")}><input aria-label={uiText('Future assumption for {{name}}',{name:chosen.name})} inputMode="decimal" value={factor.value} placeholder={chosen.unit} onChange={e=>onChange({value:e.target.value})}/></Field>}
      </div>
      <label className="check-line"><input type="checkbox" checked={factor.monthly} onChange={e=>onChange({monthly:e.target.checked})}/>{uiText("Set values by month")}</label>
      {factor.monthly&&<div className="form-grid">{periods.map(period=><Field key={period} title={planningMonth(period,basis)}><input aria-label={uiText('{{name}} assumption for {{month}}',{name:chosen.name,month:planningMonth(period,basis)})} inputMode="decimal" value={factor.monthlyValues[period]??''} placeholder={uiText("Not provided")} onChange={e=>onChange({monthlyValues:{...factor.monthlyValues,[period]:e.target.value}})}/></Field>)}</div>}
    </div>}
  </section>;
}

export function FactorLink({run,api,ui,canEdit,onSaved,onManageSources,initialSnapshot,initialProfileSeriesId,requiredSeriesId,autoOpen=false,onDismiss,buttonLabel='Add forecast factors',saveLabel='Calculate comparison'}) {
  const {Button,Field,Pick,Table,Modal,ErrorBox}=ui;
  const [open,setOpen]=useState(false),[options,setOptions]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [factors,setFactors]=useState([]),[add,setAdd]=useState(''),[expanded,setExpanded]=useSmoothState('');
  const [review,setReview]=useState(null),[approved,setApproved]=useState(false);
  const [scoped,setScoped]=useState(false),[seriesIds,setSeriesIds]=useState([]),[method,setMethod]=useState('');
  const [preparation,setPreparation]=useState(null);
  const attempt=useRef(null);
  const snapshots=options?.snapshots||[];
  const basis=planningBasis(run);
  function invalidate(){setReview(null);setApproved(false);attempt.current=null;}
  function update(id,patch){setFactors(v=>v.map(f=>f.id===id?{...f,...patch}:f));invalidate();}
  function body(){return {links:factors.map(f=>({snapshot_id:f.id,lag_months:Number(f.lag),...futureAssumptions(f.monthly,f.value,f.monthlyValues),
    ...(snapshots.find(s=>s.id===f.id)?.public_vintage&&f.timingAccepted?{availability_policy:'vintage_month_end'}:{}),
    ...(snapshots.find(s=>s.id===f.id)?.live_what_if&&f.timingAccepted?{availability_policy:'reviewed_what_if'}:{}),
    ...(snapshots.find(s=>s.id===f.id)?.calendar==='jalali'&&f.calendarAccepted?{period_alignment:'last_completed_jalali_month'}:{})})),
    ...(requiredSeriesId?{series_ids:[requiredSeriesId]}:scoped?{series_ids:seriesIds}:{}),...(method?{method}:{}),...(preparation?{preparation}:{})};}
  async function act(work){setBusy(true);setError('');try{await work();}catch(e){setError(e.message);}finally{setBusy(false);}}
  const available=snapshots.filter(s=>!factors.some(f=>f.id===s.id));
  const whatIf=factors.some(f=>snapshots.find(s=>s.id===f.id)?.live_what_if);
  const testedMethods=[...new Set((run.leaderboard||[]).map(m=>run.method_selection==='factor_test'?m.model.split(' [')[0]:m.model))];
  const liveMethods=testedMethods.filter(name=>factorMethods.has(name)).map(name=>['model:'+name,name]);
  const methods=whatIf?liveMethods:[['','Keep baseline method'],['factor_test','Test which factors help'],['recommended','Choose automatically'],...testedMethods.map(name=>['model:'+name,name])];
  const defaultLiveMethod=liveMethods.find(m=>m[0]==='model:Ridge + drivers')?.[0]||liveMethods[0]?.[0]||'';
  const ready=factors.length>0&&(!scoped||seriesIds.length>0)&&(!whatIf||liveMethods.some(m=>m[0]===method))&&factors.every(f=>{
    const s=snapshots.find(s=>s.id===f.id);return (!(s?.public_vintage||s?.live_what_if)||f.timingAccepted)&&(s?.calendar!=='jalali'||f.calendarAccepted);
  });
  function closeDialog(){setOpen(false);onDismiss?.();}
  function openDialog(){setPreparation(null);setFactors([]);setReview(null);setApproved(false);setAdd('');setScoped(false);setSeriesIds([]);setMethod('');setOptions(null);attempt.current=null;setOpen(true);act(async()=>{const next=await api('/api/runs/'+run.run_id+'/factor-links');setOptions(next);if(initialSnapshot){if(!next.snapshots.some(s=>s.id===initialSnapshot))throw new Error('This factor does not match this forecast’s real/demo data type. Choose a matching baseline.');if(next.snapshots.find(s=>s.id===initialSnapshot)?.live_what_if)setMethod(defaultLiveMethod);setFactors([{id:initialSnapshot,lag:'2',value:'',monthly:false,monthlyValues:{},timingAccepted:false}]);setExpanded(initialSnapshot);}});}
  useEffect(()=>{if(autoOpen)openDialog();},[autoOpen]);
  return <>
    {!autoOpen&&<Button disabled={!canEdit} onClick={openDialog}>{uiText(buttonLabel)}</Button>}
    <Modal open={open} onClose={closeDialog} dismissible={!busy} title={uiText("Forecast factors")} wide className="factor-link-modal" description={uiText("Choose relevant factors and compare with your baseline.")}>
      <ErrorBox error={error}/>
      {open&&options&&!initialSnapshot&&<FactorPreparation run={run} api={api} ui={ui} disabled={busy||!canEdit} initialProfileSeriesId={initialProfileSeriesId} lockedProfile={!!requiredSeriesId} onReset={()=>{setFactors([]);setPreparation(null);setScoped(false);setSeriesIds([]);setMethod('');setExpanded('');invalidate();}} onManage={onManageSources?()=>{closeDialog();onManageSources();}:null} onPrepared={selected=>{
        if(selected.factors.some(f=>!snapshots.some(s=>s.id===f.id)))throw Error('The source versions changed. Close this dialog and reopen it.');
        setFactors(selected.factors);setMethod(selected.method);setPreparation(selected.preparation);setScoped(!!selected.seriesIds);setSeriesIds(selected.seriesIds||[]);setExpanded(selected.factors[0].id);invalidate();
      }}/>}
      {options&&(!snapshots.length?<p>{uiText("Connect a source in Data → Factors first.")}</p>:<fieldset className="factor-link-fields" disabled={busy||!canEdit}>
        {available.length>0&&factors.length<8&&<details className="help-details"><summary>{uiText("Choose a source myself")}</summary><div className="factor-add-row"><Pick label={uiText("Factor to add")} value={add} options={[["",uiText("Choose a saved factor")],...available.map(s=>[s.id,s.name])]} onChange={setAdd}/><Button disabled={!add} onClick={()=>{setPreparation(null);if(snapshots.find(s=>s.id===add)?.live_what_if&&!liveMethods.some(m=>m[0]===method))setMethod(defaultLiveMethod);setFactors(v=>[...v,{id:add,lag:'2',value:'',monthly:false,monthlyValues:{},timingAccepted:false}]);setExpanded(add);setAdd('');invalidate();}}>{uiText("Add")}</Button></div></details>}
        {factors.map(f=><FactorSettings key={f.id} factor={f} chosen={snapshots.find(s=>s.id===f.id)} periods={options.forecast_periods} basis={basis} ui={ui} expanded={expanded===f.id} disabled={busy} onToggle={()=>setExpanded(expanded===f.id?'':f.id)} onChange={patch=>update(f.id,patch)} onRemove={()=>{setPreparation(null);setFactors(v=>v.filter(r=>r.id!==f.id));invalidate();}}/>)}
        {!!factors.length&&<>
          <Field title={uiText("Calculation method")} help={whatIf?uiText("Choose a factor-aware method. Downloaded history cannot support an automatic best-model or accuracy claim."):uiText("Test which factors help compares history-only, individual factors and all factors. It requires two earlier test windows and a separate final check; future values stay your reviewed assumptions.")}><Pick label={uiText("Factor scenario method")} value={method} options={methods.map(([value,label])=>[value,uiText(label)])} onChange={v=>{setMethod(v);invalidate();}}/></Field>
        {requiredSeriesId?<p className="muted">{uiText("Applies only to")}{' '}{options.series.find(r=>r.id===requiredSeriesId)?.customer} · {options.series.find(r=>r.id===requiredSeriesId)?.sku}{uiText(". Other products stay unchanged.")}</p>:preparation?.profile_series_id?<p className="muted">{uiText("Applies only to the saved profile’s customer and product. Choose a different profile above to change scope.")}</p>:<details className="help-details"><summary>{uiText("Choose customers / products")}</summary>
          <label className="check-line"><input type="checkbox" checked={scoped} onChange={e=>{setScoped(e.target.checked);invalidate();}}/>{uiText("Apply only to selected customers / products")}</label>
          {scoped&&<div className="factor-scope-list" role="group" aria-label={uiText("Customers and products")}>{(options.series||[]).map(row=><label className="check-line" key={row.id}><input type="checkbox" checked={seriesIds.includes(row.id)} onChange={e=>{setSeriesIds(ids=>e.target.checked?[...ids,row.id]:ids.filter(id=>id!==row.id));invalidate();}}/>{row.customer?row.customer+' · ':''}{row.sku||row.id}</label>)}</div>}
        </details>}</>}
        <Button disabled={!ready} onClick={()=>act(async()=>{setReview(await api('/api/runs/'+run.run_id+'/factor-links/preview',body()));setApproved(false);})}>{uiText("Review inputs")}</Button>
        {review&&<>
          <p>{uiText('{{factors}} factors · {{series}} customer/product pairs · {{missing}} missing values',{factors:review.factor_count,series:review.series_count,missing:review.missing})}</p>
          {!!review.missing&&<p role="alert">{uiText("This factor does not cover every required month. Choose a factor with longer history, or provide the missing future assumptions. Past values are never invented.")}</p>}
          <Table headers={[uiText("Factor"),uiText("Month"),uiText("Value"),uiText("Source")]}>
            {review.rows.filter(r=>r.kind==='future').map(r=><tr key={r.snapshot_id+'-'+r.sales_month}><td>{r.factor}</td><td>{planningMonth(r.sales_month,basis)}</td><td>{r.value??'—'} {r.unit}</td><td>{r.treatment==='planning_assumption'?uiText("Your assumption"):r.treatment==='missing_or_unpublished'?uiText("Missing"):r.treatment==='saved_observation'?uiText("Saved observation"):r.treatment==='archived_vintage'?'Version '+r.vintage_month:'Published '+r.publication_date}</td></tr>)}
          </Table>
          <details className="help-details"><summary>{uiText("Historical matching and accuracy test")}</summary><p>{review.policy}</p>
            <p>{review.retrospective?uiText("This compares forecast quantities, not past accuracy. The factor was downloaded after the historical months."):uiText("Methods use the same past periods. Adding factors can increase error.")}{' '}{uiText("With selected customers/products, other forecasts retain their baseline.")}</p>
            <Table headers={[uiText("Factor"),uiText("Sales month"),uiText("Observation"),uiText("Available"),uiText("Value")]}>{review.rows.filter(r=>r.kind==='history').map(r=><tr key={r.snapshot_id+'-'+r.sales_month}><td>{r.factor}</td><td>{r.sales_month.slice(0,7)}</td><td>{r.observation_period}</td><td>{r.availability_date||r.publication_date||'Unavailable'}</td><td>{r.value??'—'}</td></tr>)}</Table>
          </details>
          <label className="check-line"><input type="checkbox" checked={approved} onChange={e=>setApproved(e.target.checked)}/>{uiText("I reviewed locations, dates and future assumptions.")}</label>
        </>}
      </fieldset>)}
      <div className="dialog-actions"><Button disabled={busy} onClick={closeDialog}>{uiText("Cancel")}</Button>{review&&<Button kind="primary" disabled={busy||!canEdit||!approved||review.missing>0} onClick={()=>act(async()=>{
        attempt.current ||= crypto.randomUUID();const saved=await api('/api/runs/'+run.run_id+'/factor-links',{...body(),reviewed:true,review_token:review.review_token,request_id:attempt.current});await onSaved(saved,attempt.current);closeDialog();
      })}>{busy?uiText("Saving…"):uiText(saveLabel)}</Button>}</div>
    </Modal>
  </>;
}

export function FactorLinkEvidence({scenario,ui}) {
  if(scenario?.type!=='factor_link')return null;
  const {Table}=ui,a=scenario.alignment;
  const factors=a.factors||[a];
  return <details className="surface disclosure"><summary>{factors.length===1?uiText("Linked factor"):uiText("Combined factors")} · {factors.map(f=>f.factor).join(' + ')}</summary><div className="detail-body">
    {factors.map(f=><p key={f.snapshot_id}>{f.factor} · {f.geography} · {f.unit} · {f.lag_months}{uiText("-month lag")}{f.normalization?.factor_details?.kind==='exchange_rate'&&<> · {f.normalization.factor_details.market.replaceAll('_',' ')} · {f.normalization.factor_details.side}</>}{f.attribution&&<> · {f.attribution} <a href={f.license_url} target="_blank" rel="noreferrer">{uiText("Terms of use")}</a></>}</p>)}
    <p>{a.scope}</p><p>{a.policy}</p>
    <Table headers={[uiText("Factor"),uiText("Sales month"),uiText("Observation"),uiText("Available"),uiText("Value"),uiText("Use")]}>{factors.flatMap(f=>f.rows.map(r=><tr key={f.snapshot_id+'-'+r.kind+'-'+r.sales_month}><td>{f.factor}</td><td>{r.sales_month}</td><td>{r.observation_period}</td><td>{r.availability_date||r.publication_date||'—'}</td><td>{r.value} {f.unit}</td><td>{r.kind==='history'?uiText("Historical input"):r.treatment==='planning_assumption'?uiText("Future assumption"):uiText("Known future input")}</td></tr>))}</Table>
  </div></details>;
}

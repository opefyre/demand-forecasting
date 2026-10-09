import {t as uiText} from './localization.mjs';
import {companyMode} from './company-api.mjs';
import React,{useEffect,useState,useRef} from 'react';
import {ArrowRight,CalendarDots,ArrowClockwise} from '@phosphor-icons/react';
import {Panel,Stack,Grid,Actions,Disclosure} from './ui-layout.jsx';

export function RecurringRows({schedules,ui,onOpen,onCheck,onData,busy,canAdmin}){
  const {Button}=ui;
  return schedules.map(s=><div className="ui-list-row" key={s.id}>
    <div className="ui-list-body"><strong>{s.name}</strong><small>{s.cycle?.period?s.cycle.period+' · ':''}{!s.enabled?uiText("Paused"):s.cycle?.state==='calculating'?uiText("Calculating draft"):s.cycle?.state==='review'?uiText("Ready for review"):s.cycle?.state==='attention'?uiText("Needs attention"):uiText("Monthly · day {{day}} · {{calendar}} months",{day:s.day,calendar:uiText(s.basis==='jalali'?"Persian":"Gregorian")})}</small>
      {s.enabled&&s.cycle?.attention&&<p role="status">{uiText(s.cycle.attention)}</p>}
      {s.cycle?.changes?.change_count>0&&<Disclosure title={uiText("Sales changes")}><p>{s.cycle.changes.changed_groups}{' '}{uiText("monthly quantities changed;")}{' '}{s.cycle.changes.added_groups}{' '}{uiText("added;")}{' '}{s.cycle.changes.removed_groups}{' '}{uiText("removed.")}</p></Disclosure>}
    </div>
    <Actions>{s.cycle?.update_id&&<Button disabled={busy} onClick={()=>onOpen(s.cycle.update_id)}>{uiText("Review update")}{' '}<ArrowRight size={16}/></Button>}
      {!s.cycle?.update_id&&s.enabled&&s.cycle?.state==='attention'&&onData&&<Button disabled={busy} onClick={onData}>{uiText("Review inputs")}{' '}<ArrowRight size={16}/></Button>}
      {canAdmin&&s.enabled&&<button className="icon-button" disabled={busy} aria-label={'Check monthly draft for '+s.name} title={uiText("Check now")} onClick={()=>onCheck(s.id)}><ArrowClockwise size={18}/></button>}
    </Actions>
  </div>);
}

export function RecurringForecasts({api,ui,runs,run,datasets,canAdmin,resumeUpdate,refresh,navigate,onCycles,settings=false,timezone='Asia/Tehran'}){
  const {Button,Modal,Pick,Field,ErrorBox}=ui;
  const [schedules,setSchedules]=useState([]),[open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),
    [selected,setSelected]=useState(''),[day,setDay]=useState('5'),[months,setMonths]=useState('6'),[method,setMethod]=useState('recommended'),[enabled,setEnabled]=useState(false),[confirmed,setConfirmed]=useState(false),[connection,setConnection]=useState(''),[connections,setConnections]=useState([]);
  const request=useRef(null);
  const choices=runs.filter(r=>{const d=datasets.find(d=>d.id===r.dataset_id);return !r.scenario_name&&!r.base_run_id&&d?.settings.frequency==='monthly'&&!d.sources.operations&&!d.sources.future&&!d.scenario_provenance;}).map(r=>[r.run_id,r.name||'Sales forecast']);
  const load=()=>api('/api/recurring-forecasts').then(r=>setSchedules(r.schedules));
  useEffect(()=>{load().catch(e=>setError(e.message));},[]);
  useEffect(()=>{onCycles?.(schedules.map(s=>s.cycle?.update_id).filter(Boolean));},[schedules]);
  useEffect(()=>{if(!schedules.some(s=>s.enabled&&s.cycle?.state==='calculating'))return;
    const timer=setInterval(()=>load().catch(()=>{}),10000);return()=>clearInterval(timer);
  },[schedules]);
  const methods=[['recommended','Automatic'],['seasonal','Seasonal patterns'],['trend','Trend'],['intermittent','Irregular demand']].map(([id,title])=>[id,uiText(title)]);
  if(!methods.some(m=>m[0]===method))methods.push([method,method.replace(/^model:/,'')]);
  function choose(id){setSelected(id);const s=schedules.find(v=>v.run_id===id);setDay(String(s?.day||5));setMonths(String(s?.months||6));setMethod(s?.method||'recommended');setEnabled(s?.enabled||false);setConnection(s?.connection_id||'');setConfirmed(false);request.current=null;}
  async function setup(){setOpen(true);setError('');choose(run&&choices.some(c=>c[0]===run.run_id)?run.run_id:choices[0]?.[0]||'');
    if(!companyMode())try{setConnections((await api('/api/integrations/folders')).connections);}catch(e){setError(e.message);}}
  async function act(work){setBusy(true);setError('');try{await work();await load();await refresh?.();}catch(e){setError(e.message);}finally{setBusy(false);}}
  const rows=<RecurringRows schedules={schedules} ui={ui} canAdmin={canAdmin} busy={busy} onOpen={resumeUpdate} onData={()=>navigate('data')} onCheck={id=>act(()=>api('/api/recurring-forecasts/'+id+'/check',{}))}/>;
  const setupAction=canAdmin&&choices.length>0&&<Button onClick={setup}><CalendarDots size={18}/>{uiText("Monthly draft settings")}</Button>;
  return <>
    {settings?<Panel title={uiText('Schedules')} actions={setupAction}><ErrorBox error={!open?error:''}/>{schedules.length>0?rows:<p>{uiText('Prepare a baseline from reviewed sales. Review factors and orders before export.')}</p>}</Panel>:<>
    <ErrorBox error={!open?error:''}/>
    {schedules.length>0&&<section className="home-recent"><div className="home-section-heading"><h2>{uiText("Monthly drafts")}</h2></div>
      {rows}
    </section>}
    {canAdmin&&choices.length>0&&<button className="home-text-link" onClick={setup}><CalendarDots size={18}/>{uiText("Monthly draft settings")}</button>}
    </>}
    <Modal open={open} title={uiText("Monthly drafts")} description={uiText("Prepare a baseline from reviewed sales. Review factors and orders before export.")} dismissible={!busy} onClose={()=>setOpen(false)}>
      <Stack><ErrorBox error={error}/>
        <Field title={uiText("Sales forecast")}><Pick label={uiText("Monthly draft baseline")} value={selected} options={choices} disabled={busy} onChange={choose}/></Field>
        <Grid><Field title={uiText("Day of month")}><input aria-label={uiText("Day of month")} type="number" min="1" max="28" value={day} onChange={e=>{setDay(e.target.value);setConfirmed(false);}}/></Field>
          <Field title={uiText("Months ahead")}><input aria-label={uiText("Months ahead")} type="number" min="1" max="24" value={months} onChange={e=>{setMonths(e.target.value);setConfirmed(false);}}/></Field></Grid>
        {!companyMode()&&<Field title={uiText("Sales connection")} help={uiText("Uses reviewed versions only. New files still need review in Data.")}><Pick label={uiText("Monthly sales connection")} value={connection} options={[["",uiText("Reviewed saved versions")],...connections.filter(c=>c.dataset_id===runs.find(r=>r.run_id===selected)?.dataset_id).filter(c=>Object.keys(c.files).length===1&&c.files.history).map(c=>[c.id,c.name])]} disabled={busy} onChange={v=>{setConnection(v);setConfirmed(false);}}/></Field>}
        <Field title={uiText("Method")}><Pick label={uiText("Monthly forecasting method")} value={method} options={methods} disabled={busy} onChange={v=>{setMethod(v);setConfirmed(false);}}/></Field>
        <p className="ui-panel-description">{companyMode()?uiText("Uses the forecast calendar and site time zone: {{timezone}}.",{timezone}):uiText("Uses the forecast’s Persian or Gregorian months, on Tehran time. Runs only while this app server is running.")}</p>
        <label className="ui-check"><input type="checkbox" checked={enabled} disabled={busy} onChange={e=>{setEnabled(e.target.checked);setConfirmed(false);}}/>{uiText("Prepare a draft each month")}</label>
        <label className="ui-check"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e=>setConfirmed(e.target.checked)}/>{uiText("I allow draft calculations from reviewed sales. Factors, orders and exports still need review.")}</label>
      <Actions><Button disabled={busy} onClick={()=>setOpen(false)}>{uiText("Cancel")}</Button><Button kind="primary" disabled={busy||!selected||!confirmed||!Number.isInteger(Number(day))||Number(day)<1||Number(day)>28||!Number.isInteger(Number(months))||Number(months)<1||Number(months)>24} onClick={()=>act(async()=>{
        const body={run_id:selected,day:Number(day),months:Number(months),method,enabled,confirmed:true,connection_id:connection||null},signature=JSON.stringify(body);
        if(request.current?.signature!==signature)request.current={signature,id:crypto.randomUUID()};await api('/api/recurring-forecasts',{...body,request_id:request.current.id});request.current=null;setOpen(false);
      })}>{busy?uiText("Saving…"):uiText("Save settings")}</Button></Actions>
      <button className="home-text-link" disabled={busy} onClick={()=>{setOpen(false);navigate('data');}}>{uiText("Manage sales connections")}{' '}<ArrowRight size={16}/></button>
      </Stack>
    </Modal>
  </>;
}

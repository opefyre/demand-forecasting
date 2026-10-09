import React,{useEffect,useRef,useState} from 'react';
import {useSmoothState} from './ui-motion.jsx';
import {ArrowLeft,ArrowRight,CheckCircle,UploadSimple} from '@phosphor-icons/react';
import {t as uiText,unitLabel,i18n} from './localization.mjs';
import {FORECAST_CHOICES,forecastInputs,remainingMethods,readForecastDraft,FORECAST_DRAFT_KEY} from './forecast-start.mjs';
import {ForecastFactors} from './forecast-factors.jsx';
import {ForecastOrders} from './forecast-orders.jsx';
import {Panel,Stack,Grid,Actions} from './ui-layout.jsx';

export function NewForecast({datasets=[],api,ui,renderImport,runDataset,refresh,openRun,navigate,setDataView,canEdit,embedded=false,onWorkingChange}){
  const {Button,Pick,Field,ErrorBox,Help}=ui;
  const sources=forecastInputs(datasets);
  const [draft]=useState(()=>readForecastDraft(typeof sessionStorage==='undefined'?null:sessionStorage,sources.map(source=>source.id)));
  const [importInitial,setImportInitial]=useState(null);
  const [source,setSource]=useState(draft?.source||''),[saved,setSaved]=useState(null),[step,setStep]=useSmoothState(draft?.step||0),[importing,setImporting]=useSmoothState(false);
  const [methods,setMethods]=useState(draft?.methods||['recommended']),[jobs,setJobs]=useState(draft?.jobs||[]),[busy,setBusy]=useState(false),[error,setError]=useState(null);
  useEffect(()=>{onWorkingChange?.(busy);return()=>onWorkingChange?.(false);},[busy,onWorkingChange]);
  const submitting=useRef(false);
  const [summaries,setSummaries]=useState({});
  const [factorsReady,setFactorsReady]=useState(true);
  const [salesInputId,setSalesInputId]=useState(draft?.salesInputId||null);
  const [customer,setCustomer]=useState(draft?.customer||'');
  const [groupId,setGroupId]=useState(draft?.groupId||crypto.randomUUID().replaceAll('-',''));
  const [name,setName]=useState(draft?.name||uiText('Forecast')+' · '+new Date().toISOString().slice(0,10));
  const [settings,setSettings]=useState(null);
  const dataset=saved?.id===source?saved:sources.find(d=>d.id===source);
  const settingsDirty=!!settings&&!!dataset&&['horizon','month_basis','calendar_country'].some(k=>settings[k]!==({month_basis:'gregorian',calendar_country:'IR',...dataset.settings})[k]);
  useEffect(()=>{setSettings(dataset?{horizon:dataset.settings.horizon,month_basis:dataset.settings.month_basis||'gregorian',calendar_country:dataset.settings.calendar_country??'IR'}:null);},[dataset?.id]);
  const whatIf=dataset?.settings?.evidence_policy==='reviewed_what_if';
  const hasFactors=!!dataset?.settings?.drivers?.length;
  const choices=whatIf||hasFactors?FORECAST_CHOICES.filter(([id])=>['model:Ridge + drivers','model:Elastic Net + drivers','model:Histogram gradient boosting'].includes(id)):FORECAST_CHOICES;
  useEffect(()=>{if(whatIf||hasFactors)setMethods(previous=>{
    const allowed=previous.filter(id=>choices.some(([key])=>key===id));
    return allowed.length===previous.length?previous:allowed.length?allowed:['model:Ridge + drivers'];
  });},[whatIf,hasFactors]);
  async function next(continueStep=true){
    if(step!==1){setStep(step+1);return;}
    setBusy(true);setError(null);
    try{const d=await api('/api/datasets/'+dataset.id+'/forecast-settings',{...settings,request_id:crypto.randomUUID()});
      setSaved(d);setSource(d.id);if(d.id!==dataset.id)setSalesInputId(null);await refresh();if(continueStep)setStep(2);
    }catch(e){setError(e);}finally{setBusy(false);}
  }
  useEffect(()=>{try{sessionStorage.setItem(FORECAST_DRAFT_KEY,JSON.stringify({version:2,source,step,methods,salesInputId,customer,groupId,name,jobs:jobs.map(({id,method})=>({id,method}))}));}catch{}},[source,step,methods,jobs,salesInputId,customer,groupId,name]);
  useEffect(()=>{
    let live=true;
    const ready=jobs.filter(job=>job.state==='succeeded'&&job.run_id);
    if(!ready.length)return;
    Promise.all(ready.map(async job=>{const run=await api('/api/runs/'+job.run_id);
      if(customer&&run.sales_input_snapshot_id){const outlook=await api('/api/sales/inputs/'+run.sales_input_snapshot_id+'/outlook');const rows=outlook.rows.filter(r=>r.customer===customer);return [job.run_id,{total:rows.length&&rows.every(r=>r.total!=null)?rows.reduce((sum,r)=>sum+r.total,0):null,unit:run.unit}];}
      return [job.run_id,run.demand_summary||{total:null,unit:run.unit}];}))
      .then(entries=>{if(live)setSummaries(Object.fromEntries(entries));}).catch(e=>{if(live)setError(e);});
    return()=>{live=false;};
  },[jobs.map(j=>j.id+':'+j.state).join('|'),api]);
  useEffect(()=>{
    if(!jobs.some(j=>!['succeeded','failed','interrupted','cancelled'].includes(j.state)))return;
    let live=true,timer;
    const poll=async()=>{
      try{const updates=await Promise.all(jobs.map(async j=>({...await api('/api/jobs/'+j.id),method:j.method})));
        if(live){setJobs(updates);setError(null);}}
      catch(e){if(live)setError(e);}
      if(live)timer=setTimeout(poll,2000);
    };timer=setTimeout(poll,1000);
    return()=>{live=false;clearTimeout(timer);};
  },[jobs.map(j=>j.id+':'+j.state).join('|'),api]);
  async function start(){
    if(submitting.current||!canEdit||!dataset||!methods.length||!salesInputId)return;
    submitting.current=true;setBusy(true);setError(null);setStep(4);
    try{for(const method of remainingMethods(methods,jobs)){
      const job=await runDataset(dataset.id,{method,sales_input_id:salesInputId,forecast_group_id:groupId,forecast_name:name.trim()});
      if(!job)throw Error(uiText('The forecast could not start. Your data is still saved.'));
      setJobs(previous=>[...previous,{...job,method}]);
    }}catch(e){setError(e);}finally{submitting.current=false;setBusy(false);}
  }
  async function retry(job){
    if(busy||!canEdit)return;setBusy(true);setError(null);
    try{const replacement=await api('/api/jobs/'+job.id+'/retry',{request_id:crypto.randomUUID()});
      setJobs(previous=>previous.map(row=>row.id===job.id?{...replacement,method:job.method}:row));
    }catch(e){setError(e);}finally{setBusy(false);}
  }
  function beginAgain(){setGroupId(crypto.randomUUID().replaceAll('-',''));setJobs([]);setCustomer('');setSalesInputId(null);setSource('');setSaved(null);setStep(0);setMethods(['recommended']);setError(null);}
  async function viewForecast(job){
    if(busy)return;setBusy(true);setError(null);
    try{await refresh();await openRun(job.run_id,'demand',customer?{customer}:null);}
    catch(e){setError(e);}finally{setBusy(false);}
  }
  if(importing)return renderImport({initial:importInitial||undefined,chooseMethodsLater:true,returnLabel:'Back to new forecast',onCancel:()=>setImporting(false),onSaved:async d=>{
    setSaved(d);setSource(d.id);setSalesInputId(null);setStep(1);setImporting(false);await refresh();
  }});
  return <Stack step={step}>
    {!embedded&&<div className="page-heading"><h1>{uiText(step===4?'Results':'New forecast')}</h1><div className="row-actions">{step===4&&<Button disabled={busy} onClick={beginAgain}>{uiText('Start another forecast')}</Button>}<Button onClick={()=>navigate('demand')}>{uiText('Close')}</Button></div></div>}
    <ol className="forecast-steps" aria-label={uiText('Forecast progress')}>
      {['Sales data','Factors','Customers & orders','Methods','Results'].map((title,index)=><li key={title} aria-current={step===index?'step':undefined} className={index<step?'complete':step===index?'current':''}><span>{index<step?<CheckCircle size={18}/>:index+1}</span>{uiText(title)}</li>)}
    </ol>
    <ErrorBox error={error}/>
    <Panel title={uiText(['Choose your sales history','Check your forecast inputs','Customers & orders','Choose one or more methods','Total demand'][step])}>
      {step===0&&<>
        <Field title={uiText('Forecast name')}><input value={name} maxLength={160} onChange={e=>setName(e.target.value)}/></Field>
        {!!sources.length&&<Field title={uiText('Sales data')}><Pick label={uiText('Sales data')} value={source} onChange={id=>{setSource(id);setSaved(null);setSalesInputId(null);}} options={[['',uiText('Choose sales data')],...sources.map(d=>[d.id,d.name])]}/></Field>}
        <Button disabled={!canEdit} onClick={()=>{setSource('');setSaved(null);setSalesInputId(null);setImportInitial(null);setImporting(true);}}><UploadSimple size={18}/>{uiText('Import sales history')}</Button>
      </>}
      {step===1&&dataset&&<>
        
        {settings&&<Grid><Field title={uiText('Forecast horizon')}><input type="number" min="1" max="24" disabled={busy||!canEdit} value={settings.horizon} onChange={e=>setSettings(s=>({...s,horizon:Number(e.target.value)}))}/></Field><Field title={uiText('Planning months')}><Pick disabled={busy||!canEdit||hasFactors} label={uiText('Planning months')} value={settings.month_basis} options={[["gregorian",uiText('Gregorian months')],["jalali",uiText('Persian months')]]} onChange={v=>setSettings(s=>({...s,month_basis:v}))}/></Field><Field title={uiText('Holiday calendar')}><Pick disabled={busy||!canEdit} label={uiText('Holiday calendar')} value={settings.calendar_country} options={[["IR",uiText('Iran')],["",uiText('No public holidays')]]} onChange={v=>setSettings(s=>({...s,calendar_country:v}))}/></Field></Grid>}
        {settingsDirty&&<Button disabled={busy||!canEdit||!Number.isInteger(settings.horizon)||settings.horizon<1||settings.horizon>24} onClick={()=>next(false)}>{uiText('Apply changes')}</Button>}
        {(dataset.settings?.frequency||'monthly')!=='monthly'?<p className="table-note">{uiText('Live factor matching needs monthly sales. You can still forecast this history without extra live factors.')}</p>:dataset.import_provenance?.type==='forecast_factors'?<Button disabled={!canEdit} onClick={()=>{setSource(dataset.parent_dataset_id);setSaved(null);setSalesInputId(null);setFactorsReady(true);setMethods(['recommended']);}}>{uiText('Change factors')}</Button>:<ForecastFactors key={dataset.id} dataset={dataset} api={api} ui={ui} canEdit={canEdit&&!settingsDirty&&!busy} onReady={setFactorsReady} navigate={()=>{setDataView?.('external');navigate('data');}} onSaved={async d=>{setSaved(d);setSource(d.id);setSalesInputId(null);setFactorsReady(true);setMethods(['model:Ridge + drivers']);await refresh();}}/>}
      </>}
      {step===2&&dataset&&<ForecastOrders key={dataset.id} api={api} ui={ui} dataset={dataset} snapshotId={salesInputId} canEdit={canEdit} onWorkingChange={onWorkingChange} onReady={id=>{setSalesInputId(id);if(id)setStep(3);}}/>}
      {step===3&&<>
        
        <Grid>{choices.map(([id,title,description])=><div className="ui-choice" key={id}>
          <label className="ui-check"><input type="checkbox" disabled={!canEdit} checked={methods.includes(id)} onChange={e=>setMethods(previous=>e.target.checked?[...previous,id]:previous.filter(m=>m!==id))}/><strong>{uiText(title)}</strong></label>
          <Help text={uiText(description)}/>
        </div>)}</Grid>
      </>}
      {step===4&&<>
        {!!jobs.length&&<Help text={uiText('Confirmed orders and calculated demand are combined for each customer, product and month. Orders are not counted twice.')}/>}
        {!jobs.length&&busy&&<p role="status">{uiText('Starting…')}</p>}
        <Stack>{jobs.map(job=><div key={job.id} className="ui-list-row">
          <div className="ui-list-body"><strong>{uiText(FORECAST_CHOICES.find(([id])=>id===job.method)?.[1]||job.method)}</strong><small role="status">{summaries[job.run_id]?(summaries[job.run_id].total==null?uiText('Check customer history and orders'):`${new Intl.NumberFormat(i18n.language,{maximumFractionDigits:1}).format(summaries[job.run_id].total)} ${unitLabel(summaries[job.run_id].unit)}`):uiText(({loading:'Loading…',queued:'Queued',running:'Calculating…',publishing:'Saving…',succeeded:'Ready',failed:'Failed',interrupted:'Interrupted',cancelled:'Cancelled'})[job.state]||'Working')}</small>
            {job.error&&<details><summary>{uiText('What needs attention?')}</summary><p>{job.error}</p></details>}
          </div>
          {job.state==='succeeded'&&<Button disabled={busy} kind="primary" onClick={()=>viewForecast(job)}>{uiText('View forecast')}<ArrowRight size={16}/></Button>}
          {['failed','interrupted','cancelled'].includes(job.state)&&<Button disabled={busy||!canEdit} onClick={()=>retry(job)}>{uiText('Retry')}</Button>}
        </div>)}</Stack>
        {error&&remainingMethods(methods,jobs).length>0&&<Button disabled={busy} onClick={start}>{uiText('Continue remaining methods')}</Button>}
      </>}
    </Panel>
    {embedded&&step===4&&<Actions><Button disabled={busy} onClick={beginAgain}>{uiText('Start another forecast')}</Button></Actions>}
    {step<4&&<Actions>
      <Button disabled={step===0} onClick={()=>setStep(step-1)}><ArrowLeft size={18}/>{uiText('Back')}</Button>
      {(step!==2||salesInputId)&&<Button kind="primary" disabled={busy||!canEdit||!dataset||!name.trim()||step===1&&(!factorsReady||!settings||!Number.isInteger(settings.horizon)||settings.horizon<1||settings.horizon>24)||step===3&&(!methods.length||!salesInputId)} onClick={()=>step===3?start():next()}>{uiText(step===3?'Run selected methods':'Continue')}<ArrowRight size={18}/></Button>}
    </Actions>}
  </Stack>;
}

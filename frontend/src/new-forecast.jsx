import {sessionState} from './workspace-storage.mjs';
import React,{useEffect,useRef,useState} from 'react';
import {useSmoothState} from './ui-motion.jsx';
import {ArrowLeft,ArrowRight,UploadSimple} from '@phosphor-icons/react';
import {t as uiText,unitLabel,i18n} from './localization.mjs';
import {FORECAST_CHOICES,forecastInputs,remainingMethods,readForecastDraft,FORECAST_DRAFT_KEY} from './forecast-start.mjs';
import {ForecastFactors,IncludedForecastFactors} from './forecast-factors.jsx';
import {ForecastOrders} from './forecast-orders.jsx';
import {Panel,Stack,Grid,Actions,Steps} from './ui-layout.jsx';
import {companyMode} from './company-api.mjs';
import {cloudTransportEnabled} from './cloud-transport.mjs';
import {ForecastMethods,inputMethodChoices} from './forecast-methods.jsx';
import {BatchGroupTable} from './factor-batch.jsx';
import {DefinitionList,Disclosure} from './ui-layout.jsx';
import {planningMonth} from './planning-calendar.mjs';

export function PreparedFactorSummary({dataset,baseline,ui,methodsOnly=false}){
  const {Table}=ui,proof=dataset.scenario_provenance;
  const metadata=baseline?.metadata||Object.fromEntries((proof.alignment.groups||[]).flatMap(group=>group.series||[]).map(row=>[row.id,row]));
  const groups=proof.type==='factor_batch'?proof.alignment.groups.map(group=>({id:group.dataset_id,scenario_provenance:{alignment:group.alignment}})):[{...dataset,scenario_provenance:{...proof,alignment:{...proof.alignment,series_ids:proof.alignment.series_ids||Object.keys(metadata)}}}];
  const unchanged=proof.alignment.unchanged_series_ids?.length;
  return <Stack>
    <BatchGroupTable groups={groups} run={{metadata}} ui={ui}/>
    {!methodsOnly&&<>
      <DefinitionList rows={[[uiText('Forecast horizon'),new Intl.NumberFormat(i18n.language).format(dataset.settings.horizon)],[uiText('Planning months'),uiText(dataset.settings.month_basis==='jalali'?'Persian months':'Gregorian months')],...(unchanged?[[uiText('Keep baseline instead'),new Intl.NumberFormat(i18n.language).format(unchanged)]]:[])]}/>
      <Disclosure title={uiText('Future assumptions')}>
        <Table headers={[uiText('Customer / product'),uiText('Factor'),uiText('Month'),uiText('Value'),uiText('Source')]}>
          {groups.flatMap(group=>group.scenario_provenance.alignment.rows.filter(row=>row.kind==='future').map(row=><tr key={group.id+row.snapshot_id+row.sales_month}>
            <td>{(group.scenario_provenance.alignment.series_ids||Object.keys(metadata)).map(id=>[metadata[id]?.customer,metadata[id]?.sku||id].filter(Boolean).join(' · ')).join(', ')}</td>
            <td>{row.factor}</td><td>{planningMonth(row.sales_month,dataset.settings.month_basis||'gregorian')}</td><td>{row.value??'—'} {row.unit}</td>
            <td>{uiText(row.treatment==='planning_assumption'?'Your assumption':row.treatment==='saved_observation'?'Saved observation':'Known future input')}</td>
          </tr>))}
        </Table>
      </Disclosure>
    </>}
  </Stack>;
}

export function NewForecast({datasets=[],api,ui,renderImport,runDataset,refresh,openRun,navigate,setDataView,canEdit,embedded=false,onWorkingChange,parentForecastId=null,initialDraft=null,draftKey=FORECAST_DRAFT_KEY,submitGroup=null,allowAnother=true,lockCalendar=false,prepareImport=null,preparedScenario=null,scenarioBaseline=null}){
  const {Button,Pick,Field,ErrorBox,Help}=ui;
  const sources=preparedScenario?[preparedScenario]:forecastInputs(datasets);
  const scenario=preparedScenario?.scenario_provenance;
  const [draft]=useState(()=>initialDraft?.jobs?.length?initialDraft:readForecastDraft(typeof sessionState==='undefined'?null:sessionState,sources.map(source=>source.id),draftKey,scenario?['reviewed_factors']:undefined)||initialDraft);
  const [revisionParent,setRevisionParent]=useState(parentForecastId||draft?.parentForecastId||null);
  const [importInitial,setImportInitial]=useState(null);
  const [source,setSource]=useState(draft?.source||preparedScenario?.id||''),[saved,setSaved]=useState(null),[step,setStep]=useSmoothState(draft?.step||0),[importing,setImporting]=useSmoothState(false);
  const [methods,setMethods]=useState(draft?.methods||(scenario?['reviewed_factors']:['recommended'])),[jobs,setJobs]=useState(draft?.jobs||[]),[busy,setBusy]=useState(false),[error,setError]=useState(null);
  const [ordersBusy,setOrdersBusy]=useState(false);
  const [factorsBusy,setFactorsBusy]=useState(false);
  const [ordersEditing,setOrdersEditing]=useState(false);
  const working=busy||ordersBusy||factorsBusy;
  useEffect(()=>{onWorkingChange?.(working);return()=>onWorkingChange?.(false);},[working,onWorkingChange]);
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
  useEffect(()=>{setSettings(dataset?{horizon:dataset.id===initialDraft?.source&&!initialDraft?.jobs?.length?initialDraft.horizon||dataset.settings.horizon:dataset.settings.horizon,month_basis:dataset.settings.month_basis||'gregorian',calendar_country:dataset.settings.calendar_country??'IR'}:null);},[dataset?.id]);
  const whatIf=dataset?.settings?.evidence_policy==='reviewed_what_if';
  const hasFactors=!!dataset?.settings?.drivers?.length;
  const choices=inputMethodChoices(dataset);
  useEffect(()=>{if(!scenario&&(whatIf||hasFactors))setMethods(previous=>{
    const allowed=previous.filter(id=>choices.some(([key])=>key===id));
    return allowed.length===previous.length?previous:allowed.length?allowed:['model:Ridge + drivers'];
  });},[whatIf,hasFactors]);
  async function next(continueStep=true){
    if(working)return;
    if(step!==1){setStep(step+1);return;}
    if(scenario){if(continueStep)setStep(2);return;}
    if(!settingsDirty){if(continueStep)setStep(2);return;}
    setBusy(true);setError(null);
    try{const d=await api('/api/datasets/'+dataset.id+'/forecast-settings',{...settings,request_id:crypto.randomUUID()});
      setSaved(d);setSource(d.id);if(d.id!==dataset.id)setSalesInputId(null);await refresh();if(continueStep)setStep(2);
    }catch(e){setError(e);}finally{setBusy(false);}
  }
  useEffect(()=>{try{sessionState.setItem(draftKey,JSON.stringify({version:2,source,step,methods,salesInputId,customer,groupId,name,parentForecastId:revisionParent,jobs:jobs.map(({id,method})=>({id,method}))}));}catch{}},[source,step,methods,jobs,salesInputId,customer,groupId,name,revisionParent,draftKey]);
  useEffect(()=>{if(scenario&&jobs.length&&jobs.every(job=>job.state==='succeeded')){
    try{const pending=JSON.parse(sessionState.getItem(FORECAST_DRAFT_KEY+'.prepared')||'null');if(pending?.datasetId===source)sessionState.removeItem(FORECAST_DRAFT_KEY+'.prepared');}catch{}
  }},[scenario,source,jobs.map(job=>job.id+':'+job.state).join('|')]);
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
    try{if(submitGroup||companyMode()){
      const body={name:name.trim(),dataset_id:dataset.id,
        sales_input_id:salesInputId,methods,request_id:groupId,parent_forecast_id:revisionParent};
      const group=submitGroup?await submitGroup(body):await api('/api/v1/forecasts',body);
      setJobs(group.jobs.map(job=>({...job,method:scenario?'reviewed_factors':job.payload.method})));
    }else for(const method of remainingMethods(methods,jobs)){
      const job=await runDataset(dataset.id,{method:scenario?null:method,...(scenario?{base_run_id:scenario.base_run_id}:{}),sales_input_id:salesInputId,forecast_group_id:groupId,forecast_name:name.trim()});
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
  function beginAgain(){setRevisionParent(null);setGroupId(crypto.randomUUID().replaceAll('-',''));setJobs([]);setCustomer('');setSalesInputId(null);setSource('');setSaved(null);setStep(0);setMethods(['recommended']);setError(null);}
  async function viewForecast(job){
    if(busy)return;setBusy(true);setError(null);
    try{await refresh();await openRun(job.run_id,'demand',customer?{customer}:null);}
    catch(e){setError(e);}finally{setBusy(false);}
  }
  async function importHistory(){
    if(working||!canEdit)return;setBusy(true);setError(null);
    try{const initial=prepareImport?await prepareImport(dataset):null;
      if(!prepareImport){setSource('');setSaved(null);}
      setSalesInputId(null);setImportInitial(initial);setImporting(true);
    }catch(e){setError(e);}finally{setBusy(false);}
  }
  if(importing)return renderImport({initial:importInitial||undefined,draftStorageKey:prepareImport?draftKey+'.history':undefined,chooseMethodsLater:true,returnLabel:prepareImport?'Back to forecast update':'Back to new forecast',onCancel:()=>setImporting(false),onSaved:async d=>{
    setSaved(d);setSource(d.id);setSalesInputId(null);setStep(1);setImporting(false);await refresh();
  }});
  return <Stack step={step}>
    {!embedded&&<div className="page-heading"><h1>{uiText(step===4?'Results':'New forecast')}</h1><div className="row-actions">{step===4&&<Button disabled={busy} onClick={beginAgain}>{uiText('Start another forecast')}</Button>}<Button onClick={()=>navigate('demand')}>{uiText('Close')}</Button></div></div>}
    <Steps items={['Sales data','Factors','Customers & orders','Methods','Results']} current={step} label={uiText('Forecast progress')}/>
    <ErrorBox error={error}/>
    <Panel title={uiText(step===3&&scenario?'Reviewed methods':['Choose your sales history','Check your forecast inputs','Customers & orders','Choose one or more methods','Total demand'][step])}
      actions={step===4&&!!jobs.length&&<Help text={uiText('Confirmed orders and calculated demand are combined for each customer, product and month. Orders are not counted twice.')}/>}>
      {step===0&&<>
        <Field title={uiText('Forecast name')}><input value={name} maxLength={160} onChange={e=>setName(e.target.value)}/></Field>
        {scenario?<DefinitionList rows={[[uiText('Sales data'),dataset?.name]]}/>:<>
          {!!sources.length&&<Field title={uiText('Sales data')}><Pick label={uiText('Sales data')} value={source} onChange={id=>{setSource(id);setSaved(null);setSalesInputId(null);}} options={[['',uiText('Choose sales data')],...sources.map(d=>[d.id,d.name])]}/></Field>}
          <Button disabled={working||!canEdit} onClick={importHistory}><UploadSimple size={18}/>{uiText(prepareImport?'Upload updated history':'Import sales history')}</Button>
        </>}
      </>}
      {step===1&&dataset&&(scenario?<PreparedFactorSummary dataset={dataset} baseline={scenarioBaseline} ui={ui}/>:<>
        
        {settings&&<Grid><Field title={uiText('Forecast horizon')}><input type="number" min="1" max="24" disabled={working||!canEdit} value={settings.horizon} onChange={e=>setSettings(s=>({...s,horizon:Number(e.target.value)}))}/></Field><Field title={uiText('Planning months')}><Pick disabled={working||!canEdit||hasFactors||lockCalendar} label={uiText('Planning months')} value={settings.month_basis} options={[["gregorian",uiText('Gregorian months')],["jalali",uiText('Persian months')]]} onChange={v=>setSettings(s=>({...s,month_basis:v}))}/></Field><Field title={uiText('Holiday calendar')}><Pick disabled={working||!canEdit} label={uiText('Holiday calendar')} value={settings.calendar_country} options={[["IR",uiText('Iran')],["",uiText('No public holidays')]]} onChange={v=>setSettings(s=>({...s,calendar_country:v}))}/></Field></Grid>}
        {settingsDirty&&<Button disabled={working||!canEdit||!Number.isInteger(settings.horizon)||settings.horizon<1||settings.horizon>24} onClick={()=>next(false)}>{uiText('Apply changes')}</Button>}
        {(dataset.settings?.frequency||'monthly')!=='monthly'?<p className="table-note">{uiText('Live factor matching needs monthly sales. You can still forecast this history without extra live factors.')}</p>:dataset.import_provenance?.type==='forecast_factors'?<><IncludedForecastFactors dataset={dataset} ui={ui}/><Button disabled={working||!canEdit} onClick={()=>{setSource(dataset.parent_dataset_id);setSaved(null);setSalesInputId(null);setFactorsReady(true);setMethods(['recommended']);}}>{uiText('Change factors')}</Button></>:<ForecastFactors key={dataset.id} dataset={dataset} api={api} ui={ui} canEdit={canEdit&&!settingsDirty&&!busy} onReady={setFactorsReady} onWorkingChange={setFactorsBusy} navigate={()=>{setDataView?.('external');navigate('data');}} onSaved={async d=>{setBusy(true);try{setSaved(d);setSource(d.id);setSalesInputId(null);setFactorsReady(true);setMethods(['model:Ridge + drivers']);await refresh();}finally{setBusy(false);}}}/>}
      </>)}
      {step===2&&dataset&&<ForecastOrders key={dataset.id} api={api} ui={ui} dataset={dataset} snapshotId={salesInputId} canEdit={canEdit} onWorkingChange={setOrdersBusy} onPendingEditChange={setOrdersEditing} onReady={id=>{setSalesInputId(id);if(id)setStep(3);}}/>}
      {step===3&&<>
        {scenario&&<Field title={uiText('Forecast name')}><input disabled={working||!canEdit} value={name} maxLength={160} onChange={e=>setName(e.target.value)}/></Field>}
        
        {scenario?<PreparedFactorSummary dataset={dataset} baseline={scenarioBaseline} ui={ui} methodsOnly/>:<ForecastMethods choices={choices} methods={methods} onChange={setMethods} disabled={!canEdit||working} ui={ui}/>}
      </>}
      {step===4&&<>
        {!jobs.length&&busy&&<p role="status">{uiText(cloudTransportEnabled()?'Calculating…':'Starting…')}</p>}
        <Stack>{jobs.map(job=><div key={job.id} className="ui-list-row">
          <div className="ui-list-body"><strong>{uiText(scenario?'Customer/product factors':FORECAST_CHOICES.find(([id])=>id===job.method)?.[1]||job.method)}</strong><small role="status">{summaries[job.run_id]?(summaries[job.run_id].total==null?uiText('Check customer history and orders'):`${new Intl.NumberFormat(i18n.language,{maximumFractionDigits:1}).format(summaries[job.run_id].total)} ${unitLabel(summaries[job.run_id].unit)}`):uiText(({loading:'Loading…',queued:'Queued',running:'Calculating…',publishing:'Saving…',succeeded:'Ready',failed:'Failed',interrupted:'Interrupted',cancelled:'Cancelled'})[job.state]||'Working')}</small>
            {job.error&&<details><summary>{uiText('What needs attention?')}</summary><p>{job.error}</p></details>}
          </div>
          {job.state==='succeeded'&&<Button disabled={busy} kind="primary" onClick={()=>viewForecast(job)}>{uiText('View forecast')}<ArrowRight size={16}/></Button>}
          {['failed','interrupted','cancelled'].includes(job.state)&&<Button disabled={busy||!canEdit} onClick={()=>retry(job)}>{uiText('Retry')}</Button>}
        </div>)}</Stack>
        {error&&remainingMethods(methods,jobs).length>0&&<Button disabled={busy} onClick={start}>{uiText('Continue remaining methods')}</Button>}
      </>}
    </Panel>
    {embedded&&step===4&&allowAnother&&!scenario&&<Actions><Button disabled={busy} onClick={beginAgain}>{uiText('Start another forecast')}</Button></Actions>}
    {step<4&&<Actions>
      <Button disabled={working||step===0} onClick={()=>setStep(step-1)}><ArrowLeft size={18}/>{uiText('Back')}</Button>
      {(step!==2||salesInputId)&&<Button kind="primary" disabled={working||ordersEditing||!canEdit||!dataset||!name.trim()||step===1&&(!factorsReady||!settings||!Number.isInteger(settings.horizon)||settings.horizon<1||settings.horizon>24)||step===3&&(!methods.length||!salesInputId)} onClick={()=>step===3?start():next()}>{uiText(step===3?(scenario?'Run forecast':'Run selected methods'):'Continue')}<ArrowRight size={18}/></Button>}
    </Actions>}
  </Stack>;
}

import {chartTheme} from './chart-theme.mjs';
import {Page,PageControls} from './ui-layout.jsx';
import {useSmoothState} from './ui-motion.jsx';
import {t as uiText,i18n} from './localization.mjs';
import {unitLabel} from './localization.mjs';
import React, { useEffect, useMemo, useState, useRef } from 'react';
import { BarChart, Bar, LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, Legend } from 'recharts';
import { sortDemand, demandCSV, mergeDirectory, coverageStatus, demandViewLabel, COVERAGE_OPTIONS, pivotDemand, pivotCSV, coverageCSV } from './demand-view.mjs';
import { UploadSimple, ArrowLeft, DownloadSimple, UsersThree, Plus } from '@phosphor-icons/react';
import {PivotTable,CoverageTable,CustomerCalculation} from './demand-tables';
import {SavedDemandViews} from './saved-demand-views';
import {orderRevision, orderReviewMessage} from './order-revision.mjs';
import {changeReviewedInput, salesMappingReady, requireSalesHeadings,orderReviewReady} from './sales-import-state.mjs';
import {OrderReuse} from './order-reuse';
import {OrderFolder} from './order-folder';
import {DemandHandoff} from './demand-handoff';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {CustomerMatches} from './customer-matches.jsx';
import {FactorEvaluation} from './factor-evaluation.jsx';
import {demandLoadState} from './demand-load-state.mjs';
import {ModelEstimate} from './model-estimate.jsx';
import {forecastGroups} from './forecast-groups.mjs';
import {MethodComparison,methodName} from './method-comparison.jsx';

const number = n => n == null ? uiText('Unknown') : new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 2 }).format(n);
const title = value => value.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
const remembered = run => localStorage.getItem(`demandlab.orders.${run}`) || '';
export { remembered };

export function SalesDemand({ api, ui, run, runs = [], openRun, importNew, navigate, canEdit, canAdmin, showHeading = true, decisionTarget,startUpdate,startNewForecast }) {
  const { Button, Pick, Field, Table, ErrorBox, Modal, Help } = ui;
  const basis=planningBasis(run);
  const groups=forecastGroups(runs),group=groups.find(g=>g.runs.some(r=>r.run_id===run?.run_id));
  const [comparing,setComparing]=useState(false);
  const previousGroup=useRef(null);
  const [snapshots, setSnapshots] = useState([]), [selected, setSelected] = useState('');
  const [outlook, setOutlook] = useState(null), [editing, setEditing] = useState(null), [error, setError] = useState('');
  const [customer, setCustomer] = useState(''), [sku, setSku] = useState(''), [period, setPeriod] = useState(''), [unit, setUnit] = useState('');
  const [view, setView] = useSmoothState('month');
  const [page, setPage] = useState(0), [loading, setLoading] = useState(false);
  const [listing,setListing] = useState(!!run);
  const [loadRevision,setLoadRevision]=useState(0);
  const [display,setDisplay] = useState('chart'), [exporting,setExporting] = useState(false);
  const [sort,setSort] = useState('name'),[coverage,setCoverage]=useState(''),[measure,setMeasure]=useState('total');
  const pendingView=useRef(null);
  const currentRun=useRef(run?.run_id);currentRun.current=run?.run_id;
  function restoreSettings(s){setCustomer(s.customer);setSku(s.sku);setPeriod(s.period);setUnit(s.unit);setCoverage(s.coverage);setDisplay(s.display);setView(s.view);setSort(s.sort);setMeasure(s.measure);}
  function applyView(saved){
    if(!snapshots.some(s=>s.id===saved.snapshot_id))throw new Error('That order version is unavailable. No filters were changed.');
    if(saved.snapshot_id===selected)restoreSettings(saved.settings);
    else{pendingView.current=saved;setSelected(saved.snapshot_id);}
  }
  const viewSettings={customer,sku,period,unit,coverage,display,view,sort,measure};
  async function refresh(id) {
    const data = await api(`/api/sales/runs/${id}/inputs`);
    if(currentRun.current!==id)return;
    setSnapshots(data.snapshots);
    setSelected(data.snapshots.some(s => s.id === remembered(id)) ? remembered(id) : data.snapshots[0]?.id || '');
  }
  useEffect(() => {
    let live = true;
    setListing(!!run);
    setOutlook(null); setSnapshots([]); setSelected(''); setEditing(null); setError('');
    if(previousGroup.current!==group?.id){setCustomer(decisionTarget?.customer||'');setSku('');setPeriod('');setUnit('');setCoverage('');}
    previousGroup.current=group?.id;pendingView.current=null;
    if (run) api(`/api/sales/runs/${run.run_id}/inputs`).then(data => {
      if (!live) return;
      setSnapshots(data.snapshots);
      setSelected(data.snapshots.some(s => s.id === remembered(run.run_id)) ? remembered(run.run_id) : data.snapshots[0]?.id || '');
    }).catch(e => live && setError(e)).finally(()=>live&&setListing(false));
    return () => { live = false; };
  }, [run?.run_id,decisionTarget?.customer]);
  useEffect(() => {
    let live = true; setOutlook(null); setError(''); setLoading(!!selected);
    if (selected) api(`/api/sales/inputs/${selected}/outlook`).then(data => {
      if (!live) return;
      setOutlook(data); setUnit(data.rows[0]?.unit || '');
      if(pendingView.current?.snapshot_id===selected){restoreSettings(pendingView.current.settings);pendingView.current=null;}
      localStorage.setItem(`demandlab.orders.${run.run_id}`, selected);
    }).catch(e => live && setError(e)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [selected,loadRevision]);
  async function reloadSaved(){
    if(listing||loading)return;
    const id=run.run_id;
    setListing(true);setError('');
    try{await refresh(id);if(currentRun.current===id)setLoadRevision(v=>v+1);}
    catch(e){if(currentRun.current===id)setError(e);}finally{if(currentRun.current===id)setListing(false);}
  }
  useEffect(() => setPage(0), [customer, sku, period, unit, view, selected,sort,coverage,display,measure]);
  async function start(sample) {
    setError('');
    try {
      setEditing(selected && !sample
        ? orderRevision(await api(`/api/sales/inputs/${selected}`))
        : {inputs: await api(`/api/sales/runs/${run.run_id}/${sample ? 'sample' : 'starter'}`)});
    }
    catch(e) { setError(e); }
  }
  const rows = sortDemand((outlook?.rows || []).filter(r => (!customer || r.customer === customer) && (!sku || r.sku === sku) && (!period || r.period === period) && r.unit === unit && (!coverage||coverageStatus(r)===coverage)),sort);
  const loadState=demandLoadState({loading,listing,selected,outlook,error});
  const demandLoading=loadState==='loading';
  const total = key => rows.some(r => r[key] == null) ? null : rows.reduce((sum, r) => sum + r[key], 0);
  const chart = useMemo(() => {
    const groups = Object.create(null);
    for (const r of rows) {
      const key = view === 'customer' ? r.customer : view === 'sku' ? r.sku : r.period;
      const g = groups[key] ||= { label: view==='month'?planningMonth(key,basis):key, booked: 0, remaining: 0, fulfilled: 0, total: 0, baseline: 0, unknown: false };
      g.booked += r.booked; g.fulfilled += r.fulfilled;
      for (const field of ['remaining', 'total', 'baseline']) g[field] = g[field] == null || r[field] == null ? null : g[field] + r[field];
      g.unknown ||= r.remaining == null;
    }
    return sortDemand(Object.values(groups),sort);
  }, [rows, view,sort,basis]);
  function downloadView() {
    const csv=display==='pivot'?pivotCSV(pivotDemand(rows,measure),measure):display==='coverage'?coverageCSV(rows):demandCSV(view==='detail'?rows:chart,view!=='detail',unit);
    const url=URL.createObjectURL(new Blob(['\ufeff',csv],{type:'text/csv;charset=utf-8;'}));
    const link=document.createElement('a');link.href=url;link.download='demand-view-'+(customer||'all-customers')+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const newForecast=canEdit&&startNewForecast&&<Button kind="primary" data-action="new-forecast" onClick={()=>startNewForecast()}><Plus/>{uiText('New forecast')}</Button>;
  if (!run) return <Page title={uiText('Sales forecast')} actions={newForecast}><section className="surface demand-empty"><UsersThree size={40}/><p>{uiText("No forecasts yet")}</p></section></Page>;
  if (editing) return <DemandImport api={api} ui={ui} run={run} initial={editing} onCancel={() => setEditing(null)} onSaved={async value => {
    localStorage.setItem(`demandlab.orders.${run.run_id}`, value.id);
    setEditing(null); await refresh(run.run_id);
  }}/>;
  return <Page title={showHeading&&uiText('Sales forecast')} actions={<>{outlook&&!comparing&&<><SavedDemandViews api={api} ui={ui} runId={run.run_id} snapshotId={selected} settings={viewSettings} onApply={applyView} canEdit={canEdit}/><Button onClick={() => setExporting(true)}><DownloadSimple/>{uiText('Export demand')}</Button></>}{newForecast}</>} controls={
    <div className="compact-toolbar demand-context">
      {canEdit&&startUpdate&&!run.base_run_id&&!run.scenario_name&&<button className="home-text-link" title={uiText("Review updated sales, factors and orders; keep this forecast unchanged")} onClick={()=>startUpdate(run.run_id)}>{uiText("Update forecast")}</button>}
      {!startNewForecast&&!outlook&&!demandLoading&&!error&&canEdit&&<OrderReuse runId={run.run_id} api={api} ui={ui} onSaved={async saved=>{
        localStorage.setItem(`demandlab.orders.${run.run_id}`,saved.id);await refresh(run.run_id);
      }}/>}
      {showHeading && <Pick label={uiText("Forecast")} value={group?.id||run.run_id} options={groups.map(g => [g.id,g.name])} onChange={id=>{setComparing(false);openRun(groups.find(g=>g.id===id).runs[0].run_id,'demand');}}/>}
      {group?.runs.length>1&&<>{!comparing&&<Pick label={uiText('Method')} value={run.run_id} options={group.runs.map(r=>[r.run_id,methodName(r.method_selection)])} onChange={id=>openRun(id,'demand')}/>}<Button onClick={()=>setComparing(v=>!v)}>{uiText(comparing?'Back to results':'Compare methods')}</Button></>}
      {!comparing&&snapshots.length>1 && <Pick label={uiText("Order version")} value={selected} options={snapshots.map(s => [s.id, `${s.name} · ${s.as_of}`])} onChange={setSelected}/>}
      {outlook&&!comparing && <div className="demand-context-actions">{canEdit && <Button onClick={() => start(false)}>{outlook.fresh ? uiText("Update orders") : uiText("Review orders")}</Button>}{navigate && <button className="home-text-link" onClick={()=>navigate('forecast')}>{uiText("How was this calculated?")}</button>}{!showHeading&&<Button onClick={()=>setExporting(true)}>{uiText("Export demand")}</Button>}</div>}
    </div>}>
    <ErrorBox error={error} onReload={reloadSaved} busy={listing||loading}/>
    {demandLoading ? <p role="status">{uiText("Loading demand…")}</p> : !outlook&&error ? null : !outlook ? <ModelEstimate key={run.run_id+':'+(decisionTarget?.customer||'')} run={run} ui={ui} canEdit={canEdit} onOrders={()=>startNewForecast?startNewForecast(run.dataset_id,run.method_selection||'recommended',decisionTarget?.customer||''):start(false)} unified={!!startNewForecast} navigate={navigate} initialCustomer={decisionTarget?.customer||''}/> : <>
      <PageControls><div className="compact-toolbar demand-filters">
        {[['Customer', customer, setCustomer, 'customer'], ['SKU', sku, setSku, 'sku'], ['Month', period, setPeriod, 'period']].map(([label,value,set,field]) => <Pick key={field} label={uiText(label)} value={value} onChange={set} options={[["", uiText(`All ${label === 'SKU' ? 'SKUs' : label.toLowerCase()+'s'}`)], ...[...new Set(outlook.rows.map(r => r[field]))].sort().map(v => [v,field==='period'?planningMonth(v,basis):v])]}/>)}
        {new Set(outlook.rows.map(r=>r.unit)).size>1&&<Pick label={uiText("Unit")} value={unit} onChange={setUnit} options={[...new Set(outlook.rows.map(r => r.unit))].map(v => [v,v])}/>}
        {(display==='coverage'||coverage)&&<Pick label={uiText("Order coverage")} value={coverage} onChange={setCoverage} options={[["",uiText("All coverage")],...COVERAGE_OPTIONS.map(v=>[v,uiText(v)])]}/>}
        {(customer||sku||period||coverage)&&<button className="home-text-link" onClick={()=>{setCustomer('');setSku('');setPeriod('');setCoverage('');}}>{uiText("Clear filters")}</button>}
      </div></PageControls>
      {outlook.warnings.map((w,i) => <div key={i} role="status" className="source-notice">{w === 'Order source is unknown or expired. Final totals and demand exports are blocked.' ? orderReviewMessage(outlook,uiText,canEdit) : uiText(w)}</div>)}
      {comparing&&group?<MethodComparison group={group} activeRun={run} api={api} ui={ui} selectedOrders={selected} filters={{customer,sku,period,unit,coverage}} onReviewCoverage={()=>{setDisplay('coverage');setComparing(false);}}/>:<>
      <FactorEvaluation run={run} ui={ui} customer={customer} sku={sku}/>
      <div className="demand-summary">
        {[['Confirmed, still open','booked'],['Expected, not yet ordered','remaining'],['Total demand, including fulfilled','total']].map(([label,key]) => <article key={key}><span>{uiText(label)}</span><strong>{rows.length ? number(total(key)) : '—'} <small>{unitLabel(unit)}</small></strong></article>)}
      </div>
      <section className="surface">
        <div className="section-heading"><div className="demand-chart-title"><h2>{display==='coverage'?uiText("Customer coverage"):display==='pivot'?uiText("Demand by month"):uiText("Demand breakdown")}</h2><Help text={uiText("Orders replace expected demand only for the same customer, product and month. Total demand also includes quantities already fulfilled.")}/></div><div className="demand-segments" role="group" aria-label={uiText("Display results")}>{['chart','trend','table','pivot','coverage'].map(v=><button key={v} aria-pressed={display===v} onClick={()=>{setDisplay(v);if(v==='trend'){setView('month');setSort('name');}else if(v==='chart'&&view==='detail')setView('month');}}>{uiText(demandViewLabel(v))}</button>)}</div></div>
        <div className="compact-toolbar view-toolbar">{display==='pivot'&&<Pick label={uiText("Pivot quantity")} value={measure} onChange={setMeasure} options={[['total',uiText("Total demand")],['baseline',uiText("Calculated estimate")],['booked',uiText("Open orders")],['remaining',uiText("Still expected")],['still_to_serve',uiText("Still to serve")]]}/>} {['chart','table'].includes(display)&&<Pick label={uiText("Group results")} value={view} onChange={setView} options={[...(display==='table'?[['detail',uiText("Detailed")]]:[]),['month',uiText("By month")],['customer',uiText("By customer")],['sku',uiText("By SKU")]]}/>} {display!=='trend'&&<Pick label={uiText("Sort results")} value={sort} onChange={setSort} options={[['name',uiText("Name / month")],['largest',uiText("Highest demand")],['smallest',uiText("Lowest demand")]]}/>}<button className="home-text-link" disabled={!rows.length} title={uiText("CSV of the filtered table, including fulfilled demand. For review, not a planning-system import.")} onClick={downloadView}><DownloadSimple size={16}/>{uiText("Download view")}</button></div>
        {display==='trend'&&rows.length>0&&<div className="demand-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={sortDemand(chart,'name')} margin={chartTheme.margin}><XAxis dataKey="label" tick={chartTheme.ticks} minTickGap={30} interval="preserveStartEnd"/><YAxis tick={chartTheme.ticks}/><Tooltip formatter={(value,name)=>[number(value)+' '+unit,name]}/><Legend/><Line isAnimationActive={false} name={uiText("Calculated estimate")} dataKey="baseline" stroke="var(--chart-history)" strokeDasharray="4 4" dot={chart.length===1}/><Line isAnimationActive={false} name={uiText("Total demand")} dataKey="total" stroke="var(--chart-forecast)" strokeWidth={2} dot={chartTheme.dot} connectNulls={false}/></LineChart></ResponsiveContainer></div>}
        {rows.length ? <>{display==='pivot'?<PivotTable rows={rows} measure={measure} sort={sort} ui={ui}/>:display==='coverage'?<CoverageTable rows={rows} ui={ui}/>:display==='trend'?null:display==='chart'?<><div className="demand-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart.slice(0,50)} margin={chartTheme.margin}><XAxis dataKey="label" tick={chartTheme.ticks} minTickGap={30} interval="preserveStartEnd"/><YAxis tick={chartTheme.ticks}/><Tooltip formatter={(value,name) => [number(value)+' '+unit,name]}/><Legend/><Bar isAnimationActive={false} name={uiText("Confirmed orders")} dataKey="booked" stackId="demand" fill="var(--chart-forecast)"/><Bar isAnimationActive={false} name={uiText("Expected demand")} dataKey="remaining" stackId="demand" fill="var(--chart-expected)"/><Bar isAnimationActive={false} name={uiText("Already fulfilled")} dataKey="fulfilled" stackId="demand" fill="var(--chart-range)"/></BarChart></ResponsiveContainer></div>{chart.length > 50 && <p>{uiText("Chart shows the first 50 groups. Filter to see more.")}</p>}{rows.some(r => r.remaining == null) && <p className="source-notice">{uiText("Unknown demand is not drawn. Bars with missing estimates show known orders only.")}</p>}</>:<>
        <Table headers={view === 'detail' ? [uiText("Customer / SKU"),uiText("Month"),uiText("Baseline"),uiText("Open orders"),uiText("Already fulfilled"),uiText("Still expected"),uiText("Total demand"),uiText("Details")] : [view === 'customer' ? uiText("Customer") : view==='month'?uiText("Month"):uiText("SKU"),uiText("Baseline"),uiText("Open orders"),uiText("Already fulfilled"),uiText("Still expected"),uiText("Total demand")]}>
          {view === 'detail' ? rows.slice(page*50,(page+1)*50).map(r => <tr key={`${r.customer}/${r.sku}/${r.period}/${r.unit}`}><td><strong>{r.customer}</strong><br/>{r.sku}</td><td>{r.period_label||planningMonth(r.period,basis)}</td>{['baseline','booked','fulfilled','remaining','total'].map(key => <td key={key}>{number(r[key])}</td>)}<td><details><summary>{uiText(r.status)}</summary><p>{r.issue || uiText('Matched within this customer, SKU and month.')}</p><p>{r.order_references.length ? 'Orders: '+r.order_references.join(', ') : uiText("No confirmed orders in the reviewed snapshot.")}</p>{r.commitment && <p>{uiText("Full-month commitment:")}{' '}{r.commitment.quantity}. {r.commitment.reason}</p>}</details></td></tr>) : chart.slice(page*50,(page+1)*50).map(r => <tr key={r.label}><td>{r.label}</td>{['baseline','booked','fulfilled','remaining','total'].map(key => <td key={key}>{number(r[key])}</td>)}</tr>)}
        </Table><div className="demand-actions"><Button disabled={!page} onClick={() => setPage(p => p-1)}>{uiText("Previous")}</Button><span>{uiText('pageProgress',{page:page+1,total:Math.max(1,Math.ceil((view === 'detail' ? rows.length : chart.length)/50))})}</span><Button disabled={(page+1)*50 >= (view === 'detail' ? rows.length : chart.length)} onClick={() => setPage(p => p+1)}>{uiText("Next")}</Button></div></>}</> : <p>{uiText("No results match these filters.")}</p>}
      </section>
      {display==='trend'&&rows.some(r=>r.remaining==null)&&<p className="source-notice">{uiText("Unknown estimates remain gaps, not zero demand.")}</p>}
      </>}
      <DemandHandoff open={exporting} onClose={()=>setExporting(false)} snapshotId={selected} runId={run.run_id} outlook={outlook} canEdit={canEdit} api={api} ui={ui}/>
      <details className="surface"><summary>{uiText("Source dates & order schedule")}</summary>{canAdmin&&<div className="row-actions"><OrderFolder key={run.run_id} api={api} ui={ui} runId={run.run_id} onReview={setEditing}/></div>}<p>{uiText('Source dates: {{asOf}} · Review again after {{until}} · Draft, not an approved plan.',{asOf:outlook.as_of,until:outlook.valid_until})}</p><Table headers={[uiText("Reference"),uiText("Customer"),uiText("SKU"),uiText("Due"),uiText("Open quantity"),uiText("Included?")]}>{outlook.orders.slice(0,200).map(o => <tr key={o.reference}><td>{o.reference}</td><td>{o.customer}</td><td>{o.sku}</td><td>{o.due_date}</td><td>{number(o.outstanding)} {o.unit}</td><td>{o.included ? uiText("Yes") : o.reason}</td></tr>)}</Table>{outlook.orders.length>200 && <p>{uiText("Showing the first 200 order lines.")}</p>}</details>
    </>}
  </Page>;
}

export function DemandImport({ api, ui, run, initial, onCancel, onSaved }) {
  const { Button, Pick, Field, Table, ErrorBox } = ui;
  const basis=planningBasis(run);
  const [inputs, setInputs] = useState(initial.inputs), [imports, setImports] = useState(initial.imports||{}), [schema,setSchema] = useState(null);
  const [orderMode,setOrderMode] = useState(initial.order_mode||(initial.base_snapshot_id && initial.inputs.order_feed==='complete_snapshot' ? 'changes' : 'replace'));
  const [reading,setReading] = useState({});
  const fileBusy = React.useCallback((role,value)=>setReading(r=>({...r,[role]:value})),[]);
  const [error,setError] = useState(''), [busy,setBusy] = useState(false), [review,setReview] = useState(null), [step,setStep] = useSmoothState(1);
  const [attempt] = useState(() => crypto.randomUUID());
  const [schemaRevision,setSchemaRevision]=useState(0);
  useEffect(() => {let live=true; api('/api/sales/schema').then(value=>live&&setSchema(value)).catch(e => live&&setError(e));return()=>{live=false;}; },[schemaRevision]);
  const change = (field,value) => {setInputs(i => changeReviewedInput(i,field,value));setReview(null);};
  const invalidateReview = () => {setInputs(i=>({...i,reviewed:false}));setReview(null);setError('');};
  const [directoryNote,setDirectoryNote]=useState('');
  async function useDirectory(){
    setBusy(true);setError('');
    try{
      const data=await api('/api/customers');
      const linked=data.customers.filter(c=>c.active&&c.products.length);
      if(!linked.length)throw new Error('Add customers and link their products on the Customers page first.');
      change('customers',mergeDirectory(inputs.customers,linked));
      setImports(v=>{const next={...v};delete next.customers;return next;});
      setDirectoryNote(linked.length+' customers included. Existing history links are preserved; new matches will be checked in the review.');
    }catch(e){setError(e);}finally{setBusy(false);}
  }
  async function check(save) {
    if(!orderReviewReady(inputs)){setError('Add a short review note and confirm the order checks first.');return;}
    setBusy(true);setError('');
    try {
      const payload = {inputs, imports, request_id:attempt, base_snapshot_id:initial.base_snapshot_id, order_mode:orderMode,
        ...(initial.order_refresh_source?{order_refresh_source:initial.order_refresh_source}:{})};
      const result = await api(save ? '/api/sales/inputs' : '/api/sales/validate', payload);
      if(save) await onSaved(result); else {setReview(result);setStep(3);}
    } catch(e) {setError(e);} finally {setBusy(false);}
  }
  return <Page title={initial.base_snapshot_id?uiText('Update orders'):uiText('Add customers & orders')} actions={<Button disabled={busy} onClick={onCancel}><ArrowLeft/>{uiText('Back')}</Button>}>
    <ol className="demand-steps">{['Choose files','Check meanings','Review demand'].map((label,i) => <li key={label} aria-current={step===i+1 ? 'step' : undefined}>{i+1}. {uiText(label)}</li>)}</ol><ErrorBox error={error} onReload={!schema?()=>{setError('');setSchemaRevision(v=>v+1);}:undefined}/>
    {step === 1 && <><section className="surface"><h2>{uiText("Customer list & order book")}</h2>{inputs.classification!=='synthetic_sample'&&<div className="demand-actions"><Button disabled={busy||Object.values(reading).some(Boolean)} onClick={useDirectory}>{uiText("Use customer directory")}</Button>{directoryNote&&<span role="status">{directoryNote}</span>}</div>}<p>{uiText("Templates use YYYY-MM-DD dates. Keep customer, SKU and unit names identical across files.")}</p>{schema && ['customers','orders','commitments'].map(role => <OptionalSalesInput key={role} role={role} count={inputs[role].length}><SalesSource key={role} api={api} ui={ui} role={role} schema={schema[role]} config={imports[role]} setConfig={config => {setImports(v => {const next={...v};if(config)next[role]=config;else delete next[role];return next;});invalidateReview();}} onBusyChange={fileBusy} run={run} fallbackCount={inputs[role].length} orderMode={orderMode} modeControl={role==='orders' && initial.base_snapshot_id && initial.inputs.order_feed==='complete_snapshot' ? <div className="compact-toolbar"><Pick label={uiText("Order file contains")} value={orderMode} onChange={v=>{setOrderMode(v);invalidateReview();}} options={[["changes",uiText("Only changed order lines")],["replace",uiText("Full order book")]]}/></div> : null}/></OptionalSalesInput>)}</section><Button kind="primary" disabled={!schema||busy||Object.values(reading).some(Boolean)} onClick={() => setStep(2)}>{uiText("Continue")}</Button></>}
    {step === 2 && <><section className="surface"><h2>{uiText("Confirm what these inputs mean")}</h2><div className="demand-controls"><Field title={uiText("Snapshot name")}><input value={inputs.name} onChange={e => change('name',e.target.value)}/></Field><Field title={uiText("Orders correct as of")}><input type="date" value={inputs.as_of} onChange={e => change('as_of',e.target.value)}/></Field><Field title={uiText("Review again after")}><input type="date" value={inputs.valid_until} onChange={e => change('valid_until',e.target.value)}/></Field><Field title={uiText("Order source")}><Pick label={uiText("Order source")} value={inputs.order_feed} onChange={v => change('order_feed',v)} options={[['unknown',uiText("Missing or incomplete")],['complete_snapshot',uiText("Complete, current order snapshot")]]}/></Field></div><p>{uiText("A complete snapshot includes every current order and this month's fulfilled quantities. An empty order book is valid only if you have confirmed there are no orders.")}</p><p>{uiText('Order status uses confirmed, unconfirmed or cancelled. Ordered quantity includes fulfilled and cancelled amounts. Each delivery schedule needs its own reference.')}</p><Field title={uiText("Review note · required")} help={uiText("Briefly say where these orders came from and what you checked.")}><textarea aria-label={uiText("Review note")} rows={3} value={inputs.note} placeholder={uiText("Where did these orders come from? What did you check?")} onChange={e => change('note',e.target.value)}/></Field><label className="check-row"><input type="checkbox" checked={inputs.reviewed} onChange={e => change('reviewed',e.target.checked)}/>{uiText("I checked the full customer list, matching, units and order meanings.")}</label></section><div className="demand-actions"><Button onClick={() => setStep(1)}>{uiText("Back")}</Button><Button kind="primary" disabled={busy || !orderReviewReady(inputs)} onClick={() => check(false)}>{busy ? uiText("Checking…") : uiText("Preview demand")}</Button></div></>}
    {step === 3 && review && <><section className="surface"><h2>{uiText("Review before saving")}</h2><p>{uiText('Results: {{rows}} · Order lines: {{orders}}',{rows:review.rows.length,orders:review.orders.length})} · {review.can_export ? uiText("Ready for draft export") : uiText("Inputs need attention before export")}</p><OrderChanges changes={review.order_changes} Table={Table}/>{review.warnings.map((w,i) => <p key={i} className="source-notice">{w}</p>)}<Table headers={[uiText("Customer"),uiText("SKU"),uiText("Month"),uiText("Calculated estimate"),uiText("Open orders"),uiText("Already fulfilled"),uiText("Still expected"),uiText("Total demand"),uiText("Check")]}>{review.rows.slice(0,30).map((r,i) => <tr key={i}><td>{r.customer}</td><td>{r.sku}</td><td>{r.period_label||planningMonth(r.period,basis)}</td>{['baseline','booked','fulfilled','remaining','total'].map(k => <td key={k}>{number(r[k])} {r.unit}</td>)}<td>{r.issue || r.status}</td></tr>)}</Table>{review.rows.length>30 && <p>{uiText('First 30 results shown. The saved view includes every row.')}</p>}</section><div className="demand-actions"><Button disabled={busy} onClick={() => setStep(2)}>{uiText("Back")}</Button><Button kind="primary" disabled={busy} onClick={() => check(true)}>{busy ? uiText("Saving…") : uiText("Save reviewed snapshot")}</Button></div></>}
  </Page>;
}

function OptionalSalesInput({role,count,children}) {
  const [open,setOpen]=useState(count>0);
  if(role!=='commitments')return children;
  return <details className="optional-section" open={open} onToggle={e=>setOpen(e.currentTarget.open)}>
    <summary>{uiText("Customer-confirmed monthly totals")}<span>{count ? count+' loaded' : uiText("Optional")}</span></summary>
    {children}
  </details>;
}

function OrderChanges({changes,Table}) {
  if (!changes) return null;
  if (!changes.length) return <p>{uiText('No order lines changed. Saving records a new review.')}</p>;
  const value=(row,field)=>!row?'—':['due_date','status'].includes(field)?row[field]:number(row[field])+' '+row.unit;
  return <details open><summary>{uiText('{{count}} order lines changed',{count:changes.length})}</summary><Table headers={[uiText("Order line"),uiText("Changed field"),uiText("Before"),uiText("After")].map(uiText)}>{changes.slice(0,100).flatMap(c=>{
    const fields=['due_date','ordered','fulfilled','cancelled','status'].filter(k=>c.before?.[k]!==c.after?.[k]);
    const source=c.after||c.before;
    return fields.map((k,i)=><tr key={c.reference+'/'+k}>{i===0&&<td rowSpan={fields.length} title={source.customer+' · '+source.sku}>{c.reference}{c.change!=='updated'&&<small> · {title(c.change)}</small>}</td>}<td>{title(k)}</td><td>{value(c.before,k)}</td><td>{value(c.after,k)}</td></tr>);
  })}</Table>{changes.length>100&&<p>{uiText('First 100 changed orders shown. All changes are saved with this version.')}</p>}</details>;
}

export function SalesSource({api,ui,role,schema,config,setConfig,run,fallbackCount,orderMode,modeControl,onBusyChange,templateBase,embedded=false}) {
  const {Button,Pick,Field,Table,ErrorBox} = ui;
  const [source,setSource] = useState(config?._source || null), [preview,setPreview] = useState(config?._preview || null), [busy,setBusy] = useState(false), [error,setError] = useState('');
  const [heading,setHeading] = useState(config?.header_row || 1);
  const mappingReady = salesMappingReady(schema,config,heading);
  useEffect(()=>{onBusyChange?.(role,busy||!!error||!mappingReady);},[role,busy,error,mappingReady,onBusyChange]);
  useEffect(()=>{if(!config){setSource(null);setPreview(null);setHeading(1);}},[config]);
  function accept(data, id, uploaded = source) {
    requireSalesHeadings(data);
    setPreview(data);
    const mapping = Object.fromEntries(Object.keys(schema).map(field => [field,data.columns.find(c => String(c.label).trim().toLowerCase() === field)?.id || '']));
    setConfig({source_id:id,sheet:data.sheet,header_row:data.header_row,mapping,calendar:config?.calendar||'gregorian',customer_matches:config?.customer_matches,_preview:data,_source:uploaded});
  }
  async function upload(file) {
    if(!file)return;setBusy(true);setError('');
    try {const form=new FormData();form.append('file',file);form.append('role',role);const s=await api('/api/sales/sources',form);requireSalesHeadings(s.preview);setSource(s);setHeading(s.preview.header_row);accept(s.preview,s.id,s);} catch(e){setError(e);}finally{setBusy(false);}
  }
  async function rePreview(sheet) {
    setBusy(true);setError('');
    try {accept(await api(`/api/sales/sources/${source.id}/preview`,{sheet,header_row:Number(heading)}),source.id);}catch(e){setError(e);}finally{setBusy(false);}
  }
  function resetUpload() {
    setError('');setSource(null);setPreview(null);setHeading(1);setConfig(undefined);
  }
  return <article className={embedded?'ui-stack':'sales-source'}><div className={embedded?'ui-panel-header':'section-heading'}><div><h3 className={embedded?'ui-panel-title':undefined}>{uiText(title(role))}{role==='commitments' ? <> · {uiText('optional')}</> : ''}</h3>{!embedded&&<p>{role==='customers' ? uiText('{{count}} relationships loaded. Upload a full list to replace them.',{count:fallbackCount}) : role==='orders' ? <>{uiText('{{count}} order lines loaded.',{count:fallbackCount})}{' '}{uiText(orderMode==='changes' ? 'Matching references are updated; other lines are kept. Use full quantities, not increases.' : 'A full file replaces the order book, including any missing lines.')}</> : uiText('Only for customers who explicitly confirm their entire monthly requirement.')}</p>}</div><a className="btn secondary" href={`${templateBase||'/api/sales/runs/'+run.run_id+'/template'}/${role}`}>{uiText("Template")}</a></div>{modeControl}<label className="sales-upload"><UploadSimple size={22}/><span>{busy ? uiText("Reading file…") : source?.name || (embedded&&fallbackCount?uiText('{{count}} {{label}} loaded — choose a file to replace',{count:fallbackCount,label:uiText(title(role))}):uiText(`Choose ${role} file`))}</span><input aria-label={uiText('Upload {{label}}',{label:uiText(title(role))})} type="file" accept=".csv,.tsv,.xlsx,.xlsm,.json" disabled={busy} onChange={e => {const file=e.target.files[0];e.target.value='';upload(file);}}/></label><ErrorBox error={error}/>{(source||error)&&<Button disabled={busy} onClick={resetUpload}>{fallbackCount ? uiText('Use saved {{label}}',{label:uiText(title(role))}) : uiText("Clear upload")}</Button>}{preview&&!mappingReady&&!error&&<p role="status">{uiText(Number(heading)!==config?.header_row ? 'Read the new heading row before continuing.' : 'Choose a column for each required field before continuing.')}</p>}
    {preview && <>{role!=='customers'&&<Field title={uiText("Dates in this file")}><Pick label={uiText("Order file calendar")} value={config?.calendar||'gregorian'} options={[["gregorian",uiText("Gregorian")],["jalali",uiText("Persian (Jalali)")]]} onChange={calendar=>setConfig({...config,calendar})}/></Field>}<CustomerMatches api={api} ui={ui} matches={config?.customer_matches||{}} onChange={customer_matches=>setConfig({...config,customer_matches})}/><div className="demand-controls">{!!preview.sheets.length && <Field title={uiText("Worksheet")}><Pick label={uiText("Worksheet")} value={preview.sheet} onChange={rePreview} options={preview.sheets.map(v=>[v,v])}/></Field>}<Field title={uiText("Heading row")}><input type="number" min="1" max="200" value={heading} onChange={e=>setHeading(e.target.value)}/></Field><Button disabled={busy} onClick={()=>rePreview(preview.sheet)}>{uiText("Read headings")}</Button></div><div className="demand-mapping">{Object.entries(schema).map(([field,rule])=><Field key={field} title={`${uiText(title(field))}${rule.required?' *':''}`}><Pick label={uiText(title(field))} value={config?.mapping[field] || ''} onChange={v=>setConfig({...config,mapping:{...config.mapping,[field]:v}})} options={[["",rule.required?uiText('Choose column'):uiText("Not provided")],...preview.columns.map(c=>[c.id,c.label])]}/></Field>)}</div><details><summary>{uiText("Preview source rows")}</summary><Table headers={preview.columns.map(c=>c.label)}>{(preview.preview || preview.rows || []).slice(0,5).map((r,i)=><tr key={i}>{preview.columns.map(c=><td key={c.id}>{String((r.values || r)[c.id] ?? '')}</td>)}</tr>)}</Table></details></>}
  </article>;
}

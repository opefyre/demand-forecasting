import React,{useState} from 'react';
import {ComposedChart,Area,Line,ResponsiveContainer,XAxis,YAxis,Tooltip,Legend} from 'recharts';
import {DownloadSimple} from '@phosphor-icons/react';
import {t as uiText,i18n,unitLabel} from './localization.mjs';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {estimateRows,estimateTotal,estimateChart} from './model-estimate.mjs';
import {PivotTable} from './demand-tables.jsx';
import {csvTable} from './demand-view.mjs';
import {chartTheme} from './chart-theme.mjs';

export function ModelEstimate({run,ui,onOrders,canEdit,navigate,initialCustomer='',unified=false}){
  const {Button,Pick,Help}=ui;
  const [customer,setCustomer]=useState(initialCustomer),[sku,setSku]=useState(''),[period,setPeriod]=useState(''),[display,setDisplay]=useState('chart');
  const all=estimateRows(run),rows=estimateRows(run,{customer,sku,period}),total=estimateTotal(rows);
  const number=n=>n==null?'—':new Intl.NumberFormat(i18n.language,{maximumFractionDigits:1}).format(n);
  const chart=estimateChart(run,{customer,sku,period}).map(r=>({...r,label:planningMonth(r.date,planningBasis(run))}));
  function download(){const csv=csvTable(['Customer','SKU','Period start (ISO)','Month','Planning calendar','Unit','Calculated estimate','Lower forecast range','Upper forecast range'],rows.map(r=>[r.customer,r.sku,r.period,planningMonth(r.period,r.planning_calendar),r.planning_calendar,r.unit,r.total,r.lower,r.upper]));
    const url=URL.createObjectURL(new Blob(['\ufeff',csv],{type:'text/csv;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='calculated-forecast.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  return <div className="model-estimate">
    <div className="compact-toolbar demand-filters">
      {all.some(r=>r.customer)&&<Pick label={uiText('Customer')} value={customer} onChange={setCustomer} options={[["",uiText('All customers')],...[...new Set(all.map(r=>r.customer))].sort().map(v=>[v,v])]}/>}
      <Pick label={uiText('SKU')} value={sku} onChange={setSku} options={[["",uiText('All SKUs')],...[...new Set(all.map(r=>r.sku))].sort().map(v=>[v,v])]}/>
      <Pick label={uiText('Month')} value={period} onChange={setPeriod} options={[["",uiText('All months')],...[...new Set(all.map(r=>r.period))].sort().map(v=>[v,planningMonth(v,planningBasis(run))])]}/>
      {(customer||sku||period)&&<button className="home-text-link" onClick={()=>{setCustomer('');setSku('');setPeriod('');}}>{uiText('Clear filters')}</button>}
    </div>
    <section className="surface">
      <div className="section-heading"><div className="demand-chart-title"><h2>{uiText('Calculated estimate')}</h2><strong>{number(total)} {unitLabel(run.unit)}</strong><Help text={uiText('This is the model estimate. Current orders have not been reviewed for this forecast.')}/></div><div className="demand-segments" role="group" aria-label={uiText('Display results')}>{['chart','pivot'].map(v=><button key={v} aria-pressed={display===v} onClick={()=>setDisplay(v)}>{uiText(v==='chart'?'Chart':'Monthly')}</button>)}</div></div>
      {run.evidence_policy==='reviewed_what_if'&&<p className="table-note">{uiText('What-if forecast. Past accuracy and forecast ranges are not verified.')}</p>}
      {!rows.length?<p>{uiText('No results match these filters.')}</p>:display==='pivot'?<PivotTable rows={rows} ui={ui}/>:<div className="demand-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chart} margin={chartTheme.margin}><XAxis dataKey="label" tick={chartTheme.ticks} minTickGap={30} interval="preserveStartEnd"/><YAxis tick={chartTheme.ticks}/><Tooltip formatter={(value,name)=>[(Array.isArray(value)?value.map(number).join(' – '):number(value))+' '+unitLabel(run.unit),name]}/><Legend/>{chart.some(r=>r.range)&&<Area isAnimationActive={false} name={uiText('Forecast range')} dataKey="range" fill="var(--chart-range)" stroke="none" connectNulls={false}/>}<Line isAnimationActive={false} name={uiText('Historical sales')} dataKey="actual" stroke="var(--chart-history)" dot={false} connectNulls={false}/><Line isAnimationActive={false} name={uiText('Calculated estimate')} dataKey="forecast" stroke="var(--chart-forecast)" strokeWidth={2} dot={chartTheme.dot} connectNulls={false}/></ComposedChart></ResponsiveContainer></div>}
      <div className="compact-toolbar"><button className="home-text-link" disabled={!rows.length} onClick={download}><DownloadSimple size={16}/>{uiText('Download estimate')}</button>{navigate&&<button className="home-text-link" onClick={()=>navigate('forecast')}>{uiText('How was this calculated?')}</button>}</div>
    </section>
    <div className="model-order-action"><span>{uiText('Review current orders to complete the demand forecast.')}</span>{canEdit&&<Button kind="primary" onClick={onOrders}>{uiText(unified?'Complete forecast setup':'Add customers & orders')}</Button>}</div>
  </div>;
}

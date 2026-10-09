import {t as uiText,unitLabel,i18n} from './localization.mjs';
import {smoothUpdate} from './ui-motion.jsx';
import React,{useEffect,useState} from 'react';
import {coverageStatus,pivotDemand,sortDemand,customerBaseline} from './demand-view.mjs';
import {planningMonth} from './planning-calendar.mjs';

const number=n=>n==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:2}).format(n);
export function PivotTable({rows,measure='total',sort='name',ui}){
  const {Table,Button}=ui;
  const pivot=pivotDemand(rows,measure),data=sortDemand(pivot.rows,sort);
  const [page,setPage]=useState(0);
  useEffect(()=>setPage(0),[rows,measure,sort]);
  return <><Table headers={[uiText("Customer / SKU"),...pivot.periods.map(p=>planningMonth(p,rows[0]?.planning_calendar)),uiText("Total")]} empty={!data.length&&uiText('No results match these filters.')}>
    {data.slice(page*30,(page+1)*30).map(row=><tr key={JSON.stringify([row.customer,row.sku,row.unit])}><th scope="row"><strong>{row.customer}</strong><br/>{row.sku}</th>{pivot.periods.map(p=><td key={p} title={row.cells.has(p)?undefined:uiText("No matching row in this selection")}>{row.cells.has(p)?number(row.cells.get(p)):'—'}</td>)}<td><strong>{number(row.total)}</strong></td></tr>)}
    {!!data.length&&<tr className="pivot-total"><th scope="row">{uiText("Total")}</th>{pivot.totals.map((v,i)=><td key={i}>{number(v)}</td>)}<td>{number(pivot.total)}</td></tr>}
  </Table>{data.length>30&&<div className="demand-actions"><Button disabled={!page} onClick={()=>smoothUpdate(()=>setPage(p=>p-1))}>{uiText("Previous")}</Button><span>{uiText('pageProgress',{page:page+1,total:Math.ceil(data.length/30)})} · {uiText('Totals include every row')}</span><Button disabled={(page+1)*30>=data.length} onClick={()=>smoothUpdate(()=>setPage(p=>p+1))}>{uiText("Next")}</Button></div>}</>;
}

export function CoverageTable({rows,ui}){
  const {Table,Button}=ui;const [page,setPage]=useState(0);
  useEffect(()=>setPage(0),[rows]);
  return <><Table headers={[uiText("Customer / SKU"),uiText("Month"),uiText("Coverage"),uiText("Open orders"),uiText("Still expected"),uiText("What needs attention")]} empty={!rows.length&&uiText('No results match these filters.')}>
    {rows.slice(page*50,(page+1)*50).map(r=><tr key={JSON.stringify([r.customer,r.sku,r.period,r.unit])}><th scope="row"><strong>{r.customer}</strong><br/>{r.sku}</th><td>{r.period_label||r.period.slice(0,7)}</td><td><span className={'coverage-state '+(r.remaining==null||r.issue?'needs-attention':'')}>{uiText(coverageStatus(r))}</span></td><td>{number(r.booked)}</td><td>{number(r.remaining)}</td><td>{r.issue||'—'}</td></tr>)}
  </Table>{rows.length>50&&<div className="demand-actions"><Button disabled={!page} onClick={()=>smoothUpdate(()=>setPage(p=>p-1))}>{uiText("Previous")}</Button><span>{uiText('pageProgress',{page:page+1,total:Math.ceil(rows.length/50)})}</span><Button disabled={(page+1)*50>=rows.length} onClick={()=>smoothUpdate(()=>setPage(p=>p+1))}>{uiText("Next")}</Button></div>}</>;
}

export function CustomerCalculation({run,customer,ui,onOrders,canEdit}){
  const {Button}=ui;const rows=React.useMemo(()=>customerBaseline(run,customer),[run,customer]);
  return <section className="surface"><div className="section-heading"><h2>{customer} · {uiText('calculated estimate')}</h2>{canEdit&&<Button onClick={onOrders}>{uiText('Add orders')}</Button>}</div><p>{uiText('Orders have not been included in this new calculation. Quantities in {{unit}}.',{unit:unitLabel(run.unit)})}</p><PivotTable rows={rows} ui={ui}/></section>;
}

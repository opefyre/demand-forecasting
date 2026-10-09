import {planningBasis} from './planning-calendar.mjs';

// Display only the engine's non-overlapping leaf series. Orders are not inferred.
export function estimateRows(run,{customer='',sku='',period=''}={}){
  return (run?.items||[]).filter(id=>id!=='__all__').flatMap(id=>{
    const meta=run.metadata?.[id]||{};
    if(customer&&meta.customer!==customer||sku&&String(meta.sku||id)!==sku)return[];
    return(run.series?.[id]?.forecast||[]).filter(r=>!period||r.timestamp.slice(0,10)===period).map(r=>({
      customer:meta.customer||'',sku:String(meta.sku||id),unit:run.unit,
      period:r.timestamp.slice(0,10),planning_calendar:planningBasis(run),total:r.mean,lower:r.p10??null,upper:r.p90??null,
    }));
  });
}
export function estimateTotal(rows){return !rows.length||rows.some(r=>r.total==null)?null:rows.reduce((s,r)=>s+r.total,0);}
export function estimateChart(run,filters={}){
  const grouped=new Map();
  const add=(date,field,value)=>{const r=grouped.get(date)||{date};
    r[field]=!Object.hasOwn(r,field)?value:r[field]==null||value==null?null:r[field]+value;grouped.set(date,r);};
  if(!filters.period)for(const id of(run?.items||[]).filter(id=>id!=='__all__')){
    const meta=run.metadata?.[id]||{};
    if(filters.customer&&meta.customer!==filters.customer||filters.sku&&String(meta.sku||id)!==filters.sku)continue;
    for(const r of run.series?.[id]?.history||[])add(r.timestamp.slice(0,10),'actual',r.target);
  }
  for(const r of estimateRows(run,filters))add(r.period,'forecast',r.total);
  const rows=[...grouped.values()].sort((a,b)=>a.date.localeCompare(b.date));
  const ids=(run?.items||[]).filter(id=>id!=='__all__').filter(id=>{
    const meta=run.metadata?.[id]||{};
    return(!filters.customer||meta.customer===filters.customer)&&(!filters.sku||String(meta.sku||id)===filters.sku);
  });
  // Use only a range actually calculated for this scope; never sum item bounds.
  const source=ids.length===1?run.series?.[ids[0]]:!filters.customer&&!filters.sku?run.series?.__all__:null;
  const bounds=new Map((source?.forecast||[]).filter(r=>r.p10!=null&&r.p90!=null).map(r=>[r.timestamp.slice(0,10),[r.p10,r.p90]]));
  for(const row of rows)if(bounds.has(row.date))row.range=bounds.get(row.date);
  // Anchor at the final actual point, but do not invent points across missing months.
  const last=rows.filter(r=>Object.hasOwn(r,'actual')).at(-1);
  if(last&&!Object.hasOwn(last,'forecast'))last.forecast=last.actual;
  return rows;
}

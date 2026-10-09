import {planningBasis,planningMonth} from './planning-calendar.mjs';

export function salesSeriesLabel(run,id) {
  if(id==='__all__')return 'All customers & products';
  const meta=run?.metadata?.[id];
  return meta?.customer&&meta?.sku ? `${meta.customer} · ${meta.sku}` : id;
}

export function sortDemand(rows, sort='name') {
  return [...rows].sort((a,b)=>{
    if(sort==='largest'||sort==='smallest') {
      if(a.total==null) return b.total==null?0:1;
      if(b.total==null) return -1;
      return (a.total-b.total)*(sort==='largest'?-1:1);
    }
    const key=r=>r.label??[r.customer,r.sku,r.period].join(' / ');
    return key(a).localeCompare(key(b),undefined,{numeric:true});
  });
}

export const demandViewLabel=value=>({chart:'Chart',trend:'Trend',table:'Table',pivot:'Monthly',coverage:'Coverage'}[value]||value);

export function demandCSV(rows, grouped, unit) {
  const fields=grouped?['label','baseline','booked','fulfilled','remaining','total']:['customer','sku','period','period_label','planning_calendar','baseline','booked','fulfilled','remaining','total'];
  const labels={label:'Group',customer:'Customer',sku:'SKU',period:'Period start (ISO)',period_label:'Month',planning_calendar:'Planning calendar',baseline:'Calculated estimate',booked:'Open orders',fulfilled:'Fulfilled',remaining:'Still expected',total:'Total demand including fulfilled'};
  const cell=value=>{
    let text=value==null?'Unknown':String(value);
    // Prevent customer/product labels being interpreted as spreadsheet formulas.
    if(/^[\s]*[=+@-]/.test(text)&&typeof value!=='number')text="'"+text;
    return '"'+text.replaceAll('"','""')+'"';
  };
  return [[...fields.map(f=>labels[f]),'Unit'],...rows.map(row=>[...fields.map(f=>row[f]),unit])].map(row=>row.map(cell).join(',')).join('\r\n');
}

export function mergeDirectory(existing, directory) {
  const pairs=new Map(existing.map(c=>[JSON.stringify([c.customer,c.sku,c.unit]),c]));
  for(const customer of directory.filter(c=>c.active))for(const product of customer.products){
    const row={customer:customer.customer,sku:product.sku,unit:product.unit,series_id:''};
    const key=JSON.stringify([row.customer,row.sku,row.unit]);
    if(!pairs.has(key))pairs.set(key,row);
  }
  return [...pairs.values()];
}

export function coverageStatus(row) {
  if(row.status==='Orders unknown')return 'Orders unknown';
  if(row.status==='Conflict')return 'Needs review';
  if(row.remaining==null)return 'More history needed';
  if(row.issue)return 'Needs review';
  if(row.status==='Complete commitment')return 'Complete commitment';
  if(row.status==='Covered by orders')return 'Covered by orders';
  if(row.booked>0)return 'Partly booked';
  if(row.fulfilled>0)return 'Fulfilled / still expected';
  return 'No orders';
}

export const COVERAGE_OPTIONS=['No orders','Partly booked','Covered by orders','Complete commitment','Fulfilled / still expected','Orders unknown','More history needed','Needs review'];

export function pivotDemand(rows,measure='total') {
  if(new Set(rows.map(r=>r.unit)).size>1)throw new Error('Select one unit before calculating pivot totals.');
  const periods=[...new Set(rows.map(r=>r.period))].sort();
  const grouped=new Map();
  for(const row of rows){
    const key=JSON.stringify([row.customer,row.sku,row.unit]);
    if(!grouped.has(key))grouped.set(key,{customer:row.customer,sku:row.sku,unit:row.unit,cells:new Map()});
    const cells=grouped.get(key).cells;
    const value=row[measure];
    cells.set(row.period,!cells.has(row.period)?value:cells.get(row.period)==null||value==null?null:cells.get(row.period)+value);
  }
  const sum=values=>!values.length||values.some(v=>v==null)?null:values.reduce((a,b)=>a+b,0);
  const result=[...grouped.values()].map(row=>({...row,total:sum([...row.cells.values()])}));
  // Absent cells have no row in this selection; present nulls are unknown demand.
  // Totals include precisely the selected rows, also when coverage filters differ by month.
  return {periods,planning_calendar:rows[0]?.planning_calendar||'gregorian',rows:result,totals:periods.map(p=>sum(result.filter(r=>r.cells.has(p)).map(r=>r.cells.get(p)))),total:sum(result.map(r=>r.total))};
}

export function csvTable(headers,rows){
  const cell=value=>{
    let text=value==null?'Unknown':String(value);
    if(/^[\s]*[=+@-]/.test(text)&&typeof value!=='number')text="'"+text;
    return '"'+text.replaceAll('"','""')+'"';
  };
  return [headers,...rows].map(row=>row.map(cell).join(',')).join('\r\n');
}

export function pivotCSV(pivot,measure='total'){
  const label={total:'Total demand',baseline:'Calculated estimate',booked:'Open orders',remaining:'Still expected',still_to_serve:'Still to serve'}[measure];
  return csvTable(['Customer','SKU','Unit',...pivot.periods.map(p=>planningMonth(p,pivot.planning_calendar)+' '+label),'Total '+label],pivot.rows.map(r=>[r.customer,r.sku,r.unit,...pivot.periods.map(p=>r.cells.has(p)?r.cells.get(p):'Not in selection'),r.total]));
}

export function coverageCSV(rows){
  return csvTable(['Customer','SKU','Period start (ISO)','Month','Planning calendar','Unit','Coverage','Open orders','Still expected','Total demand','Issue'],rows.map(r=>[r.customer,r.sku,r.period,r.period_label||planningMonth(r.period,r.planning_calendar),r.planning_calendar||'gregorian',r.unit,coverageStatus(r),r.booked,r.remaining,r.total,r.issue||'']));
}

export function customerBaseline(run,customer){
  return Object.entries(run?.metadata||{}).flatMap(([id,meta])=>id!=='__all__'&&String(meta.customer)===customer?(run.series[id]?.forecast||[]).map(row=>({customer,sku:String(meta.sku||id),unit:run.unit,period:row.timestamp.slice(0,10),planning_calendar:planningBasis(run),total:row.mean})):[]);
}

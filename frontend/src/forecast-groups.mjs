export function forecastGroups(runs){
  const groups=new Map();
  for(const run of runs){
    const key=run.forecast_group_id?'group:'+run.forecast_group_id:run.forecast_order_inputs_id&&!run.scenario_name&&!run.base_run_id?'inputs:'+run.dataset_id+':'+run.forecast_order_inputs_id:'run:'+run.run_id;
    if(!groups.has(key))groups.set(key,{id:key,name:run.forecast_name||run.name||run.dataset_name||run.run_id,runs:[]});
    const group=groups.get(key);
    if(!group.runs.some(r=>r.method_selection&&r.method_selection===run.method_selection))group.runs.push(run);
  }
  return [...groups.values()];
}
export function methodRows(entries,{customer='',sku='',period='',unit='',coverage=''}={}){
  const periods=new Map();
  for(const entry of entries)for(const row of entry.rows){
    if(customer&&row.customer!==customer||sku&&row.sku!==sku||period&&row.period!==period||unit&&row.unit!==unit||coverage&&entry.coverage(row)!==coverage)continue;
    const target=periods.get(row.period)||{period:row.period},key=entry.run_id;
    target[key]=target[key]===null||row.total==null?null:(target[key]||0)+row.total;periods.set(row.period,target);
  }
  return [...periods.values()].sort((a,b)=>a.period.localeCompare(b.period));
}
export function comparisonAvailability(rows,methodIds){
 return {hasEstimate:rows.some(row=>methodIds.some(id=>Number.isFinite(row[id]))),hasMissing:rows.some(row=>methodIds.some(id=>row[id]==null))};
}

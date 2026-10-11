// UI choices use the existing engine's exact public method identifiers.
export const FORECAST_CHOICES=[
  ['recommended','Automatic','Compare eligible methods against past sales.'],
  ['model:Last observed','Last period','Repeat the latest actual quantity.'],
  ['model:Recent average','Recent average','Use the average of the last three periods.'],
  ['model:Weighted recent average','Weighted average','Give more weight to recent periods.'],
  ['model:Seasonal naive','Same season','Use the matching period from the previous season.'],
  ['model:Holt trend','Trend','Extend the recent growth or decline.'],
  ['model:AutoETS','Smoothing','Learn the level, trend and repeating pattern.'],
  ['model:AutoARIMA','ARIMA','Learn changes and patterns over time.'],
  ['model:Croston SBA','Infrequent sales','Estimate demand when sales happen irregularly.'],
  ['model:Ridge + drivers','Linear model + factors','Learn the relationship between sales and selected factors.'],
  ['model:Elastic Net + drivers','Selective linear model','Learn factor relationships while limiting weak signals.'],
  ['model:Histogram gradient boosting','Boosted trees','Learn non-linear patterns from sales and factors.'],
];
export function forecastInputs(datasets){return datasets.filter(d=>d.sources?.history&&!d.scenario_provenance&&!d.sources.operations&&!d.lifecycle?.archived);}
export function remainingMethods(methods,jobs){return methods.filter(method=>!jobs.some(j=>j.method===method));}
export function orderCoverageTitle(orders,uploadedOrders){return orders?.length||uploadedOrders?'All known orders included':'No current orders';}
export function forecastSummary(run){
  const rows=run.series?.__all__?.forecast||run.forecast;
  if(!Array.isArray(rows)||!rows.length||rows.some(row=>typeof row.mean!=='number'||!Number.isFinite(row.mean)))return null;
  return{total:rows.reduce((sum,row)=>sum+row.mean,0),periods:rows.length,unit:run.unit};
}
export const FORECAST_DRAFT_KEY='demandlab.newForecast';
export function forecastOrderDraft(value,source){
  if(!value||value.datasetId!==source||!Number.isInteger(value.bookVersion)||value.bookVersion<0||!value.inputs||typeof value.inputs.run_id!=='string'||value.inputs.run_id.length>80)return null;
  if(!['customers','orders','commitments'].every(key=>Array.isArray(value.inputs[key])))return null;
  if(JSON.stringify(value).length>1000000)return null;
  // Drafts are editable inputs, never proof of review. The company API revalidates
  // all lines, import mappings and source identities before accepting a snapshot.
  const inputs=Object.fromEntries(['name','run_id','as_of','valid_until','classification','order_feed','customers','orders','commitments','note'].map(key=>[key,value.inputs[key]]));
  return {datasetId:source,bookVersion:value.bookVersion,inputs:{...inputs,reviewed:false},imports:value.imports&&typeof value.imports==='object'&&!Array.isArray(value.imports)?value.imports:{},reuse:typeof value.reuse==='string'&&/^[a-f\d]{32}$/.test(value.reuse)?value.reuse:''};
}
export function forecastSettingsDraft(value){
  if(!value||!Number.isInteger(value.horizon)||value.horizon<1||value.horizon>24||!['gregorian','jalali'].includes(value.month_basis)||!['IR',''].includes(value.calendar_country))return null;
  return {horizon:value.horizon,month_basis:value.month_basis,calendar_country:value.calendar_country};
}
export function forecastFactorDraft(value,source){
  if(!value||value.datasetId!==source||!Array.isArray(value.selected)||value.selected.length>8)return null;
  if(value.selected.some(row=>!row||typeof row.id!=='string'||!row.id||!/^([1-9]|1[0-2])$/.test(String(row.lag))||typeof row.value!=='string'||row.value.length>80))return null;
  if(new Set(value.selected.map(row=>row.id)).size!==value.selected.length)return null;
  return {datasetId:source,expanded:typeof value.expanded==='string'?value.expanded:'',selected:value.selected.map(row=>({id:row.id,lag:String(row.lag),value:row.value,monthly:!!row.monthly,monthlyValues:Object.fromEntries(Object.entries(row.monthlyValues||{}).filter(([key,value])=>/^\d{4}-\d{2}-\d{2}$/.test(key)&&typeof value==='string'&&value.length<=80).slice(0,24)),timingAccepted:!!row.timingAccepted,calendarAccepted:!!row.calendarAccepted}))};
}
export function readForecastDraft(storage,availableSources,key=FORECAST_DRAFT_KEY,allowedMethods=FORECAST_CHOICES.map(([id])=>id)){
  try{const value=JSON.parse(storage?.getItem(key)||'null');
    if(!value||typeof value.source!=='string'||!Number.isInteger(value.step)||value.step<0||value.step>(value.version===2?4:3))return null;
    if(availableSources&&((value.source&&!availableSources.includes(value.source))||(!value.source&&value.step>0)))return null;
    const allowed=new Set(allowedMethods);
    if(!Array.isArray(value.methods)||value.methods.length>allowed.size||value.methods.some(m=>!allowed.has(m)))return null;
    if(!Array.isArray(value.jobs)||value.jobs.length>allowed.size||value.jobs.some(j=>typeof j.id!=='string'||!allowed.has(j.method)))return null;
    const salesInputId=typeof value.salesInputId==='string'&&/^[a-f\d]{32}$/.test(value.salesInputId)?value.salesInputId:null;
    const step=value.version===2?value.step:(value.step===3?4:value.step);
    const parentForecastId=typeof value.parentForecastId==='string'&&/^[a-f\d]{32}$/.test(value.parentForecastId)?value.parentForecastId:null;
    const factorDraft=forecastFactorDraft(value.factorDraft,value.source);
    return {source:value.source,step:factorDraft?.selected.length&&step>1&&!value.jobs.length?1:step===3&&!salesInputId?2:step,salesInputId,parentForecastId,settings:forecastSettingsDraft(value.settings),factorDraft,orderDraft:forecastOrderDraft(value.orderDraft,value.source),groupId:typeof value.groupId==='string'&&/^[a-f\d]{32}$/.test(value.groupId)?value.groupId:null,name:typeof value.name==='string'?value.name.slice(0,160):null,customer:typeof value.customer==='string'?value.customer.slice(0,160):'',methods:[...new Set(value.methods)],resumeJobs:value.jobs.some(job=>job.state!=='succeeded'),jobs:value.jobs.map(({id,method})=>({id,method,state:'loading'}))};
  }catch{return null;}
}

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
export function forecastInputs(datasets){return datasets.filter(d=>d.sources?.history&&!d.scenario_provenance&&!d.sources.operations);}
export function remainingMethods(methods,jobs){return methods.filter(method=>!jobs.some(j=>j.method===method));}
export function forecastSummary(run){
  const rows=run.series?.__all__?.forecast||run.forecast;
  if(!Array.isArray(rows)||!rows.length||rows.some(row=>typeof row.mean!=='number'||!Number.isFinite(row.mean)))return null;
  return{total:rows.reduce((sum,row)=>sum+row.mean,0),periods:rows.length,unit:run.unit};
}
export const FORECAST_DRAFT_KEY='demandlab.newForecast';
export function readForecastDraft(storage,availableSources){
  try{const value=JSON.parse(storage?.getItem(FORECAST_DRAFT_KEY)||'null');
    if(!value||typeof value.source!=='string'||!Number.isInteger(value.step)||value.step<0||value.step>(value.version===2?4:3))return null;
    if(availableSources&&((value.source&&!availableSources.includes(value.source))||(!value.source&&value.step>0)))return null;
    const allowed=new Set(FORECAST_CHOICES.map(([id])=>id));
    if(!Array.isArray(value.methods)||value.methods.length>allowed.size||value.methods.some(m=>!allowed.has(m)))return null;
    if(!Array.isArray(value.jobs)||value.jobs.length>allowed.size||value.jobs.some(j=>typeof j.id!=='string'||!allowed.has(j.method)))return null;
    const salesInputId=typeof value.salesInputId==='string'&&/^[a-f\d]{32}$/.test(value.salesInputId)?value.salesInputId:null;
    const step=value.version===2?value.step:(value.step===3?4:value.step);
    return {source:value.source,step:step===3&&!salesInputId?2:step,salesInputId,groupId:typeof value.groupId==='string'&&/^[a-f\d]{32}$/.test(value.groupId)?value.groupId:null,name:typeof value.name==='string'?value.name.slice(0,160):null,customer:typeof value.customer==='string'?value.customer.slice(0,160):'',methods:[...new Set(value.methods)],jobs:value.jobs.map(({id,method})=>({id,method,state:'loading'}))};
  }catch{return null;}
}

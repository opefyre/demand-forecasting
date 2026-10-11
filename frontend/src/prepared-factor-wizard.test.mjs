import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {readForecastDraft} from './forecast-start.mjs';
const compiler=await createServer({configFile:false,root:process.cwd(),server:{middlewareMode:true,hmr:false,ws:false,watch:null},appType:'custom',optimizeDeps:{noDiscovery:true,include:[]},cacheDir:'/private/tmp/demandlab-prepared-factor-cache'});
after(()=>compiler.close());
const {NewForecast,PreparedFactorSummary}=await compiler.ssrLoadModule('/src/new-forecast.jsx');
const {i18n}=await compiler.ssrLoadModule('/src/localization.mjs');
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),ErrorBox:()=>null,Help:()=>null,Pick:()=>null,Field:({children})=>React.createElement('div',{},children),Table:({headers,children})=>React.createElement('table',null,React.createElement('thead',null,React.createElement('tr',null,headers.map((h,i)=>React.createElement('th',{key:i},h)))),React.createElement('tbody',null,children))};
const alignment={series_ids:['a'],method:'model:Ridge + drivers',factors:[{factor:'Iran currency'}],rows:[{kind:'future',snapshot_id:'fx',sales_month:'2026-11-01',factor:'Iran currency',value:150,unit:'index',treatment:'planning_assumption'}]};
const dataset={id:'prepared',name:'Customer factors',settings:{horizon:3,month_basis:'gregorian'},scenario_provenance:{type:'factor_batch',base_run_id:'base',alignment:{groups:[{dataset_id:'child',alignment,series:[{id:'a',customer:'Mehr',sku:'001'}]}],unchanged_series_ids:['b']}}};
test('prepared factors reuse the shared five-stage modal without import or editable model controls',()=>{
  const html=renderToStaticMarkup(React.createElement(NewForecast,{ui,embedded:true,canEdit:true,preparedScenario:dataset,initialDraft:{source:dataset.id,step:3,methods:['reviewed_factors'],jobs:[]}}));
  assert.match(html,/Reviewed methods/);assert.match(html,/Mehr.*001/);assert.match(html,/Linear model \+ factors/);
  assert.doesNotMatch(html,/Import sales history|type="checkbox"|style=/);
  assert.match(html,/Customers &amp; orders/);
});
test('factor assumptions and scope stay readable in both interface languages',async()=>{
  for(const language of ['en','fa']){
    await i18n.changeLanguage(language);
    const html=renderToStaticMarkup(React.createElement(PreparedFactorSummary,{ui,dataset}));
    assert.match(html,/Mehr.*001/);assert.match(html,/Iran currency/);assert.match(html,/150/);
    if(language==='fa')assert.doesNotMatch(html,/Future assumptions|Linear model \+ factors|Your assumption|Planning months/);
    assert.doesNotMatch(html,/style=/);
  }
  await i18n.changeLanguage('en');
});
test('prepared draft marker is allowed only in its explicit isolated wizard',()=>{
  const saved={version:2,source:'prepared',step:2,methods:['reviewed_factors'],jobs:[]};
  const storage={getItem:()=>JSON.stringify(saved)};
  assert.equal(readForecastDraft(storage,['prepared']),null);
  assert.deepEqual(readForecastDraft(storage,['prepared'],'scenario',['reviewed_factors']).methods,['reviewed_factors']);
  assert.equal(readForecastDraft(storage,['other'],'scenario',['reviewed_factors']),null);
});
test('unscoped single-factor inputs show every baseline customer instead of failing',()=>{
  const single={...dataset,scenario_provenance:{type:'factor_link',alignment:{...alignment,series_ids:undefined}}};
  const html=renderToStaticMarkup(React.createElement(PreparedFactorSummary,{ui,dataset:single,baseline:{metadata:{a:{customer:'Mehr',sku:'001'},b:{customer:'Aftab',sku:'002'}}}}));
  assert.match(html,/Mehr.*001/);assert.match(html,/Aftab.*002/);
});
test('manual and assisted factor editor handoffs review orders before dispatching',async()=>{
  const root=await readFile(new URL('main.jsx',import.meta.url),'utf8');
  assert.match(root,/draftKey:FORECAST_DRAFT_KEY\+'\.scenario\.'\+saved.id/);
  assert.match(root,/saved.id\+\(parentForecastId\?'\.revision\.'\+parentForecastId:''\)/);
  assert.match(root,/onSaved=\{saved=>startScenarioForecast\(saved,run\)\}/);
  assert.match(root,/setDatasets\(previous=>\[saved,/);
  assert.match(root,/const legacyComparison=job.payload.base_run_id&&!job.payload.forecast_group_id/);
  assert.match(root,/if\(forecastRequest\)\{forecastIdentity.current=forecastRequest.id;forecastDialog.current=forecastRequest;\}/);
  assert.match(root,/preparedScenario=\{forecastDialog.current\?\.preparedScenario\}/);
  const assistant=await readFile(new URL('assistant-workspace.jsx',import.meta.url),'utf8');
  const editors=assistant.slice(assistant.indexOf('preparing?.workflow === "factor_batch_review"'),assistant.indexOf('className="ui-chat-workspace"'));
  assert.equal((editors.match(/onSaved=\{saved=>onPreparedForecast\(saved,run\)\}/g)||[]).length,2);
  assert.doesNotMatch(editors,/runDataset\(/);
});

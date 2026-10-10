import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let server,monthly,methods;
before(async()=>{
 server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
 monthly=await server.ssrLoadModule('/src/monthly-refresh.jsx');
 methods=await server.ssrLoadModule('/src/forecast-methods.jsx');
});
after(async()=>await server?.close());
test('update picker includes only original history and its descendants, safely rejecting cycles',()=>{
 const rows=[{id:'base'},{id:'corrected',parent_dataset_id:'base'},{id:'factors',parent_dataset_id:'corrected'},
  {id:'foreign'},{id:'cycleA',parent_dataset_id:'cycleB'},{id:'cycleB',parent_dataset_id:'cycleA'}];
 assert.deepEqual(monthly.updateInputVersions(rows,'base').map(r=>r.id),['base','corrected','factors']);
});
test('saved group resumes result jobs with their method and exact order review',()=>{
 const seed=monthly.groupedUpdateDraft({id:'update',dataset_id:'history',months:10,name:'October revision',
  parent_forecast_id:'original',group_id:'group',sales_input_id:'review',methods:['model:Last observed'],
  group:{jobs:[{id:'retry',state:'succeeded',payload:{method:'model:Last observed'}}]}});
 assert.equal(seed.step,4);assert.equal(seed.jobs[0].id,'retry');assert.equal(seed.jobs[0].method,'model:Last observed');
 assert.equal(seed.salesInputId,'review');assert.equal(seed.parentForecastId,'original');
 assert.equal(monthly.groupedUpdateDraft({id:'draft',months:10}).step,0);
 assert.deepEqual(monthly.groupedUpdateDraft({id:'legacy',methods:['trend']}).methods,[],
  'An older method family needs an explicit current choice, not a hidden or silently replaced model');
});
test('methods share framework controls; factor inputs expose only factor-capable models',()=>{
 const choices=methods.inputMethodChoices({settings:{drivers:['fx']}});
 assert.deepEqual(choices.map(([id])=>id),['model:Ridge + drivers','model:Elastic Net + drivers','model:Histogram gradient boosting']);
 const html=renderToStaticMarkup(React.createElement(methods.ForecastMethods,{choices,methods:[choices[0][0]],
  disabled:true,onChange(){},ui:{Help:()=>null}}));
 for(const marker of ['ui-grid','ui-choice','ui-check','disabled=""'])assert.ok(html.includes(marker),marker);
 assert.doesNotMatch(html,/style=|form-grid|section-heading/);
});
test('monthly and recurring drafts reuse the wizard and own no appearance rules or mixed import draft',async()=>{
 const monthlySource=await readFile(new URL('monthly-refresh.jsx',import.meta.url),'utf8');
 const recurringSource=await readFile(new URL('recurring-forecasts.jsx',import.meta.url),'utf8');
 const wizard=await readFile(new URL('new-forecast.jsx',import.meta.url),'utf8');
 assert.match(monthlySource,/<NewForecast/);assert.match(monthlySource,/allowAnother=\{false\} lockCalendar/);
 assert.match(monthlySource,/draftKey=\{'demandlab.monthlyForecast.'/);
 assert.match(wizard,/draftStorageKey:prepareImport\?draftKey\+'\.history'/);
 assert.match(wizard,/if\(!settingsDirty\)\{if\(continueStep\)setStep\(2\);return;\}/,
  'Unchanged saved inputs must not trigger an expensive cloud write');
 assert.match(recurringSource,/<Modal[^>]+wide fixed/);assert.match(recurringSource,/<ForecastMethods/);
 assert.match(recurringSource,/workflow:'grouped'/);
 assert.doesNotMatch(monthlySource+recurringSource,/style=|home-recent|home-text-link/);
});
test('retained factors show names and receipts before running, not just a change button',async()=>{
 const {IncludedForecastFactors}=await server.ssrLoadModule('/src/forecast-factors.jsx');
 const dataset={settings:{drivers:['generated_supply','fx'],factor_definitions:{generated_supply:{name:'Global supply pressure',source:'Federal Reserve',geography:'Global'}}},
  import_provenance:{alignment:{rows:[{kind:'future',factor:'Global supply pressure',sales_month:'2026-11-01',value:1.2,treatment:'planning_assumption'}]}}};
 const ui={Table:({children})=>React.createElement('table',null,React.createElement('tbody',null,children))};
 const html=renderToStaticMarkup(React.createElement(IncludedForecastFactors,{dataset,ui}));
 for(const marker of ['Review included factors','Global supply pressure','Federal Reserve','Future assumptions','Your assumption','ui-definition-list'])assert.ok(html.includes(marker),marker);
 assert.doesNotMatch(html,/generated_supply|style=/);
});

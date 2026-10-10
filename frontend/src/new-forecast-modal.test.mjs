import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {workspacePage} from './navigation.mjs';

const compiler=await createServer({configFile:false,root:process.cwd(),server:{middlewareMode:true,hmr:false,ws:false,watch:null},appType:'custom',optimizeDeps:{noDiscovery:true,include:[]},cacheDir:'/private/tmp/demandlab-forecast-modal-cache'});
after(()=>compiler.close());
const {NewForecast}=await compiler.ssrLoadModule('/src/new-forecast.jsx');
const {SalesDemand}=await compiler.ssrLoadModule('/src/sales-demand.jsx');
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),ErrorBox:()=>null,Help:()=>null,Pick:()=>null,Field:({children})=>React.createElement('div',{},children)};

test('legacy setup links lead to Forecast, not a standalone setup page',()=>{
  assert.equal(workspacePage('new'),'demand');assert.equal(workspacePage('assistant'),'today');
  assert.equal(workspacePage('settings'),'settings');assert.equal(workspacePage('forecast'),'forecast');
  assert.equal(workspacePage('unknown'),'today');
});
test('embedded wizard has all five stages without a duplicate title or close button',()=>{
  const html=renderToStaticMarkup(React.createElement(NewForecast,{ui,embedded:true,canEdit:true}));
  assert.doesNotMatch(html,/<h1|page-heading|>Close<|>New forecast</);
  for(const title of['Sales data','Factors','Customers &amp; orders','Methods','Results'])assert.ok(html.includes(title),title);
  assert.match(html,/Import sales history/);
});
test('Forecast has exactly one create action, including the empty state, and respects roles',()=>{
  for(const canEdit of[true,false]){
    const html=renderToStaticMarkup(React.createElement(SalesDemand,{ui,canEdit,startNewForecast:()=>{}}));
    assert.equal((html.match(/data-action="new-forecast"/g)||[]).length,canEdit?1:0);
    assert.doesNotMatch(html,/>Import sales history<|>Import data</);
  }
});
test('the app uses one shared centered modal and preserves the forecast page beneath it',async()=>{
  const source=await readFile(new URL('main.jsx',import.meta.url),'utf8');
  const topbar=source.slice(source.indexOf('<header className="topbar">'),source.indexOf('<main id="workspace">'));
  assert.doesNotMatch(topbar,/New forecast|startNewForecast/);
  assert.doesNotMatch(source,/page === "new"|onForecast=\{startNewForecast\}/);
  assert.match(source,/<Modal title=\{uiText\('New forecast'\)\} wide fixed open=\{[^}]+page==='demand'/);
  assert.match(source,/wide fixed open=\{canEdit&&!!forecastRequest/);
  assert.match(source,/dismissible=\{!forecastBusy\}/);
  assert.match(source,/<NewForecast[^>]+embedded onWorkingChange=\{setForecastBusy\}/);
  assert.match(source,/returnFocus=\{\(\)=>document.querySelector\('\[data-action="new-forecast"\]'/);
});
test('no manual create action remains in Data, Help or the assistant tools menu',async()=>{
  const source=await readFile(new URL('main.jsx',import.meta.url),'utf8');
  const data=source.slice(source.indexOf('function DataPage('),source.indexOf('function ImportFlow('));
  assert.doesNotMatch(data,/New forecast|onForecast/);
  const assistant=await readFile(new URL('assistant-workspace.jsx',import.meta.url),'utf8');
  assert.doesNotMatch(assistant,/label:uiText\('New forecast'\)/);
  assert.match(assistant.replace(/\s+/g,''),/onNewForecast\?\.\(result.dataset_id,result.method,result.customer\)/);
  const help=await readFile(new URL('help.jsx',import.meta.url),'utf8');
  assert.doesNotMatch(help,/navigate\([^)]*'new'|>\{uiText\("New forecast"\)\}<\/button>/);
});
test('cloud calculation uses the shared translated working status, not a perpetual startup label',async()=>{
  const source=await readFile(new URL('new-forecast.jsx',import.meta.url),'utf8');
  assert.match(source,/uiText\(cloudTransportEnabled\(\)\?'Calculating…':'Starting…'\)/);
  assert.doesNotMatch(source,/style=\{/);
});
test('the wizard cannot navigate backwards or dismiss while order validation is running',async()=>{
  const source=await readFile(new URL('new-forecast.jsx',import.meta.url),'utf8');
  assert.match(source,/const working=busy\|\|ordersBusy/);
  assert.match(source,/disabled=\{working\|\|step===0\}/);
  assert.match(source,/onWorkingChange=\{setOrdersBusy\}/);
  assert.match(source,/onPendingEditChange=\{setOrdersEditing\}/);
  assert.match(source,/disabled=\{working\|\|ordersEditing\|\|!canEdit/);
});

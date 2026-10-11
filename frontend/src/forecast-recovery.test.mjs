import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let server,Orders,Included,factorAmount,language,Steps;
before(async()=>{
  server=await createServer({server:{middlewareMode:true,hmr:false,ws:false,watch:null},appType:'custom'});
  ({ForecastOrders:Orders}=await server.ssrLoadModule('/src/forecast-orders.jsx'));
  ({IncludedForecastFactors:Included,factorAmount}=await server.ssrLoadModule('/src/forecast-factors.jsx'));
  ({i18n:language}=await server.ssrLoadModule('/src/localization.mjs'));
  ({Steps}=await server.ssrLoadModule('/src/ui-layout.jsx'));
});
after(async()=>{await language?.changeLanguage('en');await server?.close();});
test('shared wizard steps use the interface number system and retain current-step semantics',async()=>{
  await language.changeLanguage('fa');
  const html=renderToStaticMarkup(React.createElement(Steps,{items:['Sales data','Factors','Customers & orders'],current:1,label:'مراحل پیش‌بینی'}));
  assert.match(html,/aria-current="step"/);assert.match(html,/>۲<\/span>/);assert.match(html,/>۳<\/span>/);assert.doesNotMatch(html,/>2<\/span>|style=/);
  await language.changeLanguage('en');
});
test('initial customer/order failures expose shared reload rather than a dead-end',async()=>{
  let reload;
  const ui={ErrorBox:props=>{reload=props.onReload;return null;}};
  const html=renderToStaticMarkup(React.createElement(Orders,{dataset:{id:'history'},ui,api:()=>{},onReady:()=>{}}));
  assert.equal(typeof reload,'function');assert.match(html,/role="status"/);assert.doesNotMatch(html,/style=/);
  const source=await readFile(new URL('forecast-orders.jsx',import.meta.url),'utf8');
  assert.match(source,/targetRun\?\.run_id,readRevision\]/);
  assert.match(source,/onReload=\{\(\)=>setReadRevision\(value=>value\+1\)\}/);
});
test('pending order or commitment edits cannot replace their input context',async()=>{
  const source=await readFile(new URL('forecast-orders.jsx',import.meta.url),'utf8');
  assert.match(source,/const contextBlocked=blocked\|\|editingOrder\|\|editingCommitment/);
  assert.match(source,/async function useSaved\(id\)\{if\([^;]*editingOrder\|\|editingCommitment/);
  assert.match(source,/async function addCustomer\(\)\{if\(contextBlocked/);
  assert.match(source,/async function check\(\)\{if\([^;]*editingOrder\|\|editingCommitment/);
  assert.equal((source.match(/<FieldGroup disabled=\{contextBlocked\}>/g)||[]).length,2);
  assert.match(source,/Pick label=\{uiText\('Reuse saved orders'\)\} disabled=\{contextBlocked\}/);
  assert.doesNotMatch(source,/style=\{/);
});
test('factor reviews localize values without changing stored quantities or date direction',async()=>{
  const row={factor:'Exchange rate',sales_month:'2026-10-01',value:1250.125,unit:'tonnes',treatment:'planning_assumption',kind:'future'};
  const dataset={settings:{drivers:[],month_basis:'gregorian'},import_provenance:{alignment:{rows:[row]}}};
  const ui={Table:({headers,children})=>React.createElement('table',null,React.createElement('tbody',null,children))};
  await language.changeLanguage('en');assert.equal(factorAmount(0),'0');assert.equal(factorAmount(null),'—');
  await language.changeLanguage('fa');assert.equal(factorAmount(1250.125),'۱٬۲۵۰٫۱۲۵');
  const html=renderToStaticMarkup(React.createElement(Included,{dataset,ui}));
  assert.match(html,/۱٬۲۵۰٫۱۲۵/);assert.match(html,/تن/);assert.match(html,/<bdi>2026-10<\/bdi>/);
  assert.doesNotMatch(html,/1250\.125|Tonnes|style=/);assert.equal(row.value,1250.125);
  const source=await readFile(new URL('forecast-factors.jsx',import.meta.url),'utf8');
  assert.equal((source.match(/factorAmount\(row.value\)/g)||[]).length,3);
  assert.match(source,/<bdi>\{row.observation_period\}<\/bdi>/);
});

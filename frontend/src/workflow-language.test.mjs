import test,{after} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

// Reuse the actual JSX compiler/components. No DOM injection, provider calls,
// browser sign-in, customer writes or fake live-source accuracy claims.
const compiler=await createServer({configFile:false,root:process.cwd(),
  server:{middlewareMode:true,hmr:false,ws:false,watch:null},appType:'custom',
  optimizeDeps:{noDiscovery:true,include:[]},
  cacheDir:'/private/tmp/demandlab-workflow-language-cache'});
after(()=>compiler.close());
const locale=await compiler.ssrLoadModule('/src/localization.mjs');
const {InputMappingProposal}=await compiler.ssrLoadModule('/src/input-mapping-proposal.jsx');
const {AssistantFactorScenario}=await compiler.ssrLoadModule('/src/assistant-factor-scenario.jsx');
const {ExposureFields}=await compiler.ssrLoadModule('/src/factor-profile-editor.jsx');
const {RequestRecovery}=await compiler.ssrLoadModule('/src/request-recovery.jsx');
const {NewForecast}=await compiler.ssrLoadModule('/src/new-forecast.jsx');
const {SettingsWorkspace}=await compiler.ssrLoadModule('/src/settings-workspace.jsx');
const {responseFailure}=await compiler.ssrLoadModule('/src/request-errors.mjs');
const ui={
  Button:({children,disabled,onClick,kind,...attrs})=>React.createElement('button',{disabled,...attrs},children),
  Table:({headers,children})=>React.createElement('table',{},
    React.createElement('thead',{},React.createElement('tr',{},headers.map((h,i)=>React.createElement('th',{key:i},h)))),
    React.createElement('tbody',{},children)),
  Field:({title,help,children})=>React.createElement('label',{},title,children),
  Pick:({label,value,options,disabled})=>React.createElement('select',{'aria-label':label,value,disabled,onChange:()=>{}},options.map(([v,l])=>React.createElement('option',{key:v,value:v},l))),
  Help:({text})=>React.createElement('button',{type:'button',title:text},'?'),
  ErrorBox:()=>null,
};
const render=(component,props)=>renderToStaticMarkup(React.createElement(component,{...props,ui}));

test('real new forecast offers an explicit translated entry without changing source names',async()=>{
  await locale.changeInterfaceLanguage('fa');
  const datasets=[{id:'demo',name:'Customer Home · 0001',sources:{history:'file'},settings:{horizon:10}}];
  const html=render(NewForecast,{datasets,canEdit:true,api:()=>{throw Error('No API calls in render');}});
  assert.match(html,/پیش‌بینی جدید/);assert.match(html,/سوابق فروش را انتخاب کنید/);
  assert.match(html,/Customer Home · 0001/);assert.doesNotMatch(html,/Choose your sales history/);
  await locale.changeInterfaceLanguage('en');
});
test('real multiple-method selector uses tooltips, preserves engine keys and blocks reader execution',async()=>{
  await locale.changeInterfaceLanguage('fa');
  const previous=globalThis.sessionStorage;
  globalThis.sessionStorage={getItem:()=>JSON.stringify({version:2,source:'demo',step:3,salesInputId:'a'.repeat(32),methods:['model:Last observed','model:Recent average'],jobs:[]})};
  try{
    const html=render(NewForecast,{datasets:[{id:'demo',name:'Demo',sources:{history:'file'},settings:{}}],canEdit:false});
    assert.match(html,/یک یا چند روش را انتخاب کنید/);assert.match(html,/آخرین دوره/);assert.match(html,/میانگین اخیر/);
    assert.match(html,/title="مقدار واقعی آخرین دوره را تکرار می‌کند/);assert.match(html,/disabled=""/);
    assert.equal((html.match(/type="checkbox"/g)||[]).length,12);
    assert.doesNotMatch(html,/<small>.*Repeat the latest/);
  }finally{if(previous===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=previous;await locale.changeInterfaceLanguage('en');}
});
test('real settings shows one task section and preserves configured location values',async()=>{
  await locale.changeInterfaceLanguage('fa');
  const html=render(SettingsWorkspace,{workspace:{site:{name:'Factory 0001',province:'Tehran',timezone:'Asia/Tehran'}},access:{mode:'local'}});
  assert.match(html,/تنظیمات/);assert.match(html,/بخش‌های تنظیمات/);assert.match(html,/Factory 0001/);assert.match(html,/Asia\/Tehran/);
  assert.doesNotMatch(html,/Connection diagnostics|Location settings don.t fetch|Calls today/);
  await locale.changeInterfaceLanguage('en');
});

test('real mapping card translates chrome without rewriting original column names or authorizing a reader',async()=>{
  const action={reason:'Demo review · Customer Home',diff:[{field:'sku_col',before:'0001',after:'SKU-001'}],
    before_total:10,after_total:10,before_prepared_total:10,after_prepared_total:10,unit:'tonnes',warnings:[]};
  const original=structuredClone(action);
  await locale.changeInterfaceLanguage('fa');
  const reader=render(InputMappingProposal,{action,canEdit:false});
  assert.ok(reader.includes('بررسی تطبیق ستون‌ها'));
  assert.ok(reader.includes('0001'));assert.ok(reader.includes('SKU-001'));
  assert.ok(reader.includes('Customer Home'));assert.match(reader,/<button disabled=""/);
  const planner=render(InputMappingProposal,{action,canEdit:true});
  assert.doesNotMatch(planner,/<button disabled=""/);
  const expired=render(InputMappingProposal,{action,canEdit:true,expired:true});
  assert.ok(expired.includes('منقضی'));assert.doesNotMatch(expired,/<button/);
  assert.deepEqual(action,original);
  await locale.changeInterfaceLanguage('en');
  assert.ok(render(InputMappingProposal,{action,canEdit:true}).includes('Review input mappings'));
});

test('real factor scenario card requires confirmation and preserves source geography, methods and monthly values',async()=>{
  const action={preview:{scope:'Home · 0001',method:'model:Ridge + drivers',factors:[
    {factor:'USD/IRR',geography:'Iran · Tehran',unit:'IRR',lag_months:2,policy:'Saved policy'}],
    future_rows:[{factor:'USD/IRR',sales_month:'2026-10-01',value:1000000,unit:'IRR',treatment:'planning_assumption'}],
    retrospective:true,policy:'Not proof of client accuracy',warnings:[]}};
  const original=structuredClone(action);
  await locale.changeInterfaceLanguage('fa');
  const html=render(AssistantFactorScenario,{action,canEdit:true});
  assert.ok(html.includes('مقایسهٔ فرضی'));assert.ok(html.includes('فرض شما'));
  for(const value of ['Home · 0001','Ridge + drivers','Iran · Tehran','2026-10','1000000'])assert.ok(html.includes(value),value);
  assert.match(html,/<button disabled=""/); // not yet reviewed, even for planner
  const reader=render(AssistantFactorScenario,{action,canEdit:false});
  assert.match(reader,/<input[^>]*type="checkbox"[^>]*disabled=""/);
  const expired=render(AssistantFactorScenario,{action,canEdit:true,expired:true});
  assert.doesNotMatch(expired,/<button/);
  assert.deepEqual(action,original);
  await locale.changeInterfaceLanguage('en');
});

test('actual exposure form translates choices, not machine keys or material values',async()=>{
  const value={currency_exposure:true,global_supply:false,hormuz_route:false,materials:['copper']};
  const original=structuredClone(value);
  await locale.changeInterfaceLanguage('fa');
  const html=render(ExposureFields,{value,materials:[['copper','Copper'],['steel','Steel']],onChange:()=>{},disabled:true});
  assert.ok(html.includes('تغییر ارز'));assert.ok(html.includes('هرمز'));
  assert.ok(html.includes('value="steel"'));assert.ok(html.includes('Copper'));
  assert.match(html,/<select[^>]*disabled=""/);
  assert.deepEqual(value,original);await locale.changeInterfaceLanguage('en');
});

test('actual recovery box translates guidance, escapes source evidence and offers read-only reload',async()=>{
  let reloads=0;
  const error=responseFailure(503,{detail:'Customer Home · SKU 0001 <script>not markup</script>'});
  await locale.changeInterfaceLanguage('fa');
  const html=renderToStaticMarkup(React.createElement(RequestRecovery,{error,onReload:()=>reloads++}));
  assert.ok(html.includes('سرور نتوانست'));assert.ok(html.includes('دریافت دوبارهٔ داده'));
  assert.ok(html.includes('Customer Home · SKU 0001'));assert.ok(html.includes('&lt;script&gt;'));
  assert.doesNotMatch(html,/<script>/);assert.equal(reloads,0);
  await locale.changeInterfaceLanguage('en');
});

test('actual recovery box hides retry for permission/validation/cooldown and disables a busy reload',()=>{
  for(const status of [400,401,403,404,410,422,429]){
    const error=responseFailure(status,{detail:'Original evidence'},status===429?'60':null);
    const html=renderToStaticMarkup(React.createElement(RequestRecovery,{error,onReload:()=>{throw Error('must not auto-retry');}}));
    assert.doesNotMatch(html,/<button/);
  }
  const html=renderToStaticMarkup(React.createElement(RequestRecovery,{error:responseFailure(503,{}),onReload:()=>{},busy:true}));
  assert.match(html,/<button[^>]*disabled=""/);
  const invalid=renderToStaticMarkup(React.createElement(RequestRecovery,{error:responseFailure(400,{detail:'SKU 0001 needs more history.'})}));
  assert.ok(invalid.includes('SKU 0001 needs more history.'));assert.doesNotMatch(invalid,/<details/);
});

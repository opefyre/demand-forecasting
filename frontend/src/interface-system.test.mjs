import test from 'node:test';
import assert from 'node:assert/strict';
import{readFile,readdir}from'node:fs/promises';
import postcss from'postcss';
import{FORECAST_CHOICES,forecastInputs,remainingMethods,readForecastDraft,FORECAST_DRAFT_KEY,forecastSummary}from'./forecast-start.mjs';
import{fa}from'./locales/fa.mjs';
import{parsers}from'prettier/plugins/babel';
import{localizeSource}from'../scripts/localize-core-ui.mjs';

const root=new URL('./',import.meta.url);
test('every authored stylesheet uses the central visual registry',async()=>{
  const files=(await readdir(root)).filter(f=>f.endsWith('.css')&&f!=='tokens.css');
  const issues=[];
  for(const file of files){const tree=postcss.parse(await readFile(new URL(file,root),'utf8'));
    tree.walkDecls(d=>{if(d.parent.type==='atrule'&&d.parent.name==='font-face')return;
      if(/(?:#[\da-f]{3,8}|\b(?:rgba?|hsla?)\(|\b(?:white|black)\b|(?:\d|\.)+(?:px|rem|em|vh|vw|ms|s)\b)/i.test(d.value))issues.push(file+':'+d.prop+'='+d.value);
      if(d.prop==='font-family'&&d.value!=='inherit'&&!d.value.startsWith('var('))issues.push(file+': hard-coded font family');
    });
  }assert.deepEqual(issues,[]);
});
test('components cannot add inline styling or import page styles independently',async()=>{
  const issues=[];
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.jsx'))){const source=await readFile(new URL(file,root),'utf8');
    if(/\b(?:style|contentStyle|itemStyle)\s*=/.test(source))issues.push(file+': inline styles');
    const imports=[...source.matchAll(/import\s+["']([^"']+\.css)["']/g)].map(m=>m[1]);
    if(imports.some(value=>value!=='./design-system.css'))issues.push(file+': independent stylesheet');
  }assert.deepEqual(issues,[]);
});
test('chart appearance uses shared CSS variables rather than hard-coded paint',async()=>{
  for(const file of['main.jsx','scenario-chart.jsx','sales-demand.jsx','live-sources.jsx']){
    const source=await readFile(new URL(file,root),'utf8');assert.doesNotMatch(source,/(?:stroke|fill)=["']#/);
    assert.doesNotMatch(source,/tick=\{\{\s*fontSize/);
  }
});
test('Vrolen green comes from one primary colour token',async()=>{
  const tokens=await readFile(new URL('tokens.css',root),'utf8');assert.match(tokens,/--color-accent:\s*#5ee800/);
});
test('all shared CSS variable references have a definition',async()=>{
  const definitions=new Set(),references=new Set();
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.css'))){const source=await readFile(new URL(file,root),'utf8');
    postcss.parse(source).walkDecls(d=>{if(d.prop.startsWith('--'))definitions.add(d.prop);});
    for(const match of source.matchAll(/var\((--[a-z\d-]+)/g))references.add(match[1]);
  }assert.deepEqual([...references].filter(name=>!definitions.has(name)&&!name.startsWith('--radix-')),[]);
});
test('AI-first Home and new forecast are destinations, not a second assistant menu',async()=>{
  const source=await readFile(new URL('main.jsx',root),'utf8');
  const nav=source.slice(source.indexOf('const nav ='),source.indexOf('const METHOD_HELP'));
  assert.doesNotMatch(nav,/Assistant/);assert.match(source,/<AssistantWorkspace[^>]+home/);
  assert.doesNotMatch(source,/<footer className="app-footer">/);assert.doesNotMatch(source,/saved calculations/);
  assert.match(source,/\['help','Help',Question\]/);
});
test('new forecast exposes reviewed live factors without requiring a previously calculated run',async()=>{
  const source=await readFile(new URL('forecast-factors.jsx',root),'utf8');
  assert.match(source,/\/api\/datasets\//);assert.match(source,/forecast-factors/);
  assert.match(source,/review_token:review.review_token/);assert.match(source,/reviewed:true/);
  assert.match(source,/row.can_use===false/);assert.match(source,/review.missing>0/);
  const wizard=await readFile(new URL('new-forecast.jsx',root),'utf8');
  assert.match(wizard,/<ForecastFactors/);assert.match(wizard,/step===1&&\(!factorsReady/);
  assert.match(wizard,/chooseMethodsLater:true/);
});
test('authored translation calls always have a Persian catalogue entry',async()=>{
  const missing=[];
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.jsx'))){
    const source=await readFile(new URL(file,root),'utf8');
    for(const m of source.matchAll(/uiText\((["'])([^"']+)\1/g))if(!Object.hasOwn(fa,m[2]))missing.push(file+': '+m[2]);
  }
  assert.deepEqual(missing,[]);
});
test('completed calculations do not add unrelated banners to every destination',async()=>{
  const source=await readFile(new URL('main.jsx',root),'utf8');
  assert.match(source,/includeCompleted=\{page==='data'\|\|page==='today'\}/);
  assert.match(source,/includeCompleted=false/);
  assert.match(source,/includeCompleted&&Date.now/);
});
test('translation migration preserves status identifiers inside picker filters',async()=>{
 const source=`const test=<Pick options={plans.filter(p=>['approved','published'].includes(p.status)).map(p=>[p.id,p.name])}/>;`;
 assert.equal((await localizeSource(source)).source,source);
});
test('translations never alter equality checks or membership sets',async()=>{
 const issues=[];
 for(const file of(await readdir(root)).filter(f=>f.endsWith('.jsx'))){
  const ast=await parsers.babel.parse(await readFile(new URL(file,root),'utf8'));
  function walk(node,ancestors=[]){if(!node||typeof node!=='object')return;
   if(node.type==='CallExpression'&&node.callee?.name==='uiText'){
    const parent=ancestors.at(-1);
    if(parent?.type==='BinaryExpression'&&['===','!==','==','!='].includes(parent.operator))issues.push(file+': equality');
    if(parent?.type==='ArrayExpression'&&ancestors.some(p=>p.type==='CallExpression'&&['includes','indexOf'].includes(p.callee?.property?.name)))issues.push(file+': membership');
   }
   for(const[key,value]of Object.entries(node)){if(['loc','comments','tokens','extra'].includes(key))continue;
    if(Array.isArray(value)){for(const child of value)if(child?.type)walk(child,[...ancestors,node]);}
    else if(value?.type)walk(value,[...ancestors,node]);
   }
  }walk(ast);
 }assert.deepEqual(issues,[]);
});
test('multiple methods are distinct engine requests, and started methods are not queued twice',()=>{
  const methods=['recommended','model:Last observed','model:Recent average'];
  assert.deepEqual(remainingMethods(methods,[{id:'a',method:methods[0]}]),methods.slice(1));
  assert.equal(new Set(FORECAST_CHOICES.map(([id])=>id)).size,FORECAST_CHOICES.length);
  assert.deepEqual(forecastInputs([{id:'normal',sources:{history:'a'}},{id:'scenario',sources:{history:'a'},scenario_provenance:{}},{id:'none'}]).map(d=>d.id),['normal']);
});
test('selectable individual methods exist in the real forecasting engine',async()=>{
  const engine=await readFile(new URL('../../app/forecast_engine.py',import.meta.url),'utf8');
  const names=new Set([...engine.matchAll(/ModelSpec\(\s*"([^"]+)"/g)].map(m=>m[1]));
  for(const[id]of FORECAST_CHOICES.filter(([id])=>id.startsWith('model:')))assert.ok(names.has(id.slice(6)),id);
});
test('forecast journey resumes only validated identifiers and never stores messages or secret values',()=>{
  const payload={source:'demo',step:3,methods:['model:Last observed'],jobs:[{id:'job',method:'model:Last observed',error:'private error',state:'succeeded'}]};
  const draft=readForecastDraft({getItem:key=>{assert.equal(key,FORECAST_DRAFT_KEY);return JSON.stringify(payload);}});
  assert.deepEqual(draft.jobs,[{id:'job',method:'model:Last observed',state:'loading'}]);
  for(const value of[null,{}, {...payload,methods:['invented']},{...payload,step:100},{...payload,jobs:[{id:123,method:'recommended'}]}])assert.equal(readForecastDraft({getItem:()=>JSON.stringify(value)}),null);
  assert.equal(readForecastDraft({getItem:()=>{throw Error('blocked');}}),null);
});
test('forecast drafts discard removed data but resume existing inputs',()=>{
  const payload={version:2,source:'old-data',step:2,methods:['recommended'],jobs:[]};
  const storage=value=>({getItem:()=>JSON.stringify(value)});
  assert.equal(readForecastDraft(storage(payload),['new-data']),null);
  assert.equal(readForecastDraft(storage(payload),[]),null);
  assert.equal(readForecastDraft(storage({...payload,source:''}),['new-data']),null);
  assert.equal(readForecastDraft(storage({...payload,source:'new-data'}),['new-data']).step,2);
  assert.equal(readForecastDraft(storage({...payload,source:'',step:0}),['new-data']).step,0);
});
test('forecast choices and their descriptions have Persian translations',()=>{
  for(const [,title,description]of FORECAST_CHOICES){assert.ok(fa[title],title);assert.ok(fa[description],description);}
  for(const key of['New forecast','Approvals','Choose one or more methods','Run selected methods','Settings sections','View forecast'])assert.ok(fa[key],key);
});
test('new forecasts review customer orders before models and open combined results',async()=>{
  const source=await readFile(new URL('new-forecast.jsx',root),'utf8');
  assert.match(source,/\['Sales data','Factors','Customers & orders','Methods','Results'\]/);
  assert.match(source,/<ForecastOrders/);assert.match(source,/sales_input_id:salesInputId/);
  assert.match(source,/run.demand_summary/);
  assert.doesNotMatch(source,/Current orders are reviewed on the result page/);
  assert.match(source,/whatIf\|\|hasFactors/);
});
test('resumed model selection cannot bypass customer order review',()=>{
  const base={version:2,source:'history',step:3,methods:['recommended'],jobs:[]};
  assert.equal(readForecastDraft({getItem:()=>JSON.stringify(base)}).step,2);
  const saved=readForecastDraft({getItem:()=>JSON.stringify({...base,salesInputId:'a'.repeat(32),customer:'Customer 001'})});
  assert.equal(saved.step,3);assert.equal(saved.customer,'Customer 001');
  assert.equal(saved.salesInputId,'a'.repeat(32));
});
test('result summaries use only the portfolio estimate and never count each product twice',()=>{
  const result={unit:'tonnes',series:{__all__:{forecast:[{mean:10},{mean:20}]},SKU1:{forecast:[{mean:10},{mean:20}]}}};
  assert.deepEqual(forecastSummary(result),{total:30,periods:2,unit:'tonnes'});
  assert.equal(forecastSummary({forecast:[{mean:null}]}),null);assert.equal(forecastSummary({forecast:[]}),null);
});

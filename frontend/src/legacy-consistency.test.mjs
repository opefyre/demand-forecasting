import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let compiler,RangeCheck,ActualResults,locale;
before(async()=>{
  compiler=await createServer({configFile:false,root:process.cwd(),server:{middlewareMode:true,hmr:false,ws:false,watch:null},appType:'custom',optimizeDeps:{noDiscovery:true,include:[]},cacheDir:'/private/tmp/demandlab-legacy-test-cache'});
  ({RangeCheck}=await compiler.ssrLoadModule('/src/range-check.jsx'));
  ({ActualResults}=await compiler.ssrLoadModule('/src/actuals.jsx'));
  locale=await compiler.ssrLoadModule('/src/localization.mjs');
});
after(async()=>{await locale?.changeInterfaceLanguage('en');await compiler?.close();});
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),
  Table:({headers,children})=>React.createElement('table',null,React.createElement('thead',null,React.createElement('tr',null,headers.map((header,index)=>React.createElement('th',{key:index},header)))),React.createElement('tbody',null,children)),
  Help:({text})=>React.createElement('button',{title:text},'?'),ErrorBox:()=>null};
const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,{ui,...props}));
test('range review is shared, fully bilingual and does not convert missing evidence to zero',async()=>{
  const check={items:{checked:10,inside:8,coverage_pct:80,unavailable:2},portfolio:{checked:0,inside:0,coverage_pct:null},
    fitting_separate_from_selection:true,missing_prediction_points:1,skipped_incomplete_portfolio_periods:1,
    by_horizon:[{step:1,checked:10,observations:12,coverage_pct:80,mean_width:4}]};
  const run={unit:'tonnes',metrics:{range_check:check}},original=structuredClone(run);
  for(const language of ['en','fa']){
    await locale.changeInterfaceLanguage(language);
    const html=render(RangeCheck,{run,fmt:value=>new Intl.NumberFormat(language).format(value)});
    assert.match(html,/ui-disclosure/);assert.match(html,/ui-definition-list/);assert.doesNotMatch(html,/style=|range-check|detail-body/);
    assert.ok(html.includes(locale.t('Not available')));assert.ok(html.includes(locale.unitLabel('tonnes')));
    if(language==='fa'){assert.match(html,/۸۰/);assert.doesNotMatch(html,/Did the range|More history|Not available|By forecast step|tonnes/);}
  }
  assert.deepEqual(run,original);
  assert.equal(render(RangeCheck,{run:{...run,metrics:{...run.metrics,evidence_policy:'reviewed_what_if'}},fmt:String}),'');
});
test('actual-results reader entry has no write action; planner entry stays disabled while loading',async()=>{
  await locale.changeInterfaceLanguage('fa');
  const props={run:{run_id:'fixture',unit:'tonnes'},api:()=>{throw Error('No API during static rendering');},fmt:String,date:String,embedded:true};
  const reader=render(ActualResults,{...props,canEdit:false});
  assert.doesNotMatch(reader,/Add actual|actual-results|actual-empty|style=/);assert.match(reader,/در حال/);
  const planner=render(ActualResults,{...props,canEdit:true});
  assert.match(planner,/<button disabled=""/);assert.ok(planner.includes(locale.t('Add actual results')));
  await locale.changeInterfaceLanguage('en');
});
test('actual-result operations use shared controls, fresh review and guarded writes',async()=>{
  const source=await readFile(new URL('./actuals.jsx',import.meta.url),'utf8');
  for(const component of ['Stack','Panel','Grid','Actions','FieldGroup','Disclosure','DefinitionList','Steps','DownloadLink'])assert.ok(source.includes('<'+component),component);
  assert.doesNotMatch(source,/className="(?:actual-|inventory-|field-grid|section-heading|view-toolbar|check-row|help-details)|style=/);
  assert.match(source,/setForm\(\{\.\.\.draft.form,reviewed:false,accept_partial:false\}\)/);
  assert.match(source,/submitting.current\|\|busy\|\|!canEdit\|\|!review/);
  assert.match(source,/canEdit&&importNew&&<Actions>/);
  assert.match(source,/salesSeriesLabel\(run,r.key\)/);
  await locale.changeInterfaceLanguage('fa');
  for(const label of ['Choose file','Match and confirm','Review results'])assert.notEqual(locale.t(label),label);
  await locale.changeInterfaceLanguage('en');
  const demand=await readFile(new URL('./sales-demand.jsx',import.meta.url),'utf8');
  assert.match(demand,/dismissible=\{!actualsBusy\}/);assert.match(demand,/onWorkingChange=\{setActualsBusy\}/);
});
test('old calculation pages cannot reintroduce competing layout rules',async()=>{
  const source=await readFile(new URL('./main.jsx',import.meta.url),'utf8');
  const details=source.slice(source.indexOf('function ForecastPage('),source.indexOf('function AdvancedScenarios('));
  assert.match(details,/<DefinitionList/);assert.match(details,/<Panel/);assert.match(details,/<Disclosure/);
  assert.doesNotMatch(details,/className="(?:forecast-toolbar|run-select|chart-surface|forecast-stats|accuracy-summary|methods-table|plan-comparison-control|forecast-method-note)/);
  assert.match(details,/importNew=\{importNew\}\s+canEdit=\{canEdit\}/);
  const css=await readFile(new URL('./workspace.css',import.meta.url),'utf8');
  assert.doesNotMatch(css,/\.(?:actual-(?:empty|evidence|import)|range-check|accuracy-summary|forecast-stats|chart-surface|methods-table|forecast-toolbar|forecast-evidence|plan-comparison-control|forecast-method-note|run-select)\b/);
});

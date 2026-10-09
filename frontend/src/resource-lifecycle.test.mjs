import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {forecastInputs,readForecastDraft,FORECAST_DRAFT_KEY} from './forecast-start.mjs';
import {forecastGroups} from './forecast-groups.mjs';
import {fa} from './locales/fa.mjs';

test('dynamic lifecycle menu labels have Persian translations too',()=>{
  for(const key of ['Rename','Archive / restore','Versions','Create revision','Restore','Archive','Archived','Active'])assert.ok(fa[key],key);
});

test('archived history is available to review, never offered for new forecasts',()=>{
  const active={id:'active',sources:{history:'one'}},archived={id:'old',sources:{history:'two'},lifecycle:{archived:true}};
  assert.deepEqual(forecastInputs([active,archived]),[active]);
});
test('a forecast revision link survives resuming the company-separated wizard draft',()=>{
  const value={version:2,source:'input',step:1,methods:['recommended'],jobs:[],parentForecastId:'a'.repeat(32)};
  assert.equal(readForecastDraft({getItem:key=>key===FORECAST_DRAFT_KEY?JSON.stringify(value):null},['input']).parentForecastId,value.parentForecastId);
  assert.equal(readForecastDraft({getItem:()=>JSON.stringify({...value,parentForecastId:'../other-company'})}).parentForecastId,null);
});
test('all selected models share the renamed forecast rather than becoming separate items',()=>{
  const runs=['one','two'].map((run_id,i)=>({run_id,forecast_group_id:'group',forecast_name:'Tehran October',method_selection:'model'+i,lifecycle:{archived:true}}));
  const groups=forecastGroups(runs);assert.equal(groups.length,1);assert.equal(groups[0].name,'Tehran October');assert.equal(groups[0].runs.length,2);
});
test('inputs and forecasts reuse one framework menu/dialog without page-specific or inline styles',async()=>{
  const source=await readFile(new URL('resource-lifecycle.jsx',import.meta.url),'utf8');
  assert.match(source,/DropdownMenu/);assert.match(source,/className="ui-menu"/);assert.match(source,/<Modal open=\{!!dialog\} fixed/);
  assert.match(source,/<Stack>/);assert.match(source,/<Actions>/);assert.match(source,/<Table headers=/);
  assert.doesNotMatch(source,/style=|\.css['"]|localStorage|company_id/);
  for(const file of ['sales-files.jsx','sales-demand.jsx'])assert.match(await readFile(new URL(file,import.meta.url),'utf8'),/<ResourceMenu/);
});
test('metadata edits use optimistic versions and archived items remain visible by explicit choice',async()=>{
  const source=await readFile(new URL('resource-lifecycle.jsx',import.meta.url),'utf8');
  assert.match(source,/version:record.lifecycle.version/);assert.match(source,/'PATCH':'POST'/);
  assert.match(source,/archived\?'\/restore':'\/archive'/);
  const main=await readFile(new URL('main.jsx',import.meta.url),'utf8');assert.match(main,/include_archived=true/);
});

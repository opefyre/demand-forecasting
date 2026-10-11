import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {forecastSettingsDraft,forecastFactorDraft,forecastOrderDraft,readForecastDraft} from './forecast-start.mjs';

const selected={id:'factor-1',lag:'2',value:'85',monthly:true,monthlyValues:{'2026-11-01':'90'},timingAccepted:true,calendarAccepted:false,review_token:'must-not-restore'};
const factorDraft={datasetId:'history',expanded:'factor-1',selected:[selected]};
test('restore settings and factor assumptions, but never restore a review approval',()=>{
  const settings={horizon:6,month_basis:'jalali',calendar_country:'IR'};
  const value={version:2,source:'history',step:3,methods:['recommended'],jobs:[],salesInputId:'a'.repeat(32),settings,factorDraft};
  const restored=readForecastDraft({getItem:()=>JSON.stringify(value)},['history']);
  assert.deepEqual(restored.settings,settings);assert.equal(restored.step,1);
  assert.equal(restored.factorDraft.selected[0].value,'85');
  assert.deepEqual(restored.factorDraft.selected[0].monthlyValues,{'2026-11-01':'90'});
  assert.equal('review_token' in restored.factorDraft.selected[0],false);
  assert.equal('approved' in restored.factorDraft,false);
});
test('drafts stay bound to their sales history and reject invalid or excessive settings',()=>{
  assert.equal(forecastFactorDraft(factorDraft,'other-company-history'),null);
  assert.equal(forecastFactorDraft({...factorDraft,selected:[selected,selected]},'history'),null);
  assert.equal(forecastFactorDraft({...factorDraft,selected:[{...selected,lag:'0'}]},'history'),null);
  for(const horizon of [0,25,1.5,NaN])assert.equal(forecastSettingsDraft({horizon,month_basis:'gregorian',calendar_country:'IR'}),null);
  assert.equal(forecastSettingsDraft({horizon:6,month_basis:'invented',calendar_country:'IR'}),null);
  assert.equal(forecastSettingsDraft({horizon:6,month_basis:'gregorian',calendar_country:'unknown'}),null);
});
test('the shared wizard owns drafts, rechecks factors and never dereferences unavailable options',async()=>{
  const wizard=await readFile(new URL('new-forecast.jsx',import.meta.url),'utf8');
  assert.match(wizard,/initialDraft=\{factorDraft\} onDraftChange=\{setFactorDraft\}/);
  assert.match(wizard,/name,settings,factorDraft,orderDraft,parentForecastId/);
  const factors=await readFile(new URL('forecast-factors.jsx',import.meta.url),'utf8');
  assert.match(factors,/onReady\(!selected.length\)/);
  assert.match(factors,/options&&!!selected.length/);
  assert.match(factors,/onReload=\{/);
  assert.match(factors,/snapshot.can_use!==false/);
  assert.doesNotMatch(factors,/\.filter\(row=>row.live_what_if\|\|row.public_vintage\)/);
  assert.doesNotMatch(factors,/style=/);
  assert.match(wizard,/!dataset\|\|!monthlyInputs\|\|!name.trim/);
  assert.doesNotMatch(wizard,/You can still forecast this history without extra live factors/);
  const orders=await readFile(new URL('forecast-orders.jsx',import.meta.url),'utf8');
  assert.match(orders,/restored.bookVersion===data.version/);
  assert.match(orders,/restored\?\.inputs.run_id===data.context.run_id/);
});
test('orders remain editable across navigation but cannot restore approval or another input context',()=>{
  const value={datasetId:'history',bookVersion:2,inputs:{run_id:'context',customers:[{customer:'Mehr',sku:'001',unit:'tonnes'}],orders:[{reference:'Mehr-001',ordered:'25'}],commitments:[],reviewed:true,review_token:'not-proof'},imports:{},reuse:''};
  const restored=forecastOrderDraft(value,'history');
  assert.equal(restored.inputs.reviewed,false);
  assert.equal('review_token' in restored.inputs,false);
  assert.equal(restored.inputs.orders[0].ordered,'25');
  assert.equal(restored.bookVersion,2);
  assert.equal(forecastOrderDraft({...value,bookVersion:-1},'history'),null);
  assert.equal(forecastOrderDraft(value,'different-history'),null);
  assert.equal(forecastOrderDraft({...value,inputs:{...value.inputs,orders:null}},'history'),null);
});

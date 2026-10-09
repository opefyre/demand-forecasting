import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {preparedSelection} from './factor-preparation.mjs';
let server,Results;
before(async()=>{server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});({PreparationResults:Results}=await server.ssrLoadModule('/src/factor-preparation.jsx'));});
after(async()=>{await server?.close();});
const report={context:{materials:['aluminum']},review_token:'evidence',recommendations:[
  {factor_id:'aluminum',snapshot_id:'a',name:'Aluminum',can_prepare:true,what_if:true,method:'model:Ridge + drivers',lag_months:2,note:'Review 2 future assumptions.',reason:'Selected material.',history_months:24,history_missing:0},
  {factor_id:'fx',snapshot_id:'b',name:'Exchange rate',can_prepare:false,note:'24 months missing.',reason:'Declared exposure.',history_months:24,history_missing:24}]};
test('prepared sources never accept timing or invent future values',()=>{
  const selected=preparedSelection(report,['a']);assert.equal(selected.method,'model:Ridge + drivers');
  assert.deepEqual(selected.factors[0].monthlyValues,{});assert.equal(selected.factors[0].timingAccepted,false);
  assert.deepEqual(selected.preparation.snapshot_ids,['a']);assert.equal(selected.preparation.review_token,'evidence');
});
test('unavailable duplicates empty and excessive source selections cannot prepare',()=>{
  for(const ids of [[],['b'],['a','a'],Array.from({length:9},(_,i)=>String(i))])assert.throws(()=>preparedSelection(report,ids));
  const archived={...report,recommendations:[{...report.recommendations[0],what_if:false}]};
  assert.equal(preparedSelection(archived,['a']).method,'factor_test');
});
test('saved profiles keep their exact series and revision-bound evidence without accepting timing',()=>{
  const result=preparedSelection({...report,series_ids:['customer-product'],profile:{series_id:'customer-product',revision:2}},['a']);
  assert.deepEqual(result.seriesIds,['customer-product']);assert.equal(result.preparation.profile_series_id,'customer-product');
  assert.deepEqual(result.factors[0].monthlyValues,{});assert.equal(result.factors[0].timingAccepted,false);
});
test('source status and limitations remain visible; missing is not zero',()=>{
  const html=renderToStaticMarkup(React.createElement(Results,{report,selected:[],onSelect(){},ui:{}}));
  assert.match(html,/What-if only/);assert.match(html,/24 months missing/);assert.match(html,/24 of 24/);
  assert.match(html,/disabled/);assert.match(html,/not proof of better accuracy/);
});

import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let server,Component;
before(async()=>{server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});({FactorEvaluation:Component}=await server.ssrLoadModule('/src/factor-evaluation.jsx'));});
after(async()=>{await server?.close();});
const ui={Table:({children})=>React.createElement('table',null,React.createElement('tbody',null,children))};
const run={unit:'tonnes',metadata:{A:{customer:'Customer A',sku:'0001'},B:{customer:'Customer B',sku:'0002'}},
  factor_evaluation:{minimum_gain_pct:5,note:'Not a future accuracy guarantee.',search:'Each factor and the combined set.',selection_periods:['2025-01-01'],confirmation_periods:['2025-02-01'],
    rows:[{item_id:'A',selected_factors:['fx'],reason:'Earlier tests improved.',decision:'factors_selected',selection_gain_pct:15,
      confirmation_baseline:{mae:10},confirmation_selected:{mae:12},confirmation_improved:false,confirmation_points:6},
      {item_id:'B',selected_factors:[],reason:'No useful improvement.',decision:'history_only',confirmation_baseline:null,confirmation_selected:null,confirmation_points:0}]}};
test('factor choices are scoped and distinguish selection gain from a worse final check',()=>{
  const html=renderToStaticMarkup(React.createElement(Component,{run,ui,customer:'Customer A'}));
  assert.match(html,/0001/);assert.match(html,/15% less error/);assert.match(html,/10 → 12 tonnes/);assert.match(html,/No improvement/);
  assert.doesNotMatch(html,/Customer B/);assert.match(html,/not a statistical guarantee/);
});
test('missing final evidence is not a zero error and unrelated forecasts add no panel',()=>{
  const html=renderToStaticMarkup(React.createElement(Component,{run,ui,sku:'0002'}));
  assert.match(html,/Not enough separate history/);assert.match(html,/History &amp; seasonality only/);
  assert.equal(renderToStaticMarkup(React.createElement(Component,{run:{},ui})),'');
});

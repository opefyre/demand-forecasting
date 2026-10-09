import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

let server,Progress,Comparison,Exports;
before(async()=>{server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
  ({UpdateProgress:Progress,UpdateComparison:Comparison,UpdateExports:Exports}=await server.ssrLoadModule('/src/monthly-refresh.jsx'));
});
after(async()=>{await server?.close();});
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),
  Table:({headers,children})=>React.createElement('table',null,React.createElement('tbody',null,children)),
  Pick:({label,options,...props})=>React.createElement('select',{'aria-label':label,...props},options.map(([value,name])=>React.createElement('option',{key:value,value},name)))};

test('progress shows one current step; calculation is not completed just because viewed',()=>{
  const html=renderToStaticMarkup(React.createElement(Progress,{stage:'calculating'}));
  assert.equal((html.match(/aria-current="step"/g)||[]).length,1);
  assert.match(html,/aria-current="step"[^>]*>.*?Forecast/);assert.match(html,/Orders/);assert.doesNotMatch(html,/Production|Inventory/);
});
test('comparison preserves absence, exact Persian months and excludes deliveries from planning',()=>{
  const report={month_basis:'jalali',unit:'tonnes',overlap_before:10,overlap_after:14,added_rows:1,removed_rows:1,
    rows:[{customer:'A',sku:'0001',period:'2026-03-21',change:'added',before_forecast:null,after_forecast:14,after_open_orders:6,after_to_serve:12}],
    orders_note:'Earlier orders are reference only.',warnings:[],as_of:'2026-03-21',valid_until:'2026-04-01'};
  const html=renderToStaticMarkup(React.createElement(Comparison,{report,ui}));
  assert.match(html,/1405-01/);assert.match(html,/0001/);assert.match(html,/Not present/);
  assert.match(html,/matching months only/);assert.match(html,/exclude deliveries/);assert.match(html,/aria-label="Find changed customer, product or month"/);
});
test('export asks whether receiver has orders before generating links',()=>{
  const html=renderToStaticMarkup(React.createElement(Exports,{sessionId:'version',ui}));
  assert.match(html,/already have these customer orders/);assert.doesNotMatch(html,/href=/);
  assert.doesNotMatch(html,/Approved|sent to/);
});

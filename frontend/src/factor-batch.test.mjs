import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let server,GroupTable,Evidence;
before(async()=>{server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
  ({BatchGroupTable:GroupTable,BatchEvidence:Evidence}=await server.ssrLoadModule('/src/factor-batch.jsx'));});
after(async()=>{await server?.close();});
const ui={Table:({headers,children})=>React.createElement('table',null,React.createElement('thead',null,
  React.createElement('tr',null,headers.map((h,i)=>React.createElement('th',{key:i},h)))),React.createElement('tbody',null,children))};
const run={metadata:{a:{customer:'Customer A',sku:'0001'},b:{customer:'Customer B',sku:'0002'}}};
const alignment={series_ids:['a'],method:'model:Ridge + drivers',factors:[{factor:'Iran exchange rate'}]};
const groups=[{id:'g',scenario_provenance:{alignment}}];
test('batch group review identifies exact customer/product, source and method',()=>{
  const html=renderToStaticMarkup(React.createElement(GroupTable,{groups,run,ui,onEdit(){},onRemove(){}}));
  assert.match(html,/Customer A.*?0001/);assert.match(html,/Iran exchange rate/);assert.match(html,/Ridge \+ drivers/);
  assert.match(html,/aria-label="Edit factors for a"/);assert.match(html,/Keep baseline instead/);assert.doesNotMatch(html,/Customer B|Customer A.*?0002/);
});
test('readonly batch evidence has no edit actions or combined accuracy promise',()=>{
  const scenario={type:'factor_batch',alignment:{groups:[{dataset_id:'g',alignment}],unchanged_series_ids:['b']}};
  const html=renderToStaticMarkup(React.createElement(Evidence,{scenario,run,ui}));
  assert.match(html,/1 other products retain their baseline/);assert.match(html,/No combined accuracy score/);
  assert.doesNotMatch(html,/Edit factors|Remove group|Calculate|approved/);
});
test('automatic factor testing is plainly named and unrelated scenarios show no batch panel',()=>{
  const html=renderToStaticMarkup(React.createElement(GroupTable,{groups:[{id:'g',scenario_provenance:{alignment:{...alignment,method:'factor_test'}}}],run,ui}));
  assert.match(html,/Test factors/);assert.doesNotMatch(html,/factor_test/);
  assert.equal(renderToStaticMarkup(React.createElement(Evidence,{scenario:{type:'factor_link'},run,ui})), '');
});

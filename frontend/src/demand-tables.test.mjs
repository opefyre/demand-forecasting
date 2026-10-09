import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
const bundle=await build({entryPoints:[new URL('./demand-tables.jsx',import.meta.url).pathname],bundle:true,write:false,platform:'node',format:'cjs',external:['react']});
const module={exports:{}};
new Function('require','module','exports',bundle.outputFiles[0].text)(createRequire(import.meta.url),module,module.exports);
const {PivotTable,CoverageTable}=module.exports;
const customerBundle=await build({entryPoints:[new URL('./customers.jsx',import.meta.url).pathname],bundle:true,write:false,platform:'node',format:'cjs',external:['react','@phosphor-icons/react']});
const customerModule={exports:{}};
// The read-only table has no icons; avoid loading the icon package's CJS barrel.
new Function('require','module','exports',customerBundle.outputFiles[0].text)(name=>name==='@phosphor-icons/react'?{}:createRequire(import.meta.url)(name),customerModule,customerModule.exports);
// Match the existing Table contract: any truthy `empty` replaces its children.
const ui={Table:({children,empty})=>React.createElement('table',null,React.createElement('tbody',null,empty?React.createElement('tr',null,React.createElement('td',null,empty)):children)),Button:()=>null};
const rows=[{customer:'Customer A',sku:'Product P',unit:'kg',period:'2026-10-01',total:16,remaining:0,booked:16,fulfilled:0,status:'Covered by orders',issue:''}];
test('pivot actually renders its populated rows, not the empty message',()=>{
 const html=renderToStaticMarkup(React.createElement(PivotTable,{rows,ui}));
 assert.match(html,/Customer A/);assert.match(html,/Product P/);assert.match(html,/16/);assert.doesNotMatch(html,/No results/);
});
test('coverage actually renders populated rows and a meaningful empty state',()=>{
 const html=renderToStaticMarkup(React.createElement(CoverageTable,{rows,ui}));assert.match(html,/Covered by orders/);assert.match(html,/Customer A/);
 assert.match(renderToStaticMarkup(React.createElement(CoverageTable,{rows:[],ui})),/No results/);
});
test('saved customer directory records remain visible',()=>{
 const html=renderToStaticMarkup(React.createElement(customerModule.exports.CustomerList,{customers:[{id:'1',customer:'Tehran buyer',active:true,products:[{sku:'P1',unit:'tonnes'}]}],ui}));
 assert.match(html,/Tehran buyer/);assert.match(html,/P1/);assert.doesNotMatch(html,/No customers/);
});

import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {reviewedOrderRequest} from './order-update-state.mjs';
let server,Receipt,OrderTable,OrderChanges,language;
before(async()=>{
 server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
 ({OrderDemandReceipt:Receipt}=await server.ssrLoadModule('/src/forecast-orders.jsx'));
 ({OrderTable}=await server.ssrLoadModule('/src/order-books.jsx'));
 ({OrderChanges}=await server.ssrLoadModule('/src/order-changes.jsx'));
 ({i18n:language}=await server.ssrLoadModule('/src/localization.mjs'));
});
after(async()=>{await language?.changeLanguage('en');await server?.close();});
const ui={Table:({headers,children})=>React.createElement('table',null,React.createElement('thead',null,React.createElement('tr',null,headers.map((label,index)=>React.createElement('th',{key:index},label)))),React.createElement('tbody',null,children))};
test('review request preserves complete inputs, original revision, connected-source guard and import evidence',()=>{
 const inputs={run_id:'runA',customers:[{customer:'Mehr',sku:'001',unit:'tonnes'}],orders:[{reference:'ORD-01',ordered:30,fulfilled:2,cancelled:1}],commitments:[{quantity:40}],as_of:'2026-10-10',valid_until:'2026-11-10',order_feed:'complete_snapshot',reviewed:false};
 const initial={base_snapshot_id:'v1',order_refresh_source:{id:'source',sha:'evidence'}},imports={orders:{source_id:'file',mapping:{ordered:'QTY'}}};
 const before=structuredClone(inputs);
 const payload=reviewedOrderRequest(initial,inputs,imports,'requestA','changes');
 assert.equal(payload.base_snapshot_id,'v1');assert.deepEqual(payload.order_refresh_source,initial.order_refresh_source);
 assert.deepEqual(payload.imports,imports);assert.equal(payload.order_mode,'changes');assert.equal(payload.request_id,'requestA');assert.equal(payload.inputs.reviewed,true);
 for(const key of ['customers','orders','commitments','as_of','valid_until','order_feed'])assert.deepEqual(payload.inputs[key],inputs[key]);
 assert.deepEqual(inputs,before);
 assert.equal(reviewedOrderRequest(null,inputs,{},'new').order_mode,'replace');
 assert.equal('order_refresh_source' in reviewedOrderRequest(null,inputs,{},'new'),false);
});
test('receipt preserves unknown quantities and review conflicts; rows are paginated without changing inputs',async()=>{
 await language.changeLanguage('en');
 const row={customer:'Mehr',sku:'001',period:'2026-11-01',unit:'tonnes',baseline:12,booked:28,fulfilled:2,remaining:null,total:null,status:'Orders unknown',issue:'Order source is unknown or expired.'};
 const review={rows:Array.from({length:26},(_,index)=>({...row,customer:index===25?'Last customer':'Mehr'}))};
 const original=structuredClone(review);
 const render=page=>renderToStaticMarkup(React.createElement(Receipt,{ui,review,basis:'gregorian',page}));
 const html=render(0);assert.match(html,/Unknown/);assert.match(html,/Orders unknown/);assert.match(html,/expired/);assert.doesNotMatch(html,/Last customer|style=/);
 assert.match(render(1),/Last customer/);assert.equal((render(1).match(/<td>Last customer/g)||[]).length,1);assert.deepEqual(review,original);
 await language.changeLanguage('fa');
 const fa=render(1);assert.match(fa,/۲۸/);assert.match(fa,/نامشخص/);assert.match(fa,/تن/);assert.match(fa,/<bdi>/);assert.doesNotMatch(fa,/tonnes|Unknown|Orders unknown/);
});
test('shared order rows localize quantities and keep identifier/date direction explicit',async()=>{
 await language.changeLanguage('fa');
 const html=renderToStaticMarkup(React.createElement(OrderTable,{ui,inputs:{orders:[{reference:'ORD-01',customer:'Mehr',sku:'001',due_date:'2026-11-01',ordered:30,fulfilled:2,cancelled:1,status:'confirmed',unit:'tonnes'}]}}));
 assert.match(html,/۳۰/);assert.match(html,/<bdi>2026-11-01/);assert.doesNotMatch(html,/tonnes|style=/);await language.changeLanguage('en');
});
test('changed/removed order evidence uses the shared disclosure and preserves exact quantities',async()=>{
 await language.changeLanguage('fa');
 const before={customer:'Mehr',sku:'001',unit:'tonnes',ordered:'16',fulfilled:'2',cancelled:'0',due_date:'2026-11-01',status:'confirmed'};
 const changes=[{reference:'ORD-01',before,after:{...before,ordered:'30'}},{reference:'ORD-02',before,after:null}];
 const html=renderToStaticMarkup(React.createElement(OrderChanges,{ui,changes}));
 assert.match(html,/ui-disclosure/);assert.match(html,/۱۶ تن/);assert.match(html,/۳۰ تن/);assert.match(html,/ORD-02/);assert.match(html,/—/);assert.doesNotMatch(html,/style=|tonnes|Confirmed|ordered/);
 assert.equal(changes[0].before.ordered,'16');await language.changeLanguage('en');
});
test('manual and assistant order updates reuse one fixed dialog while keeping their workspaces mounted',async()=>{
 const modal=await readFile(new URL('order-update.jsx',import.meta.url),'utf8');
 assert.match(modal,/Modal open fixed wide/);assert.match(modal,/dismissible=\{!busy\}/);assert.match(modal,/<ForecastOrders/);assert.doesNotMatch(modal,/style=|className=/);
 for(const file of ['sales-demand.jsx','assistant-workspace.jsx']){
  const source=await readFile(new URL(file,import.meta.url),'utf8');assert.match(source,/<OrderUpdate/);assert.doesNotMatch(source,/return <DemandImport|return< DemandImport/);
 }
 const editor=await readFile(new URL('forecast-orders.jsx',import.meta.url),'utf8');
 assert.match(editor,/review_token:review.review_token/);assert.match(editor,/submitting.current\|\|!canEdit/);assert.match(editor,/editingOrder\|\|!checked/);assert.match(editor,/Complete monthly commitments/);assert.doesNotMatch(editor,/style=/);
});
test('saved-order reuse cannot replace inputs during validation or for a read-only actor',async()=>{
 const editor=await readFile(new URL('forecast-orders.jsx',import.meta.url),'utf8');
 assert.match(editor,/async function useSaved\(id\)\{if\(!id\|\|busy\|\|!canEdit\|\|Object.values\(reading\).some\(Boolean\)\)return/);
 assert.match(editor,/<Pick label=\{uiText\('Reuse saved orders'\)\} disabled=\{blocked\}/);
});

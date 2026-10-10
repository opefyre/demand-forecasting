import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import postcss from 'postcss';

let server,Collection,ConnectionRecord,SalesFiles,Customers,OrderBooks,OrderRows,OrderReview,OrderTable,LiveSources,FolderInputs,InputConnections,ConnectionRowReview,reviewPayload,appendOrder;
before(async()=>{
  server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
  ({Collection,ConnectionRecord}=await server.ssrLoadModule('/src/ui-layout.jsx'));
  ({SalesFiles}=await server.ssrLoadModule('/src/sales-files.jsx'));
  ({Customers}=await server.ssrLoadModule('/src/customers.jsx'));
  ({OrderBooks,OrderRows,OrderReview,OrderTable,appendOrder}=await server.ssrLoadModule('/src/order-books.jsx'));
  ({LiveSources}=await server.ssrLoadModule('/src/live-sources.jsx'));
  ({FolderInputs}=await server.ssrLoadModule('/src/folder-inputs.jsx'));
  ({InputConnections}=await server.ssrLoadModule('/src/business-connections.jsx'));
  ({ConnectionRowReview,reviewPayload}=await server.ssrLoadModule('/src/connection-review.jsx'));
});
after(async()=>await server?.close());
const ui={
  Button:({children,kind,...props})=>React.createElement('button',props,children),
  Pick:({label,disabled})=>React.createElement('button',{'aria-label':label,disabled}),
  Field:({title,children})=>React.createElement('label',null,title,children),
  ErrorBox:()=>null,Modal:()=>null,Help:()=>null,
  Table:({headers,children,empty})=>React.createElement('table',null,React.createElement('thead',null,React.createElement('tr',null,headers.map((h,i)=>React.createElement('th',{key:i},h)))),React.createElement('tbody',null,empty?React.createElement('tr',null,React.createElement('td',{colSpan:headers.length},empty)):children)),
};
const common={api:async()=>({}),ui,datasets:[],canAdmin:true,canEdit:true,embedded:true,date:String,fmt:String,search:'',onSearch:()=>{}};
test('customer imports send no order dates; order imports preserve explicit dates',()=>{
  assert.deepEqual(reviewPayload({mapping:{customer:'A'},as_of:'',valid_until:''}),{mapping:{customer:'A'},as_of:null,valid_until:null});
  assert.deepEqual(reviewPayload({as_of:'2026-10-09',valid_until:'2026-11-01'}),{as_of:'2026-10-09',valid_until:'2026-11-01'});
});
test('View orders opens the imported dataset, not an unrelated first order book',()=>{
  const datasets=[{id:'first',name:'First sales',sources:{history:'one'}},{id:'imported',name:'Imported sales',sources:{history:'two'}}];
  const reviewUi={...ui,Pick:({label,value})=>React.createElement('button',{'aria-label':label,'data-value':value})};
  for(const [preferred,expected] of [['imported','imported'],['foreign','first']]){
    const html=renderToStaticMarkup(React.createElement(OrderBooks,{...common,ui:reviewUi,datasets,initialDatasetId:preferred}));
    assert.match(html,new RegExp('data-value="'+expected+'"'));
  }
});
test('connected customer/order reviews reuse the fixed dialog and shared layout without inline styles',()=>{
  const reviewUi={...ui,Modal:({title,open,fixed,children})=>React.createElement('section',{'aria-label':title,'data-fixed':String(fixed)},children)};
  for(const role of ['sales_customers','sales_orders']){
    const candidate={id:'capture',role,source_id:'source',source:{preview:{columns:[{id:'A',label:'customer'}]}}};
    const html=renderToStaticMarkup(React.createElement(ConnectionRowReview,{candidate,api:common.api,ui:reviewUi,onClose:()=>{},onSaved:()=>{}}));
    assert.match(html,/data-fixed="true"/);assert.match(html,/ui-stack/);assert.match(html,/ui-grid/);
    assert.match(html,/aria-label="Customer"/);assert.match(html,/Review rows/);assert.doesNotMatch(html,/style=/);
    if(role==='sales_orders'){assert.equal((html.match(/type="date"/g)||[]).length,2);assert.match(html,/Order update/);assert.doesNotMatch(html,/type="checkbox"/);}
    else assert.doesNotMatch(html,/Order update|type="date"/);
  }
});
test('connection reviews refresh mapping after a worksheet/header change and scope every request',async()=>{
  const source=await readFile(new URL('connection-review.jsx',import.meta.url),'utf8');
  assert.match(source,/columnsCurrent=form\.sheet===loadedSpec\.sheet&&form\.header_row===loadedSpec\.header_row/);
  assert.match(source,/disabled=\{busy\|\|!columnsCurrent/);
  assert.match(source,/\/api\/v1\/sources\//);assert.match(source,/\/api\/v1\/connections\/imports\//);
  assert.doesNotMatch(source,/style=|\/api\/customers|\/api\/orders/);
});
test('all five Data tabs render one shared toolbar/controls/actions/body structure',()=>{
  for(const Component of[SalesFiles,Customers,OrderBooks,LiveSources,FolderInputs,InputConnections]){
    const html=renderToStaticMarkup(React.createElement(Component,common));
    assert.equal((html.match(/class="ui-collection"/g)||[]).length,1,Component.name);
    assert.ok(html.indexOf('ui-collection-controls')<html.indexOf('ui-actions'),Component.name);
    assert.ok(html.indexOf('ui-actions')<html.indexOf('ui-collection-body'),Component.name);
    assert.match(html,/<div class="ui-collection-body"><div class="ui-stack">/,Component.name);
    assert.doesNotMatch(html,/style=|customer-workspace|live-source-row|settings-section|compact-toolbar|section-heading/,Component.name);
  }
});
test('all record-list tabs use the same table component, including empty/loading states',()=>{
  for(const Component of[SalesFiles,Customers,OrderBooks,LiveSources,FolderInputs,InputConnections]){
    const html=renderToStaticMarkup(React.createElement(Component,common));
    assert.match(html,/<table>/,Component.name);assert.match(html,/<thead>/,Component.name);
    assert.match(html,/<tbody>/,Component.name);
  }
});
test('files show period/product counts and the real review action without duplicate headings',()=>{
  const html=renderToStaticMarkup(React.createElement(SalesFiles,{...common,datasets:[{id:'d1',name:'October sales',review:{summary:{start:'2026-01-01',end:'2026-07-31',series:12}}}],actions:'Import data',onReview:()=>{}}));
  assert.match(html,/October sales/);assert.match(html,/2026-01-01/);assert.match(html,/2026-07-31/);
  assert.match(html,/>12</);assert.match(html,/Review data/);assert.doesNotMatch(html,/<h[123]|Start with your historical data/);
});
test('read-only Data views never expose create/save actions',()=>{
  for(const Component of[Customers,OrderBooks,FolderInputs,InputConnections]){
    const html=renderToStaticMarkup(React.createElement(Component,{...common,canEdit:false,canAdmin:false}));
    assert.doesNotMatch(html,/Add customer|Add order|Save orders|Connect folder|Add connection/,Component.name);
  }
});
test('Collection supports different controls without changing its structural contract',()=>{
  const html=renderToStaticMarkup(React.createElement(Collection,{label:'Orders',controls:'Dataset picker',actions:'Save'},'Order inputs'));
  assert.match(html,/aria-label="Orders"/);assert.ok(html.indexOf('Dataset picker')<html.indexOf('Save'));
  assert.ok(html.indexOf('Save')<html.indexOf('Order inputs'));
});
test('live feeds and context sources share one tokenized connection row',async()=>{
  const Icon=()=>React.createElement('svg');
  for(const category of['Monthly market data','Annual context','Historical weather','Dated factor inputs']){
    const html=renderToStaticMarkup(React.createElement(ConnectionRecord,{name:'Source',icon:Icon,provider:'Provider',category,status:'Ready',tone:'success',meta:'Checked today',actions:'Details'}));
    assert.equal((html.match(/<td>/g)||[]).length,4);
    assert.match(html,/ui-record-identity/);assert.match(html,/ui-record-icon/);assert.match(html,/ui-record-state" data-tone="success"/);
    assert.match(html,/ui-record-actions/);assert.doesNotMatch(html,/style=/);
  }
  const source=await readFile(new URL('live-sources.jsx',import.meta.url),'utf8');
  assert.match(source,/return <ConnectionRecord/);assert.match(source,/extras\.map\(row=><ConnectionRecord/);
  assert.doesNotMatch(source,/<Disclosure|style=/);
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  assert.match(css,/width:var\(--record-icon-box\)/);assert.match(css,/height:var\(--record-status-dot\)/);
});
test('order addition preserves the customer/product/unit and never fabricates demand',()=>{
  const inputs={customers:[{customer:'Customer A',sku:'001',unit:'tonnes'}],as_of:'2026-10-09',orders:[]};
  const rows=appendOrder(inputs);
  assert.deepEqual(rows,[{reference:'',customer:'Customer A',sku:'001',unit:'tonnes',due_date:'2026-10-09',ordered:0,fulfilled:0,cancelled:0,status:'confirmed'}]);
  assert.deepEqual(inputs.orders,[]);
  assert.deepEqual(appendOrder({...inputs,customers:[]}),[]);
});
test('the order modal reuses global forms and can hide list-level add/remove controls',()=>{
  const inputs={as_of:'2026-10-09',customers:[{customer:'Customer A',sku:'001',unit:'tonnes'}],orders:[{reference:'Order 100',customer:'Customer A',sku:'001',unit:'tonnes',due_date:'2026-11-01',ordered:15,fulfilled:0,cancelled:0,status:'confirmed'}]};
  const html=renderToStaticMarkup(React.createElement(OrderRows,{inputs,ui,onChange:()=>{},showAdd:false,showRemove:false}));
  assert.match(html,/ui-field-group/);assert.match(html,/ui-grid ui-grid-two/);assert.match(html,/value="15"/);assert.match(html,/value="2026-11-01"/);
  assert.doesNotMatch(html,/Add order|Remove order|class="ui-panel|style=/);
});
test('large forecast order books use the same compact table as Data, not one form per order',()=>{
  const inputs={customers:[{customer:'Customer A',sku:'001',unit:'tonnes'}],orders:Array.from({length:79},(_,i)=>({reference:'Order '+i,customer:'Customer A',sku:'001',unit:'tonnes',due_date:'2026-11-01',ordered:15,fulfilled:2,cancelled:1,status:i%2?'unconfirmed':'confirmed'}))};
  const html=renderToStaticMarkup(React.createElement(OrderReview,{inputs,ui,onChange:()=>{}}));
  assert.equal((html.match(/<tbody><tr>|<\/tr><tr>/g)||[]).length,79);
  for(const label of['Already fulfilled','Cancelled','Status','Unconfirmed','Confirmed','Order 78'])assert.ok(html.includes(label),label);
  assert.doesNotMatch(html,/<input|ui-field-group|style=/);
  const readonly=renderToStaticMarkup(React.createElement(OrderTable,{inputs,ui}));
  assert.doesNotMatch(readonly,/>Edit<|Remove order|<input/);
});
test('order edits are explicit and cannot be skipped while preparing the forecast',async()=>{
  const orders=await readFile(new URL('order-books.jsx',import.meta.url),'utf8');
  const wizard=await readFile(new URL('forecast-orders.jsx',import.meta.url),'utf8');
  assert.match(orders,/orders\[index\]=editing.row/);
  assert.match(orders,/onEditingChange\?\.\(!!editing\)/);
  assert.match(wizard,/disabled=\{blocked\|\|editingOrder\|\|!checked/);
  assert.match(wizard,/<OrderReview/);assert.doesNotMatch(wizard,/<OrderRows/);
});
test('collection/search/record appearance has one CSS owner and no obsolete tab overrides',async()=>{
  const root=new URL('./',import.meta.url);
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.css'))){
    const css=await readFile(new URL(file,root),'utf8');
    postcss.parse(css).walkRules(rule=>{
      if(file!=='ui-framework.css')assert.doesNotMatch(rule.selector,/\.ui-(?:collection|search|record)(?:[-\s.:\[]|$)/,file);
      assert.doesNotMatch(rule.selector,/\.(?:customer-workspace|customer-list|customer-row-actions|live-source-list|live-source-row|live-source-name|live-source-status|live-source-actions)\b/,file);
    });
  }
});
test('long dataset names cannot enlarge the shared collection on narrow screens',async()=>{
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  for(const name of['ui-collection','ui-stack','ui-disclosure'])assert.match(css,new RegExp('\\.'+name+' \\{[^}]*grid-template-columns:minmax\\(0,1fr\\)'));
  assert.match(css,/\.ui-collection-controls>\.select-control \{[^}]*min-width:0/);
  assert.match(css,/\.ui-collection-body table \{min-width:var\(--collection-table-min-width\)/);
});

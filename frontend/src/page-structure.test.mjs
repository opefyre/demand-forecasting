import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import postcss from 'postcss';
let server,Page,ChatHistory,ChatSurface,useMenuHandoff;
before(async()=>{
 server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
 ({Page,useMenuHandoff}=await server.ssrLoadModule('/src/ui-layout.jsx'));
 ({ChatHistory}=await server.ssrLoadModule('/src/ui-chat-history.jsx'));
 ({ChatSurface}=await server.ssrLoadModule('/src/ui-chat.jsx'));
});
after(async()=>{await server?.close();});
test('shared pages always order title/actions, controls, then content',()=>{
 for(const title of['Data','Sales forecast','Settings','Approvals','Help']){
  const html=renderToStaticMarkup(React.createElement(Page,{title,actions:'Primary action',controls:'Page controls'},'Page content'));
  assert.match(html,/<section class="ui-page">/);
  assert.ok(html.indexOf('ui-page-header')<html.indexOf('ui-page-controls'));
  assert.ok(html.indexOf('ui-page-controls')<html.indexOf('ui-page-content'));
  assert.doesNotMatch(html,/style=/);
 }
});
test('all main working pages use the shared structural component, not local headers',async()=>{
 for(const file of['sales-demand.jsx','settings-workspace.jsx','demand-reviews.jsx','help.jsx']){
  const text=await readFile(new URL(file,import.meta.url),'utf8');
  assert.match(text,/<Page\s/);assert.doesNotMatch(text,/className="page-heading"/);
 }
 const main=await readFile(new URL('main.jsx',import.meta.url),'utf8');
 for(const [start,end]of[['function DataPage(','function ExternalFactors('],['function ImportFlow(','function SourceCard('],['function ForecastPage(','function ScenarioList(']]){
  const text=main.slice(main.indexOf(start),main.indexOf(end));assert.match(text,/<Page\s/);assert.doesNotMatch(text,/className="page-heading"/);
 }
});
test('structural component CSS has one global owner and tokenized dimensions',async()=>{
 const root=new URL('./',import.meta.url);
 for(const file of(await readdir(root)).filter(f=>f.endsWith('.css')&&f!=='ui-framework.css')){
  postcss.parse(await readFile(new URL(file,root),'utf8')).walkRules(rule=>assert.doesNotMatch(rule.selector,/\.ui-page(?:[-\s.:\[]|$)/,file));
 }
 const css=await readFile(new URL('ui-framework.css',root),'utf8');
 for(const token of['page-padding','page-gap','page-header-height','page-title-size','component-gap'])assert.ok(css.includes('var(--'+token+')'));
 assert.match(css,/\.ui-chat-workspace[^}]+grid-template-columns:var\(--chat-history-width\)/);
 assert.doesNotMatch(css.match(/\.ui-chat-history \{[^}]+\}/)[0],/border-radius|margin/);
 assert.match(css,/main:has\(\.ui-chat\)>#workspace[^}]+padding:0/);
});
test('history has one menu per row and no repeated identity decoration',()=>{
 const html=renderToStaticMarkup(React.createElement(ChatHistory,{chats:[{id:'1',head_id:'h1',title:'October sales',status:'active'},{id:'2',head_id:'h2',title:'November sales',status:'active'}]}));
 assert.equal((html.match(/class="ui-chat-history-menu"/g)||[]).length,2);
 assert.doesNotMatch(html,/ui-chat-history-rename|ChatCircle|PencilSimple/);
 assert.match(html,/Chat options for October sales/);assert.match(html,/aria-label="Chat folders"/);
});
test('quick actions are only on the welcome screen and the composer stays single',()=>{
 const props={value:'',onChange:()=>{},onSend:()=>{},quickActions:[{id:'data',label:'Import sales',icon:()=>null,onSelect:()=>{}}]};
 const welcome=renderToStaticMarkup(React.createElement(ChatSurface,props));
 assert.match(welcome,/Quick actions/);assert.match(welcome,/Import sales/);
 const active=renderToStaticMarkup(React.createElement(ChatSurface,{...props,active:true}));
 assert.doesNotMatch(active,/Quick actions|Import sales/);
 assert.equal((active.match(/<textarea/g)||[]).length,1);
});
test('menu actions wait for focus restoration before opening a dialog',async()=>{
 let handoff;const order=[];
 function Probe(){handoff=useMenuHandoff();return null;}
 renderToStaticMarkup(React.createElement(Probe));
 handoff.select({focus(){order.push('focus');}},()=>order.push('action'));
 handoff.close({preventDefault(){order.push('prevent');}});
 assert.deepEqual(order,['prevent','focus']);
 await Promise.resolve();assert.deepEqual(order,['prevent','focus','action']);
 handoff.close({preventDefault(){throw new Error('No pending action');}});
 await Promise.resolve();assert.equal(order.filter(x=>x==='action').length,1);
});
test('archived conversations disable the composer and its tools',()=>{
 const html=renderToStaticMarkup(React.createElement(ChatSurface,{active:true,readOnly:true,value:'',onChange:()=>{},onSend:()=>{}}));
 assert.match(html,/<textarea[^>]*disabled/);
});

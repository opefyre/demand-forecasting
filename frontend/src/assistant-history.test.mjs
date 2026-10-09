import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'esbuild';
import {createRequire} from 'node:module';
import {chatKey,readChatHead,writeChatHead,chatPayload,readInputChoice,writeInputChoice} from './assistant-history.mjs';

test('chat pointer separates forecast and order versions and stores no messages',()=>{
  const map=new Map(), storage={getItem:k=>map.get(k),setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};
  const key=chatKey('run1','orders1');writeChatHead(storage,key,'opaque-turn');
  assert.equal(readChatHead(storage,key),'opaque-turn');
  assert.equal(readChatHead(storage,chatKey('run1','orders2')),null);
  assert.equal(readChatHead(storage,chatKey('run2','orders1')),null);
  writeChatHead(storage,key,null);assert.equal(readChatHead(storage,key),null);
  assert.doesNotThrow(()=>writeChatHead({setItem:()=>{throw Error('unavailable');}},key,'id'));
});
test('followup passes only the saved parent ID, not client-supplied history',()=>{
  const payload=chatPayload('Now 10 months','run1','orders1',[{id:'a',answer:'Earlier'},{id:'b',answer:'Latest'}]);
  assert.equal(payload.previous_turn_id,'b');assert.equal(payload.history,undefined);
  assert.equal(chatPayload('New chat','run1','',[]).previous_turn_id,null);
  assert.equal(payload.mode,'auto');
});
test('first forecast chat binds saved inputs separately from forecasts and orders',()=>{
  assert.notEqual(chatKey(null,null,'sales-a'),chatKey(null,null,'sales-b'));
  assert.notEqual(chatKey(null,null,'sales-a'),chatKey('sales-a',null));
  const payload=chatPayload('Forecast all customers',null,'',[],'sales-a');
  assert.equal(payload.run_id,null);assert.equal(payload.snapshot_id,null);
  assert.equal(payload.dataset_id,'sales-a');assert.equal(payload.previous_turn_id,null);
});
test('selected inputs survive reload but never silently follow another forecast',()=>{
  const map=new Map(),storage={getItem:k=>map.get(k),setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)};
  writeInputChoice(storage,'run-a','sales-a');
  assert.equal(readInputChoice(storage,'run-a',[{id:'sales-a'}]),'dataset:sales-a');
  assert.equal(readInputChoice(storage,'run-b',[{id:'sales-a'}]),'');
  assert.equal(readInputChoice(storage,'run-a',[{id:'sales-a',scenario_provenance:{}}]),'');
  assert.equal(readInputChoice(storage,'run-a',[]),'');
  assert.doesNotMatch(JSON.stringify([...map.values()]),/quantity|question|answer/);
  writeInputChoice(storage,'run-a',null);assert.equal(map.size,0);
});

const bundle=await build({entryPoints:[new URL('./assistant-workspace.jsx',import.meta.url).pathname],bundle:true,write:false,platform:'node',format:'cjs',external:['react','@phosphor-icons/react','./sales-demand']});
const module={exports:{}};
const icons=await import('@phosphor-icons/react');
new Function('require','module','exports',bundle.outputFiles[0].text)(name=>name==='./sales-demand'?{}:name==='@phosphor-icons/react'?icons:createRequire(import.meta.url)(name),module,module.exports);
const ui={Button:({children,...props})=>React.createElement('button',props,children)};
ui.Table=({children})=>React.createElement('table',null,React.createElement('tbody',null,children));
const turn={id:'one',question:'Customer A for 10 months',answer:'Ready for review',actions:[{kind:'forecast',customer:'A',months:10,method:'recommended'}]};
const render=t=>renderToStaticMarkup(React.createElement(module.exports.AssistantMessages,{turns:[t],ui,canEdit:true,actionBusy:'',execute:()=>{}}));
test('restored conversation renders questions and proposals, with expired actions disabled',()=>{
  assert.match(render(turn),/Customer A for 10 months/);
  assert.match(render(turn),/Review inputs &amp; continue/);
  const expired=render({...turn,actions_expired:true});assert.match(expired,/proposal expired/);assert.doesNotMatch(expired,/Review inputs &amp; continue/);
});
test('saved execution receipt replaces the confirmation button after reload',()=>{
  const html=render({...turn,results:{'0':{job:{id:'job1'}}}});
  assert.match(html,/Forecast queued/);assert.doesNotMatch(html,/Confirm &amp; run/);
});
test('all customer proposal has human-readable scope and method',()=>{
  const html=render({...turn,actions:[{kind:'forecast',customer:'',months:10,method:'recommended'}]});
  assert.match(html,/All customers/);assert.match(html,/Compare available methods/);
});
test('saved orders proposal shows coverage review, not a forecast run button',()=>{
  const action={kind:'order_reuse',preview:{source_name:'Synthetic orders',customer_count:2,order_count:2,
    as_of:'2026-10-03',valid_until:'2026-10-10',month_basis:'jalali',unit:'tonnes',warnings:[],outside_open_orders:[],can_save:true,
    months:[{period:'2026-09-23',booked:140,remaining:94,total:254}]}};
  const html=render({...turn,actions:[action]});
  assert.match(html,/1405-07/);assert.match(html,/includes all known orders/);
  assert.match(html,/Confirm &amp; save demand draft/);assert.doesNotMatch(html,/Confirm &amp; run/);
  const saved=render({...turn,actions:[action],results:{'0':{snapshot_id:'draft',run_id:'run'}}});
  assert.match(saved,/Open demand forecast/);assert.doesNotMatch(saved,/Confirm &amp; save/);
});
test('mapping proposal shows before/after and explicit approval, then saved version',()=>{
  const mapping={kind:'input_mapping',reason:'Confirmed quantity column',diff:[{field:'target_col',before:'qty',after:'actual'}],before_total:21,after_total:210,before_prepared_total:21,after_prepared_total:210,unit:'tonnes',warnings:['Check source dates']};
  const html=render({...turn,actions:[mapping]});
  assert.match(html,/Sales quantity/);assert.match(html,/actual/);assert.match(html,/21 → 210/);
  assert.match(html,/Check source dates/);assert.match(html,/Approve &amp; save new input version/);
  const saved=render({...turn,actions:[mapping],results:{'0':{dataset_id:'new',dataset_name:'History reviewed'}}});
  assert.match(saved,/History reviewed/);assert.doesNotMatch(saved,/Approve &amp; save/);
});

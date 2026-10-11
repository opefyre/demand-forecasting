import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {openAssistantForecast} from './assistant-handoff.mjs';
const result={dataset_id:'reviewed-draft',method:'model:Last observed',customer:'Mehr'};
test('assistant hands exact source, method and customer to the shared wizard after refresh',async()=>{
  const calls=[];
  assert.equal(await openAssistantForecast(result,{refresh:async()=>calls.push('refresh'),isCurrent:()=>true,onNewForecast:(...args)=>calls.push(args)}),true);
  assert.deepEqual(calls,['refresh',['reviewed-draft','model:Last observed','Mehr']]);
});
test('leaving chat during a slow refresh cannot reopen an old forecast',async()=>{
  let current=true,release;const calls=[];
  const pending=openAssistantForecast(result,{refresh:()=>new Promise(resolve=>release=resolve),isCurrent:()=>current,onNewForecast:()=>calls.push('open')});
  current=false;release();assert.equal(await pending,false);assert.deepEqual(calls,[]);
});
test('stale actions and failed refresh never navigate',async()=>{
  const forbidden=()=>{throw Error('Unexpected navigation');};
  assert.equal(await openAssistantForecast(result,{refresh:forbidden,isCurrent:()=>false,onNewForecast:forbidden}),false);
  await assert.rejects(openAssistantForecast(result,{refresh:async()=>{throw Error('Reload failed');},isCurrent:()=>true,onNewForecast:forbidden}),/Reload failed/);
});
test('assistant forecast handoff remains wired to the shared review wizard',async()=>{
  const chat=await readFile(new URL('assistant-workspace.jsx',import.meta.url),'utf8');
  const main=await readFile(new URL('main.jsx',import.meta.url),'utf8');
  assert.match(chat,/await openAssistantForecast\(result/);
  assert.match(chat,/isCurrent:\(\)=>current===generation.current/);
  assert.match(main,/source:datasetId,step:1,methods:\[method\],customer,jobs:\[\]/);
});

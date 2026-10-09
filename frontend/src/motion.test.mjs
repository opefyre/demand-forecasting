import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import postcss from 'postcss';
import {createMotionController} from './motion.mjs';

function browser({reduced=false,visibility='visible',start}={}){
  return {visibilityState:visibility,defaultView:{matchMedia:()=>({matches:reduced})},startViewTransition:start};
}
function transition(){return {ready:Promise.resolve(),updateCallbackDone:Promise.resolve(),finished:Promise.resolve(),skipTransition(){}};}

test('unsupported, hidden and reduced-motion browsers apply updates immediately once',()=>{
  for(const host of[null,browser(),browser({visibility:'hidden',start:()=>assert.fail('hidden snapshot')}),browser({reduced:true,start:()=>assert.fail('reduced snapshot')})]){
    let calls=0;createMotionController({host,commit:change=>change()})(()=>calls++);assert.equal(calls,1);
  }
});
test('CSS fallback reveals updated content only when motion is permitted',()=>{
  for(const reduced of[false,true]){
    let calls=0,reveals=0;
    createMotionController({host:browser({reduced}),commit:change=>change(),reveal:()=>reveals++})(()=>calls++);
    assert.equal(calls,1);assert.equal(reveals,reduced?0:1);
  }
});
test('interactive app transitions commit immediately without native snapshot click blockers',()=>{
 let updates=0,reveals=0;
 const update=createMotionController({nativeSnapshots:false,host:browser({start:()=>assert.fail('No native snapshots')}),commit:f=>f(),reveal:()=>reveals++});
 update(()=>updates++);update(()=>updates++);
 assert.equal(updates,2);assert.equal(reveals,2);
});
test('failed snapshot setup falls back without dropping or replaying the operation',()=>{
  for(const afterCommit of[false,true]){
    let calls=0;
    const update=createMotionController({host:browser({start:change=>{if(afterCommit)change();throw Error('snapshot failed');}}),commit:change=>change()});
    if(afterCommit)assert.throws(()=>update(()=>calls++));else update(()=>calls++);
    assert.equal(calls,1);
  }
});
test('rapid transitions skip old animation, but commit every queued update once in order',async()=>{
  const callbacks=[],changes=[],first=transition();let skips=0;
  first.skipTransition=()=>skips++;
  const update=createMotionController({host:browser({start:change=>{callbacks.push(change);return callbacks.length===1?first:transition();}}),commit:change=>change()});
  update(()=>changes.push('first'));update(()=>changes.push('second'));
  assert.equal(skips,1);
  for(const apply of callbacks){apply();apply();}
  assert.deepEqual(changes,['first','second']);
  await Promise.resolve();
});
test('snapshot cancellation rejections are handled and do not repeat actions',async()=>{
  let calls=0;
  const update=createMotionController({host:browser({start:change=>{change();return {ready:Promise.reject(Error('skipped')),updateCallbackDone:Promise.resolve(),finished:Promise.reject(Error('skipped')),skipTransition(){}};}}),commit:change=>change()});
  update(()=>calls++);await new Promise(resolve=>setImmediate(resolve));assert.equal(calls,1);
});
test('late snapshot callbacks cannot undo newer navigation',()=>{
 const callbacks=[],changes=[];
 const update=createMotionController({host:browser({start:change=>{callbacks.push(change);return transition();}}),commit:change=>change()});
 update(()=>changes.push('settings'));update(()=>changes.push('help'));
 callbacks[1]();callbacks[0]();
 assert.deepEqual(changes,['settings','help']);
});
test('shared motion never waits for an API action and never remounts forms',async()=>{
  const source=await readFile(new URL('ui-motion.jsx',import.meta.url),'utf8');
  assert.match(source,/flushSync\(\(\)=>\{change\(\);\}\)/);
  assert.doesNotMatch(source,/await|setTimeout|\.animate\(|\.style\b/);
  assert.match(source,/useCallback/);
});
test('all animation and transition rules have one global owner',async()=>{
  const root=new URL('./',import.meta.url),issues=[];
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.css')&&!['tokens.css','ui-framework.css'].includes(f))){
    const ast=postcss.parse(await readFile(new URL(file,root),'utf8'));
    ast.walkDecls(d=>{if(/^(transition|animation)(-|$)/.test(d.prop))issues.push(file+': '+d.prop);});
    ast.walkAtRules('keyframes',r=>issues.push(file+': '+r.params));
  }
  assert.deepEqual(issues,[]);
});
test('motion is tokenized, role-based and disabled completely for reduced motion',async()=>{
  const css=await readFile(new URL('ui-framework.css',import.meta.url),'utf8');
  const tokens=await readFile(new URL('tokens.css',import.meta.url),'utf8');
  for(const role of['button','input','textarea','summary','modal','modal-overlay','select-menu','ui-menu','tooltip','ui-chat-message','working-bar','ui-disclosure'])assert.ok(css.includes(role),role);
  for(const token of['motion-fast','motion-control','motion-enter','motion-exit','motion-layout','motion-ease','motion-offset','motion-scale-press'])assert.ok(tokens.includes('--'+token+':'),token);
  assert.doesNotMatch(css,/transition\s*:\s*all\b|will-change\s*:/);
  assert.match(css,/prefers-reduced-motion:reduce/);
  assert.match(css,/animation:none!important;transition:none!important;scroll-behavior:auto!important/);
  assert.match(css,/::view-transition \{pointer-events:none;/);
});
test('navigation, forecast, orders, data, factors and Settings reuse the same state transition helper',async()=>{
  for(const file of['main.jsx','new-forecast.jsx','sales-demand.jsx','factor-imports.jsx','factor-links.jsx','forecast-factors.jsx','settings-workspace.jsx','assistant-workspace.jsx','demand-handoff.jsx']){
    assert.match(await readFile(new URL(file,import.meta.url),'utf8'),/useSmoothState/);
  }
  assert.match((await readFile(new URL('assistant-workspace.jsx',import.meta.url),'utf8')).replace(/\s+/g,''),/smoothUpdate\(\(\)=>\{setPending\(submittedQuestion\)/);
});

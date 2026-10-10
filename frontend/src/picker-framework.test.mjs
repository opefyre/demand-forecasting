import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import postcss from 'postcss';

test('picker runtime measurements resolve on the menu, never in root tokens',async()=>{
  const tokens=await readFile(new URL('tokens.css',import.meta.url),'utf8');
  assert.doesNotMatch(tokens,/var\(--radix-select-/);
  const css=postcss.parse(await readFile(new URL('ui-framework.css',import.meta.url),'utf8'));
  const menu=css.nodes.find(n=>n.type==='rule'&&n.selector==='.select-menu');
  const props=Object.fromEntries(menu.nodes.filter(n=>n.type==='decl').map(n=>[n.prop,n.value]));
  assert.equal(props['min-width'],'var(--radix-select-trigger-width)');
  assert.equal(props['max-height'],'min(var(--radix-select-content-available-height,var(--picker-max-height)),var(--picker-max-height))');
  assert.equal(props.overflow,'hidden');
  assert.equal(props['z-index'],'var(--layer-picker)');
});

test('all picker appearance has one global owner',async()=>{
  const issues=[],root=new URL('./',import.meta.url);
  for(const file of(await readdir(root)).filter(f=>f.endsWith('.css')&&f!=='ui-framework.css')){
    postcss.parse(await readFile(new URL(file,root),'utf8')).walkRules(rule=>{
      if(/\.select-(?:menu|option|scroll)\b/.test(rule.selector))issues.push(file+': '+rule.selector);
    });
  }
  assert.deepEqual(issues,[]);
});

test('factor review indicates progress and invalidates the previous approval before requesting',async()=>{
  const source=await readFile(new URL('forecast-factors.jsx',import.meta.url),'utf8');
  assert.match(source,/setReview\(null\);setApproved\(false\);setReview\(await api\(endpoint\+'\/preview'/);
  assert.match(source,/uiText\(busy&&!review\?'Checking…':'Review factors'\)/);
  const wizard=await readFile(new URL('new-forecast.jsx',import.meta.url),'utf8');
  assert.match(wizard,/type==='forecast_factors'\?<Button disabled=\{working\|\|!canEdit\}/);
});

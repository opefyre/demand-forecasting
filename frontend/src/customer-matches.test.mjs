import test from 'node:test';
import assert from 'node:assert/strict';
import {directoryMatches} from './customer-matches.mjs';
test('aliases and leading-zero ERP IDs are explicit matches, inactive excluded',()=>{
  const items=[{customer:'Tehran buyer',external_id:'001',aliases:['خریدار تهران'],active:true},{customer:'Old',aliases:['Former'],active:false}];
  assert.deepEqual(directoryMatches(items),{'001':'Tehran buyer','خریدار تهران':'Tehran buyer'});
  assert.deepEqual(items[0].aliases,['خریدار تهران']);
});
test('ambiguous identities never silently overwrite',()=>{
  assert.throws(()=>directoryMatches([{customer:'A',aliases:['x']},{customer:'B',external_id:'x'}]),/more than one/);
});

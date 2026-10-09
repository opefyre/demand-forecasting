import test from 'node:test';
import assert from 'node:assert/strict';
import {futureAssumptions} from './factor-assumptions.mjs';

test('monthly values preserve zero and leave blanks unknown, without constant fallback',()=>{
  assert.deepEqual(futureAssumptions(true,'999',{'2026-01-01':'0','2026-02-01':'','2026-03-01':'120.5'}),
    {future_value:null,future_values:{'2026-01-01':0,'2026-03-01':120.5}});
});
test('constant mode ignores inactive monthly inputs',()=>{
  assert.deepEqual(futureAssumptions(false,'125',{'2026-01-01':'bad'}),{future_value:125});
  assert.deepEqual(futureAssumptions(false,' ',{}),{future_value:null});
});
test('invalid numbers cannot silently become missing assumptions',()=>{
  for(const value of ['wrong','Infinity']) {
    assert.throws(()=>futureAssumptions(false,value,{}),/Enter a number/);
    assert.throws(()=>futureAssumptions(true,'',{'2026-01-01':value}),/Enter a number/);
  }
});

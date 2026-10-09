import test from 'node:test';
import assert from 'node:assert/strict';
import {comparisonRows} from './order-comparison.mjs';
const row=(customer,sku,total)=>({customer,sku,period:'2026-10-01',unit:'tonnes',booked:2,fulfilled:1,before_remaining:3,after_remaining:total==null?null:total-3,before_total:6,after_total:total,difference:total==null?null:total-6});
test('customer and SKU filters intersect and All restores reconciled totals',()=>{
  const rows=[row('A','X',7),row('A','Y',9),row('B','X',8)];
  assert.equal(comparisonRows(rows,'A','X')[0].after_total,7);
  assert.equal(comparisonRows(rows,'A')[0].after_total,16);
  assert.equal(comparisonRows(rows)[0].after_total,24);
  assert.equal(comparisonRows(rows)[0].difference,6);
  assert.deepEqual(comparisonRows(rows,'unknown'),[]);
});
test('unknown demand is not zero and units cannot be added together',()=>{
  const rows=[row('A','X',7),row('B','X',null),{...row('C','X',8),unit:'kg'}];
  const result=comparisonRows(rows);assert.equal(result.length,2);
  assert.equal(result.find(r=>r.unit==='tonnes').after_total,null);
  assert.equal(result.find(r=>r.unit==='tonnes').booked,4);
});

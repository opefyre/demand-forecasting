import test from 'node:test';
import assert from 'node:assert/strict';
import {orderCoverageTitle} from './forecast-start.mjs';
test('uploaded orders are not described as no current orders before review',()=>{
  assert.equal(orderCoverageTitle([],{source_id:'synthetic-file'}),'All known orders included');
  assert.equal(orderCoverageTitle([{reference:'one'}],null),'All known orders included');
  assert.equal(orderCoverageTitle([],null),'No current orders');
});

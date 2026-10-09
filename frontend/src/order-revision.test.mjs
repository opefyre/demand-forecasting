import test from 'node:test';
import assert from 'node:assert/strict';
import {orderRevision, orderReviewMessage} from './order-revision.mjs';

test('freshness guidance follows server status without silently renewing dates',()=>{
  const outlook={fresh:false,valid_until:'2026-09-24'};
  assert.match(orderReviewMessage(outlook),/2026-09-24/);
  assert.match(orderReviewMessage(outlook),/current order book/);
  assert.equal(orderReviewMessage({...outlook,fresh:true}),'');
  assert.equal(orderReviewMessage(null),'');
  assert.equal(outlook.valid_until,'2026-09-24');
});

test('update starts with saved relationships, orders and commitments, but needs new review',()=>{
  const saved={id:'v1',inputs:{customers:[{customer:'A'}],orders:[{reference:'ERP/1/1',ordered:10}],commitments:[{quantity:20}],reviewed:true,note:'Previous review',as_of:'2026-09-23',valid_until:'2026-09-30'}};
  const draft=orderRevision(saved);
  assert.equal(draft.base_snapshot_id,'v1');
  assert.deepEqual(draft.inputs.orders,saved.inputs.orders);
  assert.deepEqual(draft.inputs.customers,saved.inputs.customers);
  assert.deepEqual(draft.inputs.commitments,saved.inputs.commitments);
  assert.equal(draft.inputs.reviewed,false);
  assert.equal(draft.inputs.note,'');
  assert.equal(draft.inputs.as_of,saved.inputs.as_of);
  draft.inputs.orders[0].ordered=99;
  assert.equal(saved.inputs.orders[0].ordered,10);
  assert.equal(saved.inputs.reviewed,true);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {commitmentPeriods,commitmentError} from './commitment-state.mjs';
const customer={customer:'Mehr',sku:'001',unit:'tonnes'};
const row={...customer,period:'2026-10-01',quantity:'0',owner:'Planner',reason:'Confirmed full requirement',valid_until:'2026-11-01'};
const inputs={as_of:'2026-10-11',customers:[customer],commitments:[]};
test('calendar picker uses real forecast boundaries, including Persian months, not Gregorian dates',()=>{
 assert.deepEqual(commitmentPeriods({series:{a:{forecast:[{timestamp:'2026-10-23'},{timestamp:'2026-09-23'}]},b:{forecast:[{timestamp:'2026-10-23'}]}}}),['2026-09-23','2026-10-23']);
 assert.equal(commitmentError({...row,period:'2026-09-23'},inputs,['2026-09-23'],0),null);
});
test('zero and precise quantities are valid; blank, negative and infinite quantities are not',()=>{
 for(const quantity of ['0','15.123456789'])assert.equal(commitmentError({...row,quantity},inputs,[row.period],0),null);
 for(const quantity of ['',' ','-1','Infinity','NaN'])assert.equal(commitmentError({...row,quantity},inputs,[row.period],0),'Enter a quantity of zero or more.');
});
test('monthly entries require a real pair/month, owner, reason, expiry and unique customer-product-month',()=>{
 for(const patch of [{customer:'Other'},{period:'2026-11-01'},{owner:' '},{reason:' '},{valid_until:'2026-10-01'}])assert.ok(commitmentError({...row,...patch},inputs,[row.period],0));
 const duplicate={...inputs,commitments:[row]};
 assert.equal(commitmentError(row,duplicate,[row.period],1),'This customer and product already have a commitment for this month.');
 assert.equal(commitmentError(row,duplicate,[row.period],0),null);
 assert.equal(row.quantity,'0');
});

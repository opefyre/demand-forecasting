import test from 'node:test';
import assert from 'node:assert/strict';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
test('Persian month labels reflect exact Gregorian boundaries, not March labels',()=>{
  assert.equal(planningMonth('2025-03-21','jalali'),'1404-01');
  assert.equal(planningMonth('2025-03-20','jalali'),'1403-12');
  assert.equal(planningMonth('2025-03-21'),'2025-03');
  assert.equal(planningBasis({run_settings:{calendar_profile:{month_basis:'jalali'}}}),'jalali');
});

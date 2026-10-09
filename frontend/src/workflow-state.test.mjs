import test from 'node:test';
import assert from 'node:assert/strict';
import { workflowState, pendingImport } from './workflow-state.mjs';
test('an empty workspace starts with history, not blank charts', () => {
  assert.equal(workflowState({}).stage, 'start');
});
test('empty or corrupt draft is not unfinished work; sample drafts are labelled',()=>{
  for(const raw of [null,'invalid','{}','{"sources":{}}'])assert.equal(pendingImport(raw).exists,false);
  assert.deepEqual(pendingImport('{"sources":{"history":"h"},"classification":"synthetic_sample"}'),{exists:true,sample:true});
});
test('samples never count as company progress', () => {
  const state = workflowState({datasets:[{id:'s',classification:'synthetic_sample'}],runs:[{run_id:'r',dataset_id:'s'}],run:{run_id:'r',source_classification:'synthetic_sample'}});
  assert.equal(state.stage,'start'); assert.equal(state.sample.run_id,'r');
});
test('a saved input leads to calculation and an unfinished import takes precedence', () => {
  const inputs = {datasets:[{id:'d',classification:'user_provided'}]};
  assert.equal(workflowState(inputs).stage,'calculate');
  assert.equal(workflowState({...inputs,hasDraft:true}).stage,'import');
});
test('real saved forecast leads to review; scenarios do not replace baseline', () => {
  const state = workflowState({datasets:[{id:'d',classification:'user_provided'}],runs:[{run_id:'scenario',dataset_id:'d',scenario_name:'What if'},{run_id:'base',dataset_id:'d'}]});
  assert.equal(state.stage,'review');assert.equal(state.current.run_id,'base');
});

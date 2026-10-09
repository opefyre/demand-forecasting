import test from 'node:test';
import assert from 'node:assert/strict';
import {applyMappingSuggestion} from './import-mapping.mjs';

const settings={target_col:'revenue',date_col:'date',unit:'tonnes',drivers:['fx']};
const sources={history:{preview:{columns:['date','revenue','quantity']}}};
const diff=[{field:'target_col',before:'revenue',after:'quantity'}];
test('approved mapping changes only draft selections and preserves factors and units',()=>{
  const next=applyMappingSuggestion(settings,sources,diff);
  assert.deepEqual(next,{...settings,target_col:'quantity'});
  assert.equal(settings.target_col,'revenue');
});
test('changed mappings or replaced source reject stale proposals',()=>{
  assert.throws(()=>applyMappingSuggestion({...settings,target_col:'manual'},sources,diff),/Inputs changed/);
  assert.throws(()=>applyMappingSuggestion(settings,{history:{preview:{columns:['date','revenue']}}},diff),/Inputs changed/);
});
test('unsupported fields, repeated changes, wrong source and invented columns are rejected',()=>{
  for(const rows of [[{field:'unit',before:'tonnes',after:'quantity'}],[...diff,...diff],
    [{field:'future_date_col',before:null,after:'date'}],[{...diff[0],after:'invented'}]]) {
    assert.throws(()=>applyMappingSuggestion(settings,sources,rows));
  }
});

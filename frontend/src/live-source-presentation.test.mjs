import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceCaption,sourceRefreshState} from './live-source-presentation.mjs';
test('source captions use exact built-in IDs, never translate custom names',()=>{
  assert.equal(sourceCaption({id:'servix',name:'saved provider name'},key=>'FA:'+key),'FA:Iran exchange rate');
  assert.equal(sourceCaption({id:'custom',name:'Home'},()=>{throw Error('Do not translate data');}),'Home');
});
test('recent checks cannot make stale observations look fresh',()=>{
  const row={series:[{id:'raw'}],enabled:true,data_behind:true,last_success:'2026-10-07T12:00:00Z'};
  const original=structuredClone(row);
  assert.equal(sourceRefreshState(row).status,'Source data is behind');
  assert.equal(sourceRefreshState({...row,refresh_overdue:true}).status,'Refresh overdue');
  assert.equal(sourceRefreshState({...row,status:'refreshing'}).status,'Fetching data…');
  assert.deepEqual(row,original);
});
test('cooldown has an exact boundary and retained data does not override failure or permission',()=>{
  const row={series:[{id:'raw'}],status:'failed',enabled:true,cooldown_until:'2026-10-07T12:00:00Z'};
  assert.equal(sourceRefreshState(row,Date.parse('2026-10-07T11:59:59Z')).cooling,true);
  assert.equal(sourceRefreshState(row,Date.parse(row.cooldown_until)).cooling,false);
  assert.equal(sourceRefreshState(row).status,'Refresh failed');
  assert.equal(sourceRefreshState({...row,permission_required:true,permission_confirmed:false}).status,'Permission needed');
  assert.equal(sourceRefreshState({series:[],enabled:false}).status,'Not connected');
});

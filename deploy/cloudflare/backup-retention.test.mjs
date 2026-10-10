import test from 'node:test';
import assert from 'node:assert/strict';
import {backupCopy,persistBackup,HISTORY_PREFIX,HISTORY_DAYS} from './backup-retention.mjs';
const company='tehran',id='a'.repeat(32),key='companies/'+company+'/revisions/'+id+'.zip';
const snapshot=()=>({version:1,company_id:company,captured_at:1,head:{company,revision:id,object_key:key},
  revisions:[{company,id,object_key:key,created_at:1}],schedules:[],jobs:[{id,company,state:'succeeded',
    payload:'{}',grant_json:JSON.stringify({company_id:company,subject:'user',session_id:'never-back-up',key_id:'private-key',auth_kind:'session'})}]});
test('backup removes session/key authority without altering the live ledger',()=>{
  const original=snapshot(),copy=backupCopy(original);
  assert.equal(JSON.parse(copy.jobs[0].grant_json).auth_kind,'recovered');
  assert.equal(JSON.parse(copy.jobs[0].grant_json).session_id,undefined);
  assert.equal(JSON.parse(copy.jobs[0].grant_json).key_id,undefined);
  assert.equal(JSON.parse(original.jobs[0].grant_json).session_id,'never-back-up');
  assert.throws(()=>backupCopy({...original,company_id:'other'}));
});
test('only redundant history is expiring; latest checkpoint remains indefinitely',async()=>{
  const writes=[],bucket={put:async(key,bytes,options)=>{writes.push({key,bytes,options});return {key};}};
  const receipt=await persistBackup(bucket,snapshot());
  assert.equal(HISTORY_DAYS,30);assert.ok(writes[0].key.startsWith(HISTORY_PREFIX+company+'/'));
  assert.equal(writes[1].key,'companies/tehran/recovery/latest.json');
  assert.ok(!writes[1].key.startsWith(HISTORY_PREFIX));assert.equal(receipt.verified,true);
  assert.equal(writes[0].options.customMetadata.sha256,writes[1].options.customMetadata.sha256);
  assert.ok(!new TextDecoder().decode(writes[1].bytes).includes('never-back-up'));
});
test('replica failure cannot be reported as a verified backup',async()=>{
  await assert.rejects(persistBackup({put:async()=>null},snapshot()));
});

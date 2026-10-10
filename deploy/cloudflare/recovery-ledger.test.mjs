import test from 'node:test';
import assert from 'node:assert/strict';
import {validateRecovery,recoveryObjects,recoveredGrant} from './recovery-ledger.mjs';
function fixture(){const company='tehran_test',id='a'.repeat(32),key='companies/'+company+'/revisions/'+id+'.zip';return {
  version:1,company_id:company,captured_at:1,head:{company,revision:id,object_key:key,view_key:null},
  revisions:[{company,id,object_key:key}],jobs:[],schedules:[]};}
test('recovery requires company-bound committed head and bounded rows',()=>{
  const value=fixture();assert.equal(validateRecovery(value,'tehran_test'),value);assert.equal(recoveryObjects(value).length,1);
  for(const change of [v=>v.company_id='other',v=>v.head.object_key='companies/other/file',v=>v.revisions=[],
    v=>v.schedules=[{company:'other'}],v=>v.jobs=[{company:'tehran_test',id:'bad'}],v=>v.version=2]) {
    const bad=fixture();change(bad);assert.throws(()=>validateRecovery(bad,'tehran_test'));
  }
});
test('completed receipts keep ownership but never restore session authority',()=>{
  assert.deepEqual(JSON.parse(recoveredGrant(JSON.stringify({company_id:'tehran_test',subject:'owner',role:'admin',session_id:'expired',cookie:'never-copy',permissions:['reports:read']}))),
    {auth_kind:'recovered',company_id:'tehran_test',subject:'owner',role:'admin',permissions:['reports:read']});
});
test('recovery byte limit includes multi-byte Persian text',()=>{
  const value=fixture();value.notes='ف'.repeat(3*1024*1024);
  assert.ok(JSON.stringify(value).length<4*1024*1024);
  assert.throws(()=>validateRecovery(value,'tehran_test'));
});

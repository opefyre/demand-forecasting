import test from 'node:test';
import assert from 'node:assert/strict';
import {canShare,recipient} from './ai-sharing.mjs';

test('permission does not survive a provider or endpoint change',()=>{
  const status={ready:true,consent_id:'a'.repeat(64),provider_label:'OpenAI'};
  assert.equal(canShare(status,status.consent_id),true);
  assert.equal(canShare({...status,consent_id:'b'.repeat(64)},status.consent_id),false);
  assert.equal(canShare({...status,ready:false},status.consent_id),false);
  assert.equal(canShare(status,true),false);
  assert.equal(canShare({ready:true},undefined),false);
  assert.equal(canShare({ready:true,consent_id:'bad'},'bad'),false);
});

test('sharing text names the real recipient',()=>{
  assert.equal(recipient({provider_label:'Local AI on this computer'}),'Local AI on this computer');
  assert.equal(recipient(null),'the selected AI provider');
});

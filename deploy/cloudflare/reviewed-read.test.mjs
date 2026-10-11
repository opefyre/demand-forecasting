import test from 'node:test';
import assert from 'node:assert/strict';
import {reviewedReadLifetime,sameReadPrincipal,reusableRead} from './reviewed-read.mjs';
const who={company_id:'tehran_a',issuer:'https://forecast.vrolen.com',subject:'owner',role:'admin',auth_kind:'session',
  permissions:['ai:query','chats:own','reports:read','drafts:read','inputs:read','factors:read','customers:read']};
const revision='a'.repeat(32),id='b'.repeat(32),attempt='c'.repeat(32),now=100000000;
const key=`companies/tehran_a/outputs/${id}/${attempt}/api-response.json`;
const row={company:'tehran_a',kind:'api',state:'succeeded',api_status:200,input_revision:revision,created_at:now-100000,completed_at:now-1000,id,attempt,
  payload:JSON.stringify({method:'GET',path:'/ai/conversations'}),grant_json:JSON.stringify(who),artifacts:JSON.stringify({'api-response.json':key})};
test('private list reads reuse exact immutable results, not bodies, actions or exports',()=>{
  assert.equal(reusableRead(row,'/ai/conversations',who,revision,now),key);
  for(const path of ['/ai/conversations/'+id,'/ai/conversations/'+id+'/export','/ai/status','/views','/runs/'+id+'/export','/connections/external-sources'])
    assert.equal(reviewedReadLifetime(path,who),0,path);
  assert.equal(reviewedReadLifetime('/ai/conversations?status=archived&offset=50&search=Mehr',who),43200000);
  assert.equal(reviewedReadLifetime('/ai/conversations?ignored=1',who),0);
});
test('company, actor, role, permissions and current revision are never substituted',()=>{
  for(const replacement of [{company_id:'tehran_b'},{issuer:'other'},{subject:'other'},{role:'planner'},{auth_kind:'api_key'},
    {key_kind:'company'},{permissions:who.permissions.filter(p=>p!=='inputs:read')}])
    assert.equal(reusableRead(row,'/ai/conversations',{...who,...replacement},revision,now),null);
  assert.equal(reusableRead(row,'/ai/conversations',who,'d'.repeat(32),now),null);
  assert.equal(sameReadPrincipal(who,{...who,permissions:[...who.permissions].reverse()}),true);
  for(const principal of [{...who,role:'viewer'},{...who,role:'approver'},{...who,subject:'service:owner'},{...who,subject:'company-key:owner'}])
    assert.equal(reviewedReadLifetime('/ai/conversations',principal),0);
});
test('unsuccessful, expired, foreign, malformed and downloaded reads miss safely',()=>{
  for(const replacement of [{state:'running'},{api_status:403},{kind:'forecast'},{company:'tehran_b'},
    {completed_at:now+1},{completed_at:now-43200000},{completed_at:0.1},{completed_at:null},{grant_json:'broken'},
    {artifacts:JSON.stringify({'api-response.json':'companies/tehran_b/private'})},
    {artifacts:JSON.stringify({'api-response.json':key,'api-download.bin':key})}])
    assert.equal(reusableRead({...row,...replacement},'/ai/conversations',who,revision,now),null);
  assert.equal(reusableRead(row,'/ai/conversations?offset=50',who,revision,now),null);
});
test('factor choices have a short lifetime, exact inputs and no query extensions',()=>{
  for(const suffix of ['links','profiles']) {
    const path='/runs/'+id+'/factor-'+suffix,read={...row,payload:JSON.stringify({method:'GET',path})};
    assert.equal(reviewedReadLifetime(path,who),30000);
    assert.equal(reusableRead(read,path,who,revision,now),key);
    assert.equal(reusableRead({...read,completed_at:now-30000},path,who,revision,now),null);
    assert.equal(reviewedReadLifetime(path+'?ignored=yes',who),0);
  }
});

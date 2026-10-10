import test from 'node:test';
import assert from 'node:assert/strict';
import {managementRoute,managementResponse} from './management-api.mjs';
const who={company_id:'tehran_a',subject:'owner',role:'admin',auth_kind:'session',session_id:'private-session',key_id:'private-key'};
function request(path,method='GET',body){return new Request('https://forecast.vrolen.com/api/v1'+path,{method,...(body===undefined?{}:{body:JSON.stringify(body)})});}
test('all native access routes are mapped, not guessed business endpoints',()=>{
  for(const [method,path] of [['GET','/me'],['GET','/api-keys'],['POST','/api-keys'],['PATCH','/api-keys/key'],['DELETE','/api-keys/key'],['POST','/api-keys/key/rotate'],
    ['GET','/access-options'],['GET','/members'],['PATCH','/members/member'],['DELETE','/members/member'],['POST','/members/member/revoke-sessions'],['POST','/invitations'],['DELETE','/invitations/invite'],['GET','/audit-events']])
    assert.ok(managementRoute(method,path),path);
  assert.equal(managementRoute('POST','/members'),null);assert.equal(managementRoute('GET','/api-keys/key/rotate'),null);
});
test('native requests retain current company and credentials, hide session IDs and require interactive sign-in',async()=>{
  let calls=[];const identity={operation:async(op,body)=>{calls.push([op,body]);return{status:200,body:{updated:true}};}};
  const me=await managementResponse(identity,{},request('/me'),who);assert.equal((await me.json()).session_id,undefined);
  assert.equal((await managementResponse(identity,{},request('/me?company_id=tehran_b'),who)).status,400);
  const created=await managementResponse(identity,{cookie:'validated-cookie'},request('/api-keys','POST',{kind:'personal',name:'read',scopes:['reports:read']}),who);
  assert.equal(created.status,201);assert.equal(calls[0][1].company_id,'tehran_a');assert.equal(calls[0][1].cookie,'validated-cookie');
  assert.equal((await managementResponse(identity,{},request('/members'),{...who,auth_kind:'api_key'})).status,403);
  assert.equal((await managementResponse(identity,{},request('/api-keys','POST',{company_id:'tehran_b',name:'bad'}),who)).status,422);
  assert.equal(calls.length,1);
});
test('member changes are single actions; oversized or unknown body fields never reach identity',async()=>{
  const calls=[],identity={operation:async(op,body)=>{calls.push([op,body]);return{status:200,body:{updated:true}};}};
  await managementResponse(identity,{},request('/members/one','PATCH',{suspended:true}),who);
  assert.equal(calls[0][1].operation,'suspend');assert.equal(calls[0][1].id,'one');
  for(const body of [{role:'viewer',suspended:true},{suspended:'false'}, {},{operation:'remove'}])
    assert.equal((await managementResponse(identity,{},request('/members/one','PATCH',body),who)).status,422);
  assert.equal((await managementResponse(identity,{},request('/api-keys','POST',{name:'a'.repeat(10000)}),who)).status,413);
  assert.equal(calls.length,1);
});

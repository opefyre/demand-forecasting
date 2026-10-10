import test from 'node:test';
import assert from 'node:assert/strict';
import edge from './edge.mjs';
function setup(user=null){const calls=[];return {calls,env:{PRIVATE_ACCESS:'closed',OWNER_ONLY_ACCEPTANCE:'true',
  IDENTITY:{owner:async body=>{calls.push(['identity',body]);return user?{status:200,body:{user,csrf:'test-csrf'}}:{status:401,body:{}};},browser:async()=>new Response(null,{status:404})},
  STORAGE:{companyApi:async(...args)=>{calls.push(['storage',...args]);return Response.json({customers:[]});}},
  ASSETS:{fetch:async r=>{calls.push(['assets',new URL(r.url).pathname]);return new Response('compiled interface');}}}};}
const request=(path,init={})=>new Request('https://forecast.vrolen.com'+path,init);
test('anonymous users get only static sign-in UI, never company routes, files or keys',async()=>{
  const f=setup();assert.equal((await edge.fetch(request('/'),f.env)).status,200);
  assert.equal((await edge.fetch(request('/api/v1/customers'),f.env)).status,401);
  assert.equal((await edge.fetch(request('/api/auth/runtime'),f.env)).status,401);
  for(const path of ['/secrets','/.env','/ui/index.html','/assets/index.js','/api/unknown'])assert.equal((await edge.fetch(request(path),f.env)).status,404);
  assert.equal(f.calls.filter(c=>c[0]==='storage').length,0);
  const state=await (await edge.fetch(request('/api/auth/session'),f.env)).json();assert.equal(state.user,null);assert.equal(state.mode,'better_auth');
});
test('even a signed-in outsider or owner without MFA cannot reach company data',async()=>{
  for(const user of [{email:'stranger@example.test',mfa_required:false},{email:'opefyre@gmail.com',mfa_required:true}]){
    const f=setup(user);assert.equal((await edge.fetch(request('/api/v1/customers'),f.env)).status,user.mfa_required?403:401);
    assert.equal(f.calls.filter(c=>c[0]==='storage').length,0);
    assert.equal((await edge.fetch(request('/api/auth/runtime'),f.env)).status,user.mfa_required?403:401);
  }
});
test('owner runtime inspection reads private status without starting an engine',async()=>{
  const f=setup({email:'opefyre@gmail.com',mfa_required:false});let reads=0;
  f.env.ENGINE={status:async()=>{reads++;return {running:false,busy:false,idle_timeout_ms:300000};}};
  assert.deepEqual(await (await edge.fetch(request('/api/auth/runtime'),f.env)).json(),{running:false,busy:false,idle_timeout_ms:300000});
  assert.equal(reads,1);
  const page=await edge.fetch(request('/api/auth/runtime',{headers:{accept:'text/html'}}),f.env);
  assert.match(page.headers.get('content-type'),/^text\/html/);assert.match(await page.text(),/"running": false/);
  assert.equal((await edge.fetch(request('/api/auth/runtime',{method:'POST'}),f.env)).status,404);
  assert.equal(reads,2);
});
test('owner changes require origin and synchronizer token; browser headers cannot choose company',async()=>{
  const f=setup({email:'opefyre@gmail.com',mfa_required:false,session_id:'private',company_id:'verified-company'});
  const state=await (await edge.fetch(request('/api/auth/session'),f.env)).json();assert.equal(state.user.session_id,undefined);
  assert.equal((await edge.fetch(request('/api/v1/customers',{method:'POST',headers:{cookie:'valid'},body:'{}'}),f.env)).status,403);
  assert.equal((await edge.fetch(request('/api/v1/customers',{headers:{authorization:'Bearer key'}}),f.env)).status,403);
  assert.equal((await edge.fetch(request('/api/v1/customers',{headers:{cookie:'valid','x-company-id':'other'}}),f.env)).status,200);
  assert.deepEqual(f.calls.find(c=>c[0]==='storage')[1],{cookie:'valid'});
});
test('invalid engine status never becomes a false sleeping claim',async()=>{
  const f=setup({email:'opefyre@gmail.com',mfa_required:false});
  f.env.ENGINE={status:async()=>({})};
  assert.equal((await edge.fetch(request('/api/auth/runtime'),f.env)).status,503);
});

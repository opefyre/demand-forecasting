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
test('owner session renewal stays secure and never becomes JSON or an outsider cookie',async()=>{
  const f=setup();
  const cookie='__Secure-better-auth.session_token=synthetic-test-token; Max-Age=172800; Path=/; HttpOnly; Secure; SameSite=Lax';
  const make=(email,status=200)=>({status,body:{user:{email,mfa_required:false,session_id:'private-session'},csrf:'test-csrf'},cookies:[cookie,
    'unrelated=value; HttpOnly; Secure','__Secure-better-auth.session_token=unsafe; Secure']});
  f.env.IDENTITY.owner=async()=>make('opefyre@gmail.com');
  const response=await edge.fetch(request('/api/auth/session'),f.env);
  assert.deepEqual(response.headers.getSetCookie(),[cookie]);
  assert.doesNotMatch(await response.text(),/synthetic-test-token|private-session|cookies/);
  for(const value of [make('outsider@example.test'),make('opefyre@gmail.com',401)]){
    f.env.IDENTITY.owner=async()=>value;
    assert.equal((await edge.fetch(request('/api/auth/session'),f.env)).headers.get('set-cookie'),null);
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
test('startup timings expose only bounded measurements to the private administrator',async()=>{
  const f=setup({email:'opefyre@gmail.com',mfa_required:false,role:'admin'});
  const timing={kind:'forecast',cold:true,startup_ms:100,input_ms:20,calculation_ms:500,persistence_ms:60,total_ms:680,artifacts:6,secret:'never expose'};
  f.env.ENGINE={status:async()=>({running:false,busy:false,idle_timeout_ms:300000,last_timing:timing})};
  const value=await (await edge.fetch(request('/api/auth/runtime'),f.env)).json();
  assert.equal(value.last_timing.total_ms,680);assert.equal(value.last_timing.secret,undefined);
  timing.total_ms=-1;
  assert.equal((await (await edge.fetch(request('/api/auth/runtime'),f.env)).json()).last_timing,undefined);
  const viewer=setup({email:'opefyre@gmail.com',mfa_required:false,role:'viewer'});viewer.env.ENGINE=f.env.ENGINE;timing.total_ms=680;
  assert.equal((await (await edge.fetch(request('/api/auth/runtime'),viewer.env)).json()).last_timing,undefined);
});
test('source diagnostics are admin-only, bounded codes with no credentials or raw exception fields',async()=>{
  const f=setup({email:'opefyre@gmail.com',mfa_required:false,role:'admin'});
  const source_failure={reason:'dns',checked_at:'2026-10-10T17:00:00.000Z',url:'private',headers:{authorization:'private'},message:'private'};
  const source_check={status:200,format:'xlsx',checked_at:source_failure.checked_at,body:'private'};
  f.env.ENGINE={status:async()=>({running:false,busy:false,idle_timeout_ms:300000,source_failure,source_check})};
  const value=await (await edge.fetch(request('/api/auth/runtime'),f.env)).json();
  assert.deepEqual(value.source_failure,{reason:'dns',checked_at:source_failure.checked_at});
  assert.deepEqual(value.source_check,{status:200,format:'xlsx',checked_at:source_failure.checked_at});
  source_failure.reason='<script>private</script>';
  assert.equal((await (await edge.fetch(request('/api/auth/runtime'),f.env)).json()).source_failure,undefined);
  const viewer=setup({email:'opefyre@gmail.com',mfa_required:false,role:'viewer'});viewer.env.ENGINE=f.env.ENGINE;source_failure.reason='dns';
  assert.equal((await (await edge.fetch(request('/api/auth/runtime'),viewer.env)).json()).source_failure,undefined);
});
test('fixed DNS probe is fresh-MFA admin-only and never allows arbitrary queries',async()=>{
  const f=setup({email:'opefyre@gmail.com',mfa_required:false,role:'admin'});let calls=0;
  f.env.ENGINE={status:async()=>({running:false,busy:false,idle_timeout_ms:300000}),sourceProbe:async()=>{calls++;return {ready:false,reason:'dns_request',message:'private'};}};
  const value=await (await edge.fetch(request('/api/auth/runtime?check_sources=1'),f.env)).json();
  assert.deepEqual(value.source_probe,{ready:false,reason:'dns_request'});assert.equal(calls,1);
  assert.equal((await edge.fetch(request('/api/auth/runtime?check_sources=other'),f.env)).status,404);
  const viewer=setup({email:'opefyre@gmail.com',mfa_required:false,role:'viewer'});viewer.env.ENGINE=f.env.ENGINE;
  assert.equal((await edge.fetch(request('/api/auth/runtime?check_sources=1'),viewer.env)).status,404);assert.equal(calls,1);
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

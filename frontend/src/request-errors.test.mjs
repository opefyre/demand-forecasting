import test from 'node:test';
import assert from 'node:assert/strict';
import {requestJSON,responseFailure,recoveryPresentation,retryAfter,RequestFailure} from './request-errors.mjs';
import {demandLoadState} from './demand-load-state.mjs';
import {orderReviewMessage} from './order-revision.mjs';

test('request keeps exact payload, method and CSRF without retries',async()=>{
  const input={customer:'Home',sku:'0001',quantity:10,request_id:'stable-id'};
  const original=structuredClone(input),calls=[];
  const result=await requestJSON('/local',input,'PUT',{csrfToken:'local-token',fetcher:async(...args)=>{
    calls.push(args);return {ok:true,json:async()=>({saved:true})};}});
  assert.deepEqual(result,{saved:true});assert.deepEqual(input,original);assert.equal(calls.length,1);
  assert.equal(calls[0][1].method,'PUT');assert.deepEqual(JSON.parse(calls[0][1].body),input);
  assert.equal(calls[0][1].headers['X-DemandLab-CSRF'],'local-token');
});
test('file request preserves multipart and does not set a JSON content type',async()=>{
  const form=new FormData();form.append('file','synthetic');let options;
  await requestJSON('/local',form,undefined,{fetcher:async(_,o)=>{options=o;return {ok:true,json:async()=>({})};}});
  assert.equal(options.body,form);assert.equal(options.method,'POST');assert.equal(options.headers['Content-Type'],undefined);
});
test('network loss never repeats a save or says the save definitely failed',async()=>{
  let calls=0;
  await assert.rejects(()=>requestJSON('/local',{quantity:10},undefined,{fetcher:async()=>{calls++;throw Error('private transport details');}}),e=>{
    const view=recoveryPresentation(e);assert.equal(e.kind,'connection');
    assert.match(view.next,/check whether it was saved/);assert.doesNotMatch(e.message,/private/);return true;});
  assert.equal(calls,1);
});
test('read failure offers concise recovery without a misleading save warning',async()=>{
  await assert.rejects(()=>requestJSON('/local',undefined,undefined,{fetcher:async()=>{throw Error('offline');}}),e=>{
    assert.equal(e.operation,'read');assert.equal(recoveryPresentation(e).next,'Reload saved data to try again.');return true;});
});
test('session expiry notifies once and offers no local reload',async()=>{
  let expired=0,calls=0;
  await assert.rejects(()=>requestJSON('/local',undefined,undefined,{onSessionExpired:()=>expired++,fetcher:async()=>{
    calls++;return {ok:false,status:401,headers:new Headers(),json:async()=>({detail:'Sign-in required'})};}}),e=>{
      assert.equal(e.status,401);assert.equal(recoveryPresentation(e).canReload,false);return true;});
  assert.equal(expired,1);assert.equal(calls,1);
});
test('access, missing-version and validation failures do not suggest repeating a request',()=>{
  for(const status of [400,403,404,410,422])assert.equal(recoveryPresentation(responseFailure(status,{detail:'Original message'})).canReload,false);
  assert.equal(recoveryPresentation(responseFailure(409,{detail:'Replaced version'})).title,'The saved data changed.');
});
test('validation preserves field evidence but never retains input or context',()=>{
  const payload={detail:[{loc:['body','orders',2,'quantity'],msg:'Must be positive',input:'secret value',ctx:{key:'private'}}]};
  const original=structuredClone(payload),e=responseFailure(422,payload);
  assert.deepEqual(e.fields,[{field:'orders → 2 → quantity',message:'Must be positive'}]);
  assert.doesNotMatch(JSON.stringify(e),/secret value|private/);assert.deepEqual(payload,original);
});
test('retry after accepts seconds/date and expires at exact boundary',()=>{
  const now=Date.parse('2026-10-07T10:00:00Z');
  assert.equal(retryAfter('60',now),now+60000);assert.equal(retryAfter('2026-10-07T10:01:00Z',now),now+60000);
  assert.equal(retryAfter('invalid',now),null);
  const e=responseFailure(429,{detail:'Limited'},'60',now);
  assert.equal(recoveryPresentation(e,now+59999).canReload,false);assert.equal(recoveryPresentation(e,now+60000).canReload,true);
});
test('invalid successful JSON reports uncertain result without retrying writes',async()=>{
  let calls=0;
  await assert.rejects(()=>requestJSON('/local',{},undefined,{fetcher:async()=>{calls++;return {ok:true,status:200,json:async()=>{throw Error('not JSON');}};}}),e=>{
    assert.equal(e.kind,'response');assert.match(recoveryPresentation(e).next,/check whether it was saved/);return true;});
  assert.equal(calls,1);
});
test('plain data messages remain exact and unknown errors are not translated',()=>{
  const message='Customer Home · SKU 0001 is missing';
  assert.equal(recoveryPresentation(message).message,message);
  assert.equal(recoveryPresentation(new Error(message)).message,message);
  assert.equal(recoveryPresentation(null),null);
});
test('failed demand reads never become an empty-order setup',()=>{
  for(const selected of ['', 'orders-v1'])assert.equal(demandLoadState({selected,error:new RequestFailure('failed')}),'unavailable');
  assert.equal(demandLoadState({selected:'orders-v1'}),'loading');
  assert.equal(demandLoadState({listing:true}),'loading');
  assert.equal(demandLoadState({selected:'',outlook:null,error:''}),'setup');
  assert.equal(demandLoadState({outlook:{rows:[]},error:'A save failed'}),'ready');
});
test('expired orders direct readers to a planner, not a button they cannot use',()=>{
  const outlook={fresh:false,valid_until:'2026-10-07'};const original=structuredClone(outlook);
  const translate=(key,{date})=>key.replace('{{date}}',date);
  assert.match(orderReviewMessage(outlook,translate,true),/Use “Review orders”/);
  assert.match(orderReviewMessage(outlook,translate,false),/A planner must/);
  assert.equal(orderReviewMessage({...outlook,fresh:true},translate,false),'');
  assert.deepEqual(outlook,original);
});

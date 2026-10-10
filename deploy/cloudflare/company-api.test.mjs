import test from 'node:test';
import assert from 'node:assert/strict';
import {companyRoute,savedResponse} from './company-api.mjs';
import {companyScreenRequest} from './screen-gateway.mjs';
const who={permissions:['reports:read','reports:export'],subject:'reader',issuer:'https://forecast.vrolen.com',role:'viewer'};
const document={checked_at:new Date().toISOString(),timezone:'Asia/Tehran',views:{'/runs':{runs:[{run_id:'draft'}]},'/releases/report':{state:'awaiting_review',submitted_by:who}},
  report_views:{'/runs':{runs:[{run_id:'approved'}]},'/releases':{releases:[]}}};
test('Viewer projections never substitute draft content; expired projections fail closed',()=>{
  const url=new URL('https://forecast.vrolen.com/api/v1/runs');
  const entry=companyRoute('GET','/runs');
  assert.deepEqual(savedResponse(entry,url,document,who).body.runs,[{run_id:'approved'}]);
  assert.equal(savedResponse(companyRoute('GET','/runs/{id}'.replace('{id}','draft')),new URL(url+'/draft'),document,who).status,404);
  assert.equal(savedResponse(entry,url,{...document,checked_at:'2000-01-01'},who).status,409);
  assert.equal(companyRoute('GET','/../runs'),null);
  assert.equal(companyRoute('GET','/releases/report/export?kind=csv&ignored=yes'),null);
});
test('approval buttons use current actor, scopes and role; own submission cannot be approved',()=>{
  const entry=companyRoute('GET','/releases/report'),url=new URL('https://forecast.vrolen.com/api/v1/releases/report');
  const planner={...who,permissions:['drafts:read','releases:approve'],role:'approver'};
  assert.equal(savedResponse(entry,url,document,planner).body.can_approve,false);
  assert.equal(savedResponse(entry,url,document,{...planner,subject:'another-reviewer'}).body.can_approve,true);
  assert.equal(savedResponse(entry,url,document,{...planner,subject:'another-reviewer',role:'viewer'}).body.can_approve,false);
});
test('private screen gateway forwards exact revision/body, not caller-selected company; rejects unsigned session changes',async()=>{
  let captured;
  const storage={companyApi:async(...args)=>{captured=args;return Response.json({ok:true});},companyApiResult:async(_,id)=>Response.json({id})};
  const url='https://forecast.vrolen.com/api/v1/customers';
  const headers={origin:'https://forecast.vrolen.com','X-Company-Revision':'a'.repeat(32),'X-Company-Request':'stable-command','content-type':'application/json'};
  const make=()=>new Request(url,{method:'POST',headers,body:'{"customer":"Mehr"}'});
  assert.equal((await companyScreenRequest(storage,{cookie:'test-only'},make())).status,403);
  await companyScreenRequest(storage,{cookie:'test-only'},make(),async()=>true);
  assert.equal(captured[2],'stable-command');assert.equal(captured[3],'a'.repeat(32));
  assert.equal(captured[1].headers.get('content-length'),'19');
  assert.equal(await captured[1].text(),'{"customer":"Mehr"}');
  const response=await companyScreenRequest(storage,{},new Request('https://forecast.vrolen.com/api/v1/cloud/operations/'+'b'.repeat(32)));
  assert.equal((await response.json()).id,'b'.repeat(32));
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {configureCloudTransport,cloudFetch} from './cloud-transport.mjs';
import {requestJSON} from './request-errors.mjs';
const access=subject=>({mode:'better_auth',transport:'cloud',user:{issuer:'https://forecast.vrolen.com',company_id:'tehran-a',subject,role:'planner',permissions:['customers:write']}});
const revision='a'.repeat(32),operation='b'.repeat(32),next='c'.repeat(32);
test('one cloud write, saved polling and exact completed response; local mode unchanged',async()=>{
  configureCloudTransport(access('planner'));
  const calls=[];
  const fetcher=async(url,options)=>{
    calls.push([url,options]);
    if(url.endsWith('/revision'))return Response.json({revision});
    if(url.endsWith('/customers'))return Response.json({id:operation,state:'queued'},{status:202,headers:{'X-Company-Operation':operation}});
    return Response.json({customer:'Mehr'},{status:201,headers:{'X-Company-Revision':next}});
  };
  const response=await cloudFetch('/api/v1/customers',{method:'POST',body:'{"customer":"Mehr"}'},fetcher,{pause:async()=>{}});
  assert.equal(response.status,201);assert.equal((await response.json()).customer,'Mehr');
  assert.equal(calls.filter(([,o])=>o.method==='POST').length,1);
  assert.equal(calls[1][1].headers.get('X-Company-Revision'),revision);
  assert.equal(calls[2][0],'/api/v1/cloud/operations/'+operation);
  configureCloudTransport({mode:'local'});
  assert.deepEqual(await requestJSON('/local',undefined,undefined,{fetcher:async()=>Response.json({ok:true})}),{ok:true});
});
test('final business 202 is not mistaken for another cloud operation',async()=>{
  configureCloudTransport(access('new-planner'));
  let n=0;
  const response=await cloudFetch('/api/v1/forecasts',{method:'POST'},async()=>{
    n++;return n===1?Response.json({revision:null}):n===2?Response.json({id:operation},{status:202,headers:{'X-Company-Operation':operation}}):Response.json({id:'group',jobs:[]},{status:202});
  },{pause:async()=>{}});
  assert.equal(n,3);assert.equal((await response.json()).id,'group');configureCloudTransport(null);
});
test('lost write response never replays; user changes stop in-flight polling',async()=>{
  configureCloudTransport(access('one'));
  let writes=0;
  await assert.rejects(()=>cloudFetch('/api/v1/customers',{method:'POST'},async(url)=>{
    if(url.endsWith('/revision'))return Response.json({revision});writes++;throw Error('offline');
  }));assert.equal(writes,1);
  await assert.rejects(()=>cloudFetch('/api/v1/customers',{method:'POST'},async()=>Response.json({id:operation},{status:202,headers:{'X-Company-Operation':operation}}),
    {pause:async()=>configureCloudTransport(access('two'))}),/session changed/);
  configureCloudTransport(null);
});
test('exports retain binary bytes and attachment headers, not JSON wrappers',async()=>{
  configureCloudTransport(access('exporter'));let n=0;
  const response=await cloudFetch('/api/v1/releases/report/export?kind=xlsx',{method:'GET'},async()=>{
    n++;return n===1?Response.json({revision}):n===2?Response.json({id:operation},{status:202,headers:{'X-Company-Operation':operation}}):
      new Response(new Uint8Array([80,75,1,2]),{headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','Content-Disposition':'attachment; filename="report.xlsx"'}});
  },{pause:async()=>{}});
  assert.deepEqual([...new Uint8Array(await response.arrayBuffer())],[80,75,1,2]);assert.match(response.headers.get('Content-Disposition'),/report.xlsx/);configureCloudTransport(null);
});

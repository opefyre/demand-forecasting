import test from 'node:test';
import assert from 'node:assert/strict';
import {allowedRequest,publicAddress,NetworkBroker,networkFailureReason} from './network-broker.mjs';
const jsonBody=value=>Buffer.from(JSON.stringify(value)).toString('base64');
function fixture(path='/connections/inputs/abc/fetch') {
  const values=new Map(),calls=[];
  const job={kind:'api',company_id:'tehran_a',job_id:'1'.repeat(32),attempt:'2'.repeat(32),deadline:Date.now()+60000,
    payload:{method:'POST',path,principal:{subject:'owner',company_id:'tehran_a',issuer:'https://forecast.vrolen.com',required_scopes:['connections:sync']},
      _cloud_ai:{models:{query:'test-query',title:'test-title'}}}};
  values.set('active',{attempt:job.attempt});
  let block=Promise.resolve();
  const ctx={storage:{get:async k=>values.get(k),put:async(k,v)=>typeof k==='object'?Object.entries(k).forEach(([a,b])=>values.set(a,b)):values.set(k,v)},
    blockConcurrencyWhile(fn){const result=block.then(fn);block=result.catch(()=>{});return result;}};
  const env={IDENTITY:{operation:async()=>({status:200,body:{allowed:true,permissions:['connections:sync']}})},STORAGE:{authorizeAttempt:async()=>true},
    AI_ENABLED:'true',AI_ELIGIBILITY_CONFIRMED:'true',OPENAI_API_KEY:'synthetic-provider-key'}; // pragma: allowlist secret - test fake
  const fetcher=async(url,options)=>{calls.push([url,options]);return url.startsWith('https://cloudflare-dns.com/')?
    Response.json({Answer:[{type:1,data:'8.8.8.8'}]}):Response.json({ok:true});};
  const broker=new NetworkBroker(ctx,env,job,{fetcher});
  return {broker,job,env,values,calls,ctx};
}
const http={kind:'http',category:'connection',config:{provider:'http',url:'https://erp.example/export.json'},url:'https://erp.example/export.json',method:'GET',body:''};
test('default transport never invokes the Worker fetch global with the broker as receiver',async()=>{
  const original=globalThis.fetch,f=fixture();let calls=0;
  globalThis.fetch=function(url){assert.notEqual(this,f.broker);calls++;return Promise.resolve(url.includes('dns-query')?Response.json({Answer:[{type:1,data:'8.8.8.8'}]}):Response.json({ok:true}));};
  try{
    f.broker=new NetworkBroker(f.ctx,f.env,f.job);
    assert.equal((await f.broker.exchange(http)).status,200);assert.equal(calls,2);
  }finally{globalThis.fetch=original;}
});
test('private network diagnostics expose only controlled failure categories, never exception contents',async()=>{
  assert.equal(networkFailureReason(new Error('private credential and URL')),'unavailable');
  const f=fixture();f.env.IDENTITY.operation=async()=>({status:200,body:{allowed:false}});
  await assert.rejects(f.broker.exchange(http),error=>networkFailureReason(error)==='access');
  const dns=fixture();dns.broker.fetcher=async()=>Response.json({Answer:[]});
  await assert.rejects(dns.broker.exchange(http),error=>networkFailureReason(error)==='dns');
  assert.equal(f.calls.length,0);
});
test('connection reads match the exact configuration and reject private, alternate or write destinations',async()=>{
  const f=fixture();assert.equal(allowedRequest(f.job,http),true);
  for(const change of [{url:'http://erp.example/export.json'},{url:'https://erp.example/other'}, {method:'POST'}, {url:'https://u:p@erp.example/export.json'},{url:'https://erp.example/export.json#fragment'}])
    assert.equal(allowedRequest(f.job,{...http,...change}),false);
  assert.equal(allowedRequest(f.job,{}),false);
  for(const ip of ['127.0.0.1','10.1.2.3','169.254.169.254','192.168.1.1','100.64.0.1','198.18.0.1','203.0.113.1','::1','01.2.3.4'])assert.equal(publicAddress(ip),false);
  assert.equal(publicAddress('8.8.8.8'),true);
  for(const host of ['localhost','localhost.local','127.0.0.1','10.1.2.3'])await assert.rejects(f.broker.publicHost(host));
  f.broker.fetcher=async()=>Response.json({Answer:[{type:1,data:'8.8.8.8'},{type:1,data:'127.0.0.1'}]});
  await assert.rejects(f.broker.publicHost('erp.example'));
});
test('all five Odoo read models work in both supported versions; creation and arbitrary RPC do not',()=>{
  const f=fixture();
  for(const model of ['res.partner','sale.order','sale.order.line','product.product','uom.uom']){
    const config={provider:'odoo19',url:'https://odoo.example'};
    assert.equal(allowedRequest(f.job,{...http,config,method:'POST',url:config.url+'/json/2/'+model+'/search_read'}),true);
    assert.equal(allowedRequest(f.job,{...http,config,method:'POST',url:config.url+'/json/2/'+model+'/create'}),false);
    config.provider='odoo18';
    assert.equal(allowedRequest(f.job,{...http,config,method:'POST',url:config.url+'/jsonrpc',body:jsonBody({method:'call',params:{service:'object',method:'execute_kw',args:['db',1,'key',model,'search_read']}})}),true);
    assert.equal(allowedRequest(f.job,{...http,config,method:'POST',url:config.url+'/jsonrpc',body:jsonBody({method:'call',params:{service:'object',method:'execute_kw',args:['db',1,'key',model,'unlink']}})}),false);
  }
});
test('Sheets limits the token and values endpoints to the configured spreadsheet',()=>{
  const f=fixture(),config={provider:'sheets',spreadsheet_id:'one'};
  assert.equal(allowedRequest(f.job,{...http,config,url:'https://oauth2.googleapis.com/token',method:'POST'}),true);
  assert.equal(allowedRequest(f.job,{...http,config,url:'https://sheets.googleapis.com/v4/spreadsheets/one/values/A1'}),true);
  assert.equal(allowedRequest(f.job,{...http,config,url:'https://sheets.googleapis.com/v4/spreadsheets/two/values/A1'}),false);
});
test('fixed live providers are available only to external-source actions',()=>{
  const f=fixture('/connections/external-sources/supply/refresh');
  for(const url of ['https://servix.cc/api/v1/assets/supported','https://hormuz.now/api/daily.json',
    'https://api.worldbank.org/v2/country/IRN/indicator/FP.CPI.TOTL.ZG?format=json',
    'https://www.newyorkfed.org/medialibrary/research/interactives/data/gscpi/gscpi_interactive_data.csv',
    'https://api.imf.org/external/sdmx/2.1/data/IMF.STA,CPI,5.0.0/IRN.CPI._T.IX.M?format=csvfile'])
    assert.equal(allowedRequest(f.job,{...http,category:'source',url}),true,url);
  assert.equal(allowedRequest(f.job,{...http,category:'source',url:'https://www.newyorkfed.org/medialibrary/other'}),false);
  f.job.payload.path='/customers';assert.equal(allowedRequest(f.job,{...http,category:'source',url:'https://hormuz.now/api/daily.json'}),false);
});
test('live permission, cancellation, attempt and revision checks happen before any outbound call',async()=>{
  for(const change of ['identity','ledger','attempt','deadline']){
    const f=fixture();
    if(change==='identity')f.env.IDENTITY.operation=async()=>({status:200,body:{allowed:false}});
    if(change==='ledger')f.env.STORAGE.authorizeAttempt=async()=>false;
    if(change==='attempt')f.values.set('active',{attempt:'other'});
    if(change==='deadline')f.job.deadline=Date.now()-1;
    await assert.rejects(f.broker.exchange(http));assert.equal(f.calls.length,0);
  }
});
test('outbound HTTP removes ambient headers, bounds content and never follows redirects',async()=>{
  const f=fixture();await f.broker.exchange({...http,headers:{cookie:'private',host:'bad',authorization:'Bearer approved'}});
  const options=f.calls.at(-1)[1];assert.equal(options.redirect,'manual');assert.equal(options.headers.has('cookie'),false);
  assert.equal(options.headers.get('authorization'),'Bearer approved');
  f.broker.fetcher=async url=>url.includes('dns-query')?Response.json({Answer:[{type:1,data:'8.8.8.8'}]}):new Response(null,{status:302,headers:{location:'http://localhost'}});
  await assert.rejects(f.broker.exchange(http));
  await assert.rejects(f.broker.exchange({...http,body:Buffer.alloc(1024*1024+1).toString('base64')}));
});
test('AI uses configured task models, strips foreign billing headers and reserves calls durably before sending',async()=>{
  const f=fixture('/ai/chat'),item={kind:'http',category:'ai',method:'POST',url:'https://api.openai.com/v1/responses',
    body:jsonBody({model:'test-query',store:false}),headers:{authorization:'not-real','openai-project':'foreign'}};
  await Promise.all(Array.from({length:6},()=>f.broker.exchange(item)));
  await assert.rejects(f.broker.exchange(item));assert.equal(f.calls.length,6);
  assert.equal(f.calls[0][1].headers.get('authorization'),'Bearer synthetic-provider-key');
  assert.equal(f.calls[0][1].headers.has('openai-project'),false);
  for(const body of [{model:'other',store:false},{model:'test-query',store:true},{model:'test-query',store:false,stream:true}])await assert.rejects(f.broker.exchange({...item,body:jsonBody(body)}));
  for(const setting of ['AI_ENABLED','AI_ELIGIBILITY_CONFIRMED']){
    f.env[setting]='false';await assert.rejects(f.broker.exchange(item));f.env[setting]='true';
  }
  assert.equal(f.calls.length,6,'No rejected request reaches the provider');
});
test('scheduled identity relay is company-bound and notification endpoints are limited',()=>{
  const f=fixture('/notifications/check');
  const item={kind:'identity',operation:'schedules/authorize',body:{company_id:'tehran_a',issuer:'https://forecast.vrolen.com',subject:'owner'}};
  assert.equal(allowedRequest(f.job,item),true);assert.equal(allowedRequest(f.job,{...item,body:{...item.body,company_id:'tehran_b'}}),false);
  const retry=fixture('/jobs/one/retry');assert.equal(allowedRequest(retry.job,item),true);
  retry.job.payload.method='GET';assert.equal(allowedRequest(retry.job,item),false);
  assert.equal(allowedRequest(f.job,{...http,category:'notification',method:'POST',url:'https://hooks.slack.com/services/one/two/three'}),true);
  assert.equal(allowedRequest(f.job,{...http,category:'notification',method:'POST',url:'https://hooks.slack.com/arbitrary'}),false);
});
test('SFTP pins public IP, bounds socket count and closes the socket at the end',async()=>{
  const f=fixture();let target,closed=0;
  f.broker.connector=(address)=>{target=address;return{opened:Promise.resolve(),readable:new ReadableStream({start(c){c.enqueue(new Uint8Array([1,2,3]));c.close();}}),
    writable:new WritableStream({write(){}}),close:async()=>{closed++;}};};
  const item={kind:'tcp-open',config:{provider:'sftp',host:'sftp.example',port:22}};
  const result=await f.broker.exchange(item);assert.deepEqual(target,{hostname:'8.8.8.8',port:22});
  await assert.rejects(f.broker.exchange(item));
  const read=await f.broker.exchange({kind:'tcp-read',socket_id:result.socket_id,size:2});
  assert.deepEqual([...Buffer.from(read.body,'base64')],[1,2]);
  await f.broker.close();assert.equal(closed,1);assert.equal(f.broker.sockets.size,0);
});

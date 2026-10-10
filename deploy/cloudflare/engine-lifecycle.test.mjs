import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { CloudEngineController } from './engine-lifecycle.mjs';

// Cloudflare's fixed-size stream, emulated only in Node unit tests.
globalThis.FixedLengthStream=class extends TransformStream {
  constructor(size) {let seen=0;super({transform(chunk,ctl){seen+=chunk.byteLength;if(seen>size)throw new Error('length');ctl.enqueue(chunk);},flush(){if(seen!==size)throw new Error('length');}});}
};
function fixture({badResponse=false,backupFailure=false,badSize=false,startFailure=false,apiStatus=null,apiRead=false}={}) {
  const values=new Map(),objects=new Map(),backup=new Map(),events=[];
  const job={company_id:'company-a',job_id:'1'.repeat(32),attempt:'2'.repeat(32),object_key:'companies/company-a/revisions/'+ '3'.repeat(32)+'.zip',deadline:Date.now()+60000,payload:{}};
  const response=(text,type='application/octet-stream')=>new Response(text,{headers:{'content-type':type,'content-length':String(Buffer.byteLength(text)+(badSize?1:0))}});
  const bucket=map=>({get:async key=>map.has(key)?{body:new Response(map.get(key)).body}:null,
    put:async(key,body)=>{if(map===backup && backupFailure)throw new Error('backup');if(map.has(key))return null;map.set(key,new Uint8Array(await new Response(body).arrayBuffer()));events.push('saved:'+key);return {key};}});
  objects.set(job.object_key,new Uint8Array([1,2,3]));
  const ctx={storage:{get:async key=>values.get(key),put:async(key,value)=>values.set(key,value),delete:async key=>values.delete(key),setAlarm:async date=>values.set('alarm',date),deleteAlarm:async()=>values.delete('alarm')},
    blockConcurrencyWhile:async fn=>fn(),container:{running:false,images:{base:'test-image'},start(options){events.push(['start',options]);if(startFailure)throw new Error('start');this.running=true;},destroy:async()=>{events.push('destroy');ctx.container.running=false;},
    setInactivityTimeout:async ms=>events.push(['idle',ms]),getTcpPort:()=>({fetch:async(url,options)=>{
      if(url.endsWith('/ready'))return new Response('ready');
      if(url.endsWith('/forecast'))return badResponse?new Response(null,{status:500}):Response.json({job_id:job.attempt,company_id:job.company_id,run_id:'4'.repeat(12),artifacts:['result.json','forecast.csv']});
      if(url.endsWith('/api-operation'))return Response.json({job_id:job.attempt,company_id:job.company_id,run_id:job.attempt,
        api_status:apiStatus,artifacts:apiRead?['api-response.json','api-download.bin']:apiStatus<300?['api-response.json','company-view.json']:['api-response.json']});
      if(options?.method==='DELETE'){events.push('cleanup');return new Response(null,{status:204});}
      if(url.endsWith('/snapshot'))return response('checkpoint','application/zip');
      return response('result','application/json');
    }})}};
  const env={PRIVATE_ACCESS:'closed',COMPANY_VAULT_KEY:'ab'.repeat(32),FILES:bucket(objects),BACKUPS:bucket(backup)};
  return {controller:new CloudEngineController(ctx,env),ctx,env,job,events,objects,backup,values};
}
test('cold status does not wake; successful work is durable before it becomes idle',async()=>{
  const f=fixture();assert.deepEqual(await f.controller.status(),{running:false,busy:false,idle_timeout_ms:300000});assert.equal(f.events.length,0);
  const result=await f.controller.execute(f.job);
  const started=f.events.find(e=>e[0]==='start')[1];assert.deepEqual(started.instance,{vcpu:0.25,memoryMib:1024,diskMb:4000});assert.equal(started.enableInternet,false);assert.equal(started.env.DEMANDLAB_COMPANY_VAULT_KEY,f.env.COMPANY_VAULT_KEY);
  assert.ok(f.events.some(e=>e[0]==='idle' && e[1]===300000));assert.equal(f.backup.size,1);assert.equal(f.objects.has(result.artifacts['result.json']),true);assert.equal(f.events.at(-1),'cleanup');assert.equal(f.values.has('active'),false);
  assert.ok(f.values.get('idle_until')>Date.now());assert.equal(f.values.get('alarm'),f.values.get('idle_until'));
  assert.equal((await f.controller.status()).busy,false);assert.equal(f.events.filter(e=>e[0]==='start').length,1);
  await f.controller.execute({...f.job,attempt:'5'.repeat(32),job_id:'6'.repeat(32)}).catch(()=>{});
  assert.equal(f.events.filter(e=>e[0]==='start').length,1,'warm instance reused without a pool');
});
test('a busy engine rejects a second caller without destroying the active attempt',async()=>{
  const f=fixture();f.ctx.container.running=true;f.values.set('active',{attempt:'9'.repeat(32),deadline:Date.now()+60000});
  await assert.rejects(f.controller.execute(f.job),/busy/);assert.equal(f.ctx.container.running,true);assert.equal(f.events.includes('destroy'),false);assert.equal(f.values.get('active').attempt,'9'.repeat(32));
});
for(const apiStatus of [201,422])test('company API '+apiStatus+' saves its response and promotes only successful changes',async()=>{
  const f=fixture({apiStatus});
  const bodyKey='companies/company-a/requests/'+'7'.repeat(64);
  f.objects.set(bodyKey,new Uint8Array([1,2,3]));
  const result=await f.controller.execute({...f.job,kind:'api',object_key:null,payload:{body_key:bodyKey}});
  assert.equal(result.api_status,apiStatus);
  assert.ok(f.objects.has(result.artifacts['api-response.json']));
  assert.equal(f.backup.size,apiStatus<300?1:0);
  assert.equal(result.object_key===null,apiStatus>=300);
  assert.equal(f.events.at(-1),'cleanup');
});
test('deadline alarm stops abandoned work and clears its lease',async()=>{
  const f=fixture();f.ctx.container.running=true;f.values.set('active',{attempt:f.job.attempt,deadline:Date.now()-1});f.values.set('alarm',1);
  await f.controller.alarm();assert.equal(f.ctx.container.running,false);assert.equal(f.values.size,0);
});
test('read-only exports save binary artifacts without a checkpoint or backup revision',async()=>{
  const f=fixture({apiStatus:200,apiRead:true}),bodyKey='companies/company-a/requests/'+'7'.repeat(64);
  f.objects.set(bodyKey,new Uint8Array());
  const result=await f.controller.execute({...f.job,kind:'api',payload:{method:'GET',body_key:bodyKey}});
  assert.equal(result.object_key,null);assert.equal(f.backup.size,0);assert.ok(result.artifacts['api-download.bin']);
});
test('alarm preserves bounded active work until its deadline',async()=>{
  const f=fixture();f.ctx.container.running=true;f.values.set('active',{attempt:f.job.attempt,deadline:f.job.deadline});
  await f.controller.alarm();assert.equal(f.ctx.container.running,true);assert.equal(f.values.get('alarm'),f.job.deadline);
});
test('status inspection cannot extend durable idle shutdown; alarm never wakes a cold engine',async()=>{
  const f=fixture();await f.controller.execute(f.job);const idle=f.values.get('idle_until');
  await f.controller.status();await f.controller.status();assert.equal(f.values.get('idle_until'),idle);
  await f.controller.alarm();assert.equal(f.ctx.container.running,true);assert.equal(f.values.get('alarm'),idle);
  f.values.set('idle_until',Date.now()-1);await f.controller.alarm();
  assert.equal(f.ctx.container.running,false);assert.equal(f.values.size,0);
  await f.controller.alarm();assert.equal(f.events.filter(e=>e[0]==='start').length,1);
});
test('warm constructor preserves an existing idle deadline across DO eviction',async()=>{
  const f=fixture();f.ctx.container.running=true;const idle=Date.now()+10000;f.values.set('idle_until',idle);
  new CloudEngineController(f.ctx,f.env);await new Promise(resolve=>setImmediate(resolve));
  assert.equal(f.values.get('idle_until'),idle);assert.equal(f.values.get('alarm'),idle);
});
for(const option of ['badResponse','backupFailure','badSize','startFailure'])test(option+' fails closed, stops compute and never returns a saved result',async()=>{
  const f=fixture({[option]:true});await assert.rejects(f.controller.execute(f.job));assert.equal(f.ctx.container.running,false);assert.equal(f.values.size,0);
});
test('privacy and secret configuration are checked before startup',async()=>{
  for(const change of [{PRIVATE_ACCESS:'open'},{COMPANY_VAULT_KEY:''}]){
    const f=fixture();Object.assign(f.env,change);await assert.rejects(f.controller.execute(f.job),/configuration/);assert.equal(f.events.length,0);
  }
});
test('engine configuration has no public routes, timers or unrelated resources',async()=>{
  const config=JSON.parse(await readFile(new URL('./engine.wrangler.jsonc',import.meta.url),'utf8'));
  assert.equal(config.name,'demandlab-forecast-engine');assert.equal(config.account_id,'b53df72f41f5135daf312100e73ff6a1');
  assert.equal(config.workers_dev,false);assert.equal(config.preview_urls,false);assert.deepEqual(config.routes,[]);assert.equal(config.vars.PRIVATE_ACCESS,'closed');
  assert.equal(config.observability.enabled,false);assert.equal(config.containers.length,1);assert.equal(config.containers[0].scheduling_policy,'durable_object');
  assert.deepEqual(config.r2_buckets.map(x=>x.bucket_name),['demandlab-forecast-files','demandlab-forecast-backups']);
  assert.equal(config.triggers,undefined);assert.deepEqual(config.services.map(s=>s.service),['demandlab-forecast-identity','demandlab-forecast-storage']);assert.equal(config.d1_databases,undefined);
  assert.equal(config.vars.AI_ENABLED,'false');assert.equal(config.vars.AI_ELIGIBILITY_CONFIRMED,'false');
});
test('private relay mediates one source request, preserves failed-source state and remains offline',async()=>{
  const f=fixture(),bodyKey='companies/company-a/requests/'+'7'.repeat(64);f.objects.set(bodyKey,new Uint8Array([1]));
  const job={...f.job,kind:'api',object_key:null,payload:{method:'POST',path:'/connections/external-sources/industry/refresh',body_key:bodyKey,
    principal:{subject:'owner',required_scopes:['connections:sync'],permissions:['connections:sync']}}};
  f.env.IDENTITY={operation:async()=>({status:200,body:{allowed:true,permissions:['connections:sync']}})};
  f.env.STORAGE={authorizeAttempt:async()=>true};
  let delivered=false,answered,finish;
  const original=f.ctx.container.getTcpPort().fetch;
  f.ctx.container.getTcpPort=()=>({fetch:async(url,options)=>{
    if(url.endsWith('/next')){if(delivered)return Response.json({request:null});delivered=true;return Response.json({request:{id:'relay',kind:'http',category:'source',
      url:'https://api.worldbank.org/v2/country/IRN/indicator/NV.IND.TOTL.KD.ZG?format=json',method:'GET',body:''}});}
    if(url.endsWith('/relay')){answered=JSON.parse(options.body);finish?.();return Response.json({saved:true});}
    if(url.endsWith('/api-operation')){if(!answered)await new Promise(resolve=>{finish=resolve;});return Response.json({job_id:job.attempt,company_id:job.company_id,
      run_id:job.attempt,api_status:502,committed:true,artifacts:['api-response.json','company-view.json','company-schedules.json']});}
    return original(url,options);
  }});
  const requests=[],fetcher=async url=>{requests.push(url);return url.includes('dns-query')?Response.json({Answer:[{type:1,data:'8.8.8.8'}]}):new Response('unavailable',{status:503});};
  const controller=new CloudEngineController(f.ctx,f.env,{fetcher}),result=await controller.execute(job);
  assert.equal(answered.status,503);assert.equal(requests.length,2);assert.equal(result.api_status,502);assert.equal(result.committed,true);
  assert.equal(f.backup.size,1);assert.ok(result.artifacts['company-schedules.json']);
  assert.equal(f.events.find(e=>e[0]==='start')[1].enableInternet,false);
  assert.equal((await controller.status()).busy,false);
});

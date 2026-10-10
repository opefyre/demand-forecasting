import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';
type Fetcher={fetch(url:string,options?:RequestInit):Promise<Response>};

test('cloud storage is private and binds only the new forecast resources',async()=>{
  const config=JSON.parse(await readFile(new URL('../../deploy/cloudflare/storage.wrangler.jsonc',import.meta.url),'utf8'));
  assert.equal(config.workers_dev,false);assert.equal(config.preview_urls,false);assert.deepEqual(config.routes,[]);
  assert.equal(config.vars.PRIVATE_ACCESS,'closed');assert.equal(config.observability.enabled,false);
  assert.deepEqual(config.r2_buckets.map((b:any)=>b.bucket_name),['demandlab-forecast-files','demandlab-forecast-backups']);
  assert.deepEqual(config.services.map((b:any)=>b.service),['demandlab-forecast-identity','demandlab-forecast-engine']);
  assert.ok(!config.triggers && !config.assets);
});

test('native company ledger: durable checkpoints, roles, deduplication, cancellation, restart and cold result reads',
  {timeout:60000,skip:!process.env.DEMANDLAB_TEST_CLOUD_STORAGE},async()=>{
  // No Docker/real credentials/network. The engine and identity are explicit
  // service-bound TEST doubles; the actual R2/SQLite/alarms run in workerd.
  const directory=await import('node:os').then(os=>os.tmpdir());
  const fs=await import('node:fs/promises');
  const persistent=await fs.mkdtemp(directory+'/forecast-native-test-');
  const callerScript=`export default {async fetch(req,env) {
    const data=await req.json(),cred=data.credentials;
    if(data.op==='stage')return Response.json(await env.STORAGE.stageWorkspace(cred,data.revision??null,
      new Request('http://private.test/',{method:'POST',body:'synthetic-checkpoint',headers:{'content-length':'20'}})));
    if(data.op==='submit')return Response.json(await env.STORAGE.submit(cred,data.payload,data.request_id));
    if(data.op==='jobs')return Response.json(await env.STORAGE.jobs(cred));
    if(data.op==='cancel')return Response.json(await env.STORAGE.cancel(cred,data.id));
    if(data.op==='artifact')return env.STORAGE.artifact(cred,data.id,data.name);
    // Test-only alarm trigger. No such RPC exists on production entrypoint.
    if(data.op==='drain') {await env.LEDGER.get(env.LEDGER.idFromName('forecast-cloud-v1')).drainForTest();return Response.json({done:true});}
    if(data.op==='engine_count')return Response.json(await env.ENGINE.count());
  }};`;
  const identityScript=`import{WorkerEntrypoint}from'cloudflare:workers';
    export class Identity extends WorkerEntrypoint {async operation(op,body) {
      if(op==='work/authorize')return {status:200,body:{allowed:body.subject!=='revoked'}};
      const company=body.company_id,role=body.role;
      const scopes={admin:['settings:manage','forecasts:run','forecasts:write','reports:export','drafts:read'],
        planner:['forecasts:run','forecasts:write','reports:export','drafts:read'],approver:['drafts:read','reports:export'],viewer:['reports:read']};
      if(!['tehran_a','tehran_b'].includes(company)||!scopes[role])return{status:401,body:{}};
      return{status:200,body:{issuer:'https://forecast.vrolen.com',company_id:company,role,subject:body.subject||role,
        auth_kind:'session',session_id:'test-only',mfa_required:!!body.mfa_required,permissions:scopes[role]}};
    }}export default{fetch(){return new Response(null,{status:404});}};`;
  const engineScript=`import{WorkerEntrypoint}from'cloudflare:workers';let calls=0;
    export class Engine extends WorkerEntrypoint {async count(){return calls;}async execute(job){calls++;
      const key='companies/'+job.company_id+'/revisions/'+job.attempt+'.zip';
      // Short pause lets cancellation enter while a real DO request is pending.
      if(job.payload.method==='cancel-test')await new Promise(resolve=>setTimeout(resolve,100));
      if(job.payload.method==='failure-test')throw new Error('Sensitive provider exception');
      await this.env.FILES.put(key,'synthetic-completed-checkpoint');
      await this.env.BACKUPS.put(key,'synthetic-completed-checkpoint');
      const file='companies/'+job.company_id+'/outputs/'+job.job_id+'/'+job.attempt+'/result.json';
      await this.env.FILES.put(file,JSON.stringify({company:job.company_id,total:49}));
      return{company_id:job.company_id,attempt:job.attempt,run_id:'abcdef123456',object_key:key,artifacts:{'result.json':file}};
    }}export default{fetch(){return new Response(null,{status:404});}};`;
  const build=(await readFile(new URL('../../deploy/cloudflare/build/storage/cloud-storage.js',import.meta.url),'utf8')) +
    '\nForecastCloud.prototype.drainForTest=async function(){return this.alarm();};';
  const options:any={telemetry:{enabled:false},resourcePersistencePath:persistent,workers:[
    {name:'storage',modules:true,compatibilityDate:'2026-10-09',script:build,
      bindings:{PRIVATE_ACCESS:'closed'},durableObjects:{CLOUD:{className:'ForecastCloud',useSQLite:true}},r2Buckets:{FILES:'files',BACKUPS:'backups'},
      serviceBindings:{IDENTITY:{name:'identity-test',entrypoint:'Identity'},ENGINE:{name:'engine-test',entrypoint:'Engine'}}},
    {name:'identity-test',modules:true,compatibilityDate:'2026-10-09',script:identityScript},
    {name:'engine-test',modules:true,compatibilityDate:'2026-10-09',script:engineScript,r2Buckets:{FILES:'files',BACKUPS:'backups'}},
    {name:'test-only-caller',modules:true,compatibilityDate:'2026-10-09',script:callerScript,
      durableObjects:{LEDGER:{className:'ForecastCloud',scriptName:'storage',useSQLite:true}},
      serviceBindings:{STORAGE:{name:'storage',entrypoint:'ForecastStorage'},ENGINE:{name:'engine-test',entrypoint:'Engine'}}},
  ]};
  let runtime=new Miniflare(convertV4MiniflareOptions(options));
  try {
    let caller=await runtime.getWorker('test-only-caller') as unknown as Fetcher;
    const call=async(data:any)=>(await(await caller.fetch('http://local.test/',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(data)})).json())as any;
    const admin={company_id:'tehran_a',role:'admin'},planner={company_id:'tehran_a',role:'planner'},other={company_id:'tehran_b',role:'admin'};
    const payload={dataset_id:'a'.repeat(32),method:'model:Last observed'};
    const worker=await runtime.getWorker('storage') as unknown as Fetcher;
    for(const path of ['/','/api/v1/customers','/internal','/files'])assert.equal((await worker.fetch('http://local.test'+path)).status,404);
    assert.equal((await call({op:'stage',credentials:planner})).status,403);
    assert.equal((await call({op:'stage',credentials:{...admin,mfa_required:true}})).status,403);
    const first=await call({op:'stage',credentials:admin});assert.equal(first.status,200);
    assert.equal((await call({op:'stage',credentials:admin})).status,409);
    assert.equal((await call({op:'stage',credentials:other})).status,200);
    assert.equal((await call({op:'submit',credentials:{company_id:'tehran_a',role:'viewer'},payload,request_id:'viewer-request'})).status,403);
    const submitted=await Promise.all([1,2].map(()=>call({op:'submit',credentials:planner,payload,request_id:'same-request'})));
    assert.equal(submitted[0].status,202);assert.equal(submitted[1].status,202);assert.equal(submitted[0].body.id,submitted[1].body.id);
    assert.equal((await call({op:'submit',credentials:planner,payload:{...payload,method:'another'},request_id:'same-request'})).status,409);
    assert.equal((await call({op:'stage',credentials:admin,revision:first.body.revision})).status,409);
    await call({op:'drain'});
    const job=(await call({op:'jobs',credentials:planner})).body[0];assert.equal(job.state,'succeeded');
    const calls=await call({op:'engine_count'});
    assert.deepEqual(await call({op:'artifact',credentials:planner,id:job.id,name:'result.json'}),{company:'tehran_a',total:49});
    assert.equal((await call({op:'artifact',credentials:other,id:job.id,name:'result.json'})).detail,'Forecast result not found');
    assert.equal((await call({op:'artifact',credentials:{company_id:'tehran_a',role:'viewer'},id:job.id,name:'result.json'})).detail,'Your role does not allow this action');
    assert.equal(await call({op:'engine_count'}),calls); // Saved reads never wake compute.
    const cancelled=await call({op:'submit',credentials:planner,payload:{...payload,method:'cancel-test'},request_id:'cancel-request'});
    const draining=call({op:'drain'});
    await new Promise(resolve=>setTimeout(resolve,30));
    assert.equal((await call({op:'cancel',credentials:planner,id:cancelled.body.id})).body.state,'cancelled');
    await draining;
    assert.equal((await call({op:'artifact',credentials:planner,id:cancelled.body.id,name:'result.json'})).detail,'Forecast result not found');
    await call({op:'submit',credentials:{...planner,subject:'revoked'},payload,request_id:'revoked-request'});
    await call({op:'drain'});
    assert.equal((await call({op:'jobs',credentials:planner})).body.find((r:any)=>r.message?.startsWith('Access changed')).state,'failed');
    const pending=await call({op:'submit',credentials:other,payload,request_id:'restart-request'});
    await runtime.dispose();
    runtime=new Miniflare(convertV4MiniflareOptions(options));caller=await runtime.getWorker('test-only-caller') as unknown as Fetcher;
    const recovered=await call({op:'jobs',credentials:planner});
    assert.equal(recovered.body.find((row:any)=>row.id===job.id)?.state,'succeeded',JSON.stringify(recovered));
    assert.deepEqual(await call({op:'artifact',credentials:planner,id:job.id,name:'result.json'}),{company:'tehran_a',total:49});
    await call({op:'drain'});
    assert.equal((await call({op:'jobs',credentials:other})).body.find((r:any)=>r.id===pending.body.id).state,'succeeded');
  } finally {await runtime.dispose();await fs.rm(persistent,{recursive:true,force:true});}
});

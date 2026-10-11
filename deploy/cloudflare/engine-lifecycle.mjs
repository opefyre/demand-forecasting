import {NetworkBroker,networkFailureReason} from './network-broker.mjs';
import {companyRoute} from './company-api.mjs';
const ID=/^[a-f0-9]{32}$/,RUN=/^(?:[a-f0-9]{12}|[a-f0-9]{32})$/,COMPANY=/^[A-Za-z0-9_-]{1,128}$/;
const SLEEP_MS=5*60*1000;
function closed() { return new Response(null,{status:404,headers:{'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'}}); }

export class CloudEngineController {
  constructor(ctx,env,networkOptions={}) {
    this.ctx=ctx; this.env=env;
    this.networkOptions=networkOptions;
    if (ctx.container?.running) ctx.blockConcurrencyWhile(async()=>{
      await ctx.container.setInactivityTimeout(SLEEP_MS);
      // Platform inactivity starts after the DO becomes inactive, and status
      // requests can extend it. A durable deadline bounds idle cost independently.
      if(!await ctx.storage.get('active')) {
        const idle=await ctx.storage.get('idle_until') || Date.now()+SLEEP_MS;
        await ctx.storage.put('idle_until',idle);await ctx.storage.setAlarm(idle);
      }
    });
  }
  async execute(job) {
    const started=Date.now();let cold=false;
    if (this.env.PRIVATE_ACCESS!=='closed' || !COMPANY.test(job.company_id) || !ID.test(job.job_id) || !ID.test(job.attempt) ||
        (!(job.kind==='api' && job.object_key===null) && !job.object_key?.startsWith('companies/'+job.company_id+'/revisions/')) ||
        !Number.isSafeInteger(job.deadline) || job.deadline<=Date.now() || job.deadline>Date.now()+12*60*1000 ||
        !/^[a-f0-9]{64}$/.test(this.env.COMPANY_VAULT_KEY || '')) throw new Error('Private engine configuration unavailable');
    // Fixed singleton with a durable busy marker. No pool, random routing, warm
    // pings or in-container task scheduler. Expired attempts cannot publish.
    let claimError;
    await this.ctx.blockConcurrencyWhile(async()=>{ try {
      const active=await this.ctx.storage.get('active');
      if (active && active.deadline>Date.now()) throw new Error('Engine is busy');
      if (active) await this.ctx.container.destroy();
      // A controller deployment does not resize an already-warm container.
      // Replace only an idle, old allocation before claiming the next job.
      if (this.ctx.container.running && await this.ctx.storage.get('instance_profile')!=='cpu1-memory3') await this.ctx.container.destroy();
      await this.ctx.storage.put('active',{attempt:job.attempt,deadline:job.deadline});
      await this.ctx.storage.delete('idle_until');
      await this.ctx.storage.setAlarm(job.deadline);
      if (!this.ctx.container.running) { this.ctx.container.start({image:this.ctx.container.images.base,
        // CPU is metered by active use. Avoid throttling a serial mathematical
        // comparison. Cloudflare requires >=3 GiB memory per custom vCPU.
        instance:{vcpu:1,memoryMib:3072,diskMb:4000},enableInternet:false,
        env:{DEMANDLAB_COMPANY_VAULT_KEY:this.env.COMPANY_VAULT_KEY}});
        cold=true;
        await this.ctx.storage.put('instance_profile','cpu1-memory3');
      }
      // Do not await a VM-dependent operation inside the claim gate. During a
      // cold allocation it can outlive the gate and strand the busy marker.
      // The durable job alarm already bounds startup; set idle time once ready.
    } catch(error) {
      claimError=error;
      const current=await this.ctx.storage.get('active');
      if(current?.attempt===job.attempt) {
        if(this.ctx.container.running)await this.ctx.container.destroy();
        await this.ctx.storage.delete('active');await this.ctx.storage.delete('instance_profile');await this.ctx.storage.delete('idle_until');await this.ctx.storage.deleteAlarm();
      }
    } });
    if(claimError)throw claimError;
    const port=this.ctx.container.getTcpPort(8080);
    const request=async(path,options={})=>port.fetch('http://engine'+path,{...options,
      signal:options.signal||AbortSignal.timeout(Math.max(1,job.deadline-Date.now()))});
    let completed=false,relayStopped=false,relayTask=null,readyAt=null,startupExit=null;
    // start() validates options, but later VM/process failures are asynchronous.
    // Observe them without keeping the engine awake after this operation ends.
    const startupStopped=this.ctx.container.monitor?.().then(()=>{throw new Error('Engine stopped during startup');},error=>{
      if(Number.isSafeInteger(error?.exitCode))startupExit=error.exitCode;
      throw new Error('Engine startup failed');
    });
    startupStopped?.catch(()=>{});
    let failRelay;
    const relayFailure=new Promise((_,reject)=>{failRelay=reject;});
    // A relay failure stops its operation; it must not become an unhandled
    // promise or leave a credential-bearing request waiting until the deadline.
    relayFailure.catch(()=>{});
    const broker=new NetworkBroker(this.ctx,this.env,job,this.networkOptions);
    const save=async(key,response,limit=64*1024*1024)=>{
      const size=Number(response.headers.get('content-length'));
      if(!Number.isSafeInteger(size) || size<1 || size>limit)throw new Error('Invalid output size');
      const stream=new FixedLengthStream(size);
      const [,written]=await Promise.all([response.body.pipeTo(stream.writable),this.env.FILES.put(key,stream.readable,
        {onlyIf:{etagDoesNotMatch:'*'},httpMetadata:{contentType:response.headers.get('content-type') || 'application/octet-stream'}})]);
      if(!written)throw new Error('Output already exists');
    };
    try {
      // Loading the immutable company checkpoint need not wait for Python boot.
      // Observe rejection even if startup fails before this promise is awaited.
      const inputTask=job.object_key===null?Promise.resolve(null):this.env.FILES.get(job.object_key);
      inputTask.catch(()=>{});
      const bootLimit=Math.min(job.deadline,Date.now()+60000);
      while (true) {
        const readiness=request('/ready',{signal:AbortSignal.timeout(Math.max(1,Math.min(5000,bootLimit-Date.now())))});
        try { const ready=await (startupStopped?Promise.race([readiness,startupStopped]):readiness);if(ready.ok)break; }
        catch(error){if(error?.message==='Engine startup failed'||error?.message==='Engine stopped during startup')throw error;}
        if(Date.now()>=bootLimit)throw new Error('Engine did not start');
        await new Promise(resolve=>setTimeout(resolve,1000));
      }
      readyAt=Date.now();
      await this.ctx.container.setInactivityTimeout(SLEEP_MS);
      const input=await inputTask;
      if(job.object_key!==null && !input)throw new Error('Company inputs unavailable');
      if(job.kind==='api') {
        if(!job.payload?.body_key?.startsWith('companies/'+job.company_id+'/requests/'))throw new Error('Invalid company request');
        const body=await this.env.FILES.get(job.payload.body_key);
        if(!body || body.size>51*1024*1024)throw new Error('Company request unavailable');
        const staged=await request('/request/'+job.attempt,{method:'PUT',body:body.body});
        if(!staged.ok)throw new Error('Company request unavailable');
        job.payload._cloud_ai={enabled:this.env.AI_ENABLED==='true'&&this.env.AI_ELIGIBILITY_CONFIRMED==='true',
          configured:!!this.env.OPENAI_API_KEY,models:{query:this.env.AI_QUERY_MODEL || 'gpt-4.1-mini',
            review:this.env.AI_REVIEW_MODEL || 'gpt-4.1',decision:this.env.AI_DECISION_MODEL || 'o3',title:this.env.AI_TITLE_MODEL || 'gpt-4.1-nano'}};
        if(companyRoute(job.payload.method,job.payload.path)?.network) {
          // Poll ONLY while one explicit operation is executing, never while idle.
          relayTask=(async()=>{const pending=new Set();
            try{while(!relayStopped&&Date.now()<job.deadline){
              const next=await request('/network/'+job.attempt+'/next');
              const item=(await next.json()).request;
              if(item){
                const task=(async()=>{let answer;try{answer=await broker.exchange(item);
                  if(item.category==='source'){
                    const type=answer.headers?.['content-type']||'';
                    await this.ctx.storage.put('source_check',{status:answer.status,format:type.includes('json')?'json':type.includes('html')?'html':type.includes('spreadsheet')?'xlsx':'other',checked_at:new Date().toISOString()});
                    if(answer.status>=400)await this.ctx.storage.put('source_failure',{reason:'provider_http',status:answer.status,checked_at:new Date().toISOString()});
                    else await this.ctx.storage.delete('source_failure');
                  }
                }catch(error){
                  answer={error:true};
                  // Private owner diagnostic only: controlled code, no URL,
                  // headers, request/response body, credentials or exception text.
                  if(item.category==='source')await this.ctx.storage.put('source_failure',{
                    reason:networkFailureReason(error),checked_at:new Date().toISOString()});
                }
                  if(!relayStopped)await request('/network/'+job.attempt+'/'+item.id,{method:'PUT',body:JSON.stringify(answer)});
                })();pending.add(task);task.finally(()=>pending.delete(task)).catch(()=>{});
              }else await new Promise(resolve=>setTimeout(resolve,100));
            }}finally{await Promise.allSettled(pending);}
          })();
          relayTask.catch(()=>failRelay(new Error('Private network operation unavailable')));
        }
      }
      const calculationAt=Date.now();
      const operation=request(job.kind==='api'?'/api-operation':'/forecast',{method:'POST',body:input?.body || null,
        headers:{'x-forecast-job':JSON.stringify({company_id:job.company_id,job_id:job.attempt,payload:job.payload})}});
      const response=await Promise.race([operation,relayFailure]);
      if(!response.ok)throw new Error('Forecast calculation unavailable');
      const result=await response.json();
      const persistenceAt=Date.now();
      if(result.job_id!==job.attempt || result.company_id!==job.company_id || !RUN.test(result.run_id) ||
          !Array.isArray(result.artifacts) || !result.artifacts.includes(job.kind==='api'?'api-response.json':'result.json') || result.artifacts.length>100 ||
          result.artifacts.some(name=>typeof name!=='string' || !/^[a-zA-Z0-9_.-]{1,160}$/.test(name)))throw new Error('Invalid engine output');
      const root='companies/'+job.company_id+'/',key=root+'revisions/'+job.attempt+'.zip';
      const apiStatus=job.kind==='api'?result.api_status:undefined;
      const entry=job.kind==='api'?companyRoute(job.payload.method,job.payload.path):null;
      if(job.kind==='api' && (!Number.isInteger(apiStatus) || apiStatus<200 || apiStatus>=600 ||
          (apiStatus>=500&&!entry?.network)||
          ((apiStatus<300||result.committed===true) && job.payload.method!=='GET' && !result.artifacts.includes('company-view.json'))))throw new Error('Invalid company output');
      const publish=apiStatus===undefined || ((apiStatus<300||entry?.network&&result.committed===true)&&job.payload.method!=='GET');
      if(publish) {
        const snapshot=await request('/output/'+job.attempt+'/snapshot');
        if(!snapshot.ok)throw new Error('Checkpoint unavailable');
        await save(key,snapshot);
        const saved=await this.env.FILES.get(key);
        if(!saved || !await this.env.BACKUPS.put(key,saved.body,{onlyIf:{etagDoesNotMatch:'*'}}))throw new Error('Backup unavailable');
      }
      const artifacts={};
      for(let offset=0;offset<result.artifacts.length;offset+=3) {
        // Bound memory/network use, and settle every started write before
        // cleanup. A single failure still prevents ledger publication.
        const settled=await Promise.allSettled(result.artifacts.slice(offset,offset+3).map(async name=>{
          const file=await request('/output/'+job.attempt+'/artifact/'+encodeURIComponent(name));
          if(!file.ok)throw new Error('Output file unavailable');
          const object=root+'outputs/'+job.job_id+'/'+job.attempt+'/'+name;
          await save(object,file,name==='company-view.json'?12*1024*1024:64*1024*1024);
          return [name,object];
        }));
        const failure=settled.find(value=>value.status==='rejected');
        if(failure)throw failure.reason;
        for(const value of settled)artifacts[value.value[0]]=value.value[1];
      }
      if(Date.now()>=job.deadline)throw new Error('Forecast deadline exceeded');
      // Controlled numbers only; no company IDs, paths, credentials or inputs.
      await this.ctx.storage.put('last_timing',{kind:job.kind==='api'?'api':'forecast',cold,
        startup_ms:readyAt-started,input_ms:calculationAt-readyAt,
        calculation_ms:persistenceAt-calculationAt,persistence_ms:Date.now()-persistenceAt,
        total_ms:Date.now()-started,artifacts:result.artifacts.length});
      await this.ctx.storage.delete('last_failure');
      completed=true;
      return {company_id:job.company_id,attempt:job.attempt,run_id:result.run_id,
        object_key:publish?key:null,artifacts,...(apiStatus!==undefined?{api_status:apiStatus,committed:publish}:{})};
    } catch(error) {
      await this.ctx.storage.put('last_failure',{stage:readyAt===null?'startup':'execution',
        ...(startupExit!==null?{exit_code:startupExit}:{}),elapsed_ms:Date.now()-started});
      throw error;
    } finally {
      relayStopped=true;
      await broker.close();
      if(relayTask)await relayTask.catch(()=>{});
      await this.ctx.blockConcurrencyWhile(async()=>{
        const current=await this.ctx.storage.get('active');
        if(current?.attempt!==job.attempt)return;
        if(completed) { try { await request('/output/'+job.attempt,{method:'DELETE'}); }catch{} }
        else await this.ctx.container.destroy();
        await this.ctx.storage.delete('active');
        if(completed && this.ctx.container.running) {
          const idle=Date.now()+SLEEP_MS;
          await this.ctx.storage.put('idle_until',idle);await this.ctx.storage.setAlarm(idle);
        } else {
          await this.ctx.storage.delete('instance_profile');
          await this.ctx.storage.delete('idle_until');await this.ctx.storage.deleteAlarm();
        }
      });
    }
  }
  async alarm() {
    await this.ctx.blockConcurrencyWhile(async()=>{
    const active=await this.ctx.storage.get('active');
    if(active && active.deadline>Date.now()) { await this.ctx.storage.setAlarm(active.deadline);return; }
    const idle=await this.ctx.storage.get('idle_until');
    if(!active && idle>Date.now()) { await this.ctx.storage.setAlarm(idle);return; }
    if(active || this.ctx.container.running)await this.ctx.container.destroy();
    await this.ctx.storage.delete('active');
    await this.ctx.storage.delete('instance_profile');
    await this.ctx.storage.delete('idle_until');
    await this.ctx.storage.deleteAlarm();
    });
  }
  // Inspecting status never starts a stopped container.
  async sourceProbe(){
    // Fixed public host only; no company inputs, credentials, provider API,
    // forecast, replay or container wake. Used by fresh-MFA owner diagnostics.
    try{await new NetworkBroker(this.ctx,this.env,{},this.networkOptions).publicHost('api.worldbank.org');return {ready:true};}
    catch(error){return {ready:false,reason:networkFailureReason(error)};}
  }
  async status() { const failure=await this.ctx.storage.get('source_failure'),check=await this.ctx.storage.get('source_check'),timing=await this.ctx.storage.get('last_timing'),operationFailure=await this.ctx.storage.get('last_failure'),active=await this.ctx.storage.get('active');return {running:!!this.ctx.container?.running,busy:!!active,idle_timeout_ms:SLEEP_MS,...(active?{busy_remaining_ms:Math.max(0,Math.min(720000,active.deadline-Date.now()))}:{}),...(failure?{source_failure:failure}:{}),...(check?{source_check:check}:{}),...(timing?{last_timing:timing}:{}),...(operationFailure?{last_failure:operationFailure}:{})}; }
  fetch() { return closed(); }
}

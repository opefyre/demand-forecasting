const ID=/^[a-f0-9]{32}$/,RUN=/^(?:[a-f0-9]{12}|[a-f0-9]{32})$/,COMPANY=/^[A-Za-z0-9_-]{1,128}$/;
const SLEEP_MS=5*60*1000;
function closed() { return new Response(null,{status:404,headers:{'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow'}}); }

export class CloudEngineController {
  constructor(ctx,env) {
    this.ctx=ctx; this.env=env;
    if (ctx.container?.running) ctx.blockConcurrencyWhile(()=>ctx.container.setInactivityTimeout(SLEEP_MS));
  }
  async execute(job) {
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
      if (active && this.ctx.container.running) await this.ctx.container.destroy();
      await this.ctx.storage.put('active',{attempt:job.attempt,deadline:job.deadline});
      await this.ctx.storage.setAlarm(job.deadline);
      if (!this.ctx.container.running) this.ctx.container.start({image:this.ctx.container.images.base,
        instance:{vcpu:0.25,memoryMib:1024,diskMb:4000},enableInternet:false,
        env:{DEMANDLAB_COMPANY_VAULT_KEY:this.env.COMPANY_VAULT_KEY}});
      await this.ctx.container.setInactivityTimeout(SLEEP_MS);
    } catch(error) {
      claimError=error;
      const current=await this.ctx.storage.get('active');
      if(current?.attempt===job.attempt) {
        if(this.ctx.container.running)await this.ctx.container.destroy();
        await this.ctx.storage.delete('active');await this.ctx.storage.deleteAlarm();
      }
    } });
    if(claimError)throw claimError;
    const port=this.ctx.container.getTcpPort(8080);
    const request=async(path,options={})=>port.fetch('http://engine'+path,{...options,
      signal:AbortSignal.timeout(Math.max(1,job.deadline-Date.now()))});
    let completed=false;
    const save=async(key,response,limit=64*1024*1024)=>{
      const size=Number(response.headers.get('content-length'));
      if(!Number.isSafeInteger(size) || size<1 || size>limit)throw new Error('Invalid output size');
      const stream=new FixedLengthStream(size);
      const [,written]=await Promise.all([response.body.pipeTo(stream.writable),this.env.FILES.put(key,stream.readable,
        {onlyIf:{etagDoesNotMatch:'*'},httpMetadata:{contentType:response.headers.get('content-type') || 'application/octet-stream'}})]);
      if(!written)throw new Error('Output already exists');
    };
    try {
      const bootLimit=Math.min(job.deadline,Date.now()+60000);
      while (true) {
        try { const ready=await request('/ready');if(ready.ok)break; }catch{}
        if(Date.now()>=bootLimit)throw new Error('Engine did not start');
        await new Promise(resolve=>setTimeout(resolve,1000));
      }
      const input=job.object_key===null?null:await this.env.FILES.get(job.object_key);
      if(job.object_key!==null && !input)throw new Error('Company inputs unavailable');
      if(job.kind==='api') {
        if(!job.payload?.body_key?.startsWith('companies/'+job.company_id+'/requests/'))throw new Error('Invalid company request');
        const body=await this.env.FILES.get(job.payload.body_key);
        if(!body || body.size>51*1024*1024)throw new Error('Company request unavailable');
        const staged=await request('/request/'+job.attempt,{method:'PUT',body:body.body});
        if(!staged.ok)throw new Error('Company request unavailable');
      }
      const response=await request(job.kind==='api'?'/api-operation':'/forecast',{method:'POST',body:input?.body || null,
        headers:{'x-forecast-job':JSON.stringify({company_id:job.company_id,job_id:job.attempt,payload:job.payload})}});
      if(!response.ok)throw new Error('Forecast calculation unavailable');
      const result=await response.json();
      if(result.job_id!==job.attempt || result.company_id!==job.company_id || !RUN.test(result.run_id) ||
          !Array.isArray(result.artifacts) || !result.artifacts.includes(job.kind==='api'?'api-response.json':'result.json') || result.artifacts.length>100 ||
          result.artifacts.some(name=>typeof name!=='string' || !/^[a-zA-Z0-9_.-]{1,160}$/.test(name)))throw new Error('Invalid engine output');
      const root='companies/'+job.company_id+'/',key=root+'revisions/'+job.attempt+'.zip';
      const apiStatus=job.kind==='api'?result.api_status:undefined;
      if(job.kind==='api' && (!Number.isInteger(apiStatus) || apiStatus<200 || apiStatus>=500 ||
          (apiStatus<300 && job.payload.method!=='GET' && !result.artifacts.includes('company-view.json'))))throw new Error('Invalid company output');
      const publish=apiStatus===undefined || (apiStatus<300&&job.payload.method!=='GET');
      if(publish) {
        const snapshot=await request('/output/'+job.attempt+'/snapshot');
        if(!snapshot.ok)throw new Error('Checkpoint unavailable');
        await save(key,snapshot);
        const saved=await this.env.FILES.get(key);
        if(!saved || !await this.env.BACKUPS.put(key,saved.body,{onlyIf:{etagDoesNotMatch:'*'}}))throw new Error('Backup unavailable');
      }
      const artifacts={};
      for(const name of result.artifacts) {
        const file=await request('/output/'+job.attempt+'/artifact/'+encodeURIComponent(name));
        if(!file.ok)throw new Error('Output file unavailable');
        const object=root+'outputs/'+job.job_id+'/'+job.attempt+'/'+name;
        await save(object,file,name==='company-view.json'?12*1024*1024:64*1024*1024);
        artifacts[name]=object;
      }
      if(Date.now()>=job.deadline)throw new Error('Forecast deadline exceeded');
      completed=true;
      return {company_id:job.company_id,attempt:job.attempt,run_id:result.run_id,
        object_key:publish?key:null,artifacts,...(apiStatus!==undefined?{api_status:apiStatus}:{})};
    } finally {
      await this.ctx.blockConcurrencyWhile(async()=>{
        const current=await this.ctx.storage.get('active');
        if(current?.attempt!==job.attempt)return;
        if(completed) { try { await request('/output/'+job.attempt,{method:'DELETE'}); }catch{} }
        else if(this.ctx.container.running)await this.ctx.container.destroy();
        await this.ctx.storage.delete('active');await this.ctx.storage.deleteAlarm();
      });
    }
  }
  async alarm() {
    await this.ctx.blockConcurrencyWhile(async()=>{
    const active=await this.ctx.storage.get('active');
    if(active && active.deadline>Date.now()) { await this.ctx.storage.setAlarm(active.deadline);return; }
    if(this.ctx.container.running)await this.ctx.container.destroy();
    await this.ctx.storage.delete('active');
    await this.ctx.storage.deleteAlarm();
    });
  }
  // Inspecting status never starts a stopped container.
  async status() { return {running:!!this.ctx.container?.running,busy:!!await this.ctx.storage.get('active'),idle_timeout_ms:SLEEP_MS}; }
  fetch() { return closed(); }
}

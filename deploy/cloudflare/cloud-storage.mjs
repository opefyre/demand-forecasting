import { DurableObject, WorkerEntrypoint } from 'cloudflare:workers';
import { companyRoute, savedResponse, sameReportDay } from './company-api.mjs';
import {managementRoute,managementResponse} from './management-api.mjs';
import { validateRecovery } from './recovery-ledger.mjs';
import {persistBackup} from './backup-retention.mjs';

const FORECAST_DEADLINE_MS = 12 * 60 * 1000;
const ID = /^[a-f0-9]{32}$/;
const RUN = /^(?:[a-f0-9]{12}|[a-f0-9]{32})$/;
const COMPANY = /^[A-Za-z0-9_-]{1,128}$/;
const ROOT = 'companies/';
const now = () => Date.now();
const random = () => crypto.randomUUID().replaceAll('-', '');
class CloudStorageError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
function safe(error) {
  return { status: error instanceof CloudStorageError ? error.status : 503,
    body: { detail: error instanceof CloudStorageError ? error.message : 'Cloud operation unavailable' } };
}
function closed(request) {
  return new Response(request.method === 'HEAD' ? null : 'Not found.\n', { status: 404,
    headers: { 'Cache-Control':'no-store', 'X-Robots-Tag':'noindex, nofollow', 'X-Content-Type-Options':'nosniff',
      'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'" } });
}
function config(env) {
  if (env.PRIVATE_ACCESS !== 'closed' || !env.FILES || !env.BACKUPS || !env.IDENTITY || !env.ENGINE)
    throw new CloudStorageError(503, 'Private cloud configuration is unavailable');
}
function jobPayload(payload) {
  const fields = ['dataset_id','method','adjustment','scenario_name','base_run_id','sales_input_id',
    'forecast_group_id','forecast_name','parent_forecast_id'];
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) ||
      Object.keys(payload).some(key => !fields.includes(key)) || JSON.stringify(payload).length > 8192 ||
      !ID.test(payload.dataset_id)) throw new CloudStorageError(400, 'Invalid forecast request');
  return payload;
}

// Native SQLite ledger is authoritative. Immutable company checkpoint objects
// live in R2; an object uploaded without a committed ledger entry is NOT visible.
// One ledger/one mathematical engine is intentional for this low-traffic setup.
export class ForecastCloud extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.sql.exec(`CREATE TABLE IF NOT EXISTS companies(company TEXT PRIMARY KEY,revision TEXT NOT NULL,object_key TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS revisions(company TEXT NOT NULL,id TEXT NOT NULL,object_key TEXT NOT NULL,created_at INTEGER NOT NULL,
        PRIMARY KEY(company,id));
      CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,company TEXT NOT NULL,request_id TEXT NOT NULL,payload TEXT NOT NULL,
        grant_json TEXT NOT NULL,state TEXT NOT NULL,attempt TEXT,deadline INTEGER,run_id TEXT,artifacts TEXT,
        input_revision TEXT NOT NULL,created_at INTEGER NOT NULL,message TEXT,UNIQUE(company,request_id));
      CREATE INDEX IF NOT EXISTS cloud_job_state ON jobs(state,created_at);`);
    this.sql.exec(`CREATE TABLE IF NOT EXISTS schedules(company TEXT NOT NULL,id TEXT NOT NULL,subject TEXT NOT NULL,due INTEGER NOT NULL,
      path TEXT NOT NULL,body TEXT NOT NULL,paused INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(company,id));
      CREATE INDEX IF NOT EXISTS cloud_schedule_due ON schedules(paused,due);`);
    for(const [table,name,type] of [['companies','view_key','TEXT'],['jobs','kind',"TEXT NOT NULL DEFAULT 'forecast'"],['jobs','api_status','INTEGER']])
      if(!this.rows('PRAGMA table_info('+table+')').some(row=>row.name===name))this.sql.exec('ALTER TABLE '+table+' ADD COLUMN '+name+' '+type);
  }
  rows(sql, ...values) { return this.sql.exec(sql, ...values).toArray(); }
  async serialized(work) {
    // A rejected blockConcurrencyWhile resets the object. Catch INSIDE the
    // block, then raise outside it so an ordinary conflict never resets a ledger.
    let failure;
    const result=await this.ctx.blockConcurrencyWhile(async()=>{
      try{return await work();}catch(error){failure=error;return null;}
    });
    if(failure)throw failure;
    return result;
  }
  head(company) { return this.rows('SELECT * FROM companies WHERE company=?', company)[0] || null; }
  pending(company) { return this.rows("SELECT 1 FROM jobs WHERE company=? AND state IN ('queued','running') LIMIT 1", company).length; }
  publicJob(row) {
    if (!row) throw new CloudStorageError(404, 'Forecast job not found');
    return { id:row.id, company_id:row.company, state:row.state, run_id:row.kind==='api'?null:row.run_id, created_at:row.created_at,
      input_revision:row.input_revision, message:row.message, kind:row.kind, api_status:row.api_status };
  }
  async operation(operation, args) {
    if (!['stage','enqueue','enqueueApi','jobs','cancel','artifact','apiResult'].includes(operation)) return safe(new CloudStorageError(404,'Operation not found'));
    try { return {status:['enqueue','enqueueApi'].includes(operation)?202:200,body:await this[operation](...args)}; }
    catch(error) { return safe(error); }
  }
  async stage(company, expected, objectKey) {
    return this.serialized(async () => {
      if (!COMPANY.test(company) || !objectKey.startsWith(ROOT + company + '/revisions/')) throw new CloudStorageError(400, 'Invalid company checkpoint');
      const old = this.head(company);
      if ((old?.revision || null) !== expected) throw new CloudStorageError(409, 'Company inputs changed. Reload before saving.');
      if (this.pending(company)) throw new CloudStorageError(409, 'Wait for the current forecast before replacing inputs.');
      // Verify BOTH writes have completed before acknowledging a new revision.
      if (!await this.env.FILES.head(objectKey) || !await this.env.BACKUPS.head(objectKey))
        throw new CloudStorageError(503, 'Checkpoint was not durably saved');
      const revision = objectKey.split('/').at(-1).replace('.zip','');
      if (!ID.test(revision)) throw new CloudStorageError(400, 'Invalid company checkpoint');
      this.ctx.storage.transactionSync(() => {
        this.sql.exec('INSERT INTO revisions(company,id,object_key,created_at) VALUES(?,?,?,?)', company, revision, objectKey, now());
        this.sql.exec('INSERT INTO companies(company,revision,object_key) VALUES(?,?,?) ON CONFLICT(company) DO UPDATE SET revision=excluded.revision,object_key=excluded.object_key,view_key=NULL', company, revision, objectKey);
      });
      await this.persistRecovery(company);
      return { revision };
    });
  }
  async checkpoint(company) { return this.head(company); }
  // Read-only operator RPC on the private native object. Not forwarded through
  // ForecastStorage, the app gateway or any HTTP endpoint. Cloudflare operators
  // may bind a separate rehearsal Worker; it cannot replace the live ledger.
  async recoverySnapshot(company) {
    return this.serialized(()=>this.recoveryValue(company));
  }
  async recoveryValue(company) {
      if(!COMPANY.test(company))throw new CloudStorageError(400,'Invalid company');
      const value={version:1,company_id:company,captured_at:now(),
        head:this.head(company),revisions:this.rows('SELECT * FROM revisions WHERE company=?',company),
        jobs:this.rows('SELECT * FROM jobs WHERE company=?',company),
        schedules:this.rows('SELECT * FROM schedules WHERE company=?',company)};
      validateRecovery(value,company);
      value.bookmark=await this.ctx.storage.getCurrentBookmark();
      return value;
  }
  async persistRecovery(company) {
    if(!this.head(company))return {verified:false,phase:'empty'};
    let result;
    try {result=await persistBackup(this.env.BACKUPS,await this.recoveryValue(company));}
    catch {result={verified:false,phase:'replication',attempted_at:now()};}
    // A replica failure must not misreport a committed forecast as failed or
    // replay a write. Native SQLite recovery and immutable ZIP backups remain.
    await this.ctx.storage.put('recovery:'+company,result);
    return result;
  }
  async captureBackup(company) {
    return this.serialized(async()=>{
      if(!COMPANY.test(company))throw new CloudStorageError(400,'Invalid company');
      return this.persistRecovery(company);
    });
  }
  async authorizeAttempt(company,id,attempt) {
    const row=this.rows("SELECT * FROM jobs WHERE company=? AND id=? AND attempt=? AND state='running'",company,id,attempt)[0];
    return !!(row&&row.deadline>now()&&(this.head(company)?.revision || '')===row.input_revision);
  }
  async armNext() {
    if(this.rows("SELECT 1 FROM jobs WHERE state='queued' LIMIT 1").length){await this.ctx.storage.setAlarm(now()+1000);return;}
    const due=this.rows('SELECT min(due) AS due FROM schedules WHERE paused=0')[0]?.due;
    if(due!=null)await this.ctx.storage.setAlarm(Math.max(now()+1000,due));else await this.ctx.storage.deleteAlarm();
  }
  async enqueueDue() {
    const item=this.rows('SELECT * FROM schedules WHERE paused=0 AND due<=? ORDER BY due,company,id LIMIT 1',now())[0];
    if(!item)return;
    // Claim once before I/O. An interrupted fetch/send never auto-replays.
    this.sql.exec('UPDATE schedules SET paused=1 WHERE company=? AND id=?',item.company,item.id);
    const entry=companyRoute('POST',item.path);if(!entry?.network)return;
    const owner={issuer:'https://forecast.vrolen.com',company_id:item.company,subject:item.subject};
    const auth=await this.env.IDENTITY.operation('schedules/authorize',owner);
    if(auth.status!==200||!auth.body.allowed||!entry.scopes.every(s=>auth.body.permissions?.includes(s)))return;
    if(this.pending(item.company)){
      this.sql.exec('UPDATE schedules SET paused=0,due=? WHERE company=? AND id=?',now()+60000,item.company,item.id);return;
    }
    const bytes=new TextEncoder().encode(item.body),hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
    const body_key=ROOT+item.company+'/requests/'+hash;
    await this.env.FILES.put(body_key,bytes,{onlyIf:{etagDoesNotMatch:'*'}});
    const grant={...owner,auth_kind:'session',scheduled:true,role:'admin',permissions:auth.body.permissions,required_scopes:entry.scopes};
    await this.enqueueApi(item.company,{method:'POST',path:item.path,content_type:'application/json',body_key,body_hash:hash},
      'schedule:'+item.id+':'+item.due,grant,this.head(item.company)?.revision || null);
  }
  async enqueueApi(company,payload,requestId,grant,expected) {
    return this.serialized(async()=>{
      const entry=companyRoute(payload?.method,payload?.path);
      if(!entry || (entry.method==='GET'&&!entry.queued&&!entry.fresh) || !COMPANY.test(company) || typeof requestId!=='string' || requestId.length<8 || requestId.length>160 ||
          !payload.body_key?.startsWith(ROOT+company+'/requests/') || !/^[a-f0-9]{64}$/.test(payload.body_hash) ||
          !entry.scopes.every(scope=>grant.permissions.includes(scope)) || JSON.stringify(payload).length>16384)
        throw new CloudStorageError(400,'Invalid company operation');
      const saved=this.rows('SELECT * FROM jobs WHERE company=? AND request_id=?',company,requestId)[0];
      if(saved) {
        if(saved.kind!=='api' || saved.payload!==JSON.stringify(payload) || saved.grant_json!==JSON.stringify(grant))throw new CloudStorageError(409,'This request identifier belongs to different work');
        return this.publicJob(saved);
      }
      const head=this.head(company);
      if((head?.revision || null)!==expected)throw new CloudStorageError(409,'Company inputs changed. Reload before saving.');
      if(this.pending(company) && (payload.method!=='GET' || this.rows("SELECT payload FROM jobs WHERE company=? AND state IN ('queued','running')",company).some(row=>JSON.parse(row.payload).method!=='GET')))
        throw new CloudStorageError(409,'Wait for the current company operation before saving.');
      if(this.rows("SELECT count(*) AS n FROM jobs WHERE state IN ('queued','running')")[0].n>=20)throw new CloudStorageError(429,'The company queue is full');
      const id=random();
      await this.ctx.storage.setAlarm(now()+1000);
      this.sql.exec("INSERT INTO jobs(id,company,request_id,payload,grant_json,state,input_revision,created_at,kind) VALUES(?,?,?,?,?,'queued',?,?,'api')",
        id,company,requestId,JSON.stringify(payload),JSON.stringify(grant),head?.revision || '',now());
      return this.publicJob(this.rows('SELECT * FROM jobs WHERE id=?',id)[0]);
    });
  }
  async apiResult(company,id,subject,permissions,role) {
    const row=this.rows("SELECT * FROM jobs WHERE company=? AND id=? AND kind='api'",company,id)[0];
    if(!row)throw new CloudStorageError(404,'Company operation not found');
    const grant=JSON.parse(row.grant_json);
    if(grant.subject!==subject || grant.role!==role || !grant.required_scopes.every(scope=>permissions.includes(scope)))throw new CloudStorageError(403,'Your access does not allow this operation');
    const payload=JSON.parse(row.payload),files=row.state==='succeeded'?JSON.parse(row.artifacts):{};
    if(payload.method==='GET' && (this.head(company)?.revision || '')!==row.input_revision)
      throw new CloudStorageError(409,'Report inputs changed. Download the current version.');
    return {...this.publicJob(row),revision:files['company-view.json']&&payload.method!=='GET'?row.attempt:row.input_revision,
      response_key:files['api-response.json'] || null,download_key:files['api-download.bin'] || null};
  }
  async enqueue(company, payload, requestId, grant) {
    return this.serialized(async () => {
    jobPayload(payload);
    if (!COMPANY.test(company) || typeof requestId !== 'string' || requestId.length < 8 || requestId.length > 160)
      throw new CloudStorageError(400, 'Provide a stable request identifier');
    const saved = this.rows('SELECT * FROM jobs WHERE company=? AND request_id=?',company,requestId)[0];
    if (saved) {
      if (saved.payload !== JSON.stringify(payload) || saved.grant_json !== JSON.stringify(grant))
        throw new CloudStorageError(409, 'This request identifier belongs to different work');
      return this.publicJob(saved);
    }
    const head = this.head(company);
    if (!head) throw new CloudStorageError(409, 'Provide reviewed company inputs first');
    if (this.rows("SELECT count(*) AS n FROM jobs WHERE state IN ('queued','running')")[0].n >= 20)
      throw new CloudStorageError(429, 'The forecast queue is full. Try again later.');
    const id = random();
    // Awaiting alarm persistence before row insertion leaves at worst a harmless
    // empty alarm if the row write fails, never an accepted job without a wake.
    await this.ctx.storage.setAlarm(now() + 1000);
    this.sql.exec("INSERT INTO jobs(id,company,request_id,payload,grant_json,state,input_revision,created_at) VALUES(?,?,?,?,?,'queued',?,?)",
      id,company,requestId,JSON.stringify(payload),JSON.stringify(grant),head.revision,now());
    return this.publicJob(this.rows('SELECT * FROM jobs WHERE id=?',id)[0]);
    });
  }
  async jobs(company) { return this.rows('SELECT * FROM jobs WHERE company=? ORDER BY created_at DESC LIMIT 100',company).map(row => this.publicJob(row)); }
  async job(company, id) { return this.publicJob(this.rows('SELECT * FROM jobs WHERE company=? AND id=?',company,id)[0]); }
  async cancel(company, id) {
    this.publicJob(this.rows('SELECT * FROM jobs WHERE company=? AND id=?',company,id)[0]);
    this.sql.exec("UPDATE jobs SET state='cancelled',message='Cancelled' WHERE company=? AND id=? AND state IN ('queued','running')",company,id);
    return this.job(company,id);
  }
  async artifact(company, id, name) {
    const row = this.rows("SELECT * FROM jobs WHERE company=? AND id=? AND state='succeeded' AND kind='forecast'",company,id)[0];
    if (!row) throw new CloudStorageError(404, 'Forecast result not found');
    const files = JSON.parse(row.artifacts);
    const key = files[name];
    if (!key || !key.startsWith(ROOT+company+'/')) throw new CloudStorageError(404, 'Forecast file not found');
    return key;
  }
  async alarm() {
    config(this.env);
    const active = this.rows("SELECT * FROM jobs WHERE state='running' ORDER BY created_at LIMIT 1")[0];
    if (active && active.deadline > now()) {
      await this.ctx.storage.setAlarm(active.deadline + 1000); return;
    }
    if (active) {
      // Fail closed after an interrupted execution. No automatic expensive
      // retries and no replay of mail, imports, orders or approval actions.
      this.sql.exec("UPDATE jobs SET state='interrupted',message='Execution interrupted. Review and retry.' WHERE id=? AND attempt=? AND state='running'",active.id,active.attempt);
    }
    const row = this.rows("SELECT * FROM jobs WHERE state='queued' ORDER BY created_at,id LIMIT 1")[0];
    if (!row) {try{await this.enqueueDue();}finally{await this.armNext();}return;}
    const attempt = random(), deadline = now()+FORECAST_DEADLINE_MS;
    await this.ctx.storage.setAlarm(deadline + 1000);
    this.sql.exec("UPDATE jobs SET state='running',attempt=?,deadline=? WHERE id=? AND state='queued'",attempt,deadline,row.id);
    try {
      const savedGrant=JSON.parse(row.grant_json);
      const authorization = await this.env.IDENTITY.operation(savedGrant.scheduled?'schedules/authorize':'work/authorize',savedGrant);
      if (authorization.status !== 200 || !authorization.body.allowed) throw new CloudStorageError(403,'Access changed. Review and retry.');
      const head = this.head(row.company);
      const payload=JSON.parse(row.payload);
      if(row.kind==='api') {
        if((head?.revision || '')!==row.input_revision)throw new CloudStorageError(409,'Company revision changed');
        const grant=JSON.parse(row.grant_json);
        payload.principal={...grant,mfa_required:false,role:authorization.body.role || grant.role,
          permissions:authorization.body.permissions || []};
      }
      const result = await this.env.ENGINE.execute({ company_id:row.company,job_id:row.id,attempt,
        payload,kind:row.kind,object_key:head?.object_key || null,deadline });
      // A canceled, timed-out or superseded attempt can never publish. Saving
      // objects alone is not publishing them. Commit head AND success together.
      const current = this.rows('SELECT * FROM jobs WHERE id=?',row.id)[0];
      if (current.state !== 'running' || current.attempt !== attempt || deadline <= now()) return;
      if (!result || !RUN.test(result.run_id) || result.company_id !== row.company || result.attempt !== attempt ||
          (!(row.kind==='api' && (result.api_status>=300 || payload.method==='GET') && result.object_key===null) && !result.object_key?.startsWith(ROOT+row.company+'/revisions/')) || !result.artifacts ||
          Object.values(result.artifacts).some(key => typeof key !== 'string' || !key.startsWith(ROOT+row.company+'/outputs/'+row.id+'/'+attempt+'/')))
        throw new CloudStorageError(503, 'Invalid engine output');
      const entry=row.kind==='api'?companyRoute(payload.method,payload.path):null;
      if(row.kind==='api' && (!Number.isInteger(result.api_status) || result.api_status<200 || result.api_status>=600 ||
          (result.api_status>=500&&!entry?.network)||
          !result.artifacts['api-response.json'] || ((result.api_status<300||result.committed===true) && payload.method!=='GET' && !result.artifacts['company-view.json']) ||
          (result.committed===true&&!entry?.network&&result.api_status>=300)||
          (payload.method==='GET' && result.object_key!==null)))throw new CloudStorageError(503,'Invalid company output');
      if (result.object_key && (!await this.env.FILES.head(result.object_key) || !await this.env.BACKUPS.head(result.object_key)))
        throw new CloudStorageError(503, 'Engine output was not durably saved');
      for (const key of Object.values(result.artifacts)) if (!await this.env.FILES.head(key)) throw new CloudStorageError(503,'Engine output was not durably saved');
      let schedules=null;
      if(result.object_key&&result.artifacts['company-schedules.json']) {
        const object=await this.env.FILES.get(result.artifacts['company-schedules.json']);
        if(!object||object.size>256*1024)throw new CloudStorageError(503,'Schedule view unavailable');
        const value=await object.json();
        if(value.company_id!==row.company||!Array.isArray(value.schedules)||value.schedules.length>200||value.schedules.some(s=>
          !/^[A-Za-z0-9:_-]{1,160}$/.test(s.id)||typeof s.subject!=='string'||!s.subject||s.subject.length>160||
          !Number.isSafeInteger(s.due)||s.due<0||!companyRoute(s.method,s.path)?.network||JSON.stringify(s.body).length>8192))throw new CloudStorageError(503,'Schedule view unavailable');
        schedules=value.schedules;
      }
      const stillAllowed=await this.env.IDENTITY.operation(savedGrant.scheduled?'schedules/authorize':'work/authorize',savedGrant);
      if(stillAllowed.status!==200||!stillAllowed.body.allowed)throw new CloudStorageError(403,'Access changed. Review and retry.');
      // R2 awaits allow cancellation to interleave; recheck INSIDE the atomic
      // SQLite transaction, not just before those awaits.
      this.ctx.storage.transactionSync(() => {
        const live = this.rows('SELECT * FROM jobs WHERE id=?',row.id)[0];
        if (live.state !== 'running' || live.attempt !== attempt || deadline <= now()) return;
        if ((this.head(row.company)?.revision || null) !== (head?.revision || null)) throw new CloudStorageError(409,'Company revision changed');
        if(result.object_key) {
          this.sql.exec('INSERT INTO revisions(company,id,object_key,created_at) VALUES(?,?,?,?)',row.company,attempt,result.object_key,now());
          this.sql.exec('INSERT INTO companies(company,revision,object_key,view_key) VALUES(?,?,?,?) ON CONFLICT(company) DO UPDATE SET revision=excluded.revision,object_key=excluded.object_key,view_key=excluded.view_key',
            row.company,attempt,result.object_key,result.artifacts['company-view.json'] || null);
          if(schedules) {
            this.sql.exec('DELETE FROM schedules WHERE company=?',row.company);
            for(const schedule of schedules)this.sql.exec('INSERT INTO schedules(company,id,subject,due,path,body) VALUES(?,?,?,?,?,?)',
              row.company,schedule.id,schedule.subject,schedule.due,schedule.path,JSON.stringify(schedule.body));
          }
        }
        if(payload.method==='GET' && result.api_status<300 && result.artifacts['company-view.json'])
          this.sql.exec('UPDATE companies SET view_key=? WHERE company=? AND revision=?',result.artifacts['company-view.json'],row.company,row.input_revision);
        this.sql.exec("UPDATE jobs SET state='succeeded',run_id=?,artifacts=?,api_status=?,message=NULL WHERE id=?",result.run_id,JSON.stringify(result.artifacts),result.api_status || null,row.id);
      });
    } catch (error) {
      this.sql.exec("UPDATE jobs SET state='failed',message=? WHERE id=? AND attempt=? AND state='running'",
        error instanceof CloudStorageError ? error.message : 'Forecast execution unavailable. Review and retry.',row.id,attempt);
    } finally {
      await this.captureBackup(row.company);
      // One more bounded alarm drains queued work, then no idle polling occurs.
      await this.armNext();
    }
  }
  fetch(request) { return closed(request); }
}

export class ForecastStorage extends WorkerEntrypoint {
  ledger() { config(this.env); return this.env.CLOUD.get(this.env.CLOUD.idFromName('forecast-cloud-v1')); }
  authorizeAttempt(company,id,attempt){return this.ledger().authorizeAttempt(company,id,attempt);}
  async who(credentials, scope) {
    config(this.env);
    const result = await this.env.IDENTITY.operation('identity',credentials);
    if (result.status !== 200) throw new CloudStorageError(result.status,'Sign in to continue');
    const who = result.body;
    if (who.issuer !== 'https://forecast.vrolen.com' || !COMPANY.test(who.company_id) || who.mfa_required ||
        (scope && !who.permissions?.includes(scope))) throw new CloudStorageError(403,'Your role does not allow this action');
    return who;
  }
  async companyApi(credentials,request,requestId,expectedRevision) {
    try {
      const url=new URL(request.url),path=url.pathname.replace(/^\/api\/v1/,'');
      if(!url.pathname.startsWith('/api/v1/'))throw new CloudStorageError(404,'Company operation not found');
      if(path==='/cloud/revision'&&request.method==='GET'&&!url.search) {
        const who=await this.who(credentials),head=await this.ledger().checkpoint(who.company_id);
        return Response.json({revision:head?.revision || null},{headers:{'Cache-Control':'no-store'}});
      }
      const entry=companyRoute(request.method,path);
      if(managementRoute(request.method,path)) {
        const who=await this.who(credentials);
        return await managementResponse(this.env.IDENTITY,credentials,request,who);
      }
      if(!entry)throw new CloudStorageError(501,'This company route is not connected to cloud storage yet');
      const who=await this.who(credentials);
      if(!entry.scopes.every(scope=>who.permissions.includes(scope)))throw new CloudStorageError(403,'Your role does not allow this action');
      if(entry.interactive&&who.auth_kind!=='session'||entry.admin&&who.role!=='admin')throw new CloudStorageError(403,'Interactive administrator access required');
      const head=await this.ledger().checkpoint(who.company_id);
      if(entry.method==='GET'&&!entry.queued) {
        if(!head && entry.collection)return Response.json({[entry.collection]:[],total:0,offset:0,limit:100},{headers:{'Cache-Control':'no-store','X-Company-Revision':''}});
        if(!head?.view_key&&!entry.fresh)throw new CloudStorageError(409,'No saved cloud read view is available yet');
        if(head?.view_key) {
          const object=await this.env.FILES.get(head.view_key);
          if(!object || object.size>12*1024*1024)throw new CloudStorageError(503,'Company read view unavailable');
          const document=await object.json();
          if(document.company_id!==who.company_id)throw new CloudStorageError(503,'Company read view unavailable');
          const value=savedResponse(entry,url,document,who);
          if(value.status!==409||!entry.fresh)return Response.json(value.body,{status:value.status,headers:{'Cache-Control':'no-store','X-Company-Revision':head.revision}});
        }
      }
      if((url.search&&!entry.queued&&!entry.fresh) || !companyRoute(request.method,path+url.search) || typeof expectedRevision==='undefined' ||
          (expectedRevision!==null && !ID.test(expectedRevision)))throw new CloudStorageError(400,'Provide the current company revision');
      if(typeof requestId!=='string' || requestId.length<8 || requestId.length>160)throw new CloudStorageError(400,'Provide a stable request identifier');
      const size=Number(request.headers.get('content-length'));
      if(!Number.isSafeInteger(size) || size<0 || size>51*1024*1024)throw new CloudStorageError(413,'Provide a bounded company request');
      const type=request.headers.get('content-type') || 'application/json';
      if(type.length>256 || !/^(application\/json|multipart\/form-data)(;|$)/i.test(type))throw new CloudStorageError(415,'Use JSON or a file upload');
      // Credential requests are encrypted BEFORE any R2 write; ordinary file
      // uploads retain their bounded streaming path. No plaintext staging object.
      let sealed=false,bodyHash,bodyKey;
      if(entry.sensitive) {
        if(size>32768||!/^[a-f0-9]{64}$/.test(this.env.COMPANY_VAULT_KEY || ''))throw new CloudStorageError(503,'Private credential request unavailable');
        const raw=new Uint8Array(await request.arrayBuffer());if(raw.length!==size)throw new CloudStorageError(413,'Request size did not match');
        bodyHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),n=>n.toString(16).padStart(2,'0')).join('');
        const key=await crypto.subtle.importKey('raw',Uint8Array.from(this.env.COMPANY_VAULT_KEY.match(/../g),s=>parseInt(s,16)),{name:'AES-GCM'},false,['encrypt']);
        const nonce=crypto.getRandomValues(new Uint8Array(12)),binding=new TextEncoder().encode(JSON.stringify([who.company_id,'api-request',bodyHash]));
        const encrypted=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv:nonce,additionalData:binding},key,raw)),packed=new Uint8Array(12+encrypted.length);
        packed.set(nonce);packed.set(encrypted,12);bodyKey=ROOT+who.company_id+'/requests/sealed-'+bodyHash;
        await this.env.FILES.put(bodyKey,packed,{onlyIf:{etagDoesNotMatch:'*'}});sealed=true;
      }else{
      const stream=new FixedLengthStream(size),digest=new crypto.DigestStream('SHA-256'),[store,hash]=stream.readable.tee();
      const temporary=ROOT+who.company_id+'/requests/'+random();
      await Promise.all([(request.body || new Response('').body).pipeTo(stream.writable),hash.pipeTo(digest),
        this.env.FILES.put(temporary,store,{onlyIf:{etagDoesNotMatch:'*'}})]);
      bodyHash=Array.from(new Uint8Array(await digest.digest),n=>n.toString(16).padStart(2,'0')).join('');
      bodyKey=ROOT+who.company_id+'/requests/'+bodyHash;
      const body=await this.env.FILES.get(temporary);
      try {
        if(!body || body.size!==size)throw new CloudStorageError(413,'Request size did not match');
        await this.env.FILES.put(bodyKey,body.body,{onlyIf:{etagDoesNotMatch:'*'}});
      } finally { await this.env.FILES.delete(temporary); }
      }
      const grant=Object.fromEntries(['issuer','subject','company_id','auth_kind','session_id','key_id','key_kind','permissions','role']
        .filter(key=>who[key]!==undefined).map(key=>[key,who[key]]));
      grant.required_scopes=entry.scopes;
      const result=await this.ledger().operation('enqueueApi',[who.company_id,
        {method:entry.method,path:path+url.search,content_type:type,body_key:bodyKey,body_hash:bodyHash,...(sealed?{sealed:true}:{})},requestId,grant,expectedRevision]);
      return Response.json(result.body,{status:result.status,headers:{'Cache-Control':'no-store','X-Company-Operation':result.body.id || ''}});
    } catch(error) { const value=safe(error);return Response.json(value.body,{status:value.status,headers:{'Cache-Control':'no-store'}}); }
  }
  async companyApiResult(credentials,id) {
    try {
      const who=await this.who(credentials);
      const result=await this.ledger().operation('apiResult',[who.company_id,id,who.subject,who.permissions,who.role]);
      if(result.status!==200)throw new CloudStorageError(result.status,result.body.detail);
      const {response_key,download_key,...job}=result.body;
      if(!response_key) {
        if(job.state==='queued'||job.state==='running')return Response.json(job,{status:202,headers:{'Cache-Control':'no-store','X-Company-Operation':id}});
        // A failed engine is not an optimistic-edit conflict. Preserve only the
        // ledger's safe message; never return provider exceptions or credentials.
        return Response.json({detail:job.message || 'The operation stopped. Review before retrying.'},
          {status:job.state==='failed'?503:409,headers:{'Cache-Control':'no-store'}});
      }
      const object=await this.env.FILES.get(response_key);
      if(!object)throw new CloudStorageError(503,'Company response unavailable');
      if(download_key) {
        const descriptor=await object.json();
        if(!sameReportDay(descriptor))throw new CloudStorageError(409,'Report checks need refreshing before download');
        const file=await this.env.FILES.get(download_key);
        if(!file || !descriptor.download || /[\r\n]/.test(descriptor.download.disposition))throw new CloudStorageError(503,'Company download unavailable');
        return new Response(file.body,{status:job.api_status,headers:{'Content-Type':descriptor.download.content_type,
          'Content-Disposition':descriptor.download.disposition,'Cache-Control':'no-store','X-Company-Revision':job.revision || '',
          'X-Content-Type-Options':'nosniff'}});
      }
      return new Response(object.body,{status:job.api_status,headers:{'Content-Type':'application/json','Cache-Control':'no-store',
        ...(job.revision?{'X-Company-Revision':job.revision}:{})}});
    } catch(error) {const value=safe(error);return Response.json(value.body,{status:value.status,headers:{'Cache-Control':'no-store'}});}
  }
  async stageWorkspace(credentials, expectedRevision, request) {
    try {
      const who = await this.who(credentials,'settings:manage');
      if (who.auth_kind !== 'session') throw new CloudStorageError(403,'Use an interactive sign-in');
      const length = Number(request.headers.get('content-length'));
      if (!Number.isSafeInteger(length) || length <= 0 || length > 64*1024*1024) throw new CloudStorageError(413,'Provide a bounded company checkpoint');
      const revision = random(), key = ROOT+who.company_id+'/revisions/'+revision+'.zip';
      // Service-only staging, not an end-user import endpoint. It cannot replace
      // another company and never overwrites an existing immutable object.
      const bounded=new FixedLengthStream(length);
      await Promise.all([request.body.pipeTo(bounded.writable),this.env.FILES.put(key,bounded.readable,
        {onlyIf:{etagDoesNotMatch:'*'},httpMetadata:{contentType:'application/zip'}})]);
      const saved = await this.env.FILES.get(key);
      if (!saved || saved.size !== length) throw new CloudStorageError(413,'Checkpoint size did not match');
      await this.env.BACKUPS.put(key,saved.body,{onlyIf:{etagDoesNotMatch:'*'}});
      return await this.ledger().operation('stage',[who.company_id,expectedRevision,key]);
    } catch (error) { return safe(error); }
  }
  async submit(credentials, payload, requestId) {
    try {
      const who = await this.who(credentials,'forecasts:run');
      const grant = Object.fromEntries(['issuer','subject','company_id','auth_kind','session_id','key_id','permissions']
        .filter(key => who[key] !== undefined).map(key => [key,who[key]]));
      return await this.ledger().operation('enqueue',[who.company_id,payload,requestId,grant]);
    } catch (error) { return safe(error); }
  }
  async jobs(credentials) {
    try { const who=await this.who(credentials,'drafts:read');return await this.ledger().operation('jobs',[who.company_id]); }
    catch(error) { return safe(error); }
  }
  async cancel(credentials,id) {
    try { const who=await this.who(credentials,'forecasts:write');return await this.ledger().operation('cancel',[who.company_id,id]); }
    catch(error) { return safe(error); }
  }
  async artifact(credentials,id,name) {
    try {
      // Drafts are NOT published releases. Viewer keys cannot see unpublished
      // results through an otherwise read-only cloud shortcut.
      const who=await this.who(credentials,'drafts:read');
      if (name !== 'result.json' && !who.permissions.includes('reports:export')) throw new CloudStorageError(403,'Export access required');
      const result=await this.ledger().operation('artifact',[who.company_id,id,name]);
      if(result.status!==200)throw new CloudStorageError(result.status,result.body.detail);
      const object=await this.env.FILES.get(result.body);
      if (!object) throw new CloudStorageError(404,'Forecast file not found');
      return new Response(object.body,{headers:{'Cache-Control':'no-store','Content-Type':object.httpMetadata?.contentType || 'application/octet-stream'}});
    } catch(error) { const result=safe(error);return Response.json(result.body,{status:result.status,headers:{'Cache-Control':'no-store'}}); }
  }
}
export default { fetch: closed };

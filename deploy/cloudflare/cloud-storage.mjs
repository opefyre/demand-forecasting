import { DurableObject, WorkerEntrypoint } from 'cloudflare:workers';

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
    return { id:row.id, company_id:row.company, state:row.state, run_id:row.run_id, created_at:row.created_at,
      input_revision:row.input_revision, message:row.message };
  }
  async operation(operation, args) {
    if (!['stage','enqueue','jobs','cancel','artifact'].includes(operation)) return safe(new CloudStorageError(404,'Operation not found'));
    try { return {status:operation==='enqueue'?202:200,body:await this[operation](...args)}; }
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
        this.sql.exec('INSERT INTO companies(company,revision,object_key) VALUES(?,?,?) ON CONFLICT(company) DO UPDATE SET revision=excluded.revision,object_key=excluded.object_key', company, revision, objectKey);
      });
      return { revision };
    });
  }
  async checkpoint(company) { return this.head(company); }
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
    const row = this.rows("SELECT * FROM jobs WHERE company=? AND id=? AND state='succeeded'",company,id)[0];
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
    if (!row) return;
    const attempt = random(), deadline = now()+FORECAST_DEADLINE_MS;
    await this.ctx.storage.setAlarm(deadline + 1000);
    this.sql.exec("UPDATE jobs SET state='running',attempt=?,deadline=? WHERE id=? AND state='queued'",attempt,deadline,row.id);
    try {
      const authorization = await this.env.IDENTITY.operation('work/authorize',JSON.parse(row.grant_json));
      if (authorization.status !== 200 || !authorization.body.allowed) throw new CloudStorageError(403,'Access changed. Review and retry.');
      const head = this.head(row.company);
      const result = await this.env.ENGINE.execute({ company_id:row.company,job_id:row.id,attempt,
        payload:JSON.parse(row.payload),object_key:head.object_key,deadline });
      // A canceled, timed-out or superseded attempt can never publish. Saving
      // objects alone is not publishing them. Commit head AND success together.
      const current = this.rows('SELECT * FROM jobs WHERE id=?',row.id)[0];
      if (current.state !== 'running' || current.attempt !== attempt || deadline <= now()) return;
      if (!result || !RUN.test(result.run_id) || result.company_id !== row.company || result.attempt !== attempt ||
          !result.object_key?.startsWith(ROOT+row.company+'/revisions/') || !result.artifacts ||
          Object.values(result.artifacts).some(key => typeof key !== 'string' || !key.startsWith(ROOT+row.company+'/outputs/'+row.id+'/'+attempt+'/')))
        throw new CloudStorageError(503, 'Invalid engine output');
      if (!await this.env.FILES.head(result.object_key) || !await this.env.BACKUPS.head(result.object_key))
        throw new CloudStorageError(503, 'Engine output was not durably saved');
      for (const key of Object.values(result.artifacts)) if (!await this.env.FILES.head(key)) throw new CloudStorageError(503,'Engine output was not durably saved');
      // R2 awaits allow cancellation to interleave; recheck INSIDE the atomic
      // SQLite transaction, not just before those awaits.
      this.ctx.storage.transactionSync(() => {
        const live = this.rows('SELECT * FROM jobs WHERE id=?',row.id)[0];
        if (live.state !== 'running' || live.attempt !== attempt || deadline <= now()) return;
        if (this.head(row.company).revision !== head.revision) throw new CloudStorageError(409,'Company revision changed');
        this.sql.exec('INSERT INTO revisions(company,id,object_key,created_at) VALUES(?,?,?,?)',row.company,attempt,result.object_key,now());
        this.sql.exec('UPDATE companies SET revision=?,object_key=? WHERE company=?',attempt,result.object_key,row.company);
        this.sql.exec("UPDATE jobs SET state='succeeded',run_id=?,artifacts=?,message=NULL WHERE id=?",result.run_id,JSON.stringify(result.artifacts),row.id);
      });
    } catch (error) {
      this.sql.exec("UPDATE jobs SET state='failed',message=? WHERE id=? AND attempt=? AND state='running'",
        error instanceof CloudStorageError ? error.message : 'Forecast execution unavailable. Review and retry.',row.id,attempt);
    } finally {
      // One more bounded alarm drains queued work, then no idle polling occurs.
      if (this.rows("SELECT 1 FROM jobs WHERE state='queued' LIMIT 1").length) await this.ctx.storage.setAlarm(now()+1000);
      else await this.ctx.storage.deleteAlarm();
    }
  }
  fetch(request) { return closed(request); }
}

export class ForecastStorage extends WorkerEntrypoint {
  ledger() { config(this.env); return this.env.CLOUD.get(this.env.CLOUD.idFromName('forecast-cloud-v1')); }
  async who(credentials, scope) {
    config(this.env);
    const result = await this.env.IDENTITY.operation('identity',credentials);
    if (result.status !== 200) throw new CloudStorageError(result.status,'Sign in to continue');
    const who = result.body;
    if (who.issuer !== 'https://forecast.vrolen.com' || !COMPANY.test(who.company_id) || who.mfa_required ||
        !who.permissions?.includes(scope)) throw new CloudStorageError(403,'Your role does not allow this action');
    return who;
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

import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {randomBytes,createHash,createCipheriv} from 'node:crypto';
import {symmetricEncrypt} from 'better-auth/crypto';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
const company='wJgSr727WvzGlU4uMVSPzwA01j75gmr0';
test('rehearsal configuration has no public route, provider, engine or live identity binding',async()=>{
  const config=JSON.parse(await readFile(new URL('../../deploy/cloudflare/recovery.wrangler.jsonc',import.meta.url),'utf8'));
  assert.equal(config.workers_dev,false);assert.equal(config.preview_urls,false);assert.deepEqual(config.routes,[]);
  assert.equal(config.vars.REHEARSAL_ENABLED,'false');assert.deepEqual(config.triggers.crons,[]);assert.ok(!config.services&&!config.containers);
  assert.equal(config.d1_databases[0].database_name,'demandlab-forecast-recovery-20261010');
  assert.notEqual(config.d1_databases[0].database_id,'f0f8d4b4-ff3d-4bcc-90ac-c08ff97b64e7');
});
test('native cloud restore preserves completed work and pauses all restored execution',
  {timeout:60000,skip:!process.env.DEMANDLAB_TEST_RECOVERY_REHEARSAL},async()=>{
  const id='a'.repeat(32),key='companies/'+company+'/revisions/'+id+'.zip',viewKey='companies/'+company+'/outputs/'+id+'/'+id+'/company-view.json';
  const head={company,revision:id,object_key:key,view_key:viewKey};
  const job=(state:string,index:number)=>({id:String(index).repeat(32),company,request_id:'fixture-'+index,
    payload:JSON.stringify({dataset_id:id}),grant_json:JSON.stringify({company_id:company,subject:'owner',role:'admin',session_id:'never-restore'}),
    state,attempt:id,deadline:Date.now()+60000,run_id:'a'.repeat(12),artifacts:JSON.stringify({'company-view.json':viewKey}),
    input_revision:id,created_at:1,message:null,kind:'forecast',api_status:null});
  const snapshot={version:1,company_id:company,captured_at:1,bookmark:'fixture-only',head,
    revisions:[{company,id,object_key:key,created_at:1}],jobs:[job('succeeded',1),job('running',2),job('queued',3)],
    schedules:[{company,id:'fixture',subject:'owner',due:1,path:'/connections/external-sources/industry/refresh',body:'{}',paused:0}]};
  const source=`import{DurableObject}from'cloudflare:workers';export class Source extends DurableObject{
    async recoverySnapshot(){return ${JSON.stringify(snapshot)};}async checkpoint(){return ${JSON.stringify(head)};}
  }export default{fetch(){return new Response(null,{status:404});}};`;
  const build=await readFile(new URL('../../deploy/cloudflare/build/recovery/cloud-recovery-rehearsal.js',import.meta.url),'utf8');
  const authKey=randomBytes(32).toString('hex'),vault=randomBytes(32);
  const caller=`export default{async fetch(_request,env){const obj=env.REVIEW.get(env.REVIEW.idFromName('recovery-20261010'));
    await obj.run();return Response.json({done:true});}};`;
  const runtime=new Miniflare(convertV4MiniflareOptions({telemetry:{enabled:false},workers:[
    {name:'review',modules:true,compatibilityDate:'2026-10-09',compatibilityFlags:['nodejs_compat'],script:build,
      bindings:{PRIVATE_ACCESS:'closed',REHEARSAL_ENABLED:'true',REHEARSAL_ID:'dr-20261010',REHEARSAL_COMPANY:company,AUTH_RECOVERY_KEY:authKey,VAULT_RECOVERY_KEY:vault.toString('hex')},
      d1Databases:{IDENTITY_REVIEW_DB:'review-identity'},r2Buckets:{FILES:'review-files',BACKUPS:'review-backups'},
      durableObjects:{REVIEW:{className:'RecoveryRehearsal',useSQLite:true},SOURCE:{className:'Source',scriptName:'source',useSQLite:true}}},
    {name:'source',modules:true,compatibilityDate:'2026-10-09',script:source,durableObjects:{SOURCE:{className:'Source',useSQLite:true}}},
    {name:'caller',modules:true,compatibilityDate:'2026-10-09',script:caller,durableObjects:{REVIEW:{className:'RecoveryRehearsal',scriptName:'review',useSQLite:true}}}
  ]}));
  try {
    const db=await runtime.getD1Database('IDENTITY_REVIEW_DB','review'),sql=await readFile(new URL('../../deploy/cloudflare/migrations/0001_identity.sql',import.meta.url),'utf8');
    await db.batch(sql.replace(/^--.*$/gm,'').split(';').map(s=>s.trim()).filter(Boolean).map(s=>db.prepare(s)));
    await db.prepare('INSERT INTO "user" (id,name,email,"emailVerified","createdAt","updatedAt","twoFactorEnabled") VALUES (?,?,?,?,?,?,?)').bind('owner','Fixture','fixture@example.test',1,1,1,1).run();
    await db.prepare('INSERT INTO organization(id,name,slug,"createdAt") VALUES (?,?,?,?)').bind(company,'Fixture','fixture',1).run();
    await db.prepare('INSERT INTO member(id,"organizationId","userId",role,"createdAt") VALUES (?,?,?,?,?)').bind('member',company,'owner','admin',1).run();
    await db.prepare('INSERT INTO "twoFactor"(id,secret,"backupCodes","userId",verified) VALUES (?,?,?,?,?)').bind('factor',await symmetricEncrypt({key:authKey,data:'Synthetic-secret-not-a-real-OTP'}),'[]','owner',1).run();
    const files=await runtime.getR2Bucket('FILES','review') as any,backups=await runtime.getR2Bucket('BACKUPS','review') as any;
    await files.put(key,'synthetic-checkpoint');await backups.put(key,'synthetic-checkpoint');await files.put(viewKey,JSON.stringify({company_id:company,views:{}}));
    const clear=randomBytes(32),iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',vault,iv);
    cipher.setAAD(Buffer.from(JSON.stringify([company,'recovery-probe','dr-20261010'])));
    const sealed=Buffer.concat([iv,cipher.update(clear),cipher.final(),cipher.getAuthTag()]);
    await backups.put('companies/'+company+'/recovery/dr-20261010/vault-probe.json',JSON.stringify({sealed:sealed.toString('base64'),expected_sha256:createHash('sha256').update(clear).digest('hex')}));
    const worker=await runtime.getWorker('review') as any;assert.equal((await worker.fetch('http://private.test/')).status,404);
    const runner=await runtime.getWorker('caller') as any;assert.equal((await runner.fetch('http://private.test/')).status,200);
    const receipt=await(await backups.get('companies/'+company+'/recovery/dr-20261010/receipt.json'))!.json() as any;
    assert.equal(receipt.verified,true,JSON.stringify(receipt));assert.equal(receipt.completed_jobs,1);assert.equal(receipt.paused_schedules,1);
    assert.equal(receipt.jobs,3);assert.equal(receipt.engine_calls,0);assert.equal(receipt.wrong_company_denied,true);
    const original=await(await backups.get('companies/'+company+'/recovery/dr-20261010/ledger.json'))!.json() as any;
    assert.equal(original.jobs[1].state,'running','Backup evidence itself is immutable; only the recovered copy is sanitized.');
    assert.equal((await runner.fetch('http://private.test/')).status,200,'One-shot replay does not restore or execute twice.');
    assert.deepEqual(await(await backups.get('companies/'+company+'/recovery/dr-20261010/receipt.json'))!.json(),receipt);
  }finally{await runtime.dispose();}
});

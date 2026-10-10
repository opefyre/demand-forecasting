// One-shot, no-HTTP operator rehearsal. No login, provider, mail or engine binding.
import { ForecastCloud } from '../../deploy/cloudflare/cloud-storage.mjs';
import { validateRecovery, recoveryObjects, recoveredGrant } from '../../deploy/cloudflare/recovery-ledger.mjs';
import { symmetricDecrypt } from 'better-auth/crypto';
import { WorkerEntrypoint } from 'cloudflare:workers';

const digest=async(bytes)=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
const check=(condition)=>{if(!condition)throw Error('Recovery check failed');};
export class RecoveryRehearsal extends ForecastCloud {
  // Never let recovered queued jobs or scheduled deliveries execute.
  async alarm() { await this.ctx.storage.deleteAlarm(); }
  async run() {
    return this.serialized(async()=>{
      if(this.env.REHEARSAL_ENABLED!=='true')return {verified:false,phase:'disabled'};
      if(await this.ctx.storage.get('completed'))return this.ctx.storage.get('receipt');
      const env=this.env,company=env.REHEARSAL_COMPANY,prefix='companies/'+company+'/recovery/'+env.REHEARSAL_ID+'/';
      let phase='configuration',receipt={verified:false,live_ledger_changed:false};
      try {
        check(env.PRIVATE_ACCESS==='closed'&&env.REHEARSAL_ID==='dr-20261010');
        check(!this.rows('SELECT 1 FROM companies LIMIT 1').length);
        phase='source-ledger';
        const source=env.SOURCE.get(env.SOURCE.idFromName('forecast-cloud-v1'));
        const snapshot=validateRecovery(await source.recoverySnapshot(company),company);
        const encoded=new TextEncoder().encode(JSON.stringify(snapshot));
        await env.BACKUPS.put(prefix+'ledger.json',encoded,{onlyIf:{etagDoesNotMatch:'*'}});
        const saved=await env.BACKUPS.get(prefix+'ledger.json');
        check(saved&&await digest(await saved.arrayBuffer())===await digest(encoded.buffer));
        const references=recoveryObjects(snapshot);
        phase='archive';
        for(const key of references)check(await env.FILES.head(key));
        // The published head must exist in both independent private buckets.
        const head=await env.FILES.get(snapshot.head.object_key),backup=await env.BACKUPS.get(snapshot.head.object_key);
        check(head&&backup&&head.size<=64*1024*1024&&backup.size===head.size);
        const archiveHash=await digest(await head.arrayBuffer());check(archiveHash===await digest(await backup.arrayBuffer()));
        const identity=env.IDENTITY_REVIEW_DB;
        phase='identity';
        const count=async(table)=>Number((await identity.prepare('SELECT count(*) AS n FROM "'+table+'"').first()).n);
        const identityCounts={users:await count('user'),companies:await count('organization'),members:await count('member'),mfa:await count('twoFactor')};
        check(identityCounts.users===1&&identityCounts.companies===1&&identityCounts.members===1&&identityCounts.mfa===1);
        check(await count('session')===0&&await count('verification')===0);
        check((await identity.prepare('PRAGMA foreign_key_check').all()).results.length===0);
        check(!(await identity.prepare('SELECT 1 FROM apikey WHERE enabled=1 LIMIT 1').first()));
        check(!(await identity.prepare('SELECT 1 FROM account WHERE accessToken IS NOT NULL OR refreshToken IS NOT NULL OR idToken IS NOT NULL LIMIT 1').first()));
        check(!(await identity.prepare('SELECT 1 FROM invitation WHERE status=\'pending\' LIMIT 1').first()));
        check((await identity.prepare('SELECT "organizationId" AS company FROM member LIMIT 1').first()).company===company);
        const factor=await identity.prepare('SELECT secret FROM twoFactor LIMIT 1').first();
        phase='mfa';
        // Maintained Better Auth encryption, not a replacement authentication system.
        const clear=await symmetricDecrypt({key:env.AUTH_RECOVERY_KEY,data:factor.secret});
        check(typeof clear==='string'&&clear.length>=16); // Never print this secret or generate an OTP.
        const challenge=await env.BACKUPS.get(prefix+'vault-probe.json');check(challenge);
        phase='vault';
        const probe=await challenge.json(),bytes=Uint8Array.from(atob(probe.sealed),c=>c.charCodeAt(0));
        const key=await crypto.subtle.importKey('raw',Uint8Array.from(env.VAULT_RECOVERY_KEY.match(/../g),s=>parseInt(s,16)),{name:'AES-GCM'},false,['decrypt']);
        const restored=await crypto.subtle.decrypt({name:'AES-GCM',iv:bytes.slice(0,12),
          additionalData:new TextEncoder().encode(JSON.stringify([company,'recovery-probe',env.REHEARSAL_ID]))},key,bytes.slice(12));
        check(await digest(restored)===probe.expected_sha256);
        let wrongBindingDenied=false;
        try {await crypto.subtle.decrypt({name:'AES-GCM',iv:bytes.slice(0,12),additionalData:new TextEncoder().encode(JSON.stringify(['other_company','recovery-probe',env.REHEARSAL_ID]))},key,bytes.slice(12));}
        catch {wrongBindingDenied=true;}check(wrongBindingDenied);
        phase='restore-ledger';
        this.ctx.storage.transactionSync(()=>{
          for(const [table,rows] of [['companies',[snapshot.head]],['revisions',snapshot.revisions],['jobs',snapshot.jobs],['schedules',snapshot.schedules]]) {
            const columns=this.rows('PRAGMA table_info('+table+')').map(row=>row.name);
            for(const original of rows) {
              const row={...original};
              if(table==='jobs') {row.grant_json=recoveredGrant(row.grant_json);
                if(['queued','running'].includes(row.state)){row.state='interrupted';row.message='Restored; operator review required.';row.attempt=null;row.deadline=null;}}
              if(table==='schedules')row.paused=1;
              const fields=columns.filter(name=>row[name]!==undefined);
              this.sql.exec('INSERT INTO '+table+'('+fields.join(',')+') VALUES('+fields.map(()=>'?').join(',')+')',...fields.map(name=>row[name]));
            }
          }
        });
        await this.ctx.storage.deleteAlarm();
        check(JSON.stringify(this.head(company))===JSON.stringify(snapshot.head));
        check(!this.pending(company)&&!this.rows('SELECT 1 FROM schedules WHERE paused=0 LIMIT 1').length);
        const completed=snapshot.jobs.filter(row=>row.state==='succeeded');
        check(this.rows("SELECT count(*) AS n FROM jobs WHERE state='succeeded'")[0].n===completed.length);
        if(snapshot.head.view_key) {
          const view=await env.FILES.get(snapshot.head.view_key),projection=await view.json();check(projection.company_id===company);
        }
        // Re-read source: a rehearsal never advances or replaces production.
        phase='source-unchanged';
        check(JSON.stringify(await source.checkpoint(company))===JSON.stringify(snapshot.head));
        receipt={verified:true,company_id:company,captured_at:snapshot.captured_at,bookmark:snapshot.bookmark,
          revision:snapshot.head.revision,archive_sha256:archiveHash,ledger_sha256:await digest(encoded.buffer),
          revisions:snapshot.revisions.length,jobs:snapshot.jobs.length,completed_jobs:completed.length,
          object_references:references.length,paused_schedules:snapshot.schedules.length,
          identity:identityCounts,mfa_secret_recovered:true,vault_key_recovered:true,wrong_company_denied:true,
          sessions_restored:0,provider_tokens_restored:0,live_ledger_changed:false,engine_calls:0,provider_calls:0,
          completed_at:new Date().toISOString()};
      } catch { receipt={verified:false,phase,detail:'Isolated rehearsal failed; inspect checks privately.',live_ledger_changed:false}; }
      await env.BACKUPS.put(prefix+'receipt.json',JSON.stringify(receipt));
      await this.ctx.storage.put('completed',true);
      await this.ctx.storage.put('receipt',receipt);
      return receipt;
    });
  }
}
// Operator access uses Cloudflare's authenticated service binding. Never HTTP.
export class RecoveryOperator extends WorkerEntrypoint {
  async captureBackup() {
    if(this.env.REHEARSAL_ENABLED!=='true')return {verified:false,phase:'disabled'};
    return this.env.SOURCE.get(this.env.SOURCE.idFromName('forecast-cloud-v1')).captureBackup(this.env.REHEARSAL_COMPANY);
  }
  async rehearse() {
    if(this.env.REHEARSAL_ENABLED!=='true')return {verified:false,phase:'disabled'};
    return this.env.REVIEW.get(this.env.REVIEW.idFromName('recovery-20261010')).run();
  }
}
export default {
  fetch(){return new Response('Not found.',{status:404,headers:{'Cache-Control':'no-store'}});},
  async scheduled(_event,env){if(env.REHEARSAL_ENABLED==='true')await env.REVIEW.get(env.REVIEW.idFromName('recovery-20261010')).run();},
};

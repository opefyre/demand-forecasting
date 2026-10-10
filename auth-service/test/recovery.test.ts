import test from 'node:test';
import assert from 'node:assert/strict';
import { randomBytes } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';
import { base32 } from '@better-auth/utils/base32';
import { createAuthCore } from '../src/auth-core.js';
import { createCloudflareIdentity, FORECAST_ORIGIN, FORECAST_OWNER } from '../src/cloudflare.js';
import { ownerLogin, ownerContext } from '../src/cloudflare-browser.js';

// Entirely disposable native D1. No real credentials, provider calls or messages.
test('private native D1 password and lost-authenticator recovery', { timeout: 60000 }, async t => {
  const runtime = new Miniflare(convertV4MiniflareOptions({ modules: true,
    script: 'export default {fetch(){return new Response(null,{status:404});}}',
    compatibilityDate: '2026-10-09', d1Databases: ['IDENTITY_DB'], telemetry: { enabled: false } }));
  try {
    const db = await runtime.getD1Database('IDENTITY_DB');
    const sql = await readFile(new URL('../../deploy/cloudflare/migrations/0001_identity.sql', import.meta.url), 'utf8');
    await db.batch(sql.replace(/^--.*$/gm, '').split(';').map(s => s.trim()).filter(Boolean).map(s => db.prepare(s)));
    const env = { IDENTITY_DB: db, PRIVATE_ACCESS: 'closed', OWNER_ONLY_ACCEPTANCE: 'true',
      BETTER_AUTH_SECRET: randomBytes(32).toString('hex') };
    const mail: string[] = [];
    const deliver = async (to: string, _subject: string, text: string) => { assert.equal(to, FORECAST_OWNER); mail.push(text); };
    const identity = createCloudflareIdentity(env, deliver);
    const fixture = createAuthCore(identity.config, db, { async invitationAllowed(){return true;},
      async recordMfa(){}, async clearMfa(){} }, async()=>{});
    const password = 'Synthetic-' + randomBytes(24).toString('hex'); // pragma: allowlist secret — disposable fixture
    const nextPassword = 'Synthetic-' + randomBytes(24).toString('hex'); // pragma: allowlist secret — disposable fixture
    const created = await fixture.api.signUpEmail({ body: { name: 'Synthetic owner', email: FORECAST_OWNER, password } });
    await db.prepare('UPDATE "user" SET "emailVerified"=1 WHERE id=?').bind(created.user.id).run();
    const company = await fixture.api.createOrganization({body:{name:'Recovery test',slug:'recovery-test',userId:created.user.id}});
    const jar = new Map<string,string>();
    async function post(path: string, body: unknown, cookies=jar) {
      const response = await ownerLogin(env, deliver, new Request(FORECAST_ORIGIN+'/api/login/'+path, {
        method:'POST',headers:{origin:FORECAST_ORIGIN,'content-type':'application/json',
          cookie:[...cookies].map(([k,v])=>`${k}=${v}`).join('; ')},body:JSON.stringify(body)}));
      for(const header of response.headers.getSetCookie()){
        const pair=header.split(';')[0],at=pair.indexOf('=');
        if(/max-age=0/i.test(header))cookies.delete(pair.slice(0,at));else cookies.set(pair.slice(0,at),pair.slice(at+1));
      }
      return {status:response.status,body:await response.json() as any};
    }
    const cookie=()=>[...jar].map(([k,v])=>`${k}=${v}`).join('; ');
    assert.equal((await post('sign-in/email',{email:FORECAST_OWNER,password})).status,200);
    const setup=await post('two-factor/enable',{password}); assert.equal(setup.status,200);
    const codes: string[]=setup.body.backupCodes;
    const seed=new TextDecoder().decode(base32.decode(new URL(setup.body.totpURI).searchParams.get('secret')!));
    const totp=await fixture.api.generateTOTP({body:{secret:seed}});
    assert.equal((await post('two-factor/verify-totp',{code:totp.code,trustDevice:false})).status,200);
    assert.equal((await post('two-factor/verify-backup-code',{code:codes[0],trustDevice:false})).status,200);
    assert.equal((await ownerContext(env,deliver,{cookie:cookie(),company_id:company.id})).body.user?.mfa_required,false);
    const oldCookie=cookie();
    await t.test('reset requests refuse outsiders, other origins and external return addresses',async()=>{
      assert.equal((await post('request-password-reset',{email:'outsider@example.test',redirectTo:FORECAST_ORIGIN+'/?reset=1'})).status,403);
      assert.equal((await post('request-password-reset',{email:FORECAST_OWNER,redirectTo:'https://other.example/'})).status,403);
      const response=await ownerLogin(env,deliver,new Request(FORECAST_ORIGIN+'/api/login/request-password-reset',{
        method:'POST',headers:{origin:'https://other.example','content-type':'application/json'},body:JSON.stringify({email:FORECAST_OWNER})}));
      assert.equal(response.status,403);assert.equal(mail.length,0);
    });
    await t.test('valid reset is single-use, revokes old sessions and retains MFA and company',async()=>{
      assert.equal((await post('request-password-reset',{email:FORECAST_OWNER,redirectTo:FORECAST_ORIGIN+'/?reset=1'})).status,200);
      assert.equal(mail.length,1);
      const token=new URL(mail[0]).pathname.split('/').at(-1)!;
      assert.equal((await post('reset-password',{token,newPassword:'short'})).status,400); // pragma: allowlist secret — intentionally invalid synthetic password
      assert.equal((await post('reset-password',{token,newPassword:nextPassword})).status,200);
      assert.equal((await post('reset-password',{token,newPassword:password})).status,400);
      assert.equal((await ownerContext(env,deliver,{cookie:oldCookie,company_id:company.id})).status,401);
      assert.equal((await db.prepare('SELECT count(*) AS n FROM demandlab_session_mfa').first<{n:number}>())?.n,0);
      assert.equal((await db.prepare('SELECT "twoFactorEnabled" AS enabled FROM "user" WHERE id=?').bind(created.user.id).first<{enabled:number}>())?.enabled,1);
      assert.equal((await db.prepare('SELECT count(*) AS n FROM "member" WHERE "organizationId"=?').bind(company.id).first<{n:number}>())?.n,1);
      assert.equal((await post('sign-in/email',{email:FORECAST_OWNER,password})).status,401);
    });
    await t.test('new password still needs MFA; recovery codes cannot be reused',async()=>{
      jar.clear();const login=await post('sign-in/email',{email:FORECAST_OWNER,password:nextPassword});
      assert.equal(login.status,200);assert.equal(login.body.twoFactorRedirect,true);
      assert.equal((await ownerContext(env,deliver,{cookie:cookie(),company_id:company.id})).status,401);
      assert.notEqual((await post('two-factor/verify-backup-code',{code:codes[0],trustDevice:false})).status,200);
      assert.equal((await post('two-factor/verify-backup-code',{code:codes[1],trustDevice:false})).status,200);
      assert.equal((await ownerContext(env,deliver,{cookie:cookie(),company_id:company.id})).body.user?.mfa_required,false);
    });
    await t.test('expired reset link cannot change the password',async()=>{
      assert.equal((await post('request-password-reset',{email:FORECAST_OWNER,redirectTo:FORECAST_ORIGIN+'/?reset=1'})).status,200);
      const token=new URL(mail.at(-1)!).pathname.split('/').at(-1)!;
      await db.prepare('UPDATE "verification" SET "expiresAt"=? WHERE identifier=?').bind(Date.now()-60000,'reset-password:'+token).run();
      assert.equal((await post('reset-password',{token,newPassword:password})).status,400);
    });
  } finally { await runtime.dispose(); }
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes} from 'node:crypto';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {createAuthCore} from '../src/auth-core.js';
import {FORECAST_ORIGIN,FORECAST_OWNER,D1_POLICY_SCHEMA} from '../src/cloudflare.js';
import {ownerContext,ownerLogin} from '../src/cloudflare-browser.js';
import {getMigrations} from 'better-auth/db/migration';
import {createOTP} from '@better-auth/utils/otp';
import {base32} from '@better-auth/utils/base32';

test('private browser permits only owner, bootstraps only verified Google, and requires actual fresh MFA',{timeout:60000},async()=>{
  const runtime=new Miniflare(convertV4MiniflareOptions({modules:true,script:'export default {fetch(){return new Response(null,{status:404});}};',
    compatibilityDate:'2026-10-09',d1Databases:['IDENTITY_DB'],telemetry:{enabled:false}}));
  try{
    const db=await runtime.getD1Database('IDENTITY_DB'),secret=randomBytes(32).toString('hex');
    const env={IDENTITY_DB:db,PRIVATE_ACCESS:'closed',BETTER_AUTH_SECRET:secret,OWNER_ONLY_ACCEPTANCE:'true'};
    const fixture=createAuthCore({origin:FORECAST_ORIGIN,secret,local:false},db,{async invitationAllowed(){return true;},async recordMfa(){},async clearMfa(){}},async()=>{});
    await (await getMigrations(fixture.options)).runMigrations();await db.batch(D1_POLICY_SCHEMA.map(s=>db.prepare(s)));
    const password='Synthetic-'+randomBytes(20).toString('hex'); // pragma: allowlist secret — random disposable test password
    const user=await fixture.api.signUpEmail({body:{email:FORECAST_OWNER,name:'Synthetic owner',password}});
    await db.prepare('UPDATE "user" SET "emailVerified"=1 WHERE id=?').bind(user.user.id).run();
    const signed=await fixture.handler(new Request(FORECAST_ORIGIN+'/api/login/sign-in/email',{method:'POST',headers:{origin:FORECAST_ORIGIN,'content-type':'application/json'},body:JSON.stringify({email:FORECAST_OWNER,password})}));
    let cookie=signed.headers.getSetCookie().map(c=>c.split(';')[0]).join('; ');
    assert.equal((await ownerContext(env,async()=>{},{cookie})).status,401,'No password-only bootstrap');
    await db.prepare('UPDATE "account" SET "providerId"=? WHERE "userId"=?').bind('google',user.user.id).run();
    let ctx=await ownerContext(env,async()=>{},{cookie});assert.equal(ctx.status,200);assert.equal((ctx.body as any).user.mfa_required,true);
    assert.equal((await db.prepare('SELECT count(*) AS n FROM "organization"').first<any>()).n,1);
    assert.equal((await ownerContext(env,async()=>{},{cookie,csrf:(ctx.body as any).csrf})).status,403);
    const login=async(path:string,body:any)=>ownerLogin(env,async()=>{},new Request(FORECAST_ORIGIN+'/api/login/'+path,{method:'POST',headers:{origin:FORECAST_ORIGIN,cookie,'content-type':'application/json'},body:JSON.stringify(body)}));
    assert.equal((await login('sign-up/email',{email:FORECAST_OWNER,password,name:'Other'})).status,404);
    assert.equal((await login('sign-in/social',{provider:'google',callbackURL:'https://stranger.example/'})).status,403);
    assert.equal((await login('sign-in/email',{email:'stranger@example.test',password})).status,403);
    const enabled=await login('two-factor/enable',{});assert.equal(enabled.status,200);
    const setup=await enabled.json() as any,seed=new TextDecoder().decode(base32.decode(new URL(setup.totpURI).searchParams.get('secret')!));
    const bad=await login('two-factor/verify-totp',{code:'not-a-code',trustDevice:false});assert.notEqual(bad.status,200);
    const verified=await login('two-factor/verify-totp',{code:await createOTP(seed).totp(),trustDevice:false});assert.equal(verified.status,200);
    const updates=verified.headers.getSetCookie().map(c=>c.split(';')[0]);if(updates.length)cookie=updates.join('; ');
    ctx=await ownerContext(env,async()=>{},{cookie});assert.equal(ctx.status,200);assert.equal((ctx.body as any).user.mfa_required,false);
    assert.equal((await ownerContext(env,async()=>{},{cookie,csrf:(ctx.body as any).csrf})).status,200);
    assert.equal((await ownerContext(env,async()=>{},{cookie,csrf:'a'.repeat(64)})).status,403);
    await db.prepare('UPDATE demandlab_session_mfa SET verified_at=?').bind(Date.now()-3600001).run();
    assert.equal(((await ownerContext(env,async()=>{},{cookie})).body as any).user.mfa_required,true);
    assert.equal((await db.prepare('SELECT count(*) AS n FROM "organization"').first<any>()).n,1);
  }finally{await runtime.dispose();}
});

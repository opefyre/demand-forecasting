import test from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes} from 'node:crypto';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';
import {createAuthCore} from '../src/auth-core.js';
import {FORECAST_ORIGIN,FORECAST_OWNER,D1_POLICY_SCHEMA,ownerSessionSeconds,createCloudflareIdentity} from '../src/cloudflare.js';
import {ownerContext,ownerLogin} from '../src/cloudflare-browser.js';
import {getMigrations} from 'better-auth/db/migration';
import {createOTP} from '@better-auth/utils/otp';
import {base32} from '@better-auth/utils/base32';
import {resolveD1Identity} from '../src/cloudflare-principal.js';

test('temporary two-day sessions require closed owner-only mode and automatically expire',()=>{
  const now=Date.parse('2026-10-10T18:00:00Z');
  const env={PRIVATE_ACCESS:'closed',OWNER_ONLY_ACCEPTANCE:'true',OWNER_DEV_SESSION_UNTIL:'2026-10-17T00:00:00.000Z'};
  assert.equal(ownerSessionSeconds(env,now),172800);
  for(const change of [{PRIVATE_ACCESS:'open'},{OWNER_ONLY_ACCEPTANCE:'false'},{OWNER_DEV_SESSION_UNTIL:''},
    {OWNER_DEV_SESSION_UNTIL:'invalid'},{OWNER_DEV_SESSION_UNTIL:'2026-11-01T00:00:00.000Z'}])
    assert.equal(ownerSessionSeconds({...env,...change},now),3600);
  assert.equal(ownerSessionSeconds(env,Date.parse(env.OWNER_DEV_SESSION_UNTIL)),3600);
});

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
    // Only the verified owner gets the temporary proof window; login and
    // session-bound MFA remain mandatory, revocable and closed to outsiders.
    const dev={...env,OWNER_DEV_SESSION_UNTIL:new Date(Date.now()+2*86400000).toISOString()};
    assert.equal(createCloudflareIdentity(dev,async()=>{}).auth.options.session?.expiresIn,172800);
    await db.prepare('UPDATE demandlab_session_mfa SET verified_at=?').bind(Date.now()-47*3600000).run();
    const extended=await ownerContext(dev,async()=>{},{cookie});
    assert.equal((extended.body as any).user.mfa_required,false);
    assert.ok('cookies' in extended&&extended.cookies?.some(value=>/Max-Age=172800/.test(value)&&/HttpOnly/.test(value)&&/Secure/.test(value)), 'Existing owner session receives a managed two-day browser cookie');
    const readAgain=await ownerContext(dev,async()=>{},{cookie});
    assert.ok('cookies' in readAgain&&readAgain.cookies?.some(value=>/Max-Age=172[0-9]+/.test(value)), 'A prior server read cannot lose the browser renewal');
    await db.prepare('UPDATE "user" SET email=? WHERE id=?').bind('not-owner@example.test',user.user.id).run();
    assert.equal((await resolveD1Identity(createCloudflareIdentity(dev,async()=>{}),db,{cookie})).mfa_required,true);
    assert.equal((await ownerContext(dev,async()=>{},{cookie})).status,401);
    await db.prepare('UPDATE "user" SET email=? WHERE id=?').bind(FORECAST_OWNER,user.user.id).run();
    await db.prepare('UPDATE demandlab_session_mfa SET verified_at=?').bind(Date.now()-48*3600000-1).run();
    assert.equal(((await ownerContext(dev,async()=>{},{cookie})).body as any).user.mfa_required,true);
    await db.prepare('UPDATE demandlab_session_mfa SET verified_at=?').bind(Date.now()+1*3600000).run();
    assert.equal(((await ownerContext(dev,async()=>{},{cookie})).body as any).user.mfa_required,true);
    assert.equal((await db.prepare('SELECT count(*) AS n FROM "organization"').first<any>()).n,1);
  }finally{await runtime.dispose();}
});

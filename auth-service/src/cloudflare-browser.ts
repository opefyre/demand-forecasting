import { createCloudflareIdentity, FORECAST_OWNER, FORECAST_ORIGIN, type CloudflareIdentityEnv } from './cloudflare.js';
import { resolveD1Identity } from './cloudflare-principal.js';
import type { MailDelivery } from './auth-core.js';

const json=(value:unknown,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store'}});
const post=new Set(['sign-in/social','sign-in/email','request-password-reset','reset-password','sign-out',
  'two-factor/enable','two-factor/verify-totp','two-factor/verify-backup-code','send-verification-email']);
const get=new Set(['callback/google','verify-email','reset-password']);

// Service-binding only. Public identity HTTP stays closed. The only account
// permitted to enter private acceptance is the already agreed owner.
export async function ownerContext(env:CloudflareIdentityEnv,deliver:MailDelivery,body:Record<string,any>) {
  if(env.OWNER_ONLY_ACCEPTANCE!=='true')return {status:503,body:{detail:'Private workspace is unavailable'}};
  try {
    if(body.key || typeof body.cookie!=='string' || body.cookie.length>16384)throw Error();
    const identity=createCloudflareIdentity(env,deliver);
    const headers=new Headers({cookie:body.cookie,origin:FORECAST_ORIGIN});
    const saved=await identity.auth.api.getSession({headers,query:{disableCookieCache:true}});
    if(!saved || saved.user.email.toLowerCase()!==FORECAST_OWNER || !saved.user.emailVerified)throw Error();
    const memberships=await env.IDENTITY_DB.prepare('SELECT 1 FROM "member" WHERE "userId"=?').bind(saved.user.id).first();
    if(!memberships){
      // Only an authenticated, verified Google owner may initialize the empty
      // installation. No public bootstrap token, password or verified-email edit.
      const google=await env.IDENTITY_DB.prepare('SELECT 1 FROM "account" WHERE "userId"=? AND "providerId"=?').bind(saved.user.id,'google').first();
      const occupied=await env.IDENTITY_DB.prepare('SELECT 1 FROM "organization" LIMIT 1').bind().first();
      if(!google || occupied)throw Error();
      await identity.auth.api.createOrganization({body:{name:'Vrolen Forecast',slug:'vrolen-forecast',userId:saved.user.id}});
    }
    const who=await resolveD1Identity(identity,env.IDENTITY_DB,{cookie:body.cookie,...(body.company_id?{company_id:body.company_id}:{})});
    if(who.auth_kind!=='session'||who.email?.toLowerCase()!==FORECAST_OWNER)throw Error();
    const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(env.BETTER_AUTH_SECRET),{name:'HMAC',hash:'SHA-256'},false,['sign','verify']);
    const message=new TextEncoder().encode('csrf:'+who.session_id);
    const csrf=Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,message)),n=>n.toString(16).padStart(2,'0')).join('');
    if(body.csrf!==undefined && (typeof body.csrf!=='string'||!/^[a-f0-9]{64}$/.test(body.csrf)||who.mfa_required||
      !await crypto.subtle.verify('HMAC',key,Uint8Array.from(body.csrf.match(/../g)!,s=>parseInt(s,16)),message)))
      return {status:403,body:{detail:'Verify this signed-in change'}};
    return {status:200,body:{user:who,csrf}};
  } catch {return {status:401,body:{detail:'Sign in with the private owner account'}};}
}

export async function ownerLogin(env:CloudflareIdentityEnv,deliver:MailDelivery,request:Request) {
  const url=new URL(request.url),path=url.pathname.replace(/^\/api\/login\//,'');
  if(env.OWNER_ONLY_ACCEPTANCE!=='true'||url.origin!==FORECAST_ORIGIN||
    !(request.method==='GET'?(get.has(path)||/^reset-password\/[a-zA-Z0-9_-]{20,512}$/.test(path)):request.method==='POST'&&post.has(path)))return json({detail:'Not found'},404);
  if(request.headers.has('authorization') || request.method==='POST'&&request.headers.get('origin')!==FORECAST_ORIGIN)return json({detail:'Sign-in change denied'},403);
  const headers=new Headers();for(const name of ['cookie','content-type','origin','cf-connecting-ip'])if(request.headers.has(name))headers.set(name,request.headers.get(name)!);
  let content:Uint8Array|undefined;
  if(request.method==='POST'){
    const reader=request.body?.getReader(),chunks:Uint8Array[]= [];let size=0;
    if(reader)while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;
      if(size>65536){await reader.cancel();return json({detail:'Request too large'},413);}chunks.push(value);}
    content=new Uint8Array(size);let offset=0;for(const chunk of chunks){content.set(chunk,offset);offset+=chunk.length;}
    let body:any;try{body=JSON.parse(new TextDecoder().decode(content));}catch{return json({detail:'Use JSON'},400);}
    if(body.email && String(body.email).toLowerCase()!==FORECAST_OWNER)return json({detail:'Private account required'},403);
    if(path==='sign-in/social'&&(body.provider!=='google'||body.idToken||body.additionalData))return json({detail:'Use Google sign-in'},403);
    for(const field of ['callbackURL','newUserCallbackURL','errorCallbackURL','redirectTo'])if(body[field]){
      let target;try{target=new URL(body[field],FORECAST_ORIGIN);}catch{return json({detail:'Invalid return address'},400);}
      if(target.origin!==FORECAST_ORIGIN||target.pathname!=='/'||target.hash)return json({detail:'Invalid return address'},403);
    }
    if(path.startsWith('two-factor/')||path==='send-verification-email'){
      const identity=createCloudflareIdentity(env,deliver),saved=await identity.auth.api.getSession({headers,query:{disableCookieCache:true}});
      // Verification may use Better Auth's temporary factor cookie, without a
      // full session. Enrollment always requires the verified owner session.
      if(path==='two-factor/enable'&&(!saved||saved.user.email.toLowerCase()!==FORECAST_OWNER||!saved.user.emailVerified))return json({detail:'Private account required'},403);
      if(saved&&saved.user.email.toLowerCase()!==FORECAST_OWNER)return json({detail:'Private account required'},403);
    }
  }
  try{return await createCloudflareIdentity(env,deliver).auth.handler(new Request(request.url,{method:request.method,headers,...(content?{body:content.buffer as ArrayBuffer}:{} )}));}
  catch{return json({detail:'Sign-in could not be completed'},503);}
}

import {companyScreenRequest} from './screen-gateway.mjs';
const origin='https://forecast.vrolen.com',owner='opefyre@gmail.com';
const pages=new Set(['/','/today','/demand','/forecast','/data','/help','/settings','/approvals','/assistant']);
const json=(value,status=200)=>Response.json(value,{status});
export async function ownerRequest(request,env) {
  const url=new URL(request.url);
  if(url.origin!==origin||!env.IDENTITY||!env.STORAGE||!env.ASSETS)return json({detail:'Private workspace is unavailable'},503);
  const credentials={cookie:request.headers.get('cookie') || ''};
  // Never trust company, role, forwarded identity or raw keys from the browser.
  if(request.headers.has('authorization'))return json({detail:'Use the private owner sign-in'},403);
  if(url.pathname.startsWith('/api/login/'))return env.IDENTITY.browser(request);
  if(url.pathname==='/api/auth/providers'&&request.method==='GET')return json({password:true,google:true});
  if(url.pathname==='/api/auth/session'&&request.method==='GET'){
    const result=await env.IDENTITY.owner(credentials),who=result.body.user;
    return json({mode:'better_auth',transport:'cloud',user:result.status===200?Object.fromEntries(Object.entries(who).filter(([k])=>!['session_id','key_id'].includes(k))):null,
      csrf:result.status===200?result.body.csrf:null});
  }
  if(url.pathname==='/api/health'&&request.method==='GET')return json({status:'ok'});
  if(url.pathname.startsWith('/api/v1/')||url.pathname==='/api/auth/runtime'){
    const result=await env.IDENTITY.owner(credentials),who=result.body.user;
    if(result.status!==200||who?.email?.toLowerCase()!==owner)return json({detail:'Sign in to continue'},401);
    if(who.mfa_required)return json({detail:'Verify two-factor authentication first'},403);
    if(url.pathname==='/api/auth/runtime'){
      if(request.method!=='GET'||url.search||!env.ENGINE)return json({detail:'Not found'},404);
      const state=await env.ENGINE.status();
      if(typeof state.running!=='boolean'||typeof state.busy!=='boolean'||state.idle_timeout_ms!==300000)
        return json({detail:'Engine status is unavailable'},503);
      const value={running:state.running,busy:state.busy,idle_timeout_ms:state.idle_timeout_ms};
      if(request.headers.get('accept')?.includes('text/html'))return new Response(
        '<!doctype html><meta charset="utf-8"><title>Forecast engine</title><h1>Forecast engine</h1><pre>'+JSON.stringify(value,null,2)+'</pre>',
        {headers:{'Content-Type':'text/html; charset=utf-8'}});
      return json(value);
    }
    return companyScreenRequest(env.STORAGE,credentials,request,async(c,r)=>{
      const checked=await env.IDENTITY.owner({...c,csrf:r.headers.get('X-DemandLab-CSRF') || ''});return checked.status===200;
    });
  }
  if(!['GET','HEAD'].includes(request.method))return json({detail:'Not found'},404);
  // Only the compiled interface is served. No source, runtime directory or files.
  let path;
  if(pages.has(url.pathname))path='/index.html';
  else if(/^\/ui\/assets\/[a-zA-Z0-9_.-]+\.(js|css|woff2?|svg|png)$/.test(url.pathname)||
    /^\/ui\/avatars\/assistant-(character|mascot|mascot-simple)\.png$/.test(url.pathname))path=url.pathname.slice(3);
  else return json({detail:'Not found'},404);
  const target=new URL(request.url);target.pathname=path;target.search='';
  return env.ASSETS.fetch(new Request(target,{method:request.method}));
}

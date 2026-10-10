import {ownerRequest} from './owner-edge.mjs';
// Owner acceptance only; all company data requires verified owner plus fresh MFA.
export default {
  async fetch(request,env={}) {
    if(env.PRIVATE_ACCESS==='closed'&&env.OWNER_ONLY_ACCEPTANCE==='true') {
      let response;try{response=await ownerRequest(request,env);}catch{response=Response.json({detail:'Private workspace is unavailable'},{status:503});}
      const headers=new Headers(response.headers);
      for(const [key,value] of Object.entries({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
        'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        'Referrer-Policy':'no-referrer','X-Robots-Tag':'noindex, nofollow','Strict-Transport-Security':'max-age=31536000'}))headers.set(key,value);
      return new Response(request.method==='HEAD'?null:response.body,{status:response.status,headers});
    }
    const headers = new Headers({
      'Cache-Control': 'no-store',
      'Retry-After': '3600',
      'X-Content-Type-Options': 'nosniff',
      'X-Frame-Options': 'DENY',
      'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
      'Referrer-Policy': 'no-referrer',
      'X-Robots-Tag': 'noindex, nofollow',
      'Strict-Transport-Security': 'max-age=31536000',
    });
    const path = new URL(request.url).pathname;
    const api = path === '/api' || path.startsWith('/api/');
    headers.set('Content-Type', api ? 'application/json; charset=utf-8' : 'text/plain; charset=utf-8');
    const body = api
      ? JSON.stringify({ error: 'deployment_not_ready', message: 'Forecast is not available yet.' })
      : 'Forecast is being prepared. Please try again later.\n';
    return new Response(request.method === 'HEAD' ? null : body, { status: 503, headers });
  },
};

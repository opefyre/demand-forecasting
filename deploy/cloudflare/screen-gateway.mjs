// Private service-binding adapter. Not a fetch listener and not wired to the
// public hold. Credentials must come from the authenticated private gateway,
// never from a request's company/role headers. No login/asset routes here.
export async function companyScreenRequest(storage,credentials,request,validateMutation) {
  const url=new URL(request.url),path=url.pathname;
  if(url.origin!=='https://forecast.vrolen.com'||!path.startsWith('/api/v1/'))return new Response(null,{status:404});
  if(request.method!=='GET'&&credentials.cookie&&(request.headers.get('origin')!==url.origin ||
      !validateMutation || !await validateMutation(credentials,request)))
    return Response.json({detail:'Verify this signed-in change'},{status:403});
  const poll=/^\/api\/v1\/cloud\/operations\/([a-f0-9]{32})$/.exec(path);
  if(poll)return request.method==='GET'&&!url.search?storage.companyApiResult(credentials,poll[1]):new Response(null,{status:405});
  const raw=request.headers.get('X-Company-Revision');
  const revision=raw===null?undefined:raw===''?null:raw;
  let bounded=request;
  if(!request.headers.has('content-length')) {
    // Browsers cannot set Content-Length themselves. Bound the actual bytes at
    // the gateway before forwarding to the durable streaming command bridge.
    const reader=request.body?.getReader(),parts=[];let length=0;
    if(reader)try{while(true){const {done,value}=await reader.read();if(done)break;
      length+=value.byteLength;if(length>51*1024*1024){await reader.cancel();return new Response(null,{status:413});}parts.push(value);
    }}finally{reader.releaseLock();}
    const headers=new Headers(request.headers);headers.set('content-length',String(length));
    bounded=new Request(request.url,{method:request.method,headers,
      ...(!['GET','HEAD'].includes(request.method)?{body:new Blob(parts)}:{})});
  }
  return storage.companyApi(credentials,bounded,request.headers.get('X-Company-Request'),revision);
}

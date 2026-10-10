// Existing native Better Auth/D1 operations. No identity data in R2 snapshots.
export function managementRoute(method,path) {
  const fixed={
    'GET /me':['identity',[]], 'GET /access-options':['policy',[]], 'GET /api-keys':['keys/list',[]],
    'POST /api-keys':['keys/create',['kind','name','role','scopes','days'],201],
    'GET /members':['members/list',[]], 'POST /invitations':['members/invite',['email','role'],201],
    'GET /audit-events':['audit',[]],
  };
  const exact=fixed[method+' '+path];if(exact)return {operation:exact[0],fields:exact[1],status:exact[2] || 200};
  const key=/^\/(api-keys|members|invitations)\/([A-Za-z0-9_-]{1,128})(\/rotate|\/revoke-sessions)?$/.exec(path);
  if(!key)return null;const [,kind,id,suffix]=key;
  if(kind==='api-keys'){
    if(method==='PATCH'&&!suffix)return {operation:'keys/manage',id,action:'rename',fields:['name']};
    if(method==='DELETE'&&!suffix)return {operation:'keys/manage',id,action:'revoke',fields:[]};
    if(method==='POST'&&suffix==='/rotate')return {operation:'keys/rotate',id,fields:['days'],status:201};
  }
  if(kind==='invitations'&&method==='DELETE'&&!suffix)return {operation:'members/cancel-invitation',id,fields:[]};
  if(kind==='members'){
    if(method==='PATCH'&&!suffix)return {operation:'members/manage',id,fields:['role','suspended'],memberEdit:true};
    if(method==='DELETE'&&!suffix)return {operation:'members/manage',id,action:'remove',fields:[]};
    if(method==='POST'&&suffix==='/revoke-sessions')return {operation:'members/manage',id,action:'revoke_sessions',fields:[]};
  }
  return null;
}
export async function managementResponse(identity,credentials,request,who) {
  const url=new URL(request.url),entry=managementRoute(request.method,url.pathname.replace(/^\/api\/v1/,''));
  if(!entry)return null;
  if(url.search)return Response.json({detail:'This route does not accept query fields'},{status:400});
  if(entry.operation==='identity')return Response.json(Object.fromEntries(Object.entries(who).filter(([k])=>!['session_id','key_id'].includes(k))),{headers:{'Cache-Control':'no-store'}});
  if(who.auth_kind!=='session')return Response.json({detail:'Use an interactive sign-in'},{status:403});
  let bytes=new Uint8Array();
  if(request.body){const reader=request.body.getReader(),chunks=[];let size=0;
    while(true){const {value,done}=await reader.read();if(done)break;size+=value.length;
      if(size>8192){await reader.cancel();return Response.json({detail:'Request too large'},{status:413});}chunks.push(value);}
    bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}}
  const raw=new TextDecoder().decode(bytes);
  let body;try{body=raw?JSON.parse(raw):{};}catch{return Response.json({detail:'Use JSON'},{status:400});}
  if(!body||Array.isArray(body)||typeof body!=='object'||Object.keys(body).some(k=>!entry.fields.includes(k)))
    return Response.json({detail:'Check the request fields'},{status:422});
  if(entry.memberEdit){
    if((body.role==null)===(body.suspended==null)||body.suspended!=null&&typeof body.suspended!=='boolean')return Response.json({detail:'Change role or suspension, not both'},{status:422});
    body=body.role!=null?{role:body.role,operation:'role'}:{operation:body.suspended?'suspend':'resume'};
  }
  const result=await identity.operation(entry.operation,{...body,...(entry.id?{id:entry.id}:{}),...(entry.action?{operation:entry.action}:{}),
    ...credentials,company_id:who.company_id});
  return Response.json(result.body,{status:result.status===200?(entry.status || 200):result.status,headers:{'Cache-Control':'no-store'}});
}

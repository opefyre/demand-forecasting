// One transport for the existing screens; local/company-server mode is unchanged.
// The private gateway must explicitly advertise transport:'cloud'.
let context=null, generation=0,downloadIdentity=null,downloadVersion=0;
export function configureCloudTransport(access) {
  const user=access?.user;
  const identity=user?JSON.stringify([user.issuer,user.company_id,user.subject,user.role,user.permissions]):null;
  if(identity!==downloadIdentity){downloadIdentity=identity;downloadVersion++;}
  const next=access?.transport==='cloud'&&user?.company_id?JSON.stringify([user.issuer,user.company_id,user.subject,user.role,user.permissions]):null;
  if(next!==context?.company){generation++;context=next?{company:next,revision:undefined,revisionRead:null,revisionEpoch:0}:null;}
}
export const cloudTransportEnabled=()=>!!context;
export const downloadSession=()=>downloadVersion;
const defaultPause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function cloudFetch(url,options,fetcher=fetch,{pause=defaultPause,now=Date.now}={}) {
  if(!context || !url.startsWith('/api/v1/'))return fetcher(url,options);
  const current=context,version=generation;
  const active=()=>{if(context!==current||generation!==version)throw new Error('Company session changed');};
  const request=(target,init)=>fetcher(target,{...init,credentials:'same-origin',cache:'no-store'});
  if(current.revision===undefined){
    // Bootstrap screens share one head read, not one request per panel. This
    // shares only a read; writes and saved-operation polling are never replayed.
    const epoch=current.revisionEpoch;
    const reading=current.revisionRead ||= request('/api/v1/cloud/revision',{method:'GET'}).then(async response=>{
      if(!response.ok)return {response};
      const value=await response.json();
      if(value.revision!==null&&!/^[a-f0-9]{32}$/.test(value.revision))throw new Error('Invalid company revision');
      return value;
    });
    let value;
    try {value=await reading;active();}
    finally {if(current.revisionRead===reading)current.revisionRead=null;}
    if(value.response)return value.response.clone();
    // Parallel bootstrap reads may finish after a write. Never rewind its head.
    if(current.revision===undefined){
      if(epoch!==current.revisionEpoch)throw new Error('Company inputs changed. Reload saved data.');
      current.revision=value.revision;
    }
  }
  const id=crypto.randomUUID(),headers=new Headers(options?.headers);
  headers.set('X-Company-Request',id);headers.set('X-Company-Revision',current.revision || '');
  let response=await request(url,{...options,headers});active();
  const operation=response.headers.get('X-Company-Operation');
  if(response.status===202&&operation){
    if(!/^[a-f0-9]{32}$/.test(operation))throw new Error('Invalid company operation');
    const deadline=now()+13*60*1000;
    while(response.status===202&&response.headers.get('X-Company-Operation')){
      if(now()>=deadline)throw new Error('Company operation is still pending; reload saved data');
      await pause(1500);active();
      // Poll ONLY the saved operation. Never retry a write after a lost reply.
      response=await request('/api/v1/cloud/operations/'+operation,{method:'GET'});active();
    }
  }
  const revision=response.headers.get('X-Company-Revision');
  if(revision!==null){
    if(revision!==''&&!/^[a-f0-9]{32}$/.test(revision))throw new Error('Invalid company revision');
    // Read projections can legitimately describe an older revision. Only a
    // completed write advances optimistic-write authority in this session.
    if(!['GET','HEAD'].includes((options?.method || 'GET').toUpperCase())){current.revisionEpoch++;current.revision=revision || null;}
  }
  if(response.status===409){current.revisionEpoch++;current.revision=undefined;} // Next explicit action reloads; no write replay.
  return response;
}

// One transport for the existing screens; local/company-server mode is unchanged.
// The private gateway must explicitly advertise transport:'cloud'.
let context=null, generation=0;
export function configureCloudTransport(access) {
  const user=access?.user;
  const next=access?.transport==='cloud'&&user?.company_id?JSON.stringify([user.issuer,user.company_id,user.subject,user.role,user.permissions]):null;
  if(next!==context?.company){generation++;context=next?{company:next,revision:undefined}:null;}
}
export const cloudTransportEnabled=()=>!!context;
const defaultPause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
export async function cloudFetch(url,options,fetcher=fetch,{pause=defaultPause,now=Date.now}={}) {
  if(!context || !url.startsWith('/api/v1/'))return fetcher(url,options);
  const current=context,version=generation;
  const active=()=>{if(context!==current||generation!==version)throw new Error('Company session changed');};
  const request=(target,init)=>fetcher(target,{...init,credentials:'same-origin',cache:'no-store'});
  if(current.revision===undefined){
    const response=await request('/api/v1/cloud/revision',{method:'GET'});
    active();if(!response.ok)return response;
    const value=await response.json();
    if(value.revision!==null&&!/^[a-f0-9]{32}$/.test(value.revision))throw new Error('Invalid company revision');
    // Parallel bootstrap reads may finish after a write. Never rewind its head.
    if(current.revision===undefined)current.revision=value.revision;
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
    if(!['GET','HEAD'].includes((options?.method || 'GET').toUpperCase()))current.revision=revision || null;
  }
  if(response.status===409)current.revision=undefined; // Next explicit action reloads; no write replay.
  return response;
}
export function installCloudDownloads({onStart=()=>{},onError=()=>{},root=document}={}) {
  const busy=new WeakSet();
  async function clicked(event){
    if(!context||event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    const link=event.target.closest?.('a[href]');if(!link)return;
    const url=new URL(link.href,location.href);
    if(url.origin!==location.origin||!url.pathname.startsWith('/api/v1/')||!(/\/export$|\/files\/|\/orders\/template\//.test(url.pathname)))return;
    event.preventDefault();if(busy.has(link))return;busy.add(link);onStart();
    const current=context;
    try{
      const response=await cloudFetch(url.pathname+url.search,{method:'GET'});
      if(!response.ok){const value=await response.json().catch(()=>({}));throw new Error(value.detail||'The download could not be prepared.');}
      if(!response.headers.get('Content-Disposition'))throw new Error('The server did not return a download.');
      const blob=await response.blob();if(context!==current)throw new Error('Company session changed');
      const target=URL.createObjectURL(blob),a=document.createElement('a');a.href=target;
      a.download=/filename="?([^";]+)"?/.exec(response.headers.get('Content-Disposition'))?.[1]?.replace(/[\\/]/g,'_')||'forecast-export';
      a.click();setTimeout(()=>URL.revokeObjectURL(target),1000);
    }catch(error){onError(error);}finally{busy.delete(link);}
  }
  root.addEventListener('click',clicked);return()=>root.removeEventListener('click',clicked);
}

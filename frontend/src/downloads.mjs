import {cloudFetch,downloadSession} from './cloud-transport.mjs';
import {RequestFailure,responseFailure} from './request-errors.mjs';

export function isAppDownload(path){
  return /^\/api\/v1\/.+\/(export|files\/(csv|xlsx|models|drivers)|orders\/template\/[^/]+)$/.test(path)||
    /^\/api\/export\/[^/]+\/(csv|xlsx|models|drivers)$/.test(path)||
    /^\/api\/(sales\/(inputs|releases)|plans)\/[^/]+\/export$/.test(path);
}

export async function readDownload(path,{fetcher=fetch,isCurrent=()=>true}={}){
  try{
    const response=await cloudFetch(path,{method:'GET'},fetcher);
    if(!response.ok)throw responseFailure(response.status,await response.json().catch(()=>({})),response.headers.get('Retry-After'));
    if(!response.headers.get('Content-Disposition'))throw new RequestFailure('The server returned an unreadable response.',{kind:'response',status:response.status});
    const blob=await response.blob();
    if(!isCurrent())throw new RequestFailure('Company session changed',{status:401});
    return {blob,filename:/filename="?([^";]+)"?/.exec(response.headers.get('Content-Disposition'))?.[1]?.replace(/[\\/]/g,'_')||'forecast-export'};
  }catch(error){
    const failure=error?.name==='RequestFailure'?error:new RequestFailure('The connection was interrupted.',{kind:'connection'});
    failure.operation='download';throw failure;
  }
}

export async function saveDownload(path,{fetcher=fetch,isCurrent=()=>true}={}){
  const session=downloadSession();
  const {blob,filename}=await readDownload(path,{fetcher,isCurrent:()=>isCurrent()&&downloadSession()===session});
  const target=URL.createObjectURL(blob),anchor=document.createElement('a');
  anchor.href=target;anchor.download=filename;
  try{anchor.click();}finally{setTimeout(()=>URL.revokeObjectURL(target),1000);}
}

// Downloads stay in the workspace on failure, in local and company modes alike.
export function installDownloads({onStart=()=>{},onError=()=>{},root=document,fetcher=fetch}={}){
  const busy=new WeakSet();let live=true;
  async function clicked(event){
    if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    const link=event.target.closest?.('a[href]');if(!link||link.target==='_blank')return;
    const url=new URL(link.href,location.href);
    if(url.origin!==location.origin||!isAppDownload(url.pathname))return;
    event.preventDefault();if(busy.has(link))return;busy.add(link);
    const session=downloadSession();
    try{
      onStart();
      await saveDownload(url.pathname+url.search,{fetcher,isCurrent:()=>live&&downloadSession()===session});
    }catch(error){if(live&&downloadSession()===session)onError(error);}finally{busy.delete(link);}
  }
  root.addEventListener('click',clicked);
  return()=>{live=false;root.removeEventListener('click',clicked);};
}

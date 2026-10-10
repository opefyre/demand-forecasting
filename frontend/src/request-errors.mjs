// Preserve response evidence without treating server text as instructions or UI keys.
import {cloudFetch} from './cloud-transport.mjs';
export class RequestFailure extends Error {
  constructor(message, {status=0, kind='http', fields=[], retryAt=null}={}) {
    super(message); this.name='RequestFailure';
    this.status=status; this.kind=kind; this.fields=fields; this.retryAt=retryAt;
  }
}

export function retryAfter(value, now=Date.now()) {
  if(!value) return null;
  const seconds=Number(value);
  const deadline=Number.isFinite(seconds)?now+Math.max(0,seconds)*1000:Date.parse(value);
  return Number.isFinite(deadline)&&deadline>now?deadline:null;
}

export function responseFailure(status, payload, delay, now=Date.now()) {
  const detail=payload?.detail;
  const fields=Array.isArray(detail)?detail.slice(0,10).map(row=>({
    // Never retain validation input values or context, which can contain credentials.
    field:Array.isArray(row?.loc)?row.loc.filter(v=>['string','number'].includes(typeof v)&&!['body','query','path'].includes(v)).join(' → '):'',
    message:typeof row?.msg==='string'?row.msg:'Check this field.',
  })):[];
  return new RequestFailure(typeof detail==='string'?detail:'The request could not be completed.',
    {status,fields,retryAt:retryAfter(delay,now)});
}

export async function requestJSON(url, body, method, {csrfToken='',fetcher=fetch,onSessionExpired=()=>{}}={}) {
  const isFile=typeof FormData!=='undefined'&&body instanceof FormData;
  const requestMethod=method||(body?'POST':'GET');
  const operation=['GET','HEAD'].includes(requestMethod.toUpperCase())?'read':'write';
  const failure=error=>{error.operation=operation;return error;};
  let response;
  try {
    response=await cloudFetch(url,{
      method:requestMethod,
      ...(isFile?{body}:body?{body:JSON.stringify(body)}:{}),
      headers:{...(body&&!isFile?{'Content-Type':'application/json'}:{}),
        ...(csrfToken?{'X-DemandLab-CSRF':csrfToken}:{})},
    },fetcher);
  } catch {
    throw failure(new RequestFailure('The connection was interrupted.',{kind:'connection'}));
  }
  if(!response.ok) {
    if(response.status===401)onSessionExpired();
    const payload=await response.json().catch(()=>({}));
    throw failure(responseFailure(response.status,payload,response.headers?.get('Retry-After')));
  }
  try{return await response.json();}
  catch{throw failure(new RequestFailure('The server returned an unreadable response.',{kind:'response',status:response.status}));}
}

export function recoveryPresentation(error, now=Date.now()) {
  if(!error) return null;
  if(!(error instanceof Error)||error.name!=='RequestFailure')
    return {message:typeof error==='string'?error:error.message||'The request could not be completed.',plain:true,canReload:true};
  let title='This request needs attention.',next='Check the details below before continuing.';
  const status=error.status;
  if(error.kind==='connection'||error.kind==='response') {
    title=error.kind==='connection'?'The app could not reach the server.':'The server response could not be read.';
    next='Reload saved data. If you were saving a change, check whether it was saved before trying again.';
  } else if(status===401) {
    title='Sign in again to continue.';next='Your session ended. Sign in, then reopen this workflow.';
  } else if(status===403) {
    title='You cannot perform this action.';next='Ask a workspace administrator to check your access.';
  } else if(status===404||status===410) {
    title='This saved item is no longer available.';next='Choose an available saved version. Do not recreate orders to replace a missing view.';
  } else if(status===409) {
    title='The saved data changed.';next='Reload the latest version and review it before saving again.';
  } else if(status===429) {
    title='Please wait before trying again.';next='The request limit was reached. No automatic retry will be sent.';
  } else if(status>=500) {
    title='The server could not complete this request.';next='Reload saved data. If you were saving a change, check whether it was saved before trying again.';
  } else if(status===400||status===422) {
    title='Check the inputs before continuing.';next='Correct the fields or settings described below, then review again.';
  }
  if(error.operation==='read'&&(error.kind==='connection'||error.kind==='response'||status>=500))next='Reload saved data to try again.';
  return {title,next,details:error.message,fields:error.fields||[],retryAt:error.retryAt,inlineDetails:[400,422].includes(status),
    canReload:![400,401,403,404,410,422].includes(status)&&(!error.retryAt||error.retryAt<=now),plain:false};
}

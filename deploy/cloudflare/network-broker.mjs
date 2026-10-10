// Private attempt-scoped I/O. No HTTP listener, generic proxy, provider writes,
// ambient credentials, redirects or retries. Existing Python SDKs build requests.
const MAX=20*1024*1024;
const decode=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
const encode=bytes=>{let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);};
const deny=()=>{throw new Error('Private outside request denied');};
export function publicAddress(value) {
  if(typeof value!=='string')return false;
  // IPv4 only for the pinned TCP bridge; reject IPv6/mapped/ambiguous formats.
  const p=value.split('.').map(Number);
  if(p.length!==4||p.some(n=>!Number.isInteger(n)||n<0||n>255)||p.join('.')!==value)return false;
  const [a,b,c]=p;
  return !(a===0||a===10||a===127||a>=224||a===169&&b===254||a===172&&b>=16&&b<=31||a===192&&b===168||
    a===100&&b>=64&&b<=127||a===192&&b===0||a===192&&b===2||a===198&&(b===18||b===19||b===51&&c===100)||a===203&&b===0&&c===113);
}
export function allowedRequest(job,item) {
  if(!item||typeof item.kind!=='string')return false;
  const path=job.payload?.path?.split('?')[0],method=job.payload?.method;
  if(job.kind!=='api'||!job.payload?.principal||typeof path!=='string')return false;
  if(item.kind==='identity')return item.operation==='schedules/authorize'&&item.body?.company_id===job.company_id&&
    item.body?.issuer==='https://forecast.vrolen.com'&&typeof item.body.subject==='string'&&
    (path.startsWith('/notifications/')||path.startsWith('/recurring-forecasts')||path.endsWith('/schedule/check')||
      /^\/jobs\/[a-zA-Z0-9_-]{1,128}\/retry$/.test(path)&&method==='POST'||path==='/cloud/tick');
  if(item.kind.startsWith('tcp-'))return path.startsWith('/connections/inputs/')&&
    (path.endsWith('/fetch')||path.endsWith('/schedule/check'))||path==='/cloud/tick';
  let u;try{u=new URL(item.url);}catch{return false;}
  if(u.protocol!=='https:'||u.username||u.password||u.hash||u.port&&u.port!=='443'||!['GET','POST'].includes(item.method))return false;
  if(item.category==='ai')return method==='POST'&&['/ai/chat','/ai/import-mapping'].includes(path)&&
    item.method==='POST'&&u.origin==='https://api.openai.com'&&u.pathname==='/v1/responses'&&!u.search;
  if(item.category==='source') {
    if(!(path.startsWith('/connections/external-sources/')||path==='/cloud/tick')||item.method!=='GET')return false;
    return u.hostname==='servix.cc'&&/^\/api\/v1\/assets\/(supported|USD_RLS(?:\/history)?)$/.test(u.pathname)||
      u.hostname==='hormuz.now'&&u.pathname==='/api/daily.json'||
      u.hostname==='www.newyorkfed.org'&&u.pathname==='/medialibrary/research/interactives/data/gscpi/gscpi_interactive_data.csv'||
      u.hostname==='api.worldbank.org'&&/^\/v2\/country\/(IR|IRN)\/indicator\/(FP.CPI.TOTL.ZG|NV.IND.TOTL.KD.ZG)$/i.test(u.pathname)||
      u.hostname==='www.worldbank.org'&&u.pathname==='/en/research/commodity-markets'||
      u.hostname==='thedocs.worldbank.org'&&u.pathname.endsWith('/CMO-Historical-Data-Monthly.xlsx')||
      u.hostname==='api.imf.org'&&u.pathname==='/external/sdmx/2.1/data/IMF.STA,CPI,5.0.0/IRN.CPI._T.IX.M';
  }
  if(item.category==='connection') {
    if(!((path.startsWith('/connections/inputs/')&&(path.endsWith('/fetch')||path.endsWith('/schedule/check')))||path==='/cloud/tick'))return false;
    const c=item.config;
    if(c?.provider==='sheets')return item.method==='POST'&&u.href==='https://oauth2.googleapis.com/token'||
      item.method==='GET'&&u.hostname==='sheets.googleapis.com'&&u.pathname.startsWith('/v4/spreadsheets/'+c.spreadsheet_id+'/values/');
    let configured;try{configured=new URL(c?.url);}catch{return false;}
    if(configured.origin!==u.origin)return false;
    if(c.provider==='http')return item.method==='GET'&&u.href===configured.href;
    const models=['res.partner','sale.order','sale.order.line','product.product','uom.uom'];
    if(c.provider==='odoo19')return item.method==='POST'&&models.some(model=>u.pathname==='/json/2/'+model+'/search_read');
    if(c.provider==='odoo18'&&item.method==='POST'&&u.pathname==='/jsonrpc') {
      try{const body=JSON.parse(new TextDecoder().decode(decode(item.body))),p=body.params;
        return body.method==='call'&&(p?.service==='common'&&p.method==='authenticate'||p?.service==='object'&&p.method==='execute_kw'&&
          models.includes(p.args?.[3])&&p.args?.[4]==='search_read');}catch{return false;}
    }
    return false;
  }
  if(item.category==='notification')return method==='POST'&&
    (path.startsWith('/notifications/')||path==='/cloud/tick')&&item.method==='POST'&&
    (u.hostname==='hooks.slack.com'&&u.pathname.startsWith('/services/')||u.hostname==='api.telegram.org'&&/^\/bot[^/]+\/sendMessage$/.test(u.pathname)||
    u.hostname==='graph.facebook.com'&&/^\/v[0-9.]+\/\d+\/messages$/.test(u.pathname)||
    (u.hostname.endsWith('.api.powerplatform.com')||u.hostname.endsWith('.logic.azure.com'))&&u.pathname.includes('/workflows/')&&u.pathname.endsWith('/paths/invoke'));
  return false;
}
async function bounded(response,limit=MAX) {
  if(!response.body)return new Uint8Array();
  const reader=response.body.getReader(),chunks=[];let size=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>limit)deny();chunks.push(value);}}
  catch(error){await reader.cancel();throw error;}
  const bytes=new Uint8Array(size);let i=0;for(const chunk of chunks){bytes.set(chunk,i);i+=chunk.length;}return bytes;
}
export class NetworkBroker {
  constructor(ctx,env,job,{fetcher=fetch,connector=null}={}){this.ctx=ctx;this.env=env;this.job=job;this.fetcher=fetcher;this.connector=connector;this.sockets=new Map();this.calls=0;}
  async authorize() {
    const job=this.job,active=await this.ctx.storage.get('active');
    if(active?.attempt!==job.attempt||job.deadline<=Date.now())deny();
    const grant=job.payload.principal;
    const operation=grant.scheduled?'schedules/authorize':'work/authorize';
    const result=await this.env.IDENTITY.operation(operation,grant);
    if(result.status!==200||!result.body.allowed||!grant.required_scopes?.every(s=>result.body.permissions?.includes(s)))deny();
    const fence=await this.env.STORAGE.authorizeAttempt(job.company_id,job.job_id,job.attempt);
    if(!fence)deny();
  }
  async publicHost(host) {
    if(!/^[a-z0-9][a-z0-9.-]{0,252}$/i.test(host)||host.endsWith('.local')||host==='localhost'||!host.includes('.'))deny();
    if(/^\d+[.\d]*$/.test(host)){if(!publicAddress(host))deny();return host;}
    const response=await this.fetcher('https://cloudflare-dns.com/dns-query?name='+encodeURIComponent(host)+'&type=A',
      {headers:{accept:'application/dns-json'},redirect:'error',signal:AbortSignal.timeout(5000)});
    if(!response.ok)deny();const value=JSON.parse(new TextDecoder().decode(await bounded(response,32768)));
    const addresses=value.Answer?.filter(r=>r.type===1).map(r=>r.data);
    if(!addresses?.length||addresses.some(a=>!publicAddress(a)))deny();return addresses[0];
  }
  async exchange(item) {
    if(++this.calls>2000||!allowedRequest(this.job,item))deny();
    await this.authorize();
    if(item.kind==='identity') {
      const result=await this.env.IDENTITY.operation('schedules/authorize',item.body);
      if(result.status!==200)deny();return {body:result.body};
    }
    if(item.kind.startsWith('tcp-'))return this.tcp(item);
    const u=new URL(item.url),body=decode(item.body || '');if(body.length>1024*1024)deny();
    const headers=new Headers(item.headers || {});
    for(const name of ['host','cookie','connection','proxy-authorization','content-length','accept-encoding'])headers.delete(name);
    if(item.category==='ai') {
      if(this.env.AI_ENABLED!=='true'||this.env.AI_ELIGIBILITY_CONFIRMED!=='true'||!this.env.OPENAI_API_KEY)deny();
      const value=JSON.parse(new TextDecoder().decode(body)),models=this.job.payload._cloud_ai?.models || {};
      if(!Object.values(models).includes(value.model)||value.store!==false||value.stream===true)deny();
      // Durable reservation BEFORE sending. A failed/interrupted call still costs
      // a reservation and is never replayed automatically after a Worker restart.
      const day=new Date().toISOString().slice(0,10),company=this.job.company_id,actor=this.job.payload.principal.subject;
      const keys=['ai-day:'+company+':'+day,'ai-user:'+company+':'+actor+':'+day,'ai-attempt:'+this.job.attempt];
      let denied=false;
      await this.ctx.blockConcurrencyWhile(async()=>{
        const counts=await Promise.all(keys.map(k=>this.ctx.storage.get(k)));
        if(counts.some((n,i)=>(n || 0)>=[60,30,6][i])){denied=true;return;}
        await this.ctx.storage.put(Object.fromEntries(keys.map((k,i)=>[k,(counts[i] || 0)+1])));
      });
      if(denied)deny();
      headers.set('authorization','Bearer '+this.env.OPENAI_API_KEY);
      headers.delete('openai-organization');headers.delete('openai-project');
    } else await this.publicHost(u.hostname);
    const response=await this.fetcher(u.href,{method:item.method,headers,body:item.method==='GET'?undefined:body,
      redirect:'manual',signal:AbortSignal.timeout(item.category==='ai'?60000:30000)});
    if(response.status>=300&&response.status<400)deny();
    const bytes=await bounded(response),kept={};
    for(const name of ['content-type','link','retry-after'])if(response.headers.has(name))kept[name]=response.headers.get(name);
    return {status:response.status,headers:kept,body:encode(bytes)};
  }
  async tcp(item) {
    if(item.kind==='tcp-open') {
      const c=item.config;if(!this.connector||c?.provider!=='sftp'||!Number.isInteger(c.port)||c.port<1||c.port>65535||this.sockets.size)deny();
      const address=await this.publicHost(c.host),socket=this.connector({hostname:address,port:c.port},{secureTransport:'off',allowHalfOpen:false});
      await socket.opened;const id=crypto.randomUUID(),value={socket,reader:socket.readable.getReader(),writer:socket.writable.getWriter(),remainder:new Uint8Array(),pending:null};
      this.sockets.set(id,value);return {socket_id:id};
    }
    const s=this.sockets.get(item.socket_id);if(!s)deny();
    if(item.kind==='tcp-write'){const bytes=decode(item.body);if(bytes.length>1024*1024)deny();await s.writer.write(bytes);return {written:bytes.length};}
    if(item.kind==='tcp-close'){await s.socket.close();this.sockets.delete(item.socket_id);return {closed:true};}
    if(item.kind!=='tcp-read'||!Number.isInteger(item.size)||item.size<1||item.size>65536)deny();
    if(!s.remainder.length){s.pending ||= s.reader.read();let timer;
      const value=await Promise.race([s.pending,new Promise(resolve=>{timer=setTimeout(()=>resolve(null),Math.min(30,Math.max(1,item.timeout || 10))*1000);})]);
      clearTimeout(timer);if(value===null)return {timeout:true};s.pending=null;if(value.done)return {body:''};s.remainder=value.value;}
    const bytes=s.remainder.slice(0,item.size);s.remainder=s.remainder.slice(item.size);return {body:encode(bytes)};
  }
  async close(){for(const s of this.sockets.values())try{await s.socket.close();}catch{}this.sockets.clear();}
}

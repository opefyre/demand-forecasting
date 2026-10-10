import contract from '../../app/cloud_api_contract.json';

export function companyRoute(method,path) {
  if(typeof path!=='string' || path.length>512)return null;
  return contract.find(entry=>entry.method===method && new RegExp('^'+entry.path.replace('{id}','[a-zA-Z0-9_-]{1,128}')+'$').test(path)) || null;
}
export function savedResponse(entry,url,document) {
  const query=url.searchParams;
  const allowed=entry.collection?['limit','offset','include_archived']:entry.demand?['customer','sku','period']:entry.methods?['frequency','profile']:[];
  if([...query.keys()].some(key=>!allowed.includes(key) || query.getAll(key).length!==1))return {status:400,body:{detail:'Unsupported query parameter'}};
  let path=url.pathname.replace(/^\/api\/v1/,'');
  if(entry.methods) {
    const frequency=query.get('frequency') || 'monthly',profile=query.get('profile') || 'fast';
    if(!['monthly','weekly','daily'].includes(frequency) || !['fast','deep'].includes(profile))return {status:422,body:{detail:'Choose a valid frequency and profile'}};
    path+='?frequency='+frequency+'&profile='+profile;
  }
  const value=document.views[path];
  if(!value)return {status:404,body:{detail:'Company resource not found'}};
  if(entry.collection) {
    const integer=(key,fallback)=>query.has(key)?(/^\d+$/.test(query.get(key))?Number(query.get(key)):NaN):fallback;
    const limit=integer('limit',100),offset=integer('offset',0),archived=query.get('include_archived') || 'false';
    if(!Number.isSafeInteger(limit) || limit<1 || limit>1000 || !Number.isSafeInteger(offset) || offset<0 || !['true','false','1','0'].includes(archived))return {status:422,body:{detail:'Check pagination and archive filters'}};
    const rows=value[entry.collection].filter(row=>['true','1'].includes(archived) || (entry.collection==='customers'?row.active:!row.lifecycle?.archived));
    return {status:200,body:{[entry.collection]:rows.slice(offset,offset+limit),total:rows.length,offset,limit}};
  }
  if(entry.demand)return {status:200,body:{...value,rows:value.rows.filter(row=>
    (!query.get('customer') || row.customer===query.get('customer')) && (!query.get('sku') || row.sku===query.get('sku')) &&
    (!query.get('period') || row.period.slice(0,7)===query.get('period').slice(0,7)))}};
  return {status:200,body:value};
}

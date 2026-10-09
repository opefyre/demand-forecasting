// Explicit adapter for the existing screens. Unknown business calls fail closed.
import {RequestFailure} from './request-errors.mjs';
let company=false;
export const companyMode=()=>company;
export const companyPage=value=>company&&value==='forecast'?'demand':value;
export function configureCompanyApi(access){company=access?.mode==='better_auth';}

export function companyPath(value,method='GET'){
  const url=new URL(value,'http://app.local');
  const path=url.pathname;
  if(path.startsWith('/api/v1/')||path.startsWith('/api/auth/')||path.startsWith('/api/login/')||path==='/api/health')return path+url.search;
  const exact={'/api/workspace':'/workspace','/api/site':'/settings/site','/api/units':'/units',
    '/api/datasets':'/datasets','/api/datasets/validate':'/datasets/preview','/api/sources':'/sources',
    '/api/customers':'/customers','/api/customers/preview':'/customers/imports/preview',
    '/api/jobs':'/jobs','/api/run-list':'/runs','/api/sales/schema':'/orders/schema',
    '/api/sales/sources':'/sources','/api/sales/views':'/views','/api/sales/releases':'/releases',
    '/api/factors':'/factors','/api/live-sources':'/connections/external-sources',
    '/api/forecast-updates':'/forecast-updates','/api/recurring-forecasts':'/recurring-forecasts'};
  let target=exact[path];
  if(path==='/api/jobs'&&method==='POST')target='/scenario-jobs';
  const rules=[
    [/^\/api\/ai\/(.+)$/,'/ai/$1'],
    [/^\/api\/forecast-updates\/(.+)$/,'/forecast-updates/$1'],
    [/^\/api\/recurring-forecasts\/(.+)$/,'/recurring-forecasts/$1'],
    [/^\/api\/sources\/(.+)$/,'/sources/$1'],
    [/^\/api\/customers\/([a-f\d]+)(.*)$/,'/customers/$1$2'],
    [/^\/api\/datasets\/([^/]+)\/forecast-orders(.*)$/,'/datasets/$1/orders$2'],
    [/^\/api\/datasets\/([^/]+)\/forecast-factors(.*)$/,'/datasets/$1/factors$2'],
    [/^\/api\/datasets\/([^/]+)\/forecast-settings$/,'/datasets/$1/forecast-settings'],
    [/^\/api\/datasets\/([^/]+)$/,'/datasets/$1'],
    [/^\/api\/order-books\/([^/]+)$/,'/datasets/$1/orders'],
    [/^\/api\/jobs\/([^/]+)(.*)$/,'/jobs/$1$2'],
    [/^\/api\/runs\/([^/]+)$/,'/runs/$1'],
    [/^\/api\/runs\/([^/]+)\/(factor-links|factor-batch|factor-preparation|factor-profiles|factor-comparison|factors)(.*)$/,'/runs/$1/$2$3'],
    [/^\/api\/sales\/runs\/([^/]+)\/(order-reuse|order-comparison)(.*)$/,'/runs/$1/$2$3'],
    [/^\/api\/sales\/runs\/([^/]+)\/inputs$/,'/runs/$1/order-snapshots'],
    [/^\/api\/sales\/runs\/([^/]+)\/starter$/,'/runs/$1/orders/starter'],
    [/^\/api\/sales\/runs\/([^/]+)\/template\/(customers|orders|commitments)$/,'/runs/$1/orders/template/$2'],
    [/^\/api\/sales\/inputs\/([^/]+)\/outlook$/,'/order-snapshots/$1/demand'],
    [/^\/api\/sales\/inputs\/([^/]+)\/export$/,'/order-snapshots/$1/export'],
    [/^\/api\/sales\/inputs\/([^/]+)$/,'/order-snapshots/$1'],
    [/^\/api\/sales\/sources\/([^/]+)\/preview$/,'/sources/$1/preview'],
    [/^\/api\/sales\/releases\/(.+)$/,'/releases/$1'],
    [/^\/api\/actuals\/sources\/([^/]+)\/preview$/,'/sources/$1/preview'],
    [/^\/api\/actuals\/([^/]+)\/review$/,'/runs/$1/actuals/preview'],
    [/^\/api\/actuals\/([^/]+)$/,'/runs/$1/actuals'],
    [/^\/api\/actual-results\/([^/]+)(.*)$/,'/actuals/$1$2'],
    [/^\/api\/export\/([^/]+)\/(csv|xlsx|models|drivers)$/,'/runs/$1/files/$2'],
    [/^\/api\/live-sources\/(.+)$/,'/connections/external-sources/$1'],
  ];
  if(!target)for(const [pattern,replacement] of rules)if(pattern.test(path)){target=path.replace(pattern,replacement);break;}
  if(!target)throw new RequestFailure('This workflow is not available in company access yet.',{status:503});
  if(method==='POST'&&/^\/datasets\/[^/]+\/orders$/.test(target))target+='/snapshots';
  if(target==='/customers'&&method==='GET')url.searchParams.set('include_archived','true');
  return '/api/v1'+target+url.search;
}

export function apiLink(url){return company&&typeof url==='string'&&url.startsWith('/api/')?companyPath(url):url;}

export async function companyRequest(url,body,method,send){
  if(!company)return send(url,body,method);
  const verb=(method||(body?'POST':'GET')).toUpperCase();
  let target;
  if(url==='/api/sales/validate'||url==='/api/sales/inputs'){
    const id=body?.inputs?.run_id;
    if(!id)throw new RequestFailure('Choose a forecast first.',{status:400});
    target='/api/v1/runs/'+encodeURIComponent(id)+'/order-snapshots'+(url.endsWith('validate')?'/preview':'');
  }else if(url==='/api/actuals/sources')target='/api/v1/sources';
  else if(url==='/api/customers'&&verb==='POST'&&body?.customers)target='/api/v1/customers/imports';
  else target=companyPath(url,verb);
  if(target==='/api/v1/datasets'||target==='/api/v1/datasets/preview'){
    if(verb==='POST'){
      const {name,sources,settings,classification,accept_warnings,parent_dataset_id,request_id}=body;
      body={name,sources:Object.fromEntries(Object.entries(sources).filter(([,v])=>v)),settings,classification,
        accept_warnings:!!accept_warnings,parent_dataset_id:parent_dataset_id||null,request_id:request_id||crypto.randomUUID()};
    }
  }
  if(typeof FormData!=='undefined'&&body instanceof FormData&&target==='/api/v1/sources'){
    const copy=new FormData();for(const [k,v] of body.entries())copy.append(k,v);
    const role=copy.get('role');
    if(url==='/api/actuals/sources')copy.set('role','actuals');
    else if(['orders','commitments','customers'].includes(role))copy.set('role','sales_'+role);
    body=copy;
  }
  if(/^\/api\/sales\/releases\/[^/]+\/approve$/.test(url))body={reviewed:body.reviewed,review_token:body.review_token};
  const value=await send(target,body,method);
  if(/^\/api\/datasets\/[^/]+\/forecast-orders\/preview$/.test(url))return value;
  if(/^\/api\/jobs\/[^/]+$/.test(url)&&verb==='GET'&&value.state==='succeeded')return value;
  return value;
}

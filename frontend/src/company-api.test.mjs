import test from 'node:test';
import assert from 'node:assert/strict';
import {companyPath,companyPage,companyRequest,configureCompanyApi,apiLink} from './company-api.mjs';

test('company screens use explicit public routes without shared-data fallback',()=>{
  const paths={
    '/api/workspace':'/api/v1/workspace',
    '/api/ai/conversations?status=archived':'/api/v1/ai/conversations?status=archived',
    '/api/sales/inputs/abc/outlook':'/api/v1/order-snapshots/abc/demand',
    '/api/sales/runs/abc/starter':'/api/v1/runs/abc/orders/starter',
    '/api/sales/runs/abc/template/orders':'/api/v1/runs/abc/orders/template/orders',
    '/api/actuals/abc/review':'/api/v1/runs/abc/actuals/preview',
    '/api/actual-results/abc/export':'/api/v1/actuals/abc/export',
    '/api/live-sources/industry/refresh':'/api/v1/connections/external-sources/industry/refresh',
    '/api/customers/abcd/factor-profiles':'/api/v1/customers/abcd/factor-profiles',
    '/api/export/abc/models':'/api/v1/runs/abc/files/models',
  };
  for(const [legacy,current] of Object.entries(paths))assert.equal(companyPath(legacy),current);
  assert.throws(()=>companyPath('/api/production/abc'));
  assert.throws(()=>companyPath('/api/forecast-updates'));
  assert.equal(companyPath('/api/datasets/abc/forecast-orders','POST'),'/api/v1/datasets/abc/orders/snapshots');
});
test('company writes match strict contracts, preserving originals and request identifiers',async()=>{
  configureCompanyApi({mode:'better_auth'});
  assert.equal(companyPage('forecast'),'demand');
  assert.equal(companyPage('plans'),'plans');
  const calls=[],send=async(...args)=>{calls.push(args);return {};};
  const body={name:'Sales',sources:{history:'file',future:''},settings:{horizon:10},classification:'synthetic_sample',request_id:'stable-id'};
  await companyRequest('/api/datasets',body,undefined,send);
  assert.deepEqual(calls[0][1].sources,{history:'file'});assert.equal(body.sources.future,'');
  assert.equal(calls[0][1].request_id,'stable-id');
  await companyRequest('/api/sales/validate',{inputs:{run_id:'abc'}},undefined,send);
  assert.equal(calls[1][0],'/api/v1/runs/abc/order-snapshots/preview');
  const orders=new FormData();orders.append('role','orders');
  await companyRequest('/api/sales/sources',orders,undefined,send);
  assert.equal(calls[2][1].get('role'),'sales_orders');assert.equal(orders.get('role'),'orders');
  await companyRequest('/api/sales/releases/abc/approve',{reviewed:true,review_token:'token',demo_confirmed:true},undefined,send);
  assert.deepEqual(calls[3][1],{reviewed:true,review_token:'token'});
  await assert.rejects(()=>companyRequest('/api/sales/validate',{},undefined,send));
  assert.equal(calls.length,4);
  configureCompanyApi({mode:'local'});
  assert.equal(companyPage('forecast'),'forecast');
});
test('downloads and conversations use company routes; local mode stays unchanged',async()=>{
  configureCompanyApi({mode:'better_auth'});
  assert.equal(apiLink('/api/ai/conversations/abc/export'),'/api/v1/ai/conversations/abc/export');
  assert.equal(apiLink('https://provider.example/docs'),'https://provider.example/docs');
  configureCompanyApi({mode:'local'});
  assert.equal(apiLink('/api/ai/conversations/abc/export'),'/api/ai/conversations/abc/export');
  let original;
  await companyRequest('/api/forecast-updates',{run_id:'abc'},'POST',async(...args)=>{original=args;});
  assert.deepEqual(original,['/api/forecast-updates',{run_id:'abc'},'POST']);
});

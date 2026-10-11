import {test} from 'node:test';
import assert from 'node:assert/strict';
import {isAppDownload,readDownload,installDownloads} from './downloads.mjs';
import {configureCloudTransport} from './cloud-transport.mjs';
import {recoveryPresentation} from './request-errors.mjs';

test('only known app export routes are intercepted',()=>{
  for(const path of ['/api/v1/runs/r/files/xlsx','/api/v1/releases/r/export','/api/v1/datasets/d/orders/template/csv','/api/export/r/models','/api/sales/inputs/s/export','/api/sales/releases/r/export','/api/plans/p/export'])assert.equal(isAppDownload(path),true,path);
  for(const path of ['/api/v1/customers','/api/v1/runs/r/files/delete','/api/export/r/unknown','/settings','/api/sales/inputs/s'])assert.equal(isAppDownload(path),false,path);
});
test('export errors retain status and cooldown and never replay requests',async()=>{
  configureCloudTransport(null);let calls=0;
  await assert.rejects(()=>readDownload('/api/sales/inputs/s/export',{fetcher:async(path,options)=>{
    calls++;assert.equal(options.method,'GET');return Response.json({detail:'Try later'},{status:429,headers:{'Retry-After':'60'}});
  }}),error=>{
    assert.equal(error.status,429);assert.equal(error.operation,'download');assert.ok(error.retryAt>Date.now());
    assert.equal(recoveryPresentation(error).canReload,false);return true;
  });assert.equal(calls,1);
});
test('connection failures and non-attachment responses cannot become downloaded files',async()=>{
  for(const fetcher of [async()=>{throw Error('offline');},async()=>Response.json({detail:'not a file'})]){
    await assert.rejects(()=>readDownload('/api/export/r/xlsx',{fetcher}),error=>{
      assert.equal(error.name,'RequestFailure');assert.equal(error.operation,'download');
      assert.equal(recoveryPresentation(error).next,'Try the download again. Your forecast is unchanged.');return true;
    });
  }
});
test('successful exports retain bytes and safe filenames; session changes cancel delivery',async()=>{
  const fetcher=async()=>new Response(new Uint8Array([80,75,1,2]),{headers:{'Content-Disposition':'attachment; filename="../forecast.xlsx"'}});
  const result=await readDownload('/api/export/r/xlsx',{fetcher});
  assert.deepEqual([...new Uint8Array(await result.blob.arrayBuffer())],[80,75,1,2]);assert.equal(result.filename,'.._forecast.xlsx');
  await assert.rejects(()=>readDownload('/api/export/r/xlsx',{fetcher,isCurrent:()=>false}),error=>error.status===401);
});
test('local failed download stays in the app, blocks double click and permits a later retry',async()=>{
  const originalLocation=globalThis.location;globalThis.location={href:'http://localhost/demand',origin:'http://localhost'};
  let listener,calls=0,finish;const errors=[];
  const root={addEventListener:(_,fn)=>{listener=fn;},removeEventListener:(_,fn)=>assert.equal(fn,listener)};
  const stop=installDownloads({root,onError:error=>errors.push(error),fetcher:async()=>{calls++;return new Promise(resolve=>{finish=resolve;});}});
  const link={href:'http://localhost/api/sales/inputs/s/export?kind=xlsx'};
  let prevented=0;
  const event={button:0,target:{closest:()=>link},preventDefault:()=>{prevented++;}};
  try{
    const first=listener(event);await listener(event);assert.equal(calls,1);assert.equal(prevented,2);
    finish(Response.json({detail:'Unavailable'},{status:503}));await first;
    assert.equal(errors.length,1);assert.equal(errors[0].status,503);
    const retry=listener(event);assert.equal(calls,2);finish(Response.json({detail:'Unavailable'},{status:503}));await retry;
    assert.equal(errors.length,2);
  }finally{stop();globalThis.location=originalLocation;}
});
test('a local company change cannot deliver a pending file or stale error',async()=>{
  const originalLocation=globalThis.location;globalThis.location={href:'http://localhost/demand',origin:'http://localhost'};
  const access=id=>({mode:'better_auth',user:{company_id:id,subject:'owner'}});
  configureCloudTransport(access('a'));
  let listener,finish;const errors=[];
  const stop=installDownloads({root:{addEventListener:(_,fn)=>{listener=fn;},removeEventListener:()=>{}},onError:error=>errors.push(error),fetcher:async()=>new Promise(resolve=>{finish=resolve;})});
  try{
    const pending=listener({button:0,target:{closest:()=>({href:'http://localhost/api/v1/releases/r/export'})},preventDefault:()=>{}});
    configureCloudTransport(access('b'));
    finish(new Response('secret export',{headers:{'Content-Disposition':'attachment; filename="report.csv"'}}));await pending;
    assert.deepEqual(errors,[]);
  }finally{stop();configureCloudTransport(null);globalThis.location=originalLocation;}
});

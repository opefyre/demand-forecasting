import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Miniflare,convertV4MiniflareOptions} from 'miniflare';

// Disposable native runtime only: no company data, credentials or deployment.
test('native Worker does not support redirect:error; manual is supported', {timeout:30000}, async()=>{
  const runtime=new Miniflare(convertV4MiniflareOptions({telemetry:{enabled:false},modules:true,
    compatibilityDate:'2026-10-09',script:`export default {async fetch(){
      const result={};
      for(const redirect of ['error','manual'])try{
        const request=new Request('https://cloudflare-dns.com/dns-query?name=api.worldbank.org&type=A',
          {headers:{accept:'application/dns-json'},redirect,signal:AbortSignal.timeout(5000)});
        result[redirect]={supported:true,redirect:request.redirect};
      }catch(error){result[redirect]={supported:false,name:error.name};}
      return Response.json(result);
    }};`}));
  try {
    const result=await (await runtime.dispatchFetch('http://test.local/')).json() as any;
    assert.deepEqual(result,{error:{supported:false,name:'TypeError'},manual:{supported:true,redirect:'manual'}});
  }finally{await runtime.dispose();}
});

test('actual broker validates DNS in native runtime and refuses redirects/private answers',{timeout:30000},async()=>{
  const runtime=new Miniflare(convertV4MiniflareOptions({telemetry:{enabled:false},compatibilityDate:'2026-10-09',
    modules:[{type:'ESModule',path:'main.js',contents:`import {NetworkBroker,networkFailureReason} from './network-broker.mjs';
      export default {async fetch(request){
        const mode=new URL(request.url).pathname;
        const fetcher=async(url,options)=>{
          // Native Request catches unsupported init values hidden by Node fakes.
          const native=new Request(url,options);
          if(native.redirect!=='manual')throw Error('Native DNS redirect guard missing');
          if(mode==='/redirect')return new Response(null,{status:302,headers:{location:'https://other.test/'}});
          return Response.json({Answer:mode==='/private'?[{type:1,data:'8.8.8.8'},{type:1,data:'127.0.0.1'}]:[{type:1,data:'8.8.8.8'}]});
        };
        try{return Response.json({address:await new NetworkBroker({}, {}, {}, {fetcher}).publicHost('api.worldbank.org')});}
        catch(error){return Response.json({reason:networkFailureReason(error)});}
      }};`},
      {type:'ESModule',path:'network-broker.mjs',contents:await readFile(new URL('../../deploy/cloudflare/network-broker.mjs',import.meta.url),'utf8')}
    ]}));
  try {
    assert.deepEqual(await (await runtime.dispatchFetch('http://test.local/good')).json(),{address:'8.8.8.8'});
    assert.deepEqual(await (await runtime.dispatchFetch('http://test.local/private')).json(),{reason:'dns'});
    assert.deepEqual(await (await runtime.dispatchFetch('http://test.local/redirect')).json(),{reason:'redirect'});
  }finally{await runtime.dispose();}
});

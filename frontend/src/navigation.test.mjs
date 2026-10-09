import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {workspacePage,workspaceRequest,workspacePath,writeWorkspaceLocation} from './navigation.mjs';

test('every workspace page has a clean URL and supports direct loading',()=>{
  for(const page of ['today','demand','forecast','data','plans','settings','customers','help']){
    assert.equal(workspacePath(page),'/'+page);
    assert.equal(workspacePage(workspaceRequest({pathname:'/'+page,hash:''})),page);
    assert.equal(workspaceRequest({pathname:'/'+page+'/',hash:''}),page);
  }
});
test('old bookmarks migrate without changing their destination',()=>{
  assert.equal(workspacePath(workspaceRequest({pathname:'/',hash:'#demand'})),'/demand');
  assert.equal(workspacePath(workspaceRequest({pathname:'/',hash:'#assistant'})),'/today');
  assert.equal(workspaceRequest({pathname:'/',hash:'#new'}),'new');
  assert.equal(workspacePath('new'),'/demand');
  assert.equal(workspaceRequest({pathname:'/help',hash:'#some-section'}),'help');
  assert.equal(workspacePath('unknown'),'/today');
});
test('navigation pushes history only when needed; initial normalization replaces it',()=>{
  const calls=[],history={pushState:(...args)=>calls.push(['push',...args]),replaceState:(...args)=>calls.push(['replace',...args])};
  writeWorkspaceLocation(history,{pathname:'/today',hash:'',search:''},'demand');
  assert.deepEqual(calls.pop(),['push',null,'','/demand']);
  writeWorkspaceLocation(history,{pathname:'/demand',hash:'',search:''},'demand');
  assert.equal(calls.length,0);
  writeWorkspaceLocation(history,{pathname:'/',hash:'#demand',search:'?test=1'},'demand',{replace:true,preserveSearch:true});
  assert.deepEqual(calls.pop(),['replace',null,'','/demand?test=1']);
});
test('app uses browser history and contains no hash-based page links',async()=>{
  const main=await readFile(new URL('main.jsx',import.meta.url),'utf8');
  assert.match(main,/addEventListener\("popstate", listener\)/);
  assert.match(main,/removeEventListener\("popstate", listener\)/);
  assert.doesNotMatch(main,/location\.hash\s*=/);
  for(const file of ['main.jsx','ui-sidebar.jsx','input-mapping-proposal.jsx']){
    assert.doesNotMatch(await readFile(new URL(file,import.meta.url),'utf8'),/href=["']#(?:today|data|demand|forecast)/);
  }
});

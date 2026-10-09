import test from 'node:test';
import assert from 'node:assert/strict';
import {scopedStorage,configureWorkspaceStorage,workspaceContextKey,localState,sessionState} from './workspace-storage.mjs';

const memory=()=>{const values=new Map();return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value),removeItem:key=>values.delete(key)};};
test('personal browser drafts are separated by company and user; local demo keys stay unchanged',()=>{
  const original=[globalThis.localStorage,globalThis.sessionStorage];
  globalThis.localStorage=memory();globalThis.sessionStorage=memory();
  try{
    const access=(company_id,subject)=>({mode:'better_auth',user:{company_id,subject,issuer:'app'}});
    configureWorkspaceStorage({mode:'local'});localState.setItem('draft','local');
    configureWorkspaceStorage(access('a','planner'));assert.equal(localState.getItem('draft'),null);
    localState.setItem('draft','A');sessionState.setItem('wizard','A review');
    configureWorkspaceStorage(access('b','planner'));assert.equal(localState.getItem('draft'),null);assert.equal(sessionState.getItem('wizard'),null);
    configureWorkspaceStorage(access('a','viewer'));assert.equal(localState.getItem('draft'),null);
    configureWorkspaceStorage(access('a','planner'));assert.equal(localState.getItem('draft'),'A');assert.equal(sessionState.getItem('wizard'),'A review');
    localState.removeItem('draft');configureWorkspaceStorage({mode:'local'});assert.equal(localState.getItem('draft'),'local');
  }finally{[globalThis.localStorage,globalThis.sessionStorage]=original;configureWorkspaceStorage({mode:'local'});}
});
test('scoped storage cannot remove another namespace',()=>{
  const raw=memory(),a=scopedStorage(raw,'a:'),b=scopedStorage(raw,'b:');
  a.setItem('draft','A');b.setItem('draft','B');a.removeItem('draft');
  assert.equal(b.getItem('draft'),'B');assert.equal(a.getItem('draft'),null);
});
test('access changes discard mounted report/chat state, not just company switches',()=>{
  const user={issuer:'app',company_id:'a',subject:'planner',role:'planner',permissions:['drafts:read','reports:read']};
  const key=workspaceContextKey({mode:'better_auth',user});
  for(const changed of [{company_id:'b'},{issuer:'other'},{subject:'other'},
    {role:'viewer'},{permissions:['reports:read']}]){
    assert.notEqual(workspaceContextKey({mode:'better_auth',user:{...user,...changed}}),key);
  }
  assert.equal(workspaceContextKey({mode:'better_auth',user:{...user,permissions:[...user.permissions].reverse()}}),key);
});

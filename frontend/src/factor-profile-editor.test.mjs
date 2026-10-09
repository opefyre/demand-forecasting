import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
let server,ExposureFields,blankExposure;
before(async()=>{server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});({ExposureFields,blankExposure}=await server.ssrLoadModule('/src/factor-profile-editor.jsx'));});
after(async()=>{await server?.close();});
const ui={Field:({title,children})=>React.createElement('label',null,title,children),
  Pick:({label,options,value,disabled})=>React.createElement('select',{'aria-label':label,value,disabled,onChange(){}},options.map(([v,t])=>React.createElement('option',{key:v,value:v},t))),
  Button:({children,...props})=>React.createElement('button',props,children)};
test('exposure fields use explicit declarations, not future values or invented defaults',()=>{
  assert.deepEqual(blankExposure(),{currency_exposure:false,global_supply:false,hormuz_route:false,materials:[]});
  const html=renderToStaticMarkup(React.createElement(ExposureFields,{value:blankExposure(),materials:[['lead','Lead']],ui,onChange(){}}));
  assert.match(html,/Currency changes/);assert.match(html,/Hormuz/);assert.match(html,/Lead/);
  assert.doesNotMatch(html,/checked=""|future|inflation assumption|forecast quantity/);
});
test('readonly exposure fields cannot mutate a profile; selected materials are not offered twice',()=>{
  const html=renderToStaticMarkup(React.createElement(ExposureFields,{value:{...blankExposure(),materials:['lead']},materials:[['lead','Lead']],ui,disabled:true,onChange(){}}));
  assert.match(html,/Lead ×/);assert.doesNotMatch(html,/<option[^>]*value="lead"/);
  assert.equal((html.match(/type="checkbox" disabled=""/g)||[]).length,3);
});

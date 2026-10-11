import {test,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
const compiler=await createServer({server:{middlewareMode:true,hmr:false,ws:false,watch:null},appType:'custom'});
const {Commitments}=await compiler.ssrLoadModule('/src/commitments.jsx');
const {i18n}=await compiler.ssrLoadModule('/src/localization.mjs');
after(async()=>{await i18n.changeLanguage('en');await compiler.close();});
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),Table:({headers,children})=>React.createElement('table',null,React.createElement('thead',null,React.createElement('tr',null,headers.map((text,index)=>React.createElement('th',{key:index},text)))),React.createElement('tbody',null,children))};
const inputs={customers:[{customer:'Mehr',sku:'001',unit:'tonnes'}],commitments:[{customer:'Mehr',sku:'001',unit:'tonnes',period:'2026-09-23',quantity:'15.123456',owner:'Planner',reason:'Complete monthly requirement',valid_until:'2026-11-01'}]};
const run={run_settings:{calendar_profile:{month_basis:'jalali'}},series:{a:{forecast:[{timestamp:'2026-09-23'}]}}};
test('commitments reuse global disclosure, table and actions, localize copy and keep real calendar keys',async()=>{
 await i18n.changeLanguage('fa');
 const html=renderToStaticMarkup(React.createElement(Commitments,{ui,inputs,run,canEdit:true}));
 assert.match(html,/ui-disclosure/);assert.match(html,/افزودن تعهد ماهانه/);assert.match(html,/۱۴۰۵|1405-07/);assert.match(html,/۱۵/);assert.match(html,/تن/);
 assert.doesNotMatch(html,/style=|tonnes|Complete monthly commitments/);assert.equal(inputs.commitments[0].quantity,'15.123456');
 const readonly=renderToStaticMarkup(React.createElement(Commitments,{ui,inputs,run,canEdit:false}));
 assert.doesNotMatch(readonly,/افزودن تعهد ماهانه/);assert.match(readonly,/disabled/);
});
test('manual commitment editing clears import evidence and locks wizard navigation until applied or cancelled',async()=>{
 const source=await readFile(new URL('forecast-orders.jsx',import.meta.url),'utf8');
 assert.match(source,/onPendingEditChange\?\.\(editingOrder\|\|editingCommitment\)/);
 assert.match(source,/delete next.commitments/);assert.match(source,/editingCommitment\|\|editingOrder\|\|!checked/);
 const editor=await readFile(new URL('commitments.jsx',import.meta.url),'utf8');
 assert.doesNotMatch(editor,/style=/);assert.match(editor,/commitmentError/);assert.match(editor,/Apply changes/);
});

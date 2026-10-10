import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {comparisonLine,chartTheme} from './chart-theme.mjs';
let server,Report,Reuse,Comparison,Mapping,Correction,language;
before(async()=>{
 server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
 ({OrderComparisonReport:Report}=await server.ssrLoadModule('/src/order-comparison.jsx'));
 ({AssistantSavedOrders:Reuse}=await server.ssrLoadModule('/src/order-reuse.jsx'));
 ({AssistantComparison:Comparison}=await server.ssrLoadModule('/src/assistant-comparison.jsx'));
 ({InputMappingProposal:Mapping}=await server.ssrLoadModule('/src/input-mapping-proposal.jsx'));
 ({InputCorrectionProposal:Correction}=await server.ssrLoadModule('/src/input-correction-proposal.jsx'));
 ({i18n:language}=await server.ssrLoadModule('/src/localization.mjs'));
});
after(async()=>{await language?.changeLanguage('en');await server?.close();});
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),
 Table:({headers,children,empty})=>React.createElement('table',null,React.createElement('thead',null,React.createElement('tr',null,headers.map((header,index)=>React.createElement('th',{key:index},header)))),React.createElement('tbody',null,children),empty&&React.createElement('caption',null,empty))};
const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,{ui,...props}));
const row={period:'2026-11-01',unit:'tonnes',booked:12,fulfilled:2,before_remaining:4,after_remaining:null,before_total:18,after_total:null,difference:null};
test('shared comparison keeps unknowns, exact units and Persian calendar; source objects unchanged',async()=>{
 await language.changeLanguage('fa');const original=structuredClone(row);
 const html=render(Report,{rows:[row],basis:'gregorian'});
 assert.match(html,/۱۲/);assert.match(html,/نامشخص/);assert.match(html,/تن/);assert.match(html,/<bdi>/);
 assert.doesNotMatch(html,/Unknown|tonnes|style=|order-comparison-table/);assert.deepEqual(row,original);
 assert.match(render(Report,{rows:[{...row,period:'2026-03-21'}],basis:'jalali'}),/۱۴۰۵|1405/);
 await language.changeLanguage('en');
});
test('empty comparison is explicit, not a zero result',()=>{
 const html=render(Report,{rows:[],basis:'gregorian'});assert.match(html,/No matching customers and SKUs/);assert.doesNotMatch(html,/<td>0/);
});
test('assistant reuses the same saved-order receipt and cannot save missing or expired evidence',()=>{
 const preview={source_name:'Mehr history',customer_count:4,order_count:18,unit:'tonnes',as_of:'2026-10-10',valid_until:'2026-10-20',can_save:false,warnings:[],outside_open_orders:[],months:[{period:'2026-11-01',booked:12,remaining:4,total:18,added:true}]};
 const html=render(Reuse,{action:{preview},canEdit:true});
 assert.match(html,/ui-panel/);assert.match(html,/ui-definition-list/);assert.match(html,/ui-check/);assert.match(html,/<button disabled="">Confirm/);
 assert.doesNotMatch(html,/ai-proposal|order-comparison|style=/);
 const expired=render(Reuse,{action:{preview:{...preview,can_save:true}},canEdit:true,expired:true});assert.match(expired,/expired/);assert.doesNotMatch(expired,/Confirm &amp; save/);
});
test('assistant comparison uses shared receipt, blocks unsaveable draft and preserves missing quantities',()=>{
 const html=render(Comparison,{action:{name:'Tehran outlook',month_basis:'gregorian',preview:{customer_count:4,sku_count:2,months:[row],warnings:[],can_save:false}},canEdit:true});
 assert.match(html,/ui-panel/);assert.match(html,/Unknown/);assert.match(html,/<button disabled="">Approve/);assert.doesNotMatch(html,/ai-comparison|style=/);
});
test('input correction and mapping are shared panels with localized totals and original evidence intact',async()=>{
 await language.changeLanguage('fa');
 const mapping=render(Mapping,{action:{diff:[{field:'date_col',before:null,after:'DATE'}],before_total:12,after_total:12,before_prepared_total:12,after_prepared_total:12,unit:'tonnes'},canEdit:false});
 const correction=render(Correction,{action:{changes:[{row:3,column:'DATE',before:'۱۴۰۵',after:'1405'}],before_prepared_total:12,after_prepared_total:12,unit:'tonnes'},canEdit:true});
 for(const html of [mapping,correction]){assert.match(html,/ui-panel/);assert.match(html,/۱۲/);assert.doesNotMatch(html,/ai-proposal|style=|tonnes/);}
 assert.match(correction,/۱۴۰۵/);assert.match(correction,/&quot;1405&quot;/);assert.match(correction,/<button disabled="">/);
 await language.changeLanguage('en');
});
test('comparison paint is tokenized, distinct and stable when a method is hidden',async()=>{
 const styles=Array.from({length:24},(_,index)=>comparisonLine(index));
 assert.equal(new Set(styles.map(style=>style.stroke+style.strokeDasharray)).size,24);
 assert.notEqual(styles[0].stroke,styles[1].stroke);assert.notEqual(styles[0].strokeDasharray,styles[1].strokeDasharray);
 assert.ok(chartTheme.dot.r>0);
 const source=await readFile(new URL('method-comparison.jsx',import.meta.url),'utf8');
 assert.match(source,/comparisonLine\(entries.findIndex/);assert.doesNotMatch(source,/visible.map\(\(r, i\)/);
 assert.match(source,/interval="preserveStartEnd"/);assert.match(source,/connectNulls=\{false\}/);
});
test('no proposal/comparison-specific appearance survives migration; reviews share collections and revision modal stays fixed',async()=>{
 for(const file of ['assistant-workspace.jsx','assistant-factor-scenario.jsx','assistant-factor-batch.jsx','order-comparison.jsx','order-reuse.jsx','assistant-comparison.jsx','input-mapping-proposal.jsx','input-correction-proposal.jsx']){
  const source=await readFile(new URL(file,import.meta.url),'utf8');assert.doesNotMatch(source,/className="(?:ai-proposal|order-comparison|ai-factor)|style=|Intl.NumberFormat\('en'/);assert.match(source,/<Panel|<Stack/);
 }
 for(const file of ['workspace.css','sales-workspace.css'])assert.doesNotMatch(await readFile(new URL(file,import.meta.url),'utf8'),/\.(?:ai-proposal|ai-comparison|ai-factor-proposal|ai-factor-sources|order-comparison-(?:table|filters|approval))\b/);
 const order=await readFile(new URL('order-comparison.jsx',import.meta.url),'utf8');assert.match(order,/wide fixed/);assert.match(order,/current===version.current/);assert.match(order,/inFlight.current/);assert.match(order,/review_token:report.review_token/);
 assert.match(await readFile(new URL('demand-reviews.jsx',import.meta.url),'utf8'),/<Collection/);
 assert.match(await readFile(new URL('resource-lifecycle.jsx',import.meta.url),'utf8'),/<Modal open=\{!!dialog\} fixed/);
});

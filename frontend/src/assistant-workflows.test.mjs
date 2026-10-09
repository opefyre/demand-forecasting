import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

let server,Messages,Factor,Correction,Repeat,Batch,Receipt,RecurringRows;
before(async()=>{
  server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
  ({AssistantMessages:Messages}=await server.ssrLoadModule('/src/assistant-workspace.jsx'));
  ({AssistantFactorScenario:Factor}=await server.ssrLoadModule('/src/assistant-factor-scenario.jsx'));
  ({InputCorrectionProposal:Correction}=await server.ssrLoadModule('/src/input-correction-proposal.jsx'));
  ({RepeatUploadReview:Repeat}=await server.ssrLoadModule('/src/repeat-upload-review.jsx'));
  ({AssistantFactorBatchCard:Batch,BatchJobReceipt:Receipt}=await server.ssrLoadModule('/src/assistant-factor-batch.jsx'));
  ({RecurringRows}=await server.ssrLoadModule('/src/recurring-forecasts.jsx'));
});

test('formatting card shows quoted spaces and cannot save before review',()=>{
  const action={reason:'Trim spaces',changes:[{row:1,column:'Customer',before:' A ',after:'A'}],before_prepared_total:21,after_prepared_total:21,unit:'tonnes',warnings:[],row_reference:'Parsed data-row index, not an Excel cell address.'};
  const html=renderToStaticMarkup(React.createElement(Correction,{action,ui,canEdit:true}));
  assert.match(html,/&quot; A &quot;/);assert.match(html,/&quot;A&quot;/);
  assert.match(html,/<button disabled=""/);assert.match(html,/type="checkbox"/);
  assert.match(html,/21 → 21 tonnes/);assert.match(html,/Original files, orders and forecasts stay unchanged/);
});
test('saved and expired correction cards cannot replay a save',()=>{
  const action={changes:[],warnings:[]};
  const html=renderToStaticMarkup(React.createElement(Correction,{action,ui,canEdit:true,expired:true}));
  assert.match(html,/expired/);assert.doesNotMatch(html,/Approve &amp; save/);
});
test('repeat review distinguishes removal from zero sales and explains full replacement',()=>{
  const review={before_rows:6,after_rows:6,before_total:21,after_total:81,unit:'tonnes',added_groups:1,changed_groups:1,removed_groups:1,
    removed_periods:['2026-03-21'],message:'This file replaces full history, not appended.',same_file_contents:false,retained_factors:true,change_count:1,
    changes:[{scope:['A','P'],period:'2026-03-21',before:1,after:null}]};
  const html=renderToStaticMarkup(React.createElement(Repeat,{review,ui,basis:'jalali'}));
  assert.match(html,/1405-01/);assert.match(html,/Not present/);assert.match(html,/not appended/);
  assert.match(html,/check their dates/);assert.match(html,/Missing previous months/);
});
test('assistant history refresh has one actionable handoff, no fake export',()=>{
  const html=renderToStaticMarkup(React.createElement(Messages,{turns:[{id:'t',question:'New sales',answer:'Review updated history.',actions:[{kind:'history_refresh'}]}],ui,canEdit:true}));
  assert.match(html,/Open history upload/);assert.match(html,/Upload complete updated history/);assert.doesNotMatch(html,/Prepare this export/);
});
after(async()=>{await server?.close();});
test('monthly update has one handoff, shows its navigation receipt and blocks expired actions',()=>{
  const render=turn=>renderToStaticMarkup(React.createElement(Messages,{turns:[{id:'t',question:'Update',answer:'Review',actions:[{kind:'monthly_update'}],...turn}],ui,canEdit:true}));
  assert.match(render({}),/Start forecast update/);
  assert.doesNotMatch(render({actions_expired:true}),/Start forecast update|Open forecast update/);
  assert.match(render({results:{0:{workflow:'monthly_update'}}}),/Open forecast update/);
  assert.doesNotMatch(render({actions_expired:true,results:{0:{workflow:'monthly_update'}}}),/Open forecast update/);
  assert.doesNotMatch(render({}),/Prepare this export|Production|Inventory/);
});
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),
  Table:({headers,children})=>React.createElement('table',null,React.createElement('tbody',null,children))};
test('profile-source card is a review handoff, not a run or approval',()=>{
  const action={kind:'factor_preparation',profile:{customer:'A',target_sku:'P1',target_unit:'tonnes'},sources:[{name:'Exchange rate',note:'Refresh needed.'}]};
  const render=extra=>renderToStaticMarkup(React.createElement(Messages,{turns:[{id:'t',question:'Use my factors',answer:'Ready for review.',actions:[action],...extra}],ui,canEdit:true}));
  assert.match(render({}),/Review sources/);assert.match(render({}),/A · P1 · tonnes/);
  assert.match(render({}),/Refresh needed/);assert.doesNotMatch(render({}),/Confirm &amp; run|Prepare this export|approved/);
  assert.doesNotMatch(render({actions_expired:true}),/Review sources/);
});
const preview={scope:'1 selected customer–SKU series; others keep their baseline',method:'model:Ridge + drivers',
  factors:[{factor:'Supply pressure',geography:'Global',unit:'index',lag_months:2,policy:'Archived monthly timing'}],
  future_rows:[{factor:'Supply pressure',sales_month:'2026-03-21',value:2,unit:'index',treatment:'planning_assumption'}],
  warnings:[],policy:'Review publication timing.',retrospective:true};

test('factor card requires explicit review and labels assumptions and what-if limits',()=>{
  const html=renderToStaticMarkup(React.createElement(Factor,{action:{preview},ui,canEdit:true,basis:'jalali'}));
  assert.match(html,/Confirm &amp; calculate/);assert.match(html,/<button disabled=""/);
  assert.match(html,/type="checkbox"/);assert.match(html,/What-if comparison only/);
  assert.match(html,/Your assumption/);assert.match(html,/1405-01/);
  assert.match(html,/others keep their baseline/);
});
test('queued factor result never claims orders copied or an approved forecast',()=>{
  const html=renderToStaticMarkup(React.createElement(Factor,{action:{preview},result:{job:{id:'job'}},ui,canEdit:true}));
  assert.match(html,/Comparison queued/);assert.match(html,/Orders have not been copied/);
  assert.doesNotMatch(html,/type="checkbox"|Confirm &amp; calculate/);
});
test('expired factor proposal cannot execute',()=>{
  const html=renderToStaticMarkup(React.createElement(Factor,{action:{preview},expired:true,ui,canEdit:true}));
  assert.match(html,/expired/);assert.doesNotMatch(html,/Confirm &amp; calculate/);
});
test('long factor explanations remain available but collapsed instead of duplicating the card',()=>{
  const html=renderToStaticMarkup(React.createElement(Messages,{turns:[{id:'t',question:'Compare',
    answer:'Detailed reasoning. '.repeat(30),actions:[{kind:'factor_scenario',preview}]}],ui,canEdit:true}));
  assert.match(html,/<details class="help-details"><summary>Why this scenario\?/);
  assert.match(html,/Detailed reasoning/);assert.match(html,/Compare this factor scenario/);
});
test('order-import card opens review instead of pretending to save or export',()=>{
  const html=renderToStaticMarkup(React.createElement(Messages,{turns:[{id:'t',question:'Add current orders',
    answer:'Review the order file.',actions:[{kind:'order_import',snapshot_id:null}]}],ui,canEdit:true,execute:()=>{}}));
  assert.match(html,/Add customer orders/);assert.match(html,/Open order upload/);
  assert.match(html,/Nothing is saved until you confirm/);assert.doesNotMatch(html,/Prepare this export/);
});
test('order update is labelled correctly and blocked for viewers or expired proposals',()=>{
  for(const expired of [false,true]){
    const html=renderToStaticMarkup(React.createElement(Messages,{turns:[{id:'t',question:'Update',answer:'Review',
      actions_expired:expired,actions:[{kind:'order_import',snapshot_id:'saved'}]}],ui,canEdit:false,execute:()=>{}}));
    assert.match(html,/Update customer orders/);
    if(expired)assert.doesNotMatch(html,/Open order upload/);else assert.match(html,/<button disabled=""/);
  }
});

const batchPreview={groups:[{...preview,scope:[{id:'A',customer:'Customer A',sku:'SKU 1'}]}],unchanged_series_ids:['B'],policy:'No combined accuracy claim.'};
test('batch proposal shows exact scope and dated assumptions, with approval required',()=>{
  const html=renderToStaticMarkup(React.createElement(Batch,{action:{preview:batchPreview},ui,canEdit:true,basis:'jalali'}));
  assert.match(html,/Customer A/);assert.match(html,/SKU 1/);assert.match(html,/1405-01/);
  assert.match(html,/Your assumption/);assert.match(html,/1 other products keep their baseline/);
  assert.match(html,/type="checkbox"/);assert.match(html,/<button disabled=""/);
  assert.match(html,/Confirm &amp; calculate/);assert.match(html,/What-if only/);
});
test('expired batch cannot calculate and queued batch does not claim completion',()=>{
  const render=extra=>renderToStaticMarkup(React.createElement(Batch,{action:{preview:batchPreview},ui,canEdit:true,...extra}));
  assert.doesNotMatch(render({expired:true}),/Confirm &amp; calculate|type="checkbox"/);
  assert.match(render({result:{job:{id:'job'}}}),/Waiting to calculate/);
  assert.doesNotMatch(render({result:{job:{id:'job'}}}),/Forecast ready|Confirm &amp; calculate/);
});
test('batch review handoff is scoped, single-action and expiry protected',()=>{
  const render=extra=>renderToStaticMarkup(React.createElement(Messages,{turns:[{id:'t',question:'Prepare two products',answer:'Review',actions:[{kind:'factor_batch_review',scope:[{customer:'A',sku:'SKU 1'}]}],...extra}],ui,canEdit:true}));
  assert.match(render({}),/A · SKU 1/);assert.match(render({}),/Review batch/);
  assert.doesNotMatch(render({}),/Prepare this export|Confirm &amp; calculate/);
  assert.doesNotMatch(render({actions_expired:true}),/Review batch/);
});
test('completed batch opens order review, while errors never offer an unverified result',()=>{
  const render=status=>renderToStaticMarkup(React.createElement(Receipt,{status,ui}));
  assert.match(render({state:'succeeded',run_id:'valid'}),/Review demand &amp; orders/);
  for(const state of ['failed','cancelled','interrupted']){
    assert.match(render({state}),/No combined result was published/);
    assert.doesNotMatch(render({state}),/Review demand &amp; orders/);
  }
  assert.match(render({error:true}),/role="alert"/);
});
test('recurring queue distinguishes paused, calculating, review and missing-data states',()=>{
  const render=s=>renderToStaticMarkup(React.createElement(RecurringRows,{schedules:[{id:'one',name:'Synthetic sales',classification:'synthetic_sample',basis:'jalali',day:5,...s}],ui,canAdmin:true}));
  assert.match(render({enabled:false}),/Paused/);assert.doesNotMatch(render({enabled:false}),/Check monthly/);
  assert.match(render({enabled:true,cycle:{state:'calculating',update_id:'update'}}),/Calculating draft/);
  assert.match(render({enabled:true,cycle:{state:'review',update_id:'update'}}),/Review update/);
  assert.match(render({enabled:true,cycle:{state:'attention',attention:'Missing reviewed history'}}),/Missing reviewed history/);
  assert.match(render({enabled:true}),/Persian months/);assert.doesNotMatch(render({enabled:true}),/Sample/);
});
test('recurring status does not offer review without a saved update or checking to non-admins',()=>{
  const html=renderToStaticMarkup(React.createElement(RecurringRows,{schedules:[{id:'one',name:'Sales',enabled:true,cycle:{state:'attention',attention:'Missing history'}}],ui,canAdmin:false}));
  assert.doesNotMatch(html,/Review update|Check monthly|approved|export/i);
});

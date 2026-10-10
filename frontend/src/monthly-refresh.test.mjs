import {before,after,test} from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

let server,Progress,Comparison,Exports,Live,Repeat,Handoff,i18n,horizons,settingsKey,FactorChoice,savedUpdate,needsPolling,ReuseReport,sourceOptions;
before(async()=>{server=await createServer({server:{middlewareMode:true,hmr:false,watch:null},appType:'custom'});
  ({UpdateProgress:Progress,UpdateComparison:Comparison,UpdateExports:Exports}=await server.ssrLoadModule('/src/monthly-refresh.jsx'));
  ({LiveCheck:Live}=await server.ssrLoadModule('/src/monthly-refresh.jsx'));
  ({updateHorizons:horizons}=await server.ssrLoadModule('/src/monthly-refresh.jsx'));
  ({updateSettingsKey:settingsKey,FactorChoice}=await server.ssrLoadModule('/src/monthly-refresh.jsx'));
  ({savedForecastUpdate:savedUpdate}=await server.ssrLoadModule('/src/monthly-refresh.jsx'));
  ({updateNeedsPolling:needsPolling}=await server.ssrLoadModule('/src/monthly-refresh.jsx'));
  ({OrderReuseReport:ReuseReport,orderSourceOptions:sourceOptions}=await server.ssrLoadModule('/src/order-reuse.jsx'));
  ({RepeatUploadReview:Repeat}=await server.ssrLoadModule('/src/repeat-upload-review.jsx'));
  ({DemandHandoff:Handoff}=await server.ssrLoadModule('/src/demand-handoff.jsx'));
  ({i18n}=await server.ssrLoadModule('/src/localization.mjs'));
});
after(async()=>{await server?.close();});
const ui={Button:({children,kind,...props})=>React.createElement('button',props,children),
  ErrorBox:({error})=>error?React.createElement('p',{role:'alert'},error):null,
  Modal:({children,fixed})=>React.createElement('div',{'data-fixed':fixed,role:'dialog'},children),
  Help:()=>null,Field:({title,children})=>React.createElement('label',null,title,children),
  Table:({headers,children})=>React.createElement('table',null,React.createElement('tbody',null,children)),
  Pick:({label,options,...props})=>React.createElement('select',{'aria-label':label,...props},options.map(([value,name])=>React.createElement('option',{key:value,value},name)))};

test('progress shows one current step; calculation is not completed just because viewed',()=>{
  const html=renderToStaticMarkup(React.createElement(Progress,{stage:'calculating'}));
  assert.equal((html.match(/aria-current="step"/g)||[]).length,1);
  assert.match(html,/aria-current="step"[^>]*>.*?Forecast/);assert.match(html,/Orders/);assert.doesNotMatch(html,/Production|Inventory/);
});
test('comparison preserves absence, exact Persian months and excludes deliveries from planning',()=>{
  const report={month_basis:'jalali',unit:'tonnes',overlap_before:10,overlap_after:14,added_rows:1,removed_rows:1,
    rows:[{customer:'A',sku:'0001',period:'2026-03-21',change:'added',before_forecast:null,after_forecast:14,after_open_orders:6,after_to_serve:12}],
    orders_note:'Earlier orders are reference only.',warnings:[],as_of:'2026-03-21',valid_until:'2026-04-01'};
  const html=renderToStaticMarkup(React.createElement(Comparison,{report,ui}));
  assert.match(html,/1405-01/);assert.match(html,/0001/);assert.match(html,/Not present/);
  assert.match(html,/matching months only/);assert.match(html,/exclude deliveries/);assert.match(html,/aria-label="Find changed customer, product or month"/);
});
test('export asks whether receiver has orders before generating links',()=>{
  const html=renderToStaticMarkup(React.createElement(Exports,{sessionId:'version',ui}));
  assert.match(html,/already have these customer orders/);assert.doesNotMatch(html,/href=/);
  assert.doesNotMatch(html,/Approved|sent to/);
});
test('updates and new forecasts share the same progress contract without page overrides',()=>{
  const html=renderToStaticMarkup(React.createElement(Progress,{stage:'orders'}));
  assert.match(html,/class="ui-steps"/);assert.doesNotMatch(html,/update-progress|style=/);
  assert.equal((html.match(/data-complete="true"/g)||[]).length,3);
});
test('repeat-upload review uses shared panels and translates absence, counts and units in Persian',async()=>{
  await i18n.changeLanguage('fa');
  try {
    const review={before_rows:144,after_rows:140,before_total:1548,after_total:1511,unit:'tonnes',added_groups:0,changed_groups:1,removed_groups:4,
      removed_periods:['2026-03-21'],change_count:1,changes:[{scope:['Mehr','001'],period:'2026-03-21',before:10,after:null}]};
    const html=renderToStaticMarkup(React.createElement(Repeat,{review,ui,basis:'jalali'}));
    assert.match(html,/class="ui-panel"/);assert.match(html,/ui-definition-list/);assert.match(html,/ui-disclosure/);
    assert.match(html,/۱۴۴/);assert.match(html,/موجود نیست/);assert.match(html,/تن/);assert.match(html,/Mehr/);assert.match(html,/001/);
    assert.doesNotMatch(html,/Not present|tonnes|ai-proposal|style=/);
  } finally {await i18n.changeLanguage('en');}
});
test('live connection review uses a single shared disclosure and localized status',async()=>{
  await i18n.changeLanguage('fa');
  try {
    const html=renderToStaticMarkup(React.createElement(Live,{ui,sources:[{id:'wb',name:'Iran industry',enabled:true,status:'failed',series:[],error:'Unavailable'}]}));
    assert.match(html,/ui-disclosure/);assert.match(html,/ui-definition-list/);assert.match(html,/۱/);
    assert.doesNotMatch(html,/need attention|saved connections|update-source|style=/);
  }finally {await i18n.changeLanguage('en');}
});
test('demand export uses a fixed shared dialog and draft downloads need an exportable outlook',()=>{
  const html=renderToStaticMarkup(React.createElement(Handoff,{open:true,ui,canEdit:true,runId:'r',snapshotId:'s',outlook:{can_export:false,rows:[]}}));
  assert.match(html,/data-fixed="true"/);assert.match(html,/ui-stack/);assert.match(html,/ui-page-nav/);assert.match(html,/ui-actions/);
  assert.doesNotMatch(html,/href=|demand-handoff|release-controls|style=/);
  assert.match(html,/Resolve the flagged inputs/);
});
test('Persian horizon labels keep numeric request values unchanged',async()=>{
  await i18n.changeLanguage('fa');
  try {assert.equal(horizons().length,24);assert.deepEqual(horizons()[5],['6','۶']);assert.equal(Number(horizons()[23][0]),24);}
  finally {await i18n.changeLanguage('en');}
});
test('read-only refresh cannot reset unsaved forecast choices; another step or input can',()=>{
  const session={id:'a',dataset_id:'history',stage:'forecast',revision:1};
  assert.equal(settingsKey(session),settingsKey({...session,live_sources:[],attention:'Updated',revision:2}));
  assert.notEqual(settingsKey(session),settingsKey({...session,dataset_id:'revised'}));
  assert.notEqual(settingsKey(session),settingsKey({...session,stage:'calculating'}));
  assert.notEqual(settingsKey(session),settingsKey({...session,id:'another'}));
});
test('reload reopens only the company-scoped saved update on Forecast with write access',()=>{
  const storage={getItem:key=>key==='demandlab.forecastUpdate'?'a'.repeat(32):null};
  assert.equal(savedUpdate(storage,'demand',true),'a'.repeat(32));
  assert.equal(savedUpdate(storage,'today',true),null);
  assert.equal(savedUpdate(storage,'data',true),null);
  assert.equal(savedUpdate(storage,'demand',false),null);
  assert.equal(savedUpdate({getItem:()=>'<unsafe>'},'demand',true),null);
  assert.equal(savedUpdate({getItem:()=>{throw Error('blocked');}},'demand',true),null);
});
test('completed or stopped calculations do not poll, wake the engine or conflict with review writes',()=>{
  for(const stage of ['calculating','factor_calculating']){
    for(const state of ['queued','running'])assert.equal(needsPolling({stage,job:{state}}),true);
    for(const state of ['succeeded','failed','cancelled','interrupted'])assert.equal(needsPolling({stage,job:{state}}),false);
  }
  for(const stage of ['history','forecast','factors','orders','review','ready'])assert.equal(needsPolling({stage}),false);
  assert.equal(needsPolling(null),false);
});
test('already included factors are never described as a history-only baseline',async()=>{
  const html=renderToStaticMarkup(React.createElement(FactorChoice,{hasFactors:true,ui}));
  assert.match(html,/Review included factors/);assert.match(html,/Keep included factors/);
  assert.match(html,/ui-panel/);assert.match(html,/ui-actions/);
  assert.doesNotMatch(html,/Include external factors|Keep calculated baseline|style=/);
  await i18n.changeLanguage('fa');
  try{const fa=renderToStaticMarkup(React.createElement(FactorChoice,{hasFactors:true,ui}));
    assert.match(fa,/بررسی عوامل لحاظ‌شده/);assert.doesNotMatch(fa,/Keep included factors|Review included factors/);
  }finally{await i18n.changeLanguage('en');}
});
test('same-name order sources remain distinguishable without changing their saved IDs',()=>{
  const rows=[{id:'a'.repeat(32),name:'Tehran',as_of:'2026-10-10'},{id:'b'.repeat(32),name:'Tehran',as_of:'2026-10-10'},
    {id:'c'.repeat(32),name:'Mehr',as_of:'2026-10-10'}];
  const options=sourceOptions(rows);
  assert.deepEqual(options.map(([key])=>key),rows.map(r=>r.id));
  assert.equal(new Set(options.map(([,label])=>label)).size,3);
  assert.equal(options[2][1],'Mehr · 2026-10-10');
});
test('order reuse review uses shared layout and Persian quantities without translating business identities',async()=>{
  await i18n.changeLanguage('fa');
  try{
    const report={customer_count:5,order_count:79,unit:'tonnes',as_of:'2026-10-10',valid_until:'2026-10-17',month_basis:'jalali',warnings:[],
      months:[{period:'2026-03-21',added:false,booked:200,remaining:180,total:400}],outside_open_orders:[{reference:'Mehr-001',period:'2026-02-20',quantity:20}]};
    const html=renderToStaticMarkup(React.createElement(ReuseReport,{report,ui}));
    assert.match(html,/ui-stack/);assert.match(html,/ui-definition-list/);assert.match(html,/ui-disclosure/);
    assert.match(html,/۷۹/);assert.match(html,/تن/);assert.match(html,/Mehr-001/);
    assert.doesNotMatch(html,/order-comparison-table|style=|tonnes/);
  }finally{await i18n.changeLanguage('en');}
});

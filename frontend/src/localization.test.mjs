import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {i18n,t,LANGUAGE_KEY,storedLanguage,changeInterfaceLanguage,applyInterfaceLanguage,interfaceDirection,unitLabel} from './localization.mjs';
import {fa} from './locales/fa.mjs';
import {faWorkflows} from './locales/fa-workflows.mjs';
import {persianHelpTopics} from './locales/help-fa.mjs';
import {localizeSource} from '../scripts/localize-core-ui.mjs';
import {planningMonth} from './planning-calendar.mjs';
import {demandCSV,pivotDemand,pivotCSV,coverageCSV} from './demand-view.mjs';

test('language preference is explicit, bounded and safe when storage is unavailable',()=>{
  for(const [value,expected]of [['fa','fa'],['en','en'],['ar','en'],[null,'en']]){
    assert.equal(storedLanguage({getItem:key=>{assert.equal(key,LANGUAGE_KEY);return value;}}),expected);
  }
  assert.equal(storedLanguage({getItem:()=>{throw Error('blocked');}}),'en');
  assert.equal(interfaceDirection('fa'),'rtl');assert.equal(interfaceDirection('en'),'ltr');
});
test('language switch persists display preference and changes document semantics',async()=>{
  const saved=[],document={documentElement:{}};
  await changeInterfaceLanguage('fa',{setItem:(...args)=>saved.push(args)});
  applyInterfaceLanguage(document);
  assert.deepEqual(document.documentElement,{lang:'fa',dir:'rtl'});
  assert.deepEqual(saved,[[LANGUAGE_KEY,'fa']]);assert.equal(t('Sales forecast'),'پیش‌بینی فروش');
  assert.equal(t('Unknown'),fa.Unknown);assert.equal(t('not in catalogue'),'not in catalogue');
  assert.equal(unitLabel('tonnes'),'تن');assert.equal(unitLabel('KBlank'),'KBlank');
  assert.equal(t('stepProgress',{step:2,total:4}),'مرحلهٔ 2 از 4');
  assert.equal(t('Upload {{label}}',{label:'سابقهٔ فروش'}),'افزودن سابقهٔ فروش');
  assert.equal(t('{{count}} saved calculations',{count:4}),'4 محاسبهٔ ذخیره‌شده');
  await changeInterfaceLanguage('en');
  assert.equal(t('pageProgress',{page:1,total:3}),'Page 1 of 3');
  await assert.rejects(changeInterfaceLanguage('ar'));
  assert.equal(i18n.language,'en');
});
test('Persian help covers the sales journey with unique authored questions',()=>{
  assert.ok(persianHelpTopics.length>=20);
  assert.equal(new Set(persianHelpTopics.map(([q])=>q)).size,persianHelpTopics.length);
  assert.ok(persianHelpTopics.every(([q,a])=>/[\u0600-\u06ff]/.test(q)&&/[\u0600-\u06ff]/.test(a)));
  assert.ok(persianHelpTopics.some(([,a])=>a.includes('تومان')));
  assert.ok(persianHelpTopics.some(([,a])=>a.includes('۱۴')));
  assert.ok(persianHelpTopics.some(([,a])=>a.includes('نامشخص به معنای صفر نیست')));
});
test('blocked storage cannot disable a valid language choice',async()=>{
  await changeInterfaceLanguage('fa',{setItem:()=>{throw Error('blocked');}});
  assert.equal(i18n.language,'fa');await changeInterfaceLanguage('en');
});
test('changing interface language leaves customer/SKU data, calendars and CSV outputs identical',async()=>{
  const rows=[{customer:'Home',sku:'0001',unit:'tonnes',period:'2026-10-01',planning_calendar:'gregorian',
    baseline:10,booked:14,fulfilled:2,remaining:0,total:16,still_to_serve:14,order_references:['ORDER-001'],status:'Covered by orders'}];
  const original=structuredClone(rows);
  const exports=()=>[demandCSV(rows,false,'tonnes'),pivotCSV(pivotDemand(rows,'total'),'total'),coverageCSV(rows)];
  await changeInterfaceLanguage('en');const before=exports();
  const months=['gregorian','jalali'].map(b=>planningMonth('2026-10-01',b));
  await changeInterfaceLanguage('fa');
  assert.deepEqual(exports(),before);assert.deepEqual(rows,original);
  assert.deepEqual(['gregorian','jalali'].map(b=>planningMonth('2026-10-01',b)),months);
  assert.match(before[0],/Home/);assert.match(before[0],/0001/);
  await changeInterfaceLanguage('en');
});
test('migration touches authored labels, not identifiers, routes or submitted values',async()=>{
  const source=`const customer='Home'; const state='Forecast';
    const el=<div><h1>Home</h1><input value="Home" title="Date" onChange={()=>send('Forecast')}/>
      <span>{customer}</span><Pick value="monthly" options={[["customer","Customer"]]}/>
      <a href="/Forecast">Export demand</a></div>;`;
  const result=await localizeSource(source);
  assert.match(result.source,/const customer='Home'/);assert.match(result.source,/value="Home"/);
  assert.match(result.source,/send\('Forecast'\)/);assert.match(result.source,/href="\/Forecast"/);
  assert.match(result.source,/<span>\{customer\}<\/span>/);assert.match(result.source,/\["customer",uiText\("Customer"\)\]/);
  assert.match(result.source,/title=\{uiText\("Date"\)\}/);
  assert.equal((await localizeSource(result.source)).count,0);
});
test('translation catalogue has no duplicate keys or empty labels',async()=>{
  const {parsers}=await import('prettier/plugins/babel');
  const keys=[];
  for(const file of ['fa.mjs','fa-workflows.mjs']){
    const source=await readFile(new URL('./locales/'+file,import.meta.url),'utf8');
    const ast=await parsers.babel.parse(source);
    const object=ast.program.body.find(n=>n.type==='ExportNamedDeclaration').declaration.declarations[0].init;
    keys.push(...object.properties.filter(p=>p.type!=='SpreadElement').map(p=>p.key.value));
  }
  assert.equal(new Set(keys).size,keys.length);
  assert.ok(Object.values(fa).every(v=>typeof v==='string'&&v.trim()));
  for(const [key,value]of Object.entries(faWorkflows))assert.equal(fa[key],value,'Workflow key overridden: '+key);
});
test('migration preserves class names, route conditionals and inline text spacing',async()=>{
  const source=`const el=<div className={flag?'Review':'Forecast'}><a href={flag?'Home':'Forecast'}>Home</a><span> Before {amount} After </span><input value={flag?'Home':'Forecast'}/></div>;`;
  const result=await localizeSource(source);
  assert.match(result.source,/className=\{flag\?'Review':'Forecast'\}/);
  assert.match(result.source,/href=\{flag\?'Home':'Forecast'\}/);
  assert.match(result.source,/value=\{flag\?'Home':'Forecast'\}/);
  assert.match(result.source,/\{' '\}\{uiText\("Before"\)\}\{' '\}\{amount\}\{' '\}\{uiText\("After"\)\}\{' '\}/);
  assert.ok(!result.keys.includes('Forecast'));
  assert.equal((await localizeSource(result.source)).count,0);
});
test('advanced translations keep consent recipients and source labels literal',async()=>{
  await changeInterfaceLanguage('fa');
  const recipient='Acme <secure> · OpenAI';
  const message=t('Your messages and relevant sales, order and factor data, including customer names, will be sent to {{recipient}}. Changes still need your confirmation.',{recipient});
  assert.ok(message.includes(recipient));assert.match(message,/نام مشتریان/);assert.match(message,/تأیید شما/);
  assert.equal(t('Remove {{name}}',{name:'Home'}),'حذف Home');
  assert.equal(t('{{count}} months earlier',{count:2}),'2 ماه قبل');
  await changeInterfaceLanguage('en');
});

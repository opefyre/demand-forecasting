import test from 'node:test';
import assert from 'node:assert/strict';
import {suggestFactorMapping, factorMappingReady, factorUnit, factorTypeDefaults, factorSourceReady} from './factor-import-flow.mjs';

const columns = ['period_end','value','published'].map((label,i)=>({id:'ABC'[i],label}));
test('factor column suggestions are exact and require reviewable distinct columns',()=>{
  const mapping=suggestFactorMapping(columns);
  assert.deepEqual(mapping,{period:'A',value:'B',available_at:'C'});
  assert.equal(factorMappingReady(mapping,columns),true);
});

test('FX setup does not guess market, quote basis or currency unit',()=>{
  const config={name:'FX',geography:'Iran',provider:'Client export',factor_details:factorTypeDefaults('exchange_rate')};
  assert.equal(factorSourceReady(config),false);
  const filled={...config,factor_details:{...config.factor_details,market:'settlement',side:'settlement',amount_unit:'toman',quote_quantity:100}};
  assert.equal(factorSourceReady(filled),true);
  assert.equal(factorUnit(filled),'IRR per USD');
  for(const patch of [{quote_quantity:0},{currency:'IRR'},{market:''},{side:''}])
    assert.equal(factorSourceReady({...filled,factor_details:{...filled.factor_details,...patch}}),false);
});

test('CPI base and inflation meanings are explicit and keep generic input supported',()=>{
  const config={name:'CPI',geography:'Iran',provider:'Source',factor_details:{kind:'inflation',measure:'cpi_index',base_year:''}};
  assert.equal(factorSourceReady(config),false);
  config.factor_details.base_year='1400';
  assert.equal(factorSourceReady(config),true);
  assert.equal(factorUnit(config),'CPI index (base 1400 = 100)');
  assert.equal(factorUnit({...config,factor_details:{kind:'inflation',measure:'year_on_year'}}),'% year-on-year change');
  assert.equal(factorSourceReady({...config,factor_details:undefined,unit:'index points'}),true);
});
test('ambiguous dates are not guessed',()=>{
  assert.equal(suggestFactorMapping([...columns,{id:'D',label:'period'}]).period,undefined);
  assert.deepEqual(suggestFactorMapping([{id:'A',label:'date'},{id:'B',label:'rate'}]),{});
});
test('missing, duplicate and stale mapped columns cannot advance',()=>{
  for(const mapping of [{period:'A',value:'B'},{period:'A',value:'A',available_at:'C'},
    {period:'A',value:'B',available_at:'D'}])assert.equal(factorMappingReady(mapping,columns),false);
});

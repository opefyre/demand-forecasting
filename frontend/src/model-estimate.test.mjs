import test from 'node:test';
import assert from 'node:assert/strict';
import{estimateRows,estimateTotal,estimateChart}from './model-estimate.mjs';
const run={unit:'tonnes',items:['a','b'],metadata:{a:{customer:'A',sku:'1'},b:{customer:'B',sku:'1'}},series:{a:{history:[{timestamp:'2026-09-01',target:2}],forecast:[{timestamp:'2026-10-01',mean:3}]},b:{history:[{timestamp:'2026-09-01',target:4}],forecast:[{timestamp:'2026-10-01',mean:5}]},__all__:{forecast:[{timestamp:'2026-10-01',mean:8}]}}};
test('estimate uses leaf series only and preserves the exact forecast total',()=>{
 assert.equal(estimateRows(run).length,2);assert.equal(estimateTotal(estimateRows(run)),8);
 assert.equal(estimateTotal(estimateRows(run,{customer:'A'})),3);
 assert.equal(estimateTotal(estimateRows(run,{sku:'2'})),null);
 assert.equal(estimateTotal([{total:null},{total:1}]),null);
});
test('chart uses same filters and joins at the final actual without counting it in future totals',()=>{
 assert.deepEqual(estimateChart(run),[{date:'2026-09-01',actual:6,forecast:6},{date:'2026-10-01',forecast:8}]);
 assert.deepEqual(estimateChart(run,{customer:'A'}),[{date:'2026-09-01',actual:2,forecast:2},{date:'2026-10-01',forecast:3}]);
 assert.deepEqual(estimateChart(run,{period:'2026-10-01'}),[{date:'2026-10-01',forecast:8}]);
 assert.deepEqual(estimateRows(run,{period:'2026-11-01'}),[]);
});
test('forecast ranges are preserved only for a scope the engine actually calculated',()=>{
 const bounded=structuredClone(run);
 bounded.series.a.forecast[0].p10=1;bounded.series.a.forecast[0].p90=7;
 bounded.series.b.forecast[0].p10=2;bounded.series.b.forecast[0].p90=8;
 assert.deepEqual(estimateChart(bounded,{customer:'A'}).at(-1).range,[1,7]);
 assert.equal(estimateChart(bounded).at(-1).range,undefined);
 bounded.series.__all__.forecast[0].p10=5;bounded.series.__all__.forecast[0].p90=12;
 assert.deepEqual(estimateChart(bounded).at(-1).range,[5,12]);
});

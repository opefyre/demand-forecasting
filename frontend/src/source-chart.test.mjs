import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceChart} from './source-chart.mjs';

test('daily chart preserves missing dates and real zero counts',()=>{
  assert.deepEqual(sourceChart({frequency:'daily',points:[{period:'2026-09-01',value:0},{period:'2026-09-03',value:4}]}),
    [{period:'2026-09-01',value:0},{period:'2026-09-02',value:null},{period:'2026-09-03',value:4}]);
});
test('monthly chart uses real month ends, including leap February, with no fake bridge',()=>{
  assert.deepEqual(sourceChart({frequency:'monthly',points:[{period:'2024-01-31',value:5},{period:'2024-03-31',value:7}]}),
    [{period:'2024-01-31',value:5},{period:'2024-02-29',value:null},{period:'2024-03-31',value:7}]);
});
test('recent monthly range includes first and last known month',()=>{
  const result=sourceChart({frequency:'monthly',points:[{period:'2020-01-31',value:5},{period:'2026-09-30',value:7}]});
  assert.equal(result.length,36);assert.equal(result[0].period,'2023-10-31');assert.equal(result.at(-1).value,7);
});
test('unsupported frequencies and empty data do not make a fake chart',()=>{
  assert.deepEqual(sourceChart(null),[]);assert.deepEqual(sourceChart({frequency:'quotes',points:[{period:'2026-09-01',value:1}]}),[]);
});

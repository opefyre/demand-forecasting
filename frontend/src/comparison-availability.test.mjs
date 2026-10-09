import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {comparisonAvailability} from './forecast-groups.mjs';
test('unknown estimates cannot create an apparently valid empty chart',()=>{
 assert.deepEqual(comparisonAvailability([{period:'2026-10',a:null,b:null}],['a','b']),{hasEstimate:false,hasMissing:true});
 assert.deepEqual(comparisonAvailability([],['a']),{hasEstimate:false,hasMissing:false});
 assert.deepEqual(comparisonAvailability([{a:0,b:10},{a:null,b:20}],['a','b']),{hasEstimate:true,hasMissing:true});
 assert.deepEqual(comparisonAvailability([{a:0,b:10}],['a','b']),{hasEstimate:true,hasMissing:false});
});
test('comparison explains missing inputs, labels unknown table cells and draws only available estimates',async()=>{
 const source=await readFile(new URL('method-comparison.jsx',import.meta.url),'utf8');
 assert.match(source,/availability.hasEstimate&&<div className="chart-frame"/);
 assert.match(source,/availability.hasMissing&&<Actions><p role="status"/);
 assert.match(source,/onClick=\{onReviewCoverage\}/);
 assert.match(source,/\? uiText\("Unknown"\)/);
 assert.match(source,/connectNulls=\{false\}/);
 assert.match(source,/dot=\{rows.length===1\}/);
 const dashboard=await readFile(new URL('sales-demand.jsx',import.meta.url),'utf8');
 assert.match(dashboard,/dot=\{chart.length===1\}/);
});

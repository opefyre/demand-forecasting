import test from 'node:test';
import assert from 'node:assert/strict';
import {sortDemand,demandCSV,mergeDirectory,salesSeriesLabel} from './demand-view.mjs';
import {pivotDemand,pivotCSV,coverageStatus,coverageCSV,customerBaseline} from './demand-view.mjs';
test('customer/product labels use reviewed metadata, never parse or guess identifiers',()=>{
 const run={metadata:{'opaque':{customer:'Tehran A',sku:'001'}}};
 assert.equal(salesSeriesLabel(run,'opaque'),'Tehran A · 001');
 assert.equal(salesSeriesLabel(run,'__all__'),'All customers & products');
 assert.equal(salesSeriesLabel(run,'["Not","metadata"]'),'["Not","metadata"]');
});
test('sort quantities without treating unknown demand as zero or mutating input',()=>{
 const rows=[{total:null},{total:0},{total:30},{total:10}];
 assert.deepEqual(sortDemand(rows,'largest').map(r=>r.total),[30,10,0,null]);
 assert.deepEqual(sortDemand(rows,'smallest').map(r=>r.total),[0,10,30,null]);
 assert.equal(rows[0].total,null);
});

test('pivot reconciles cells and totals across customer/SKU/month without mixing units',()=>{
 const rows=[['A','P','2026-10',16],['B','P','2026-10',8],['C','P','2026-10',5],['A','P','2026-11',10],['B','P','2026-11',4],['C','P','2026-11',6]].map(([customer,sku,period,total])=>({customer,sku,period,total,unit:'tonnes'}));
 const result=pivotDemand(rows);assert.deepEqual(result.totals,[29,20]);assert.equal(result.total,49);assert.equal(result.rows.length,3);
 assert.equal(pivotCSV(result).split('\r\n').length,4);
 assert.throws(()=>pivotDemand([...rows,{...rows[0],unit:'kg'}]),/one unit/);
});
test('missing cells and unknown estimates never become zero in pivot or export',()=>{
 const result=pivotDemand([{customer:'A',sku:'P',period:'2026-10',unit:'kg',total:null},{customer:'B',sku:'P',period:'2026-11',unit:'kg',total:0}]);
 assert.equal(result.total,null);assert.deepEqual(result.totals,[null,0]);assert.equal(result.rows[0].cells.get('2026-11'),undefined);assert.match(pivotCSV(result),/Unknown/);assert.match(pivotCSV(result),/Not in selection/);
});
test('coverage keeps no orders distinct from missing orders, missing history and completed commitments',()=>{
 assert.equal(coverageStatus({booked:0,fulfilled:0,remaining:8,status:'Expected only'}),'No orders');
 assert.equal(coverageStatus({booked:0,remaining:null,status:'Orders unknown'}),'Orders unknown');
 assert.equal(coverageStatus({booked:16,remaining:null,status:'More history needed'}),'More history needed');
 assert.equal(coverageStatus({booked:6,remaining:0,status:'Complete commitment'}),'Complete commitment');
 assert.equal(coverageStatus({booked:6,remaining:4,status:'Partly booked',issue:'Expired'}),'Needs review');
 assert.match(coverageCSV([{customer:'A',sku:'P',period:'2026-10',unit:'kg',booked:0,remaining:8,total:8,status:'Expected only'}]),/No orders/);
});
test('assistant customer result includes all their SKUs and no other customers or aggregate series',()=>{
 const run={unit:'tonnes',metadata:{a:{customer:'A',sku:'P'},b:{customer:'A',sku:'Q'},c:{customer:'B',sku:'P'},__all__:{customer:'A'}},series:Object.fromEntries(['a','b','c','__all__'].map(k=>[k,{forecast:[{timestamp:'2026-10-01',mean:10}]}]))};
 const rows=customerBaseline(run,'A');assert.equal(rows.length,2);assert.equal(pivotDemand(rows).total,20);assert.deepEqual(customerBaseline(run,'Missing'),[]);
});
test('view CSV keeps filtered rows, unknowns, units and escapes labels',()=>{
 const result=demandCSV([{customer:'=HYPERLINK(1)',sku:'A"B',period:'2026-10',baseline:null,booked:3,fulfilled:2,remaining:null,total:null}],false,'tonnes');
 assert.match(result,/'=HYPERLINK/);assert.match(result,/A""B/);assert.match(result,/Unknown/);assert.match(result,/tonnes/);assert.equal(result.split('\r\n').length,2);
});
test('directory merge preserves existing series matches and no-order customers',()=>{
 const existing=[{customer:'A',sku:'P',unit:'kg',series_id:'A-P'}];
 const directory=[{customer:'A',active:true,products:[{sku:'P',unit:'kg'}]},{customer:'B',active:true,products:[{sku:'P',unit:'kg'}]},{customer:'C',active:false,products:[{sku:'P',unit:'kg'}]}];
 const result=mergeDirectory(existing,directory);
 assert.equal(result.length,2);assert.equal(result[0].series_id,'A-P');assert.equal(result[1].customer,'B');assert.equal(existing.length,1);
});
test('Persian baseline, pivot and coverage exports label real planning months',()=>{
 const run={unit:'kg',run_settings:{calendar_profile:{month_basis:'jalali'}},metadata:{a:{customer:'A',sku:'P'}},series:{a:{forecast:[{timestamp:'2025-03-21',mean:10}]}}};
 const rows=customerBaseline(run,'A');
 assert.equal(rows[0].planning_calendar,'jalali');
 assert.match(pivotCSV(pivotDemand(rows)),/1404-01/);
 assert.match(coverageCSV(rows),/1404-01/);
});

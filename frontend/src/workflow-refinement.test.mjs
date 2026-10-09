import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {forecastGroups,methodRows} from './forecast-groups.mjs';
import {createMotionController} from './motion.mjs';
test('methods share one forecast; matching names alone never merge unrelated runs',()=>{
 const runs=[{run_id:'a',forecast_group_id:'one',forecast_name:'October',method_selection:'A'},{run_id:'b',forecast_group_id:'one',forecast_name:'October',method_selection:'B'},{run_id:'c',name:'October',method_selection:'A'},{run_id:'d',name:'October',method_selection:'A'}];
 const groups=forecastGroups(runs);assert.equal(groups.length,3);assert.equal(groups[0].runs.length,2);
});
test('legacy reviewed-input siblings group without rewriting original records',()=>{
 const rows=['a','b'].map((id,i)=>({run_id:id,dataset_id:'history',forecast_order_inputs_id:'orders',method_selection:String(i)}));
 assert.equal(forecastGroups(rows).length,1);assert.equal(forecastGroups([...rows,{...rows[0],run_id:'c',dataset_id:'other'}]).length,2);
});
test('method comparisons apply all filters and leave missing/unknown values as gaps',()=>{
 const row={period:'2026-10-01',customer:'A',sku:'001',unit:'tonnes',total:10};
 const entries=[{run_id:'a',rows:[row,{...row,customer:'B',total:20}],coverage:()=> 'No orders'},{run_id:'b',rows:[{...row,total:null}],coverage:()=> 'No orders'}];
 assert.deepEqual(methodRows(entries,{customer:'A',sku:'001',unit:'tonnes',period:'2026-10-01',coverage:'No orders'}),[{period:'2026-10-01',a:10,b:null}]);
 assert.deepEqual(methodRows(entries,{customer:'C'}),[]);assert.equal(methodRows([entries[0]])[0].b,undefined);
});
test('open dialogs never trigger workspace snapshots above their overlay',()=>{
 let changes=0,reveals=0,snapshots=0;
 const host={visibilityState:'visible',querySelector:()=>({}),defaultView:{matchMedia:()=>({matches:false})},startViewTransition:()=>snapshots++};
 createMotionController({host,commit:f=>f(),reveal:()=>reveals++})(()=>changes++);
 assert.equal(changes,1);assert.equal(reveals,1);assert.equal(snapshots,0);
});
test('Data owns customers and orders, settings are inline and dialog geometry is shared',async()=>{
 const file=async name=>readFile(new URL(name,import.meta.url),'utf8');
 const main=await file('main.jsx');assert.match(main,/\["customers", "Customers"\]/);assert.match(main,/\["orders", "Orders"\]/);assert.doesNotMatch(main.slice(main.indexOf('const nav ='),main.indexOf('const METHOD_HELP')),/Customers/);
 assert.doesNotMatch(await file('new-forecast.jsx'),/Edit inputs|editInputs/);assert.match(await file('new-forecast.jsx'),/forecast-settings/);
 assert.match(await file('ui-framework.css'),/ui-dialog-fixed/);assert.match(await file('forecast-orders.jsx'),/order-books/);assert.doesNotMatch(await file('forecast-orders.jsx'),/SalesSource[^>]+role="customers"/);
});

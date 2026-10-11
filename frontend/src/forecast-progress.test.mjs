import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {forecastFinished,readForecastProgress,readForecastSummaries} from './forecast-progress.mjs';

test('a failed job read preserves that method while exposing other completed results',async()=>{
  const jobs=[{id:'a',method:'first',state:'running'},{id:'b',method:'second',state:'running'}];
  const failure=Error('Unavailable');
  const result=await readForecastProgress(jobs,async path=>{
    if(path.endsWith('/a'))throw failure;
    return {id:'b',state:'succeeded',run_id:'rb'};
  });
  assert.equal(result.error,failure);assert.deepEqual(result.jobs[0],jobs[0]);
  assert.deepEqual(result.jobs[1],{id:'b',method:'second',state:'succeeded',run_id:'rb'});
  assert.equal(jobs[1].state,'running');
});
test('explicit read recovery never starts or retries a calculation and skips terminal jobs',async()=>{
  const jobs=[{id:'a',method:'first',state:'loading'},...['succeeded','failed','interrupted','cancelled'].map((state,index)=>({id:String(index),method:'saved',state}))];
  const calls=[];
  const result=await readForecastProgress(jobs,async(...args)=>{calls.push(args);return {id:'a',state:'interrupted'};});
  assert.deepEqual(calls,[['/api/jobs/a']]);assert.equal(result.error,null);
  assert.equal(result.jobs[0].method,'first');assert.ok(result.jobs.every(forecastFinished));
});
test('summary failures preserve available method totals and recover through reads',async()=>{
  const jobs=[{state:'succeeded',run_id:'a'},{state:'succeeded',run_id:'b'},{state:'running',run_id:'c'}];
  const failure=Error('Offline');
  const result=await readForecastSummaries(jobs,'',async path=>{if(path.endsWith('/a'))throw failure;return {unit:'tonnes',demand_summary:{total:42.123456,unit:'tonnes'}};});
  assert.equal(result.error,failure);assert.deepEqual(result.summaries,{b:{total:42.123456,unit:'tonnes'}});
  const calls=[];
  const recovered=await readForecastSummaries(jobs,'',async(...args)=>{calls.push(args);return {unit:'tonnes',demand_summary:{total:42.123456,unit:'tonnes'}};});
  assert.equal(recovered.error,null);assert.deepEqual(calls,[['/api/runs/a'],['/api/runs/b']]);
  assert.deepEqual(Object.keys(recovered.summaries),['a','b']);
});
test('customer summaries do not turn unknown demand into zero or include another customer',async()=>{
  const job={state:'succeeded',run_id:'r'};
  for(const [rows,expected] of [[[],null],[[{customer:'A',total:null}],null],[[{customer:'A',total:0}],0],[[{customer:'A',total:2.5},{customer:'A',total:3},{customer:'B',total:500}],5.5]]){
    const result=await readForecastSummaries([job],'A',async path=>path.includes('/outlook')?{rows}:{unit:'tonnes',sales_input_snapshot_id:'s'});
    assert.equal(result.summaries.r.total,expected);assert.equal(result.error,null);
  }
});
test('missing demand summaries stay unknown rather than substituting raw sales predictions',async()=>{
  const result=await readForecastSummaries([{state:'succeeded',run_id:'r'}],'',async()=>({unit:'tonnes',forecast:[{mean:999}]}));
  assert.deepEqual(result.summaries.r,{total:null,unit:'tonnes'});
});
test('wizard keeps read errors separate from writes and reload does not replay a mutation',async()=>{
  const source=await readFile(new URL('./new-forecast.jsx',import.meta.url),'utf8');
  assert.match(source,/if\(progressError\|\|!jobs.some/);
  assert.match(source,/if\(live&&!result.error\)timer=setTimeout/);
  assert.match(source,/onReload=\{!error&&\(progressError\|\|summaryError\)\?\(\)=>\{setProgressError\(null\);setReadRevision\(value=>value\+1\);\}/);
  assert.match(source,/setSummaries\(previous=>\(\{\.\.\.previous,\.\.\.result.summaries\}\)\)/);
  assert.doesNotMatch(source,/style=\{/);
});

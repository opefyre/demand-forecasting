import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {orderCoverageTitle} from './forecast-start.mjs';
test('uploaded orders are not described as no current orders before review',()=>{
  assert.equal(orderCoverageTitle([],{source_id:'synthetic-file'}),'All known orders included');
  assert.equal(orderCoverageTitle([{reference:'one'}],null),'All known orders included');
  assert.equal(orderCoverageTitle([],null),'No current orders');
});
test('cloud startup does not fetch checkpoint-backed monthly workflows; explicit updates still resume existing work',async()=>{
  const source=await readFile(new URL('./main.jsx',import.meta.url),'utf8');
  const refresh=source.slice(source.indexOf('const refresh ='),source.indexOf('useEffect(() => {',source.indexOf('const refresh =')));
  assert.match(refresh,/cloudTransportEnabled\(\)\?Promise\.resolve\(\{updates\}\):api\('\/api\/forecast-updates'\)/);
  const update=source.slice(source.indexOf('async function startUpdate'),source.indexOf('const context =',source.indexOf('async function startUpdate')));
  assert.match(update,/cloudTransportEnabled\(\)&&!requestId\?\(await api\('\/api\/forecast-updates'\)\)\.updates:updates/);
  assert.match(update,/current\.find\(value=>value\.base_run_id===runId&&value\.stage!=='ready'\)/);
});

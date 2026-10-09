import test from 'node:test';
import assert from 'node:assert/strict';
import {releaseLabel,releaseDownload,releaseReady,visibleReleases} from './demand-release-state.mjs';
test('review inbox separates company demand from local demonstrations',()=>{
  const rows=[{id:'company',demo_only:false},{id:'demo',demo_only:true}];
  assert.deepEqual(visibleReleases(rows),[rows[0]]);
  assert.deepEqual(visibleReleases(rows,true),rows);
  assert.deepEqual(rows,[{id:'company',demo_only:false},{id:'demo',demo_only:true}]);
});
test('approval labels distinguish demo signoff, missing inputs and replacement',()=>{
  assert.equal(releaseLabel({state:'approved'}),'Approved');
  assert.equal(releaseLabel({state:'approved',demo_only:true}),'Demo approved');
  assert.equal(releaseLabel({state:'approved',blocked:'Expired'}),'Inputs need review');
  assert.equal(releaseLabel({state:'approved',superseded:true}),'Replaced');
  assert.equal(releaseLabel({state:'awaiting_review'}),'Awaiting review');
});
test('approved downloads do not allow changing the receiving-system mode',()=>{
  assert.equal(releaseDownload({id:'release',can_export:true},'csv'),'/api/sales/releases/release/export?kind=csv');
  assert.equal(releaseDownload({id:'release',can_export:false},'csv'),null);
  assert.equal(releaseDownload({id:'release',can_export:true},'exe'),null);
});
test('changing receiver or order policy requires reviewing quantities again',()=>{
  const report={contract:{receiver:'ERP',mode:'remaining_forecast'}};
  assert.equal(releaseReady(' ERP ',report,'remaining_forecast'),true);
  assert.equal(releaseReady('Other ERP',report,'remaining_forecast'),false);
  assert.equal(releaseReady('ERP',report,'combined_demand'),false);
  assert.equal(releaseReady('ERP',null,'remaining_forecast'),false);
});

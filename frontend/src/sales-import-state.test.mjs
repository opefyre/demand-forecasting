import test from 'node:test';
import assert from 'node:assert/strict';
import {changeReviewedInput, salesMappingReady, requireSalesHeadings,orderReviewReady} from './sales-import-state.mjs';

test('order review requires both a meaningful note and a new confirmation',()=>{
  for(const note of ['', '  ', 'ok', null])assert.equal(orderReviewReady({reviewed:true,note}),false);
  assert.equal(orderReviewReady({reviewed:false,note:'Checked all orders'}),false);
  assert.equal(orderReviewReady({reviewed:true,note:'Checked all orders'}),true);
  assert.equal(orderReviewReady(null),false);
});

test('empty heading previews explain the correction before replacing mappings', () => {
  assert.throws(()=>requireSalesHeadings({columns:[]}), /Choose the row with your column names/);
  assert.throws(()=>requireSalesHeadings(null), /No columns found/);
  const preview={columns:[{id:'A',label:'customer'}]};
  assert.equal(requireSalesHeadings(preview),preview);
});

test('changed meanings require a fresh confirmation without editing the saved input', () => {
  const saved = {reviewed:true, note:'Checked'};
  assert.equal(changeReviewedInput(saved, 'note', 'Corrected').reviewed, false);
  assert.equal(changeReviewedInput(saved, 'reviewed', true).reviewed, true);
  assert.equal(saved.note, 'Checked');
  assert.equal(saved.reviewed, true);
});

test('mapping requires real columns and freshly read headings, but saved rows need no upload', () => {
  const schema = {customer:{required:true}, reference:{required:false}};
  const config = {header_row:1, mapping:{customer:'A'}, _preview:{columns:[{id:'A'}]}};
  assert.equal(salesMappingReady(schema, null, 1), true);
  assert.equal(salesMappingReady(schema, config, 1), true);
  assert.equal(salesMappingReady(schema, config, '2'), false);
  assert.equal(salesMappingReady(schema, {...config, mapping:{}}, 1), false);
  assert.equal(salesMappingReady(schema, {...config, mapping:{customer:'deleted'}}, 1), false);
  assert.equal(salesMappingReady(schema, {...config, mapping:{customer:'A',reference:'deleted'}}, 1), false);
});

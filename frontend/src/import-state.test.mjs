import test from "node:test";
import assert from "node:assert/strict";
import {
  replacementMapping,
  importDraftKey,
  saveAttempt,
  sameSavedInputs,
  suggestedSalesGrouping,
  salesGroupingReady,
} from "./import-state.mjs";

test('normal sales columns need no prebuilt customer/product identifier',()=>{
  const result=suggestedSalesGrouping(['date','customer','sku','quantity']);
  assert.deepEqual(result,{customer_col:'customer',sku_col:'sku',item_col:'sku',series_mode:'customer_product'});
  assert.equal(salesGroupingReady(result),true);
  assert.equal(salesGroupingReady({...result,customer_col:''}),false);
  assert.equal(salesGroupingReady({...result,customer_col:'sku'}),false);
  assert.equal(suggestedSalesGrouping(['date','sku','quantity']).series_mode,'column');
  assert.equal(suggestedSalesGrouping(['Client','Product']).customer_col,'');
});

test('replacement never switches a reviewed grouping contract',()=>{
  const settings={...suggestedSalesGrouping(['customer','sku']),date_col:'date',target_col:'quantity'};
  const replacement={...settings,...replacementMapping(settings,['date','quantity','sku'],'history')};
  assert.equal(replacement.series_mode,'customer_product');
  assert.equal(salesGroupingReady(replacement),false);
});

const settings = {
  date_col: "Month",
  target_col: "Actual",
  item_col: "Product",
  sku_col: "Code",
  drivers: ["FX", "Price"],
  driver_roles: { FX: "external", Price: "internal" },
  unit: "KBlank",
};
test("same-schema replacement retains exact user mapping and factors", () => {
  const result = replacementMapping(
    settings,
    ["Price", "Product", "Actual", "Month", "FX", "Code"],
    "history",
  );
  assert.equal(result.target_col, "Actual");
  assert.deepEqual(result.drivers, ["FX", "Price"]);
  assert.deepEqual(result.driver_roles, settings.driver_roles);
  assert.equal({ ...settings, ...result }.unit, "KBlank");
});
test('new history never inherits old row corrections; future replacement retains them',()=>{
  const corrected={...settings,history_cell_corrections:[{row:1}],history_corrections_sha256:'old'};
  const next={...corrected,...replacementMapping(corrected,['Month','Actual','Product','Code'],'history')};
  assert.deepEqual(next.history_cell_corrections,[]);assert.equal(next.history_corrections_sha256,null);
  const future={...corrected,...replacementMapping(corrected,['date'],'future')};
  assert.deepEqual(future.history_cell_corrections,[{row:1}]);
});
test("missing fields are cleared, not guessed from plausible alternatives", () => {
  const result = replacementMapping(
    settings,
    ["date", "quantity", "Product", "Price"],
    "history",
  );
  assert.equal(result.date_col, "");
  assert.equal(result.target_col, "");
  assert.equal(result.sku_col, "");
  assert.deepEqual(result.drivers, ["Price"]);
  assert.deepEqual(result.driver_roles, { Price: "internal" });
});
test("future replacement does not change history or factor choices", () => {
  const result = replacementMapping(
    { ...settings, future_date_col: "Month", future_item_col: "Product" },
    ["Month"],
    "future",
  );
  assert.deepEqual(result, { future_date_col: "Month", future_item_col: "" });
  assert.deepEqual(settings.drivers, ["FX", "Price"]);
});
test("new and existing dataset drafts have isolated keys", () => {
  assert.equal(importDraftKey(), "demandlab.importDraft");
  assert.notEqual(importDraftKey("a"), importDraftKey("b"));
  assert.notEqual(importDraftKey("a"), importDraftKey());
});

test("save request survives draft serialization but changes with inputs", () => {
  const first = saveAttempt(
    null,
    { name: "A", sources: { history: "one" } },
    () => "request-1",
  );
  const restored = JSON.parse(JSON.stringify(first));
  assert.deepEqual(
    saveAttempt(
      restored,
      { name: "A", sources: { history: "one" } },
      () => "unused",
    ),
    first,
  );
  assert.equal(
    saveAttempt(
      restored,
      { name: "A", sources: { history: "two" } },
      () => "request-2",
    ).id,
    "request-2",
  );
});

test("viewing saved inputs does not create an unfinished edit", () => {
  const initial = {
    name: "A",
    classification: "user_provided",
    sources: { history: "one" },
    settings: { horizon: 2 },
  };
  assert.equal(
    sameSavedInputs(
      initial,
      { ...initial, settings: { horizon: 2, unit: "units" } },
      { horizon: 1, unit: "units" },
    ),
    true,
  );
  assert.equal(
    sameSavedInputs(
      initial,
      { ...initial, classification: "synthetic_sample" },
      {},
    ),
    false,
  );
  assert.equal(
    sameSavedInputs(
      { ...initial, import_candidate_id: "pending" },
      initial,
      {},
    ),
    false,
  );
  assert.equal(
    sameSavedInputs(initial, { ...initial, settings: { horizon: 3 } }, {}),
    false,
  );
});

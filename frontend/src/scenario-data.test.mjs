import test from "node:test";
import assert from "node:assert/strict";
import { scenarioRows, factorComparisonScores } from "./scenario-data.mjs";
const base = {
  run_id: "base",
  unit: "kg",
  series: {
    __all__: {
      forecast: [
        { timestamp: "2026-09-01", mean: 100 },
        { timestamp: "2026-10-01", mean: 120 },
      ],
    },
  },
};
const scenario = {
  base_run_id: "base",
  unit: "kg",
  series: {
    __all__: {
      forecast: [
        { timestamp: "2026-10-01", mean: 121, p10: 100, p90: 140 },
        { timestamp: "2026-09-01", mean: 90, p10: 70, p90: 115 },
      ],
    },
  },
};
test('live what-if cannot display accuracy even if a stale proof claims it',()=>{
  const candidate={...scenario,scenario:{type:'factor_link',alignment:{retrospective:true}},
    metrics:{wape_pct:1,independent_accuracy_verified:true},factor_validation:{available:true,baseline_error_pct:20,scenario_error_pct:1}};
  assert.match(factorComparisonScores(base,candidate).error,/What-if/);
});
test('customer–SKU comparison never substitutes aggregate values',()=>{
  const b={...base,series:{...base.series,A:{forecast:[{timestamp:'2026-09-01',mean:10}]}}};
  const s={...scenario,series:{...scenario.series,A:{forecast:[{timestamp:'2026-09-01',mean:16}]}}};
  assert.equal(scenarioRows(b,s,'A')[0].difference,6);
  assert.throws(()=>scenarioRows(b,scenario,'A'),/missing/);
});
test('factor accuracy comparison requires identical engine, periods and separate tests',()=>{
  const b={...base,engine:{revision:'new'},metrics:{evaluation_signature:'same',wape_pct:12,independent_accuracy_verified:true}};
  const s={...scenario,engine:b.engine,scenario:{type:'factor_comparison'},metrics:{...b.metrics,wape_pct:14}};
  assert.deepEqual(factorComparisonScores(b,s),{before:12,after:14,difference:2});
  assert.ok(factorComparisonScores(b,{...s,metrics:{...s.metrics,evaluation_signature:'different'}}).error);
  assert.ok(factorComparisonScores(b,{...s,metrics:{...s.metrics,independent_accuracy_verified:false}}).error);
  assert.ok(factorComparisonScores(b,{...s,engine:{revision:'old'}}).error);
});
test('linked-factor comparisons retain the same accuracy evidence gates',()=>{
  const b={...base,engine:{revision:'new'},metrics:{evaluation_signature:'same',wape_pct:12,independent_accuracy_verified:true}};
  const s={...scenario,engine:b.engine,scenario:{type:'factor_link'},metrics:{...b.metrics,wape_pct:14}};
  assert.deepEqual(factorComparisonScores(b,s),{before:12,after:14,difference:2});
  assert.ok(factorComparisonScores(b,{...s,metrics:{...s.metrics,independent_accuracy_verified:false}}).error);
});
test('combined-factor comparison uses matched evidence and does not fall back when missing',()=>{
  const b={...base,engine:{revision:'new'},metrics:{evaluation_signature:'same'}};
  const s={...scenario,engine:b.engine,scenario:{type:'factor_link'},metrics:{...b.metrics,wape_pct:1},factor_validation:{available:true,baseline_error_pct:12,scenario_error_pct:14,change_points:2}};
  assert.deepEqual(factorComparisonScores(b,s),{before:12,after:14,difference:2});
  assert.ok(factorComparisonScores(b,{...s,factor_validation:{available:false,reason:'Mismatched actuals'}}).error);
});
test("comparison joins exact dates, preserving quantities, bounds and signed differences", () =>
  assert.deepEqual(scenarioRows(base, scenario), [
    {
      period: "2026-09-01",
      baseline: 100,
      scenario: 90,
      difference: -10,
      range: [70, 115],
    },
    {
      period: "2026-10-01",
      baseline: 120,
      scenario: 121,
      difference: 1,
      range: [100, 140],
    },
  ]));
test("missing scenario period stays unknown rather than zero", () =>
  assert.equal(
    scenarioRows(base, {
      ...scenario,
      series: { __all__: { forecast: [] } },
    })[0].scenario,
    null,
  ));
test("different unit or baseline cannot be compared", () => {
  assert.throws(() => scenarioRows(base, { ...scenario, unit: "tonnes" }));
  assert.throws(() =>
    scenarioRows(base, { ...scenario, base_run_id: "other" }),
  );
});
test("duplicate periods cannot silently overwrite values", () =>
  assert.throws(() =>
    scenarioRows(base, {
      ...scenario,
      series: {
        __all__: {
          forecast: [
            scenario.series.__all__.forecast[0],
            scenario.series.__all__.forecast[0],
          ],
        },
      },
    }),
  ));

# Customer/product sales journey — 7 October 2026

Delivered and checked locally. This is not whole-product acceptance or evidence
of real-client forecasting accuracy. No new package, live feed or paid AI request.

## Fixed

- Normal sales files can use separate customer and SKU columns. The import picks
  customer/product grouping when both exact headers exist; no extra ID is needed.
  Other headers remain subject to explicit mapping and review.
- Every customer/product pair gets a stable, collision-safe internal key. Leading
  zeros, customer aliases, original source bytes and quantities are preserved.
- Existing saved datasets retain their group-column contract. Ambiguous groups,
  missing identities and tampered derived keys are rejected, including direct runs.
  Existing validation already blocked mixed groups at import; the previous UI made
  users construct a composite ID themselves. This removes that workaround.
- The effective group key follows numerical calculation, future factors, factor
  scenarios, AI evidence and monthly/repeat input processing. Shared future factors
  remain shared; SKU-only factors cannot silently merge multiple customers.
- Calculation selectors and accuracy rows show customer/SKU labels, not internal
  JSON keys. The review names customer–product pairs; `qty` is recognized as a
  possible quantity column. Suggestions still require user review.
- AI column-review instructions explain the new grouping contract instead of asking
  for another identifier. The added AI test uses a fake provider, not live AI.

## Verification

Full regression: 612 backend checks and 114 interface checks passed; build passed.
After the final AI evidence/instruction change, 25 focused mapping/grouping/journey
checks passed. Existing dependency, database-cleanup and bundle-size warnings remain.

The isolated route test uses three customers buying the same SKU, 36 months of
known history and the existing Last observed model. Customer A has 16 ordered,
2 fulfilled; B has 6 ordered; C has no orders. First-month demand is independently
41, still to serve 39, remaining expectation 19. Over two months, six demo-approved
CSV/Excel/JSON exports reconcile to 74 combined or 54 remaining tonnes. It also
checks customer directory, AI input context, factor linking and unchanged originals.

The browser sample uses seeded varying/seasonal/intermittent synthetic history,
two customers, two SKUs and four order lines. Normal upload → column review →
ten-month automatic-model forecast → partial/cancelled orders → filtered monthly
view → centered export → reload was exercised through the UI.

- Run: `13dce80f9573`; order snapshot: `38dd9f7b9940d5e393fe5dc924b3465d`.
- 40 demand rows; 93 open-order tonnes, 12 fulfilled tonnes and
  1,199.0622538895666 remaining forecast tonnes. Total demand: 1,304.0622538895666.
- Downloaded Excel independently read back: 40 rows, both customers, SKUs `0001`
  and `0002`, and exactly the remaining forecast total. Draft downloads exclude
  fulfilled quantities and state whether open orders are included.
- Customer-filtered monthly totals, readable individual calculation labels and
  saved demand after reload checked. Mapping and centered export inspected at
  390px; mapping page/content widths both 390px. Viewport restored afterward.
- Screenshots: `outputs/customer-product-journey-dashboard.png`,
  `outputs/customer-product-journey-mobile-mapping.png` and
  `outputs/customer-product-journey-mobile-export.png`.

The sample history has invented seasonal dips, shocks and intermittent demand.
These are test conditions, not measured Tehran inflation, FX or market behaviour.
No client records were replaced. Demo orders are dated October 2026; regenerate
or review freshness before future demonstrations. This sample has no external
factors selected; separate isolated factor tests verify that integration boundary.

## Still open / next substantial build

Finish Persian/English interface and right-to-left layouts, using the same sales
workflow and true Gregorian/Persian calendar contracts; no added operational pages.
Then complete broader first-use, role/error and accessibility acceptance. Real
provider permission/history, live AI acceptance, client accuracy, receiving-system
reconciliation and secure company deployment remain separate gates. A synthetic
demo cannot close them.

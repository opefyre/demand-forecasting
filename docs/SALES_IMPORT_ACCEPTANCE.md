# Sales import-to-export acceptance

24 September 2026 — ready within the checked backend scope; not a production
acceptance or a claim of forecast accuracy on client data.

## Fix delivered

Sales-history parsing previously let pandas infer identifier types before column
mapping. A text SKU `001` became `1`, and customer code `NA` became a missing value.
The separate order importer retained these codes, so matching could fail.

The shared history reader now preserves leading-zero codes, long numeric text
identifiers, nullable integer text and literal NA/NULL codes. Numeric measures
remain available for mapping and calculation. CSV/TSV, Excel text cells and JSON
strings are covered. No new dependency was added; existing pandas parsing is used.
This cannot recover identifiers already stored numerically in a source workbook:
export identifiers as text, not numeric cells with a display-only zero mask.
Existing saved forecasts are not rewritten. Re-import/recalculate affected history
before matching orders; do not manually rename order identifiers to hide the issue.

## Reproducible journey

`tests/test_sales_import_journey.py` uses isolated temporary stores, actual public
route handlers, file parsers and the real forecast engine. No live feeds, paid AI,
client records or existing demo data are used or changed.

1. Import 36 monthly observations for three customer/SKU series; preserve codes.
2. Validate mapping, save the dataset and calculate three forecast months.
3. Import a separate customer list and four order lines; review and save once.
4. Check higher-than-forecast orders, partial fulfillment, partial cancellation,
   fully cancelled orders, unconfirmed orders and customers without firm orders.
5. Independently recompute every customer/month's open orders, fulfilled quantity,
   expected remainder and total from the model outputs and fixture order lines.
6. Reconcile all six baseline exports: Excel/CSV/JSON × combined/residual demand;
   preserve identifiers and exclude already delivered quantities from planning exports.
7. Import synthetic Iran monthly context with separate observation/publication dates;
   explicitly approve lag and future assumption, then run a separate linked scenario.
8. Compare and reuse orders on the scenario; check the final JSON export row by row
   and verify original order and history snapshots remain unchanged.
9. Check that incomplete or stale order-source coverage blocks export readiness.

Confirmed open orders are independently fixed at 21 tonnes in the fixture:
16 ordered − 2 delivered − 1 cancelled = 13 for one customer, plus 8 for another.
The third customer's unconfirmed 999-tonne line contributes zero confirmed demand;
that customer retains the mathematical expectation. Model means themselves are not
assumed to equal the historical constant exactly.

## Verification and limits

- 369 Python tests and 45 frontend tests passed; whitespace checks passed.
- Existing non-fatal lifecycle/dependency and SQLite connection warnings remain.
- New journey covers backend handlers, not a complete click-by-click import wizard
  acceptance. The prior ten-month browser demo remains intact.
- Synthetic factor data tests the pipeline, not the usefulness of Iranian inflation,
  exchange rates or disruption signals. No improved accuracy is claimed.
- Public release dates, client-specific CPI/FX sources, ERP semantics and longer
  client history still need evidence before production use.

## Next bounded task

Run the same workflow through the visible import screens at laptop and mobile
widths. Check mapping, customer matching, factor review, correction messages and
export selection; fix concrete navigation/layout gaps. Reuse this backend fixture
and existing UI components rather than add another dashboard or workflow.

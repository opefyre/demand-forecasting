# Factor evidence and with/without comparison — 24 September 2026

## Delivered scope

Sales/demand only. No production, inventory, purchasing, automatic order changes,
new AI call, or new public-feed integration. Reuses pandas, scikit-learn,
StatsForecast, Recharts, Radix, immutable DatasetStore versions and the existing
background job queue. The source files and previous client/demo runs are retained.

In Calculation details → Scenarios, **Factors & source coverage** shows each
selected factor's historical blank count, latest recorded period, file import date,
future provided/filled counts and declared source/geography/unit. Missing metadata
is shown as unspecified rather than inferred from a filename or the Tehran site
setting. Historical values are uploaded records, not independently verified facts;
future values are planning assumptions, even when supplied in a file. Counts are
customer–SKU-period cells, not distinct national data releases.

**Compare without factors** opens a centered confirmation. Approval creates a
separate saved input and calculation with the same source files, target, calendar,
units and forecast horizon, but no extra predictors. A manual method stays fixed;
automatic selection is rerun if it was the baseline policy. It is not an individual
factor causal test. Customer orders are neither copied nor edited: comparison
charts show model estimates, not an order-adjusted plan. Existing order-aware
forecasting and export behavior is unchanged.

The period chart can show all series or one customer–SKU series, with exact values.
Past-error scores and overall totals are explicitly portfolio-wide. Score comparison
requires the same engine, evaluation signature and reserved later-period tests.
Insufficient or mismatched evidence shows no accuracy winner. Excel records removed
factors, the testing policy and its limitations; original files are unchanged.

## Correction discovered during validation

Previously, ML historical tests passed the realized factor values of the test
period into the prediction. That can make tests unrealistically favorable for
inflation, FX and other inputs not known ahead of time.

The revised engine (`2026-09-factor-cutoff-3`) supplies each extra factor's last
nonmissing **raw training-period** value throughout that fold's forecast horizon.
Calendar features stay date-based. Scoring actual sales stay unchanged. Missing
training factor values cannot be filled from a later validation period; a missing
future factor with no historical value cannot silently become zero. The same
policy is recorded in result metrics and the Excel Run Settings sheet.

This fixes holdout-period predictor leakage, not all publication-time risks:
uploaded historical values can still be revised or have been published later than
their observation period. No historical release archive is supplied. Tests are
therefore a disclosed persistence approximation, not verified real-time replay.
Older saved runs remain untouched and must be recalculated before this comparison.
Manual future assumptions and their uncertainty are not proof of causation.

Method reference: [Forecasting: Principles and Practice — forecasting with
regression](https://otexts.com/fpp3/forecasting-regression.html) distinguishes
forecasting with information available ahead of time from using later predictor
observations. Our constant-factor fold policy is a conservative implementation
choice, not a guarantee that the source was published by the cutoff.

## Source decision

The existing [World Bank Iran inflation series](https://data.worldbank.org/indicator/FP.CPI.TOTL.ZG?locations=IR)
is annual country-level consumer-price inflation and lists CC BY 4.0 licensing.
It is not monthly Tehran inflation, a free-market IRR/USD quote or a future
inflation projection. Existing snapshots keep capture time and remain context-only;
the feature does not silently join or repeat those annual values into monthly
model data. Provider page checked 24 September; no new live feed was activated.
Global supply/disruption and war inputs likewise need explicit source/assumption
semantics, not arbitrary multipliers or AI-invented future observations.

## Verification

307 backend / 42 frontend tests passed; production build passed. New tests verify
raw training cutoff and retained calendar features, invariance of test score when
reserved-period factor actuals are changed, no missing-to-zero fallback, coverage
counts, unknown geography/unit, immutable/idempotent comparison inputs, method
preservation, old-engine/review/source-hash gates, normal job routing, series-level
chart selection and comparable-score guards. Existing dependency/deprecation,
SQLite resource and frontend bundle-size warnings remain.

Synthetic sample, not Tehran client accuracy:

- Baseline `9c4db36b5af8`: 12 customer–SKU series, 60 history months, 6 future months,
  Ridge with synthetic FX and energy inputs; total **8,411.013679 tonnes**.
- Comparison `314cb38ac1f4`: identical history/calendar/method without extra
  factors; total **8,422.879475 tonnes**.
- Same reserved test periods: error **12.507349% with** versus **10.350169% without**.
  Extra factors did not help this sample under this test policy. This is not a
  claim about the client's factory or future accuracy.
- Independent sum of all item-period values reconciles to each aggregate period;
  original historical series/source hashes match. Excel comparison and policy
  sheets checked with openpyxl. Reproduce read-only checks:
  `.venv/bin/python scripts/verify_factor_comparison.py --verify 314cb38ac1f4`.
- Browser: actual confirmation → queued job → completed comparison; customer–SKU
  filtering and return to All, exact-period table and visible chart lines/range.
  At 390 px, page width remains 390 and chart section width 362. Laptop centered
  modal and chart checked. No live OpenAI or client-system acceptance claimed.

## Next task

Create reusable dated factor imports with explicit unit/market/geography,
observation versus availability date, revisions, gap/freshness checks and reviewed
alignment. Preserve originals and require valid historical availability before
claiming point-in-time accuracy. Then connect one approved source through that
contract. True release archives, validated Iranian FX market choice, client actual
history/orders and live AI acceptance remain open dependencies.

# Reviewed future-factor scenarios

Historical checkpoint: operational references below describe the pre-sales-only
scope and are not an active backlog. For the current factor cutoff/comparison
workflow and current verification, see FACTOR_REVIEW.md (24 September 2026).

Verified 21 September 2026. This is a completed local workflow foundation, not
production certification or a claim that external factors improve client accuracy.

## User workflow

1. Import historical and future factor columns with the demand data. Select the
   relevant factors in Data and run a saved baseline. Driver-aware methods can
   learn their historical relationships; other methods may ignore them.
2. Open Forecast → Scenarios → Change inputs. Choose a factor and either one item
   or all items. Enter only the future periods to change; blanks retain the base.
3. State the unit, location/market and source for each changed factor. Provide a
   scenario name, owner and reason; review the values before calculating.
4. The background job refits the same method using unchanged historical inputs.
   Open its result to compare the saved baseline and scenario, then inspect the
   exact changes or export them.

The editor is part of the page, not a navigation-triggered modal. Drafts survive
reload locally; the review checkbox resets so restored values must be reviewed.
Retries with the same request and values do not create another dataset. Changed
values require a new request. Owner attribution is self-declared, not authenticated.

## What is preserved and checked

- Source IDs and SHA-256 hashes, real/sample classification, original settings,
  forecast item/date grid and chosen method must match the saved baseline.
- Only selected numeric future factors can change. Unknown factors/items, past
  dates, duplicates, non-finite values, missing review or incomplete provenance
  block saving. A no-op is not saved as a scenario.
- Earlier observations, historical tests and method choice do not change. A
  mismatched engine version or evaluation signature blocks comparison.
- Existing future-value policies and their warnings are inherited explicitly.
  Historical factor values are not overwritten with the scenario assumptions.
- Exact before/after values and source declarations are saved and included in
  Excel. Formula-like free text is escaped in the scenario evidence sheets.
- Material and capacity calculations use the recalculated forecast and the same
  source-verified production data. Missing production data is not shown as zero.

## Chart and comparison

The existing Recharts package renders saved values, joining by exact date rather
than array position. Missing scenario periods remain unknown, not zero. The
baseline is dashed, the scenario solid; the quantity axis starts at zero. The
saved asymmetric range is preserved and explicitly labelled indicative, with no
independent coverage claim. Keyboard-accessible tooltips and an exact-period
table provide the underlying quantities. Total, change and operational shortfall
counts are backed by the saved runs. Counts are material-periods or machine-periods,
not distinct materials or machines, and exclude any claim of financial impact.

## Sample evidence

Entirely synthetic Qazvin sample; **not the Tehran client's observations**.

- Baseline dataset `ab05c2a22176483fbf6463c67e2f6ba3`, run `b1cddb747ed5`:
  12 items, 60 historical months, 12 forecast months, Ridge + drivers.
- Scenario dataset `194f9f753d5f996de75a7b8e708a1fdc`, run `eda7225ef454`, created
  through the browser: September exchange rate 573,930 → 650,000 IRR/USD and
  energy curtailment 5.1 → 30 hours for all 12 items (24 changed cells).
- Baseline total 15,084.104022849 tonnes; scenario 15,003.268446031 tonnes,
  a −0.535899094% change. Only September forecasts change for this fitted model.
  History, historical metrics, evaluation signature and method weights match.
- Independently summed recipe demand matches all 72 material-periods; independently
  summed production-line demand matches all 60 capacity-periods. Material-periods
  below zero remain 62; overloaded line-periods change from 25 to 24.
- Export contains 24 changed values and two factor-source declarations.
- Browser checks: editor draft recovery/review reset; submission at 390×844;
  saved evidence; baseline/scenario navigation; 1280×850 chart layout; keyboard
  tooltip; exact values; mobile chart selection and 390px page-width containment.
  These are bounded checks, not acceptance of every viewport and workflow.
- Automated checks: 117 Python tests, four chart-data tests; frontend build passes.
  Existing bundle-size and dependency/build warnings remain non-blocking technical
  work, not hidden as a clean production-readiness claim.

Reproduce saved-result checks with `scripts/verify_assumption_sample.py --verify
eda7225ef454`. Its `--start` option creates another synthetic baseline and should
not be run merely to re-check an existing result.

## Remaining work and interpretation limits

- Tehran is the client site; exact coordinates are not inferred. Factor location,
  market and source fields are declarations, not live-feed verification. Unit
  labels are not conversions. Domain-specific value bounds remain to be added.
- Numeric future inputs are supported; categorical events, broad timeline paste,
  cross-factor constraints and large-grid load testing are not completed here.
- This is a statistical response, **not proof of causation**. A factor may have no
  effect. An energy-hours demand input does not automatically reduce machine
  capacity; operational capacity calendars still need their own governed changes.
  War or disruption assumptions are not predictive certainty or automatic news
  multipliers. Future observations cannot be obtained from a real-time feed.
- Approved Iranian FX markets, weather/disruption integrations, point-in-time
  factor vintages for backtests and automated input pipelines remain open. The
  existing World Bank cache is country context, not silently joined model data.
- Financial/service impacts, independent interval calibration, authenticated
  ownership/approvals, distributed idempotency, retention and real-site validation
  remain open. The seven supplied actual months are insufficient to establish
  annual seasonality or a reliable long-horizon client accuracy claim.

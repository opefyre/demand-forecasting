# Reviewed factor links

## Current delivery — 3 October 2026

Forecast → Calculation details → Scenarios → **Add forecast factors** now supports
one to eight saved monthly factors in one comparison. Each has its own 1–12 month
observation lag and constant or per-month future assumptions. Customers/products
and calculation method are shared controls, collapsed by default. Cards expand one
at a time; incomplete history or future assumptions block calculation.

Composition reuses identical sales/future rows and the existing forecasting models:
no extra estimator, dependency or AI call. Source dates, units, locations and exact
versions remain visible and saved. Duplicate versions of one factor are rejected.
Original sales, baseline forecast and orders are preserved. Existing order-aware
comparison/review is reused; orders are not silently changed or reapproved.

Matched historical test rows now provide baseline/scenario error and per-series
evidence, including scoped comparisons. Workbook sheets **Factor accuracy** and
**Factor test evidence** retain these calculations; **Factor alignment** and
**Factor sources** retain all drivers. Missing/mismatched evidence withholds scores.
Automatic method/model-mix changes are disclosed; improved error is not attributed
to factors alone. These are model tests, not order-aware plan accuracy or a guarantee
of future results. Test horizons hold factor values at the last training observation.

Verification: 393 backend tests, 56 frontend tests and build pass. The real-engine
integration test calculates single, scoped and two-factor scenarios and independently
recomputes the displayed error from retained rows. It verifies unchanged baselines,
row counts, source values, duplicate/missing-data gates, retry identity and exports.
Browser check: two-factor review correctly identifies incomplete synthetic history
and disables calculation; centered, scrollable controls checked at desktop/390px.
Original live demo was not replaced and no new live scenario was saved.

Remaining: verified Iranian CPI/FX sources and conversions, real-client acceptance,
broader public/combined-factor browser acceptance, and portfolio range calibration
for mixed scoped outputs. No live Iranian feed or verified source release archive is
claimed. Earlier entries below describe the original 24 September slice, not current
feature limitations. Later scoping/monthly/public/order work is recorded separately.

## Original delivery — 24 September 2026

## Delivered workflow

Forecast → Calculation details → Scenarios → **Link saved factor**.
Choose a saved monthly factor, its observation lag and an explicit future assumption.
Preview date matching, missing/unpublished periods, unit/location and scope. Approval
saves new history/future input copies and queues a separate model comparison using
the existing model libraries and job runner. Original quantities, files, forecasts,
customer directory and order book remain unchanged.

No new forecasting package or home-built estimator: the existing pandas date
handling, scikit-learn/statistical model selection, FactorStore, immutable DatasetStore,
Radix dialog, Recharts comparison and Excel export are reused.

## Exact mathematical input rule

For a sales month M and chosen lag L (1–12 months), the factor observation period is
the end of month M−L. Historical input uses the latest revision of THAT observation
published strictly before M began. It does not choose whichever older period happens
to exist, and does not use a later revision. For example, with a 2-month lag, October
sales link to August's observation only if it was published before October 1.

Historical feature values are frozen using the information declared available at
each sales month's start, rather than recalculating all history with today's revisions.
This is a conservative historical feature policy, not a certified vintage archive.
The existing validation engine still holds the last training factor value constant
through each reserved test horizon. It does not see realized holdout-period factors
or today's future scenario assumptions. Existing non-linked drivers retain their
previous, explicitly unverified provenance; linking one factor does not certify them.

For actual future predictions, all availability checks stop at the FIRST forecast
month's start. An already-published eligible value takes priority. Otherwise the
explicitly reviewed constant future assumption is used. This cutoff is intentionally
conservative and can precede today's run date. The displayed source trail distinguishes
published observations from assumptions.

Missing historical factors, late publications and missing assumptions block saving.
Sales-series gaps also block this workflow, preventing the general input cleaner
from silently interpolating linked factors into missing sales months. Annual/daily
factor conversion, Jalali conversion and currency/unit conversion are not inferred.

## Scope and limits

- Monthly factors and monthly sales only, one additional factor per comparison.
- The selected factor applies to ALL customer–SKU series in the chosen baseline.
  Geography and units are shown for explicit review, not auto-detected from customers.
- Latest saved factor versions are offered; the exact selected snapshot and its hash
  are recorded. Changing a factor file later cannot silently rewrite this comparison.
- Real and synthetic classifications must match. The baseline method is preserved;
  automatic selection, if used, is repeated. Methods ignoring factors may be unchanged.
- Future assumption is currently one constant for missing future observations.
  Per-month assumption curves, selective customer/SKU links and stacking linked
  scenarios remain follow-up work; they are not claimed as delivered here.
- This compares MODEL demand. It neither updates orders nor copies an old combined
  order-adjusted demand plan. Existing order consumption must be applied in its own
  reviewed workflow; no claim of new automatic order reconciliation is made.
- No new live public feed, live AI call, verified release archive, automatic FX market
  choice or claim of better client accuracy.

## Acceptance evidence

322 backend tests, 43 frontend tests and production build pass. Seven new backend
tests cover old revisions, late publication, missing factors/future values, sales
gaps, classification/engine gates, review-token changes, source corruption,
idempotent saves, source quantity/identifier preservation and real model/API/export
execution. The frontend accuracy comparison requires matching engine/test periods
and an independent test window. Without these it does not report a winning score.

Browser verification: full preview → approval → queued calculation → comparison;
the final dialog closes, one link action remains, and the saved scenario appears.
A duplicate React sibling key found during testing was corrected. Centered dialog
checked at 1366×900 and 390×844; narrow page width 390px, dialog 360px, stacked controls
and scrollable tables. Temporary screen-size overrides were reset.

Synthetic baseline `9c4db36b5af8`: 12 series, 60 months, 720 historical sales rows.
Factor snapshot `ce6730abd4ab58f0aa2036c36060b93c`: 62 monthly observations plus a
later revision; the first training feature remains 100, not revised 999. Lag 2,
future assumption 140. The shorter initial test factor version is preserved.

Verified comparison `ca2163878f2b`: aggregate forecast 8,013.923295943224 tonnes;
baseline 8,411.013679348196. Past error 13.110294610517673% versus baseline
12.507348847610642%. The extra synthetic factor made this test WORSE, which is
displayed rather than hidden. It is not evidence about the client's future accuracy.
Customer/SKU totals reconcile; displayed history is unchanged; the Excel package
contains all 66 historical/future alignment rows. A second identical browser run
(`882e1d58c384`) was used to verify the corrected dialog completion; it is another
saved demo version with the same numerical results.

Reproducible helpers: `scripts/verify_factor_link.py --seed` reuses or versions the
labelled synthetic factor; `--verify RUN_ID` checks a finished linked comparison,
unchanged displayed history, matching test periods, aggregate reconciliation and
the Factor alignment export sheet. Source preservation is also asserted in tests.

## Next bounded task

Assess and connect ONE approved free/public factor source through this date-aware
contract, with documented units, geographic coverage, update schedule and stale-data
checks. Prefer a source whose release history can be defended. A latest-only revised
feed must stay context-only or use first-capture availability; it must not be relabelled
as historically known. Iran FX market selection and client-system credentials remain
explicit dependencies. Per-month/per-customer link flexibility follows separately.

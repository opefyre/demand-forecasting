# Cold startup and legacy scenario consolidation — 11 October 2026

## Delivered

- Future-factor edits and no-factor comparisons are company-scoped resources.
  They save immutable reviewed inputs, then enter the same fixed forecast wizard
  as manual/AI factor proposals. Customers/orders must be reviewed before a run.
- Baseline, source bytes and settings are checked again at dispatch/execution.
  Changed sources cannot publish; original forecasts stay unchanged. Orders,
  revision groups and CSV/XLSX/JSON exports remain attached to the resulting run.
- Advanced scenarios are reachable through the existing Forecast options menu,
  not an extra navigation page or toolbar. Editors/comparisons use shared layout,
  disclosures, tables and dialogs. No new CSS or inline styles.
- Fixed a completed-scenario result crash: the model label must read dataset
  settings, not scenario provenance. Added an English/Persian rendering test.
- Translated factor-frequency labels and the advanced factor action. Imported
  names, source files and product codes remain unchanged.
- Input checkpoint loading overlaps readiness. Output writes run in batches of
  at most three, all settled before error cleanup. Backup-before-publication,
  byte limits and company checks remain intact.
- Cold startup no longer awaits VM-dependent idle setup inside the claim gate.
  Readiness requests are bounded; asynchronous startup exits are observed.
  Expired pending allocations are cancelled even before `running` becomes true.
- Owner/admin-only diagnostics expose bounded timings/failure codes, never input
  content, credentials, company IDs or internal error text. Status does not wake
  the container. One allocation; five-minute idle sleep; no warm-up polling.

## Measurements — not an accuracy claim

The first real cold order-review request failed, leaving a busy lease until its
deadline. The following measurements are from the corrected controller, not a
comparison against an earlier successful benchmark:

| Private cloud operation | Readiness | Processing | Storage | Total |
| --- | ---: | ---: | ---: | ---: |
| Cold synthetic order-review save | 2.497 s | 17.741 s | 1.302 s | 21.656 s |
| Warm reviewed request | 0.033 s | 11.523 s | 1.365 s | 13.166 s |
| Warm automatic forecast | 0.035 s | 54.315 s | 1.239 s | 56.228 s |
| Automatic forecast after idle wake/review | 0.034 s | 54.542 s | 1.232 s | 56.107 s |

Totals also include input loading. These are engine-side measurements, not the
entire wizard/click-to-screen time. The automatic forecast used previously saved
synthetic Tehran history: 804 observations, 18 customer/product combinations,
six forecast months, mixed confirmed/unconfirmed/cancelled/fulfilled orders.
It saved and reopened with total demand **3,982.84 tonnes**, including
**2,099.36** still-open confirmed orders and **1,837.77** expected demand.
The balance is fulfilled quantity, not double-counted orders.

The engine was observed asleep (`running=false`, `busy=false`) after its idle
deadline. An explicitly reviewed save woke it again and reached model selection;
the subsequent full automatic forecast completed with the same total. The second
forecast row above is warm because the preceding order-review request woke the
engine; it is not a standalone cold mathematical-job measurement.

The exact offline production image became ready in 0.891 seconds on the dedicated
local build VM. That excludes Cloudflare allocation/network/storage. Host-only
profiling showed model fitting/backtests, especially ARIMA, dominate processing;
no models, validation folds or accuracy checks were removed to improve timing.

## Verification

- 48 focused backend tests plus 64 additional related regressions pass; a
  subsequent 30-test subset also passes after the final review refactor.
- 331 interface tests, 64 cloud/controller tests and production frontend build
  pass. Cloud boot verifier uses disposable offline storage.
- English browser task: future assumptions → exact method/horizon → explicit
  saved-order reuse → calculation → named result. Original preserved.
- Persian browser tasks: data/factors/orders/methods/results, three-method
  grouped result, saved-draft resume, no-factor comparison with reviewed orders.
  The latter found the result crash above; it was repaired and rechecked.
- Data's five tabs and Settings use the existing shared page/collection layout.
  Real private cloud People/API screens load, with the owner as the only member
  and no API keys. No invitations, keys or notification sends created.
- Company/role denial, changed-input rejection, exports and forecast revisions
  are covered by backend tests; synthetic test state never replaces client data.

## Still open / next acceptance chunk

1. Complete remaining English/Persian management/approval/chat/import tasks,
   including empty/error/retry states, narrow-screen and keyboard-only journeys.
   Chrome's viewport override returned 1512×736 rather than requested 390×844;
   this run does **not** count as verified mobile acceptance. Override reset.
2. Finish large-history performance and cancellation/concurrency acceptance
   without weakening model tests. A 56-second automatic run is not instantaneous.
3. Real client accuracy, verified historical factor release dates and provider AI
   eligibility remain separate gates. Synthetic data cannot prove market accuracy.

Private engine/edge only deployed; identity/storage services and other domains
unchanged. No new public routes, accounts, credentials or AI provider calls.
Whole-app acceptance remains open.

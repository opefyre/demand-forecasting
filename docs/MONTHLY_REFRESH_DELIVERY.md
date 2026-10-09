# Guided forecast update

7 October 2026 — delivered and verified

Confirmed: saved history versions, repeat-upload review, live-source status,
forecast jobs, reviewed factor scenarios, order import/reuse and planning exports
already exist. The missing piece is one recoverable journey joining them.

Build: an owner-bound, saved update session launched from Home or Assistant.
Reuse existing services for history → calculation → optional factor comparison →
current orders → change review → exports. One next action at a time, no new sidebar.
Original inputs, forecasts and orders remain unchanged. Resuming must recheck
source integrity, job results, latest orders and expiry, not infer approval from
visited pages. Compare exact overlapping customer/product/month rows; added and
removed months are not zero. Keep delivered quantities out of planning exports.

Inference: monthly planners need to retain their previous forecast for comparison.
The comparison is a change report, not proof of a factor's causal effect or accuracy.

Open: client quantity meaning/history sufficiency, source permissions and factor
benefit, actual ERP contract, deployment and wider human acceptance. No forecast
accuracy or full-product completion claim is supported by this workflow alone.

Verification checklist

- [x] Saved sessions, ownership, concurrent edits and safe retries.
- [x] Complete-history replacement or explicit reuse; integrity and matching grain.
- [x] Live-source checks disclosed; future values never fabricated.
- [x] Existing calculation queue and reviewed factor scenario handoff.
- [x] Reviewed current orders, no automatic copying or renewed freshness.
- [x] Exact change comparison and rechecked export readiness.
- [x] Home/Assistant entry, refresh recovery, desktop/small-screen checks.
- [x] Deterministic end-to-end synthetic journey, regressions and interface build.

## What changed

Home and the forecast dashboard have an Update forecast entry. Assistant can
prepare the same journey with the existing Agents SDK; its action retry always
reopens the same saved session. Each step has one next action. Uploads save inputs
first, not an untracked forecast, and use a session-specific unfinished-import
key so another saved import is not overwritten or silently restored.

History choices preserve calendar, quantity meaning and units. Calculations reuse
the existing model catalog, preflight and worker queue. Factor comparisons reuse
the existing reviewed live-factor/scenario workflow. Connected-source status is
not evidence that a source has been applied to a model. Orders require separate
review, including coverage and unchanged freshness; visiting a page is not approval.

Comparison uses exact customer/product/month matches. Missing/added periods are
not zero; totals only cover matching periods. Export asks whether the receiving
system already holds orders and produces residual demand or combined demand.
Every download rechecks the reviewed report, forecast hash, latest orders and
expiry. A newer order book or changed result blocks the old download link.
Outputs are drafts, not company-approved plans or deliveries to an ERP.

## Verification

- 532 backend tests pass (71.527s); 93 interface tests pass; production build passes.
- Real numerical calculations exercised through temporary stores: full update,
  history replacement with shifted horizon, reviewed factor comparison,
  retry/recovery, source corruption, expiry/new orders and export gating.
- Browser: saved steps survive reload but unchecked approvals do not; existing
  centered order-reuse review, calculation progress, comparison search, both
  export choices and dashboard handoff. Desktop, 390px and 320px tested. Table
  scrolling remains inside the card on mobile, with no page overflow.
- Existing SDK tool invoked directly in tests without provider calls. Wider
  paid-provider natural-language acceptance is still open; no OpenAI calls made
  by this verification. Existing source schedules were not modified.
- Known pre-existing numerical/database warnings and large-bundle build warning
  remain; these test passes do not claim deployment or client accuracy acceptance.

Browser demo: session `892a164b3b80522d86b286470869461a`, baseline `df87c7ec00ae`,
new forecast `32e479445d9d`, separately reviewed order snapshot
`5a9682bfb357437e13e940417b88039a`. Synthetic sample, 36 Persian history months,
two customers, one SKU, ten forecast months. No factor scenario was selected in
this browser demo; the factor branch was tested separately with synthetic data.
Using unchanged history/method intentionally gives unchanged calculated demand.

| Export | Rows | Planning quantity (tonnes) |
| --- | ---: | ---: |
| Expected demand only, CSV / Excel / JSON | 20 each | 2,232.62 each |
| Orders + expected demand, CSV / Excel / JSON | 20 each | 2,372.62 each |

Calculated demand is 2,339.60. First-month Customer A estimate 106.98 is consumed
by confirmed orders: 140 open plus 20 delivered means 140 still to serve, not
160. Customer B has no order and retains 126.98 expected demand. Delivered 20
is excluded from all planning-export quantities. All six live-local downloads
were parsed and reconciled; CSV was also downloaded through the browser.

Evidence: `outputs/monthly-update-desktop.png`, `outputs/monthly-update-mobile.png`.
Raw local test logs: `/private/tmp/demandlab-monthly-final-{backend,ui,build}.log`.

## Next major build

Automatic live-factor evaluation per customer/product: reuse current factor
alignment, publication timing, backtesting and numerical models to compare
seasonality-only versus factor-aware forecasts. Retain a factor only when
historical held-out evidence supports it; show the result in plain language.
Pin source versions and declare future assumptions instead of inventing future
exchange rates, inflation or disruption values. Keep user-selected methods and
scenario review available. This is a forecasting-engine build, not more sidebar
pages. Sufficient client history and source permissions remain prerequisites for
claiming real-world improvement.

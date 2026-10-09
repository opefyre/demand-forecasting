# Monthly draft forecasts — 7 October 2026

## Delivered

Home → Monthly draft settings lets an administrator choose an original sales
forecast, day of its planning month (1–28), horizon, method and optional existing
history connection. Confirmation authorizes draft calculation only. The schedule
uses Persian or Gregorian months from that forecast and Tehran time. It reuses
APScheduler, reviewed DatasetStore versions, the monthly update workflow and the
existing numerical job queue. No new package, provider, key or AI call is needed.

Home shows a compact monthly row: paused, calculating, ready for review or needs
attention. Review opens the existing update at the correct step. Changed history
counts are optional detail; exact changes remain in the normal reviewed input and
forecast comparison flows. The same update is not duplicated in Recent updates.
Sidebar Home now returns to Home; explicit start/resume actions still open updates.
Setup stays a centered dialog, not a new navigation page.

## Input and calculation rules

- Only original monthly, customer/product-mapped, history-only baselines qualify.
  Future factor files cannot silently enter a recurring calculation.
- Without a connection, use the latest saved reviewed descendant of the selected
  original sales input. With a connection, check its exact approved history file
  and use its accepted version only. New unreviewed files and failed checks block.
- History must end at the latest completed planning month. Each customer/product
  history group must contain that month. Missing is not treated as zero; explicit
  zero sales may be supplied and reviewed. Existing import validation and calendar,
  sales-meaning, unit and classification comparisons still apply.
- Automatic selection, seasonal, trend and irregular-demand choices use existing
  mathematical models. The backend also accepts named existing methods. This
  interface does not add its own mathematical formula or change the engine.
- One cycle per schedule/planning month; SQLite serialization and deterministic
  update/save/job requests avoid duplicate calculations across retries/restarts.
  Interrupted cycle publication recovers the already dispatched monthly update.
- A baseline draft stops at external-factor review. Fresh future assumptions and
  customer orders are NOT carried forward, copied or approved. The normal sequence
  remains factors → orders → exact change review → draft export/company approval.
- No factor freshness is renewed and no forecast accuracy is claimed because a
  monthly draft was calculated. No ERP write or automatically approved export.
- Configuration/check writes require administrator access and CSRF in company
  mode. Schedules and updates are owner-bound. Revoked administrator access blocks
  new automatic dispatch; original inputs and forecasts remain unchanged.
- Checks run every ten minutes while this local app server is running, on or after
  the chosen day. No offline/cloud execution is claimed. Missed previous months
  are not retroactively fabricated. The demo schedule is left paused.

## Evidence

598 backend tests and 111 interface tests pass; production build passes. Nine new
service tests use real stores and the real engine, covering scope/confirmation,
Tehran and Persian year boundaries, reviewed replacements, missing customer-months,
stale history, revoked owners, connected unreviewed files and dispatch recovery.
One actual middleware test checks administrator-only writes and CSRF. Two rendered
markup tests distinguish statuses and prevent action buttons for unavailable data.
Existing monthly tests still cover partial orders and all six exports.

An initial security-test fixture expected the wrong login redirect and omitted
FastAPI's lazy included router. The fixture was corrected; the final full suite
passed. Known library deprecation/database cleanup warnings and the large bundle
advisory remain. Tests are not proof of real-client forecasting accuracy.

Browser demo: original synthetic baseline `d729c16c0f56`, four customer/product
series over 48 months, six forecast months. Schedule
`31c8a59b92be50b389b48aff57cc0b31` generated October cycle
`ccd089ab38525012b343cc01679eb220`, update
`2303dc3e807e5768a07931feabd7213b`, job
`618f0a1ec45546c4b839f32ed9340387`, and actual result `5fc3247800e4`.
Repeated check reused the same cycle/job. Review opened at Factors; no order
snapshot was created. The schedule was explicitly paused after testing. Original
baseline/order demo remains available. Desktop and 390px/320px setup and Home
navigation checked; controls remain inside the modal and narrow viewport.
Screenshots: outputs/recurring-forecast-settings.png,
outputs/recurring-forecast-mobile.png and outputs/recurring-forecast-home.png.

The dashboard skill influenced the compact status/exception queue, optional source
change detail, no invented headline scores and reuse of the existing review page.
This is an in-app product feature, not a newly scheduled Codex/cloud dashboard job.

## Remaining / next major chunk

Release hardening and pilot package: realistic large customer/SKU/order volumes,
performance and resource limits, restart/recovery and role boundaries, deployment
instructions, and a complete import-to-planning-export acceptance demo. Reuse
existing models, jobs, source adapters and backup/recovery tools; do not add unrelated
production or inventory functions.

Whole-product acceptance still requires permitted fresh and sufficiently complete
live factors, wider AI acceptance, longer actual client history, measured forecast
benefit, receiving-system reconciliation and secure deployment. Automatic ingestion
of unreviewed sales or implicit reuse of future assumptions is deliberately excluded.

# Superseded scope — preserved 22 September 2026

Historical evidence only. The active sales/demand requirements and checklist in
../ supersede this operations-planning scope. Do not use this as a build backlog.

# DemandLab delivery checklist

21 September demo freeze: the user deferred remaining work to next week. The
in-progress delivery-file import is finished and browser-verified, including
mapping, explicit confirmation meanings, saved evidence and stock reconciliation.
Latest milestone: **222 Python tests, 16 JavaScript tests and frontend build pass**.
See `DEMO_GUIDE.md` for the prepared sample and `NEXT_WEEK_HANDOFF.md` for remaining
work. The broad goal is paused, not complete; production acceptance remains open.

21 September accessibility increment: shared caption/control and help bindings
now cover native fields and Radix selects, preserving existing accessible names.
Six new component checks (16 JavaScript checks total) pass; frontend build and
bounded import/dialog keyboard plus laptop/phone checks pass. Full screen-reader,
role-specific, RTL and end-to-end acceptance remains open. See `UX_REBUILD.md`.

21 September recovery increment: offline checksummed state backup and safe restore
now cover data/runs with process exclusion, immutable destinations, SQLite checks
and disabled restored runtime work. Full suite: 216 tests pass. Actual 244-file
restore and business-record comparison passed; live app/worker healthy after
restart. `WORKSPACE_RECOVERY.md` records exact evidence and remaining off-device,
relocated-deployment, encryption, migration and multi-host acceptance gates.

21 September inventory increment: immutable reviewed purchase/production receipt
schedules now feed native-unit stock projections. 37 targeted receipt, inventory,
unit and access tests plus frontend build pass. See `INVENTORY_RECEIPTS.md` for
rules and sample evidence. File import was subsequently completed above; scheduled
ERP imports, service targets, intra-period availability
and broader replenishment remain open; this does not close the full requirement.

The earlier completion claim is withdrawn. The approved product direction remains in `PRODUCT_REDESIGN.md`; the latest UI acceptance criteria are in `UX_REBUILD.md`. A passing sample is not production certification.

## Working local workflow

- [x] Five primary pages: Today, Forecast, Data, Plans and Supply; Settings is separate.
- [x] Source-backed Today entry point: scoped reviews/activity, material/capacity and
  demand-pattern checks, missing-evidence actions, exact supply/forecast navigation,
  filters and explicit forecast/plan basis. Owned/dated reviews, overdue/status
  filters, immutable action history and stale/concurrent-change guards are now
  implemented. Cross-plan queues and service/excess measures remain open
  (`TODAY_WORKFLOW.md`).
- [x] React, Radix UI, Phosphor Icons, Recharts and locally served fonts.
- [x] Visible laptop navigation labels, centered action dialogs and surface-based visual separation.
- [x] Guided file upload, selected Excel worksheet, column mapping, settings and validation.
- [x] Persist source bytes and input snapshots; reopen without re-uploading.
- [x] Retain unfinished import mappings and progress.
- [x] Repeat-import repair: keep exact matching column/factor choices, clear missing
  fields rather than silently remapping, isolate existing-dataset drafts and save
  parent-version lineage. Browser reload/save recovery verified; file-picker
  replacement browser acceptance remains open (details in `UX_REBUILD.md`).
- [x] Reject invalid quantities/dates and missing required future factors before fitting.
- [x] Reusable saved-input forecast runs and individual mathematical method selection.
- [x] Connected history/forecast chart, exact period table and historical test metrics.
- [x] Explicit percentage scenarios tied to the exact originating forecast.
- [x] Local plan states, owner/reason records, comments and approval history.
- [x] Linked draft revisions from locked plans, effective-adjustment inheritance, frozen previous-plan comparisons, retry-safe creation and export lineage. Local cross-process persistence is now verified in `PLAN_STORAGE.md`; authenticated approval remains open.
- [x] Prevent quantity edits after approval/publication; open a plan's exact forecast.
- [x] Review quantities, current-value edits, recorded reversals, return-to-draft/review and explicit forecast/plan/supply selection. Synthetic browser cycle and independent export/recipe reconciliation recorded in `UX_REBUILD.md`; authenticated review remains open.
- [x] BOM/material projection, quality holds, purchase receipts, MOQ and lead time.
- [x] Fix repeated material-order proposals and sum customers sharing the same SKU.
- [x] Validate production schemas, forecast SKU coverage and capacity line/month coverage.
- [x] Synthetic Iran manufacturing sample, saved baseline, selected-method rerun and scenario.
- [x] Local CSV/Excel run packages and explicit sample labels.
- [x] 203 Python checks pass after owned-review changes; ten JavaScript import/chart-data checks passed in the save-recovery phase. Bounded responsive verification and exact remaining gaps are recorded in `UX_REBUILD.md` and feature-specific records.

## Forecast reliability — implemented foundations, further validation needed

- [x] Expanding historical windows, requested-horizon evaluation and evidence warnings.
- [x] Seasonal, trend, intermittent and driver-aware candidates using open-source libraries.
- [x] Explicit Holt, Holt-Winters, NumPy-weighted recent average, Elastic Net and daily weekly/yearly MSTL candidates; training-window eligibility, convergence failures, family-ensemble guard, method/version export and saved manual-run verification (`FORECAST_METHODS.md`). Configurable cycles/tuning and genuine client validation remain open.
- [x] Direct multi-step ML training and benchmark comparisons.
- [x] WAPE, bias, per-item metrics and demand diagnostics. Ranges are indicative; independent coverage is not claimed.
- [x] Explicit missing-future-value policies; no default silent extrapolation.
- [x] Period alignment before aggregation so mid-month observations are not discarded.
- [ ] Validate model selection on genuinely unseen site data, including selection bias and drift.
- [x] Refit imputation/outlier treatment inside each validation fold; score original observed actuals. Regression checks cover future-data changes and capped-target leakage.
- [ ] Validate uncertainty independently, including correlated errors across products.
- [x] Reserved-period range checks and joint portfolio errors: separate fitting windows when history permits, exact residual widths, missing-range guards, counts/horizon evidence and reconciled exports. 149 backend tests pass. Real-site coverage, richer hierarchy ranges and longer monitoring remain open (`PLANNING_RANGES.md`).
- [ ] Implement and validate richer hierarchy reconciliation and saved hierarchy views.
- [ ] Turn stockout/lost-sales flags into a governed correction workflow.
- [ ] Add new-product analogs, substitutions, cannibalisation and promotion modelling.

## Remaining operational product work

- [ ] General connector ingestion, mapping, credential handling, provenance and freshness. Legacy adapters only test availability; the separate World Bank integration now ingests and versions country-level context.
- [x] Local export-folder ingestion: approved roots and exact files, reused reviewed
  mappings, scheduled/manual checks, change hashes, staged review, failure history,
  parent/source provenance and admin controls. Synthetic browser ingest/review/save
  and scheduler tests pass. ERP/API ingestion and deployment hardening remain open
  (`FOLDER_INPUTS.md`).
- [ ] Approved Iranian/local/global factor sources with geographic coverage and user-reviewed future assumptions.
- [x] NASA POWER historical-weather connection: explicit coordinates/permission, actual daily download, saved raw/hash/version, source/units/date checks, missing-day coverage, complete-month summaries, cache reuse and daily export. Context only, not plant-specific until coordinates are confirmed or an automatic model feed; see `WEATHER_CONNECTOR.md`.
- [ ] Advanced factor scenarios and comparisons across materials, service, capacity and financial impact.
- [x] Reviewed numeric future-factor scenarios: unchanged historical evidence, saved owner/reason/unit/location/source declarations, refit of the original method, queued jobs, exact-change export, interactive baseline/scenario comparison and recalculated material/capacity quantities. Not financial/service scenarios or live-feed certification; see `FACTOR_SCENARIOS.md`.
- [x] Explicit approved-plan supply recalculation and plan export share resolved quantities, including active adjustments. Verified production snapshots are hash-checked; draft supply is blocked. Forecast exports remain separately labelled baseline outputs.
- [ ] Editable production-data mapping, arbitrary unit conversion, service targets and validated days-of-cover.
- [x] Production table-mapping foundation: arbitrary Excel worksheet/heading/column selection, explicit material-stock date, per-material units, source-cell lineage and saved-mapping reuse for approved supply (`PRODUCTION_MAPPING.md`).
- [x] Unit-aware route workload: multi-step products, shared machines, effective rates, batch setup, net available hours and plan-adjusted exports. Five mapped operational tables; monthly aggregate scope, not finite scheduling. Independent-file inputs and advanced routing remain open (`ROUTED_PRODUCTION.md`).
- [x] Unit foundation: Pint physical conversions plus explicitly selected, reviewed, immutable product-rule versions. Exact SKU/direction/date matching and sample isolation. Stock and production recipe/route product quantities are covered; history conversion and general manufacturing conversions remain open.
- [x] Separate guided stock import, source-cell lineage, exact native units, confirmed snapshot dates, explicit usable/held/unknown status and duplicate-key validation. Immutable snapshots feed on-hand-only projections against baseline or approved quantities. This does not complete production routing, unit conversion or replenishment planning.
- [ ] Like-for-like monitoring, closed-period actuals governance and an implemented retraining workflow.
- [x] Actual-results foundation: reviewed immutable imports, paired plan comparison,
  source/quantity reconciliation, issue/approval timing gates, coverage disclosure,
  unit/date/duplicate guards and exact-row export. Comparable historical signatures
  replace unrelated-run drift claims. Automatic retraining and full authenticated
  closed-period/correction governance remain incomplete.
- [ ] Validated AI-assisted explanations and mapping; deterministic helpers are not a complete AI assistant.
- [ ] Persian UI translation, complete RTL interaction testing and Jalali input/display selection.
- [ ] Real identity, role permissions, independent approval enforcement and tenant isolation.
- [x] Authlib OIDC foundation, revocable sessions, CSRF checks, server-enforced
  roles and independent signed-in plan approval. Local real-plan approval is
  blocked. Crypto-flow and permission tests pass; real-provider deployment,
  broader identity binding and tenant isolation remain open (`ACCESS_CONTROL.md`).
- [ ] Durable production database, migrations, backups and retention controls.
- [x] Bounded local plan registry: transactional SQLite, one-time lossless legacy
  migration, cross-process update tests and consistent non-overwriting backups with
  restore verification. Whole-app recovery, automated retention and production
  database rollout remain open. See `PLAN_STORAGE.md` (166 backend tests).
- [x] Local persistent Huey queue, saved progress, cancellation checkpoints, retry lineage, duplicate-claim prevention and interrupted-attempt recovery. Partial outputs are not published.
- [ ] Authenticated concurrent-user job tests, distributed deployment, recovery/load soak tests and staging retention.
- [ ] Real-site pilot and user acceptance testing of every operational workflow.

## Completion rule

Do not call the app 100% complete or ready for live operational deployment while these items remain open. Missing functionality must be absent or labelled honestly in the UI, never represented by decorative cards or simulated connection status.

## 21 September verification evidence

- Reviewed actual-results workflow raises the suite to 80 passing checks. Live
  sample import/restart/export and two methods on matching test evidence verified;
  exact IDs, arithmetic and remaining governance limits are in ACTUAL_RESULTS.md.

- Both client workbooks inspected read-only: `CLIENT_WORKBOOK_FINDINGS.md` and local `data/client_audit/workbooks.json`. Formula caches, invalid lookups, mixed units and seven actual months are documented.
- Wide-sheet imports keep actual/plan roles, exact source cells and units. Repeated financial date columns cannot overwrite demand. Unknown labels do not default to actuals; negative quantities require correction or explicit item exclusions.
- Statistical methods now use StatsForecast 2.1.1. Unavailable methods expose their failure rather than silently substituting another forecast.
- Earlier windows select methods; the latest eligible window independently checks them. Changing confirmation actuals does not change method selection. Short histories show selection-only evidence and cannot be approved.
- Synthetic run `40b210edc4d9`: 60 months, 12 items, 12-month horizon; 288 selection predictions plus 144 separate confirmation predictions; 5.6587% confirmation WAPE. This is synthetic evidence, not client accuracy.
- Rerun `5d1b2ebe361d` reproduces that result and captures hashes for all legacy source files. Synthetic approved plan `af2fb75272` exercises adjusted supply in the browser. Already-saved runs are not retroactively given provenance they did not capture.
- Client diagnostic `0ea4f6f71c21`: 279 KBlank series, 1,953 actual rows, 1,248,635.35 KBlank; two negative-quantity items explicitly excluded. Three-month outlook; one-month selection test only, 44.9184% selection WAPE. No independent accuracy claim or approval.
- Tehran confirmed by user and saved. No exact coordinates inferred. Iran holidays/Jalali features use maintained libraries; workweek and extra closures are configurable and preserved for future periods.
- World Bank Iran inflation fetched and cached (36 annual observations, 1990–2025). Public macro context is separate from model inputs; revised history is not silently treated as information available in older backtests. FX, plant weather and disruption feeds remain open; reviewed numeric future-factor scenarios are now implemented as documented in `FACTOR_SCENARIOS.md`.
- Plan-output tests verify matching adjusted quantities in supply/Excel, unchanged statistical baseline, reverted/latest adjustments, invalid values, formula-safe text export, draft-supply rejection and source-hash mismatch rejection.
- 45 regression tests and production frontend build pass. Current UI checks and remaining viewport coverage are tracked in `UX_REBUILD.md`.
- Background execution raises the suite to 52 passing checks. Live cancel → retry
  → browser reload → Ready was verified, as was a real worker interruption with
  lease expiry and no published partial result. See `BACKGROUND_JOBS.md` for exact
  job references, operating behavior and deployment limitations.
- Inventory adds 12 checks (64 total): identifier preservation, duplicate headings,
  invalid/missing quantities, dates/units, stock keys, immutable snapshots, held
  stock, customer aggregation, unknown/mixed-unit guards, malformed files, blank
  heading recovery, source-role isolation and approved-plan quantity resolution.
- Real FG sheet reconciles independently to 270 records, 3,463 بوبین and 25,754,700
  بلنک. The source has Warehouse status throughout; its quality meaning and snapshot
  date are not inferred. Browser import correctly matches C/L/K/G/H/D and blocks
  review without a confirmed stock date. No client stock snapshot was invented.
- Sample stock imported through the UI and compared with run b2e0a2e9e080:
  COA-ART-135 opens at 2,000 usable tonnes, excludes 250 held tonnes and closes
  September at 1,883.5 after 116.5 demand (display rounding only). PKG-KRAFT-120
  shows a 142.8-tonne shortfall; other products explicitly show stock not supplied.
  This is synthetic workflow verification, not evidence of client accuracy.

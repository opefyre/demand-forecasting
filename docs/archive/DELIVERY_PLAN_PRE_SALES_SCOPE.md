# Superseded scope — preserved 22 September 2026

Historical evidence only. The active sales/demand requirements and checklist in
../ supersede this operations-planning scope. Do not use this as a build backlog.

# Operational forecasting delivery plan

Updated 21 September 2026. The approved product specification remains the scope;
this is the execution order, not a reduction of that scope. Completion is tracked
in IMPLEMENTATION_CHECKLIST.md. The application is not production-certified.

**Demo freeze:** on 21 September the user requested the current demo and deferral
of remaining development to next week. The active receipt-import increment is
finished. Use DEMO_GUIDE.md and NEXT_WEEK_HANDOFF.md; do not automatically resume
the priorities below. The broad goal is paused, not complete.

## Current execution priorities — after the credit-use checkpoint

No optional model expansion or additional visual redesign until the primary
workflows pass acceptance. Existing completed phases should not be reimplemented.
Use targeted regression checks for each change; reserve full-suite reruns for
cross-cutting changes and milestone acceptance. Record failures once and fix the
specific workflow instead of accumulating parallel redesigns.

1. **Close access-control verification.** The Authlib foundation and local sample
   regression are complete (`ACCESS_CONTROL.md`). Real provider/HTTPS/account
   configuration and full role-specific browser acceptance are separate open gates.
2. **Complete one end-to-end planning journey.** Import actuals → resolve invalid
   rows → select horizon/method → inspect honest test evidence → save/review a plan
   → compare supply → export → compare later actuals. Verify empty/error/retry,
   keyboard and laptop/small-screen states. Fix functional blockers before polish.
3. **Automate repeat inputs.** Start with one reusable, reviewed ingestion mapping
   and observable refresh history; then configured ERP/API sources. Do not present
   connection checks or context-only public feeds as automated forecast drivers.
   The local-folder route is now implemented and browser/test verified as described
   in `FOLDER_INPUTS.md`; HTTP/database/ERP ingestion is still open.
4. **Close operational decision gaps.** Owned decisions, governed stockout/actuals
   corrections, inventory receipts/netting and service measures with real units.
   Reviewed manual purchase/production receipt schedules now support period-end
   stock netting and reviewed file import (`INVENTORY_RECEIPTS.md`); scheduled ERP
   receipt ingestion, reconciliation
   and service measures remain open.
   Retain hierarchy, product lifecycle and Persian/Jalali/RTL requirements in the
   main checklist; do not substitute decorative UI for these capabilities.
5. **Deployment and client acceptance.** Whole-workspace restore, permissions,
   multi-user recovery, exact client master-data definitions and unseen actuals.
   Offline data/runs recovery is now implemented and exercised locally; see
   `WORKSPACE_RECOVERY.md`. Relocated deployment/off-device disaster acceptance
   and multi-host operation remain open.
   No production-readiness or client-accuracy claim until these gates pass.

Client inputs needed, without stopping independent implementation: longer actuals,
inventory date/status meanings, unit/routing definitions, chosen FX market and
currency convention, approved provider/accounts and precise plant coordinates
where location-specific weather is desired. Tehran alone is not a weather station.

## 1. Trustworthy inputs and client reconciliation — in progress

Completed foundation: both workbook audits; actual/plan separation; unit/source-cell
lineage; explicit exclusions; reconciled KBlank diagnostic. MPS routing, stock and
conversion mapping remain unfinished and require confirmed business definitions.

- Inspect both supplied workbooks locally, including formulas, cached errors,
  repeated date blocks, units, actual/forecast labels and production dependencies.
- Keep actual sales, customer forecasts, budgets, production schedules, stock and
  capacity separate. Unknown labels must not default to actual sales.
- Preserve source coordinates and source-file hashes. Show a plain-language
  readiness review, with blockers before forecasting and optional details.
- Reconcile normalized quantities to the actual source cells. No hidden unit
  conversions, source edits, or transmission of client data to external AI.

## 2. Forecast engine and evidence

Completed foundation: StatsForecast integration, fold-local preprocessing, separate
selection/confirmation windows, explicit model failures and saved manifests. Real
site validation, point-in-time external drivers and independently tested intervals
remain open.

Method expansion now includes Holt, Holt-Winters, weighted recent average,
Elastic Net and daily weekly/yearly MSTL using existing libraries. Eligibility is
checked per training window; nonconvergence is visible; family ensembles must
beat their best eligible member. Manual choice, exact assigned weights and
exported method/version metadata are verified with the saved synthetic runs in
FORECAST_METHODS.md. This does not establish client accuracy or finish interval
calibration, hierarchy reconciliation or model-policy configuration.

Planning ranges now have separate fitting windows where possible and a reserved
later check, with own-item scales, joint portfolio errors, unsupported-range
guards and row-level export evidence (`PLANNING_RANGES.md`). This replaces the
old blended width heuristic; it does not certify future or client coverage.
Next focus is complete primary-workflow acceptance, not optional method growth.

- Fit preprocessing inside each historical training window; score observed,
  unchanged actuals. Separate selection evidence from genuinely held-out evidence.
- Prefer maintained statistical/ML libraries. Keep simple benchmarks, intermittent
  methods and manual method selection; do not disguise a failed model as success.
- Gate seasonal claims, uncertainty and approval on available evidence. Seven
  months cannot establish annual seasonality or validate a twelve-month forecast.
- Preserve versioned inputs, model settings, future assumptions and evaluation.

## 3. Factors and automated inputs

Implemented: Tehran site profile, configurable Iranian calendar, versioned World
Bank macro context. Country-level context is not silently joined into forecasting.

Reviewed numeric future-factor scenarios are now implemented: source-verified
baseline, explicit item/period edits, owner/reason/unit/location/source declarations,
same-method refitting, historical-evidence preservation, saved comparison chart,
material/capacity recalculation and exports. See FACTOR_SCENARIOS.md. This does not
complete live local feeds, point-in-time backtest vintages, financial/service
scenarios or authenticated governance.

NASA POWER historical weather now downloads and versions actual responses for
explicitly selected coordinates, with sharing confirmation, daily quality checks,
complete-month aggregation and export. Public 0°, 0° example verified through the
browser; factory coordinates are not inferred. See WEATHER_CONNECTOR.md. It is
historical context, not future weather or an automatically selected model driver.

- Versioned, locally cached factor observations with source, geography, units,
  observation time and availability time. No backtest access to later releases.
- Iran calendars; plant/province weather; Iran macroeconomic data; explicit FX
  market and rial/toman conventions. War/disruptions are dated risk assumptions,
  not invented predictive signals or news-to-demand multipliers.
- Implement actual ingestion for suitable public APIs and user-configured sources,
  with reviewed mappings, health/freshness, retries and explicit future assumptions.
- Source suitability and licensing must be verified; free access is not an SLA.

## 4. Operational decisions

Implemented: shared approved-plan quantity resolver, supply recalculation from the
verified production snapshot and consistent plan/supply workbook exports. Broader
units, routing, inventory governance and authenticated approvals remain open.

Implemented next: separate guided stock imports (Excel/CSV/TSV/JSON), positional
column mapping, composite stock keys, explicit dates/quality, immutable SQLite
snapshots, and native-unit on-hand projections against baseline or approved-plan
quantities. Missing stock/status and incompatible units remain unknown. The stock
date must immediately precede the first forecast period; no partial-period demand
is guessed. Receipts/production are not yet included in this native-unit projection.
Client FG mapping is staged, not operationally confirmed. Unit conversion,
production routing and replenishment integration remain open.

- Approved-plan quantities drive exports and supply calculations consistently.
- Scenario comparisons include supply/capacity/financial implications only where
  real inputs and compatible units exist. Carry missing inputs as unknown.
- Match capacity by stage/machine/period and preserve unit conversions; inventory
  needs a confirmed as-of date and quality status. Do not infer either from a title.
- Comparable monitoring, governed actuals, hierarchy views, owned decisions,
  auditable overrides, and justified new-product workflows.

Implemented actual-results foundation: guided actuals import with exact item/date
joins, closed-period/unit checks, duplicate rejection, visible missing coverage,
immutable reviewed comparisons and exports. Prospective and plan-improvement
scores require issue/approval times before each period. New historical runs carry
exact evaluation signatures; unmatched runs no longer produce drift/retraining
claims. Automated retraining, authenticated period locks and a correction policy
remain open. Details and sample reconciliation: ACTUAL_RESULTS.md.

## 5. Simple interface, complete workflows

21 September routing extension: unit-aware recipes, effective multi-step routes,
shared-machine load, batch setup, net available hours and adjusted-plan exports
are implemented and reconciled with a synthetic KBlank sample. See
ROUTED_PRODUCTION.md. This is monthly workload, not a feasible job schedule;
advanced routing, production netting and real factory definitions remain open.

- One clear next action per state; readable typography; quiet black/white surfaces;
  Phosphor icons with labels; centered dialogs only for short actions.
- Progressive disclosure of assumptions and technical evidence. Full pages for
  destinations; no decorative metrics, duplicate actions or fake integrations.
- Guided import, recovery from errors, method comparisons, connected charts,
  factors and scenario controls, plan review and supply decisions.
- Verify keyboard use and 1440/1280/1024/768/390 layouts using the running app.
- Persian/Jalali/RTL and site calendar/unit settings are retained requirements.

## 6. Deployment and acceptance

Local execution foundation now includes Huey/SQLite background jobs, saved state,
cooperative cancellation, atomic output publication and interrupted-attempt retry.
It is verified with isolated race/recovery tests and a real synthetic worker-stop
test. Authentication, shared-database migration, backup/retention and multi-user
load/recovery acceptance remain incomplete.

- Identity/permissions, independent approvals, tenant isolation, durable migrations,
  backup/restore, queued/recoverable jobs and multi-user tests before deployment.
- Automated regression suite plus real-workbook reconciliation and local sample.
- Actual client pilot, confirmed master data and unseen observations are required
  before any claim of operational accuracy or deployment readiness.

## Evidence needed from the client (do not invent)

Longer dated actuals; return/cancellation/stockout definitions; authoritative site
and inventory as-of dates; product/unit conversions; confirmed FX market/currency;
machine calendars/routings; approval owners; approved external data sources.
These do not block building the import, validation and forecasting infrastructure.
# Stock-unit phase — 21 September 2026

Completed bounded stock-outlook unit definitions using Pint and immutable,
reviewed product rules. Seven new automated checks; 87 total passing. See
`UNIT_DEFINITIONS.md` for user workflow, sample reconciliation and limitations.
Production routing/BOM conversions, service targets, governed integrations and
deployment/pilot acceptance remain open; this is not overall product completion.

## Production mapping phase — 21 September 2026

Guided operational worksheet/heading/column mapping now feeds saved datasets,
forecasts, scenarios and approved-plan supply. Source cells, material stock dates
and input hashes are preserved. Unknown delivery statuses and invalid optional
values block; out-of-horizon receipts/capacity no longer create extra forecast
periods. Eight new checks, 95 total; mapped synthetic forecast and supply verified.
See `PRODUCTION_MAPPING.md`. This does not complete multi-stage routing, general
production units, service targets, live integrations or real-site acceptance.

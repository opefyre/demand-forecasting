# Sales/demand forecasting delivery plan

## Current priority — approved public-platform expansion, 9 October

Follow [PUBLIC_PLATFORM_DELIVERY.md](PUBLIC_PLATFORM_DELIVERY.md) for the current
build order. Older entries below are delivery history, not today's next-task plan.

Access foundation is published. Company-separated sales inputs, orders, factors,
grouped model jobs, results/exports and independent approvals are now implemented
as a backend milestone. See [COMPANY_FORECAST_DELIVERY.md](COMPANY_FORECAST_DELIVERY.md).
The existing local demo remains usable; do not enable company mode yet.

Core assistant/personal context, settings/views, actual results, external-source
management and primary frontend workflows now use company stores. See
[context migration](COMPANY_CONTEXT_DELIVERY.md) for evidence and bounded scope.
Advanced assistant scenarios, monthly updates and recurring drafts are delivered:
see [company workflows](COMPANY_WORKFLOWS_DELIVERY.md).
Read-only HTTPS/SFTP history/future-input connections now capture immutable inputs
and hand off to reviewed mapping: see [company connections](COMPANY_CONNECTIONS_DELIVERY.md).
Connected customers/orders, Odoo/Google Sheets, recurring captures and resource
lifecycle are delivered. Administrator notifications and delivery history are now
implemented: see [notification delivery](COMPANY_NOTIFICATIONS_DELIVERY.md).
Next: deployment/provider acceptance, production identity/mail and secret storage,
company backup/restore and role-based walkthrough. No production or inventory scope.

Private Cloudflare identity foundation, 10 October: shared maintained Better Auth
policy now supports native D1; new empty identity database and route-less private
Worker deployed. Dedicated Google/Resend/auth credentials installed securely.
Company/role/MFA/session/key tests pass; public app, login and API remain closed.
The local demo remains loopback-only and unchanged. This original foundation
checkpoint left administrator/runtime migration open; the next paragraph records
the completed runtime slice. Real Google/mail and cloud UI acceptance remain open.
See [Cloudflare checkpoint](CLOUDFLARE_DEPLOYMENT.md).
Private runtime slice, 10 October: serialized native D1 access operations,
company-only immutable R2 checkpoints, encrypted integration credentials and a
recoverable native SQLite job/revision ledger are implemented and tested. The
Linux mathematical engine reuses existing calculations and partial-order handling;
bounded native container lifecycle uses five-minute inactivity and no warm pool.
See [runtime delivery and exact limits](CLOUD_RUNTIME_DELIVERY.md).
Private company API slice, 10 October: the existing customer, input/upload,
order/factor review and grouped-forecast APIs now have a durable private command
bridge and saved read views that do not wake computation. Validation errors do
not publish scratch changes; live scope checks and company/revision fences remain.
See [scope, verification and remaining work](CLOUD_API_DELIVERY.md). The local UI
has not been switched to this asynchronous cloud protocol.
Approved reports/resource slice, 10 October: approval/export, lifecycle, settings,
personal views and saved-chat resource bridges plus shared asynchronous screen
and download adapters are implemented. See [exact scope and gates](CLOUD_REPORTS_DELIVERY.md).
The public edge remains closed; the private screen adapter is not a cloud UI launch.
Cloud workflow slice, 10 October: assistant, live connectors, durable schedules
and remaining management routes are bridged; see CLOUD_WORKFLOWS_DELIVERY.md.
Owner acceptance, 10 October: the existing interface now runs privately at
forecast.vrolen.com. Real Google login, owner-enrolled MFA and Resend delivery
are verified. Fictional Tehran history/orders produced a six-month mathematical
forecast and a 108-row CSV export. All other people remain denied. See
CLOUD_OWNER_ACCEPTANCE.md for exact evidence and unresolved gates.
Current next task: finish measured sleep/wake, then reduce cold Automatic runtime
(roughly nine minutes on the smallest engine), verify recovery/off-device restore
and explicitly configure approved live providers. AI remains separately gated.
Do not open public access automatically or change the independent local demo.

## Earlier delivery history

Latest delivery, 7 October — guided read recovery across sales demand, order-import
schema, monthly updates and saved live-source information. Failed reads no longer
suggest empty orders or permanent loading. Structured bilingual guidance preserves
permissions, source evidence and no automatic write retries. 143 interface / 65
focused backend tests and build pass; isolated actual-component browser recoveries
record zero writes. Existing demo quantities and filters remain correct. See
SALES_RECOVERY_DELIVERY.md. No new package, backend/model or credential changes.
Next substantial chunk: combined first-use/monthly-update acceptance pilot across
roles, corrected inputs, failures, calendars, filtered review and all export forms.
Broader navigation/layout changes await the user's end-to-end feedback. This
supersedes earlier next-chunk priorities, not whole-product completion.

Latest delivery, 7 October — bilingual advanced workflow controls: assistant,
factor preparation/review/batches, live-source status and saved-review navigation.
Auth and AI-setting labels included; deep forms and structured errors still partial.
129 interface / 39 focused backend tests and build pass; desktop/390px checks,
keyboard modal return and unchanged demo totals verified. No backend, credentials,
live AI request or deliberate source refresh. See BILINGUAL_WORKFLOW_DELIVERY.md.
Next major chunk: guided exception handling and complete bilingual sales-journey
acceptance, with planner/reader roles, errors, reloads, keyboard use and exports.
This supersedes earlier next-chunk priorities, not whole-product completion.

Latest delivery, 7 October — Persian/English foundation and primary sales workflow
labels delivered with open-source i18next, existing Persian font and RTL layout.
Twenty authored help topics, centered dialogs and data/export invariance checked;
121 interface checks and build pass. No backend, AI/provider or client-record change.
See PERSIAN_INTERFACE_DELIVERY.md. Advanced factor/scenario/assistant/admin/auth
screens and structured errors are not fully translated. Next substantial chunk:
finish that coverage and bilingual role/error/keyboard first-use-to-export acceptance.
Client accuracy, source/AI/receiver acceptance and secure deployment remain open.
This supersedes earlier next-chunk priorities, not whole-product completion.

Latest delivery, 7 October — normal customer/product sales import now needs no
composite identifier. Exact grouping reaches models, factor scenarios and saved
orders; old inputs remain compatible. Independent order math and six demo-approved
exports pass. A ten-month browser demo completes import, orders, customer/month
filtering, Excel download and reload. Mobile mapping/export and readable calculation
labels checked. See SALES_JOURNEY_ACCEPTANCE.md for bounded evidence and counts.
Next major build: Persian/English interface and right-to-left layouts on the same
sales workflow, then broader role/error/accessibility acceptance. Client accuracy,
live AI/provider rights, receiver acceptance and deployment remain open. This
supersedes the next-chunk priority below, not whole-product completion.

Latest delivery, 7 October — local release hardening and synthetic pilot completed.
All current automation is paused on restore without rewriting business snapshots;
stopped/missing monthly jobs show attention, and large order-book matching uses
set membership. Real imports/models/jobs, 120 series, 24,000 orders, six exports
and isolated restore reconcile independently; true Persian-month pilot passes.
606 backend / 111 interface checks and build pass. No new package, AI/provider
request, client-record replacement or new UI page. See RELEASE_PILOT.md.
Next major chunk: whole sales-journey acceptance and workflow/UX repairs across
first use, factor/order review, assistant, filtered results and planning exports,
including roles, errors, reloads and mobile. External rights/history, client accuracy,
receiving-system acceptance and company deployment remain separate open gates.
This supersedes older next-task entries; not whole-product completion.

Latest delivery, 7 October — recurring monthly draft workflow delivered. Existing
APScheduler, reviewed versions, job queue and monthly updates reused. Tehran/Persian/
Gregorian timing, latest completed-month and missing-not-zero gates, administrator
confirmation and idempotent recovery. Compact Home status queue and centered setup;
no copied orders, hidden future factors or automatic approved export. 598 backend /
111 interface checks and build pass; actual synthetic queue/demo left paused. See
RECURRING_FORECAST_DELIVERY.md. Next major chunk: release hardening and a realistic-
volume end-to-end pilot package. Source permission/freshness, client accuracy, wider
AI and secure deployment acceptance remain open. This supersedes earlier next-task
priorities; not whole-product completion.

Latest delivery, 7 October — assistant-led customer/product factor batches delivered.
Plain language resolves exact scope and opens the existing review workflow when
details are missing. Complete explicit inputs can be previewed and confirmed once,
then calculated through existing services with owner-bound progress and demand/order
handoff. 588 backend / 109 interface checks and build pass; one bounded live OpenAI
synthetic handoff and desktop/390px/320px review verified. See
ASSISTANT_FACTOR_BATCH_DELIVERY.md. Next major build: recurring monthly draft refresh
with one exception review, reusing input/order connections and factor batches;
automatic checks must never silently approve or publish. Source rights/freshness,
broader live AI acceptance, client accuracy and deployment remain open.
This supersedes earlier next-task priorities; not whole-product completion.

Latest delivery, 7 October — monthly customer/product factor batches delivered.
Different reviewed groups use existing calculations separately, then combine into
one forecast. Unselected products remain identical; current orders are reviewed
afterwards. Exact source/profile/settings checks, no overlapping scope, atomic queued
publication, draft recovery and mobile group cards. 578 backend / 105 interface tests
and build pass; synthetic partial-order demo and six demand exports reconcile.
See FACTOR_BATCH_DELIVERY.md. The assistant-led preparation, confirmation, calculation
progress and demand-result handoff priority is closed by the latest delivery above.
Live history/rights, client accuracy, wider AI and deployment acceptance remain open.
This supersedes earlier next-task priorities; not whole-product completion.

Latest delivery, 7 October — saved customer/product factor profiles and assistant
source-review handoff delivered. Exact scope, revision checks, inherited defaults,
product overrides and read-only SDK tools reuse existing services. Centered profile
dialog and forecast profile choices verified on desktop/mobile; original forecasts
and orders remain unchanged. See FACTOR_PROFILES_DELIVERY.md and checklist for tests.
The subsequent monthly batch delivery above closes this entry's next build priority.
Permitted complete live sources, client accuracy, broader AI acceptance and deployment
remain open. This supersedes earlier next-task priorities; not full completion.

Latest delivery, 7 October — declared-exposure live-source preparation delivered.
Existing adapters/alignment/models reused; historical coverage, freshness, permission
and immutable evidence gates; blank reviewed future assumptions. 556 backend / 98
interface tests and build pass. Synthetic calculation, partial orders and six exports
reconcile; desktop/390px/320px source dialog and connections handoff verified.
Actual retained feeds correctly remain blocked for refresh/permission; the commodity
refresh attempt hit its existing cooldown. See SOURCE_PREPARATION_DELIVERY.md.
Next major build: reusable customer/product exposure profiles and assistant-guided
monthly source preparation, using these same review/calculation/export services.
Client accuracy, source rights/history, wider AI acceptance and deployment remain
open. This supersedes the next-task priorities below; not full product completion.

Latest delivery, 7 October — automatic reviewed-factor testing per customer/SKU.
Existing statistical/sklearn models compare no factors, individual factors and
their combined set. Earlier-test 5% guardrail; frozen separate final check, honest
short-history fallback, filtered dashboard evidence and package exports. Six
synthetic cases/two seeds, Persian/Gregorian checks, partial confirmed-order demo
and all six planning exports verified. 544-test backend suite / 95 interface checks
and build pass, plus 10 overlapping targeted checks after the final fast-profile
fix. Desktop/mobile and incomplete-source block verified in browser. See
FACTOR_TESTING_DELIVERY.md. This supersedes earlier next-task priorities.
Next major build: source-to-factor preparation/recommendations in monthly updates,
reusing live adapters and assistant tools while preserving source timing/permission
gates. Unverified live history remains what-if only; real client accuracy, source
rights, broader AI acceptance and deployment are not yet complete.

Latest delivery, 7 October — guided monthly update delivered. Owner-bound recovery
joins reviewed history, existing calculation queue, optional factor comparisons,
current orders, exact change review and rechecked planning exports. 532 backend /
93 interface tests and build pass; ten-month Persian synthetic browser demo and
all six exports reconcile. 390px/320px layout checked; source freshness is not
renewed and no OpenAI call was needed. See MONTHLY_REFRESH_DELIVERY.md.
Next major build: automatic live-factor evaluation per customer/product using
existing timing/backtesting/models; retain only supported predictive benefit and
explicit future assumptions. Client accuracy, source permission, broader assistant
acceptance and deployment remain open. This supersedes earlier next-task entries.

Latest delivery, 7 October — reviewed formatting corrections and repeat-history
upload handoff implemented using existing agent/import/calculation services.
Original files/orders/forecasts unchanged; source-bound cell overlays, before/after
review and explicit save gates. Repeat uploads show added/changed/removed periods,
never silently append partial history. 522 backend / 89 interface checks and build
pass; actual synthetic calculation and 1280px/390px upload review verified without
OpenAI calls. See INPUT_CORRECTION_DELIVERY.md. Next major build: guided monthly
forecast refresh through history, live factors, current orders, comparison and
customer/product/month exports. This supersedes earlier next-task entries below.
Client accuracy, CPI permission/full history and deployment acceptance remain open.

Latest delivery, 3 October — assistant-guided order import/update and connected
factor scenarios implemented. Existing reviewed import, factor alignment and
forecast queue reused; exact scope/assumptions require human confirmation. No
orders are changed or automatically copied by the assistant. Calendar/required
note/fulfilled-quantity review gaps fixed. 510 backend / 84 frontend tests and
build pass. See ASSISTANT_GUIDED_WORKFLOWS.md. This supersedes older next-task
priorities below. Next major build: bounded AI input repair and repeat-import /
monthly refresh review. CPI permission, sufficient client history, wider workflow
acceptance and deployment still prevent a whole-product completion claim.

Latest delivery, 3 October — regional shipping live; official monthly Iran CPI
adapter built with commercial-permission gate. Five complete shipping months,
reconstructed-history/route limitations, immutable provider-owned projection,
strict complete-month inputs, reviewed what-if links and source charts are verified.
501 backend / 77 frontend tests and build pass. Existing synthetic demand demo and
six exports rechecked, without AI calls. See REGIONAL_LIVE_FACTORS.md.
The official CPI research sample is newer than the stale mirror, but automatic
commercial capture remains disabled pending permission. Account signup alone is
not permission. Remaining: full CPI capture, permitted longer regional trade data,
scheduled weather and client benefit/operational acceptance.
Next major build: assistant-led first order import and factor scenarios, reusing
existing mapping/review/calculation/order/export workflows with explicit approvals.
This entry supersedes older next-task priorities below; the product is not complete.

Current delivery checkpoint, 3 October — assistant onboarding and order handoff built.
No existing forecast is required. The existing import/mapping flow, Agents SDK,
numerical models, forecast queue, immutable datasets and order-consumption services
are reused. A selected sales-input version can be reviewed, corrected with approval,
forecasted, and combined with explicitly reviewed compatible saved orders.
Synthetic live run `df87c7ec00ae` has 10 Persian months, two customer/SKU series and
six reconciled planning exports; originals are preserved. See ASSISTANT_ONBOARDING.md.

Completion work, not optional polish:
1. Live monthly Iran CPI / regional shipping-trade sources with usable dated history,
   clear relevance/freshness and appropriate rights; no annual-to-monthly fabrication.
2. Assistant first order import and factor-scenario workflows; approved bounded
   cell repairs, broader ambiguous-language and failure-recovery acceptance.
3. Client quantity/calendar/order contract and sufficient actual history; measure
   whether methods/factors improve independent accuracy rather than promise it.
4. Whole-route UI/error acceptance, receiver export checks, permitted Iran AI
   deployment, deployment/backup/restore and multi-user operational acceptance.
Real ERP connectivity remains deferred. Client evidence/credentials/rights are
external acceptance dependencies, not tasks that can be marked done with code alone.
Next major implementation: the remaining live monthly Iran/regional factor pipeline.

Latest, 3 October — user authorized live external connections. Earlier integration
deferrals below are superseded for external factors. Public monthly commodities,
global supply pressure and annual Iran inflation fetched successfully; automatic
refresh controls and private Servix setup implemented. Industry API currently
fails; Servix authenticated capture and Keychain storage are now verified after
the user supplied its key. Private files are consolidated under `secrets/`. New feeds
are not automatically validated forecasting inputs. See LIVE_EXTERNAL_CONNECTIONS.md.
Latest follow-up delivered: live commodity/FX monthly alignment and reviewed what-if
scenarios, source integrity/coverage checks, Persian labels, Tehran capture cutoff,
fixed factor-aware methods, separate order drafts and labeled exports. Unsupported
past accuracy/ranges are withheld. Synthetic demo `d5fc4a311a66`; 478 backend / 69
frontend tests and build pass. See LIVE_EXTERNAL_CONNECTIONS.md for bounded evidence.
Next substantial build: monthly Iranian CPI and regional shipping/trade sources,
then genuine publication-time/prospective factor-benefit and client accuracy checks.

22 September 2026 — revised at the user's request.
Implementation authorized 23 September 2026. Orders/demand slice and OpenAI
multi-model foundation are implemented; see SALES_DEMAND_RELEASE.md for evidence.
PRODUCT_REDESIGN.md is authoritative; IMPLEMENTATION_CHECKLIST.md tracks delivery.
The former manufacturing-operations plan is archived, not an active backlog.

Current acceptance position, 3 October: core demo works; real Tehran operations need
revision. MARKET_AND_WORKFLOW_AUDIT.md records requirements, market fit, UI journeys,
independent arithmetic and remaining gaps. Actual demand reviews are now visible in
Saved reviews; 426 backend / 62 frontend tests and build pass. No paid call/live connection.
The Iran-ready sales-onboarding follow-up below supersedes the original build
priority. Remaining: client accuracy acceptance and permitted Iran AI deployment.
Live integrations are deferred. Older “next” notes below are historical, not current priority.

3 October — Iran sales onboarding implemented: true Gregorian/Persian planning
months, explicit history/order/actual-results date calendars and quantity meaning,
reviewed returns/corrections, customer aliases/ERP IDs and calendar-aware exports.
The client workbook’s Gregorian monthly totals cannot be shifted into Persian
months or finer periods. Its seven actual months remain insufficient for annual
seasonality validation. Source files and previous results are unchanged.
Synthetic Persian-month run `422d36f6e1d2`: 36 history months, two customers,
10 future months, mixed orders, 20 rows; CSV/Excel/JSON reconcile. Different calendar
order reuse is blocked. Home reuses saved history; factor actions no longer rely
on horizontal scrolling; public context is collapsed; legacy approval entry is
replaced by demand review. See current MARKET_AND_WORKFLOW_AUDIT.md checkpoint.
The AI-provider follow-up now reuses the existing SDK with OpenAI or explicit
loopback-only local models, durable daily/per-user call limits, per-request step
and input/output limits, and recipient-aware sharing permission. No automatic
fallback, retries, proxies or redirects. This is not a dollar cap or a validated
local deployment. No paid call, new credential or live integration was used.

Next substantial build: let the assistant start from uploaded data before any
forecast exists. Guide input review, propose supported fixes, calculate a draft,
combine matching orders and open the requested customer/SKU/month result/export.
Reuse current imports, numerical methods, jobs, order consumption and review gates.
Test ambiguity, missing inputs, partial orders, refusal and recovery, with no
silent changes or fabricated quantities. Include a navigation/language check of
each step. Real integrations remain deferred; client accuracy, receiver checks,
local-model compatibility and deployment acceptance remain open.

Latest, 3 October: Iran-ready factor import/linking delivered. Persian dates/digits,
real month boundaries, Tehran release-day timing, explicit FX market/basis/rial-toman
normalization, inflation measure/base year, current freshness and retained original
values. 401 backend / 58 frontend tests and build pass; desktop/390px sample checked.
See IRAN_FACTOR_INPUTS.md. Live Iranian CPI/FX feeds are NOT connected.
Next major chunk: automated factor-file refresh → validation → reviewed version →
forecast draft, then permission-cleared APIs. Correct client FX market, usable dated
sources and sufficient client history remain external dependencies.

Previous, 3 October: combined-factor scenarios delivered. One to eight dated monthly
drivers, independent future assumptions/lags, shared customer/SKU scope and optional
method choice. Exact historical test-row accuracy, model-mix disclosure and Excel
evidence; 393 backend / 56 frontend tests and build pass. See FACTOR_LINKS.md.
Next major chunk: Iran external-data onboarding — approved CPI and FX sources,
publication dates, Jalali/Gregorian and rial/toman normalization, refresh/stale-data
controls, then matched comparison on sufficient client history. Market/source
selection and actual client exports remain dependencies, not assumed integrations.

Previous, 3 October: compatible order connections reusable across forecasts, including
first order review on a new run. Source/target concurrency guards and exact retries;
391 backend / 55 frontend tests and build pass. See ORDER_FOLDER_REFRESH.md.
Next major chunk: combined-factor scenarios with Iran macro/FX, global supply and
internal events, source timing and method comparison. Real-client ingestion and
live configured-folder/mobile acceptance remain open.

Latest, 28 September: local full-order-book connections implemented with scheduled
staging, saved mapping, explicit refresh/review, pause/resume and existing demand
revision safeguards. 388 backend / 55 frontend tests and build pass. See
ORDER_FOLDER_REFRESH.md. No ERP connectivity or full browser acceptance claimed.
Next major chunk: client input pipeline acceptance and cross-run order refresh;
requires the actual client export contract, then Iran multi-factor integration.

Latest, 27 September: opt-in scheduled drafts implemented; reviewed versions only,
changed-data gates, pause/resume, retained dispatch history and job deduplication.
384 backend / 55 frontend tests and build pass. Live control acceptance pending.
Next: reviewed order-source refresh (stable IDs, fulfillment/cancellations) feeding
combined demand, without duplicate demand or silently renewed order reviews.

Previous: reviewed export-folder inputs can refresh/check and dispatch one pinned,
deduplicated draft job. 382 backend tests pass; REFRESH_DRAFT_WORKFLOW.md documents
scope and pending live UI acceptance. Next build is explicit opt-in draft scheduling
with review gates and pause/resume, not automatic publication. Order refresh remains
a separate source contract; no current-order freshness is inferred from sales files.

Latest, 27 September: combined scoped historical accuracy delivered with exact
observation matching and row-level evidence; 380 backend tests pass. Portfolio
ranges remain unavailable. Next primary build: saved-source refresh → validation →
draft forecast orchestration, explicit source selection and safe retries; never
automatic publication. Older “next task” entries below are chronological records.

27 September — customer/SKU factor output scoping implemented. Unselected saved
forecasts are preserved and combined totals/exports rebuilt. Full backend regression
377 tests passes. See SCOPED_FACTOR_SCENARIOS.md for the shared-training caveat and
withheld combined accuracy/ranges. Next build: matched historical accuracy for scoped
scenarios, then automated input-refresh-to-draft delivery; not another UI-only audit.

27 September — monthly factor curves implemented and tested. Constant or per-month
assumptions use the existing models, with known-data priority and review protection.
See MONTHLY_FACTOR_ASSUMPTIONS.md. Next substantive build: customer/SKU-specific
factor scope while preserving unaffected series and confirmed orders. Older small
audit tasks remain acceptance backlog, not the primary delivery sequence.

26 September checkpoint: customer/order correction recovery is improved and tested.
See ORDER_CORRECTION_ACCEPTANCE.md. Next bounded task: expired-order recovery and
a separately reviewed synthetic update through filtered views and planning exports.
The current selected demo's order review has expired; exports remain blocked until
reviewed again, without changing its saved evidence.

Follow-up: a separate synthetic review is now selected and exportable through
3 October; originals remain unchanged. Four exports and customer-month results
checked. Next: small-screen correction/error workflow and same-filename re-upload.

Mobile upload/correction slice completed at 320px and 390px, including same-filename
reselection and invalid-heading recovery. Next bounded task: browser acceptance for
full customer replacement and duplicate/mismatched order references, with no saved
demo overwrite. Backend coverage exists; end-to-end error guidance remains to verify.

Saved-input review and first-upload mapping suggestions are implemented as of
24 September. Acceptance evidence and current limits are in ASSISTED_INPUT_REVIEW.md.
The user's key is now configured and authenticated; one live synthetic scenario
workflow has passed. Wider AI judgment/latency/cost acceptance remains pending.

24 September checkpoint: factor evidence review and a matched without-factor
comparison are implemented. Historical tests no longer feed realized holdout
factor values to predictions. See FACTOR_REVIEW.md for evidence and limitations.
Original publication-time accuracy is still unverified; public annual snapshots
remain context-only. No new live feed or real-time exchange-rate claim was added.

24 September checkpoint: reusable dated factor imports are implemented, including
units/location/source, separate period/publication dates, revision-aware date checks,
gaps/latest-period age, reviewed immutable versions and reusable mapping. Existing
pandas/openpyxl parsing and FactorStore reused. See FACTOR_IMPORTS.md for evidence.
Importing alone still does not change forecasts.

24 September checkpoint: reviewed monthly factor links now feed existing models.
Explicit lag, publication-aware historical feature values, preview of all-series
scope, missing/unpublished blocking, approved future assumptions, separate comparison
and source-trace Excel export are implemented. See FACTOR_LINKS.md. Publication dates
remain uploader-declared; held-out predictions still use the last training factor
value. Per-customer links and per-month future assumption curves are not included.

24 September checkpoint: Iranian/global source benchmark and a live NY Fed GSCPI
context adapter added. Monthly history, retained vintage CSV, immutable versions,
attribution and freshness checks are implemented. See EXTERNAL_DATA_SOURCES.md.
No Iranian scraper or paid source enabled. Public-source forecast linking remains
unfinished: vintage headings do not yet prove historical release-day availability.

24 September checkpoint: reviewed GSCPI comparison now implemented using explicit
conservative vintage-month-end timing, NOT independently verified release dates.
334 backend / 43 frontend tests pass. The synthetic example worsened error from
2.64% to 2.86%; original forecast retained. See PUBLIC_FACTOR_COMPARISON.md.

24 September checkpoint: linked-factor scenarios now reuse saved customer/order
reviews through a filtered before/after comparison and explicit separate-draft save.
342 backend / 45 frontend tests pass. See ORDER_AWARE_SCENARIOS.md for evidence,
draft exports and limitations. No order mutation or publication approval is copied.

24 September checkpoint: assistant scenario comparison is implemented with exact
baseline scope, deterministic filtered previews, all-customer approval cards and
idempotent saves. A live synthetic run and reconciled exports passed; 349 backend /
45 frontend tests pass. See ASSISTANT_SCENARIO_COMPARISON.md. The key is configured,
locally enabled and authenticated; client data was not sent during testing.

24 September checkpoint: seven live synthetic assistant requests checked lookup,
customer/horizon continuation, ambiguity, clean-input review and unknown customers.
Input preflight now runs before forecast proposals; method-test payload reduced by
about 78% in the demo. Offline missing-factor and provider-recovery tests added;
355 Python tests pass. See ASSISTANT_ACCEPTANCE.md for usage and remaining limits.

24 September checkpoint: changed-horizon order reuse is implemented with an explicit
coverage review and separate immutable draft. Source dates, expiry and all order
records are preserved. See ORDER_REUSE.md. The user-approved ten-month synthetic
demo, desktop/mobile review and six export checks passed; 365 Python / 45 JavaScript
tests passed. Orders are never silently copied.

24 September checkpoint: isolated history/customer/order/factor import-to-export
acceptance passed using real parsers, public handlers and the forecast engine.
Fixed identifier corruption (`001` → `1`, `NA` → missing) in history parsing.
369 Python / 45 JavaScript tests pass. See SALES_IMPORT_ACCEPTANCE.md for scope.

24 September checkpoint: visible history/order import through saved demand and
export selection tested on laptop/mobile; six exports reconciled. Customer/product
mapping is now prominent, upload is keyboard-operable, imported samples are labelled
and mobile export choices fit. See IMPORT_UI_ACCEPTANCE.md for exact coverage.

24 September checkpoint: factor import is now three focused steps, assumption
values clear when switching factors, and unused commitments are collapsed. Browser
gap blocking, dated linking, separate comparison and order-aware exports passed.
The sample factor worsened historical error (7.21% → 7.89%); baseline preserved.
48 frontend tests/build pass. See FACTOR_UI_ACCEPTANCE.md.

Next bounded task: finish customer-file replacement and order correction/retry
cases through the UI, fixing concrete recovery gaps before adding more connectors.
Client FX market selection, permission-cleared CPI/FX history, client-system access,
longer historical sales and production deployment acceptance remain dependencies.

Continuing factor-pipeline acceptance:

1. Audit the current connector/scenario path and choose one defensible Iran/global
   factor source with documented geography, units, frequency and availability.
   Existing annual World Bank snapshots remain context-only unless a valid use is
   explicitly established; they are not monthly observations or Tehran-specific data.
2. Separate historical observations from user-approved future assumptions. Show
   missing/stale periods and source date; never silently fill inflation, exchange
   rates, disruption/war impacts or global supply values.
3. Preview the linked periods and create a separate scenario/input version, without
   changing the original forecast or customer order book.
4. Compare against the same baseline using eligible historical evidence only;
   preserve customer/SKU/month outputs and verify unchanged order-consumption math.
   Do not promise that extra parameters improve accuracy without test evidence.

Authenticated client-system integration follows when source access and order/status
semantics are available. Cell repair and live AI acceptance remain separate backlog
items, not prerequisites for manual forecasting.

## Delivery order after authorization

### 1. Agree the order-aware demand contract
Confirm target/date semantics, source order states, customer/SKU/unit identifiers,
partial versus complete commitments, order matching and the receiving MRP mode.
Use the numerical examples in the requirements as acceptance fixtures, including
mixed customers with and without orders in one forecast. Obtain the full customer
list and eligible customer–SKU relationships; match before aggregating.
Client history and order snapshots are needed; never fabricate them.

### 2. Deliver one complete sales-only slice
Import history and current sales orders → check source totals → choose/test a
method → combine confirmed orders and remaining expectation → inspect per
customer/SKU/month → review → export.
Prove cancellation, partial fulfillment, stale-source, duplicates and current-month
behavior. Keep the old demo intact; remove supply dependencies from the new journey.
Reuse existing forecasting, file mapping, plan/version, job and auth foundations.

### 3. Build the focused review workspace
Multi-view dashboard, filters and pivot table; booked versus expected demand;
data readiness, explainable exceptions, scenario comparisons and auditable approvals.
Validate real user tasks, keyboard and laptop/mobile layouts before visual expansion.
Only then migrate navigation away from legacy Supply features, preserving old records.

### 4. Automate sources and validate relevant factors
Connect one actual client system first, then add adapters based on demand.
Versioned API, reviewed mapping, scheduled/incremental refresh, freshness and retries.
Include internal business inputs and approved Iran/global factors only with sensible
timing, licence and predictive evidence. Implement point-in-time testing for orders
and factor data; evaluate final order-aware plans as well as the statistical baseline.

### 5. Add AI-assisted quality and the agentic assistant
Read/propose-first quality assistant, then permission-controlled draft forecast and
scenario tools, result navigation and export preparation. Numerical services remain
authoritative. Demonstrate the Customer A / 10-month request, approvals, privacy,
ambiguity handling, malicious-input resistance, cancellation and failure recovery.
AI method recommendations reference actual benchmark results, never unsupported judgement.

### 6. Complete handoff automation and release acceptance
Versioned residual-only versus combined-demand exports/API with downstream
reconciliation, acknowledgement and controlled replacement. Add opted-in recurring
draft refresh and exception review. Real roles, deployment, restore and client pilot.
Optional customer portals, CRM opportunity scenarios and order-arrival sensing come
after the core release, only if they improve this single forecasting purpose.

## Work control

- No production, inventory, material or purchasing phases.
- No new custom algorithm where a suitable maintained package meets the need.
- No open-ended connector/model collection; one demonstrable slice at a time.
- For each slice: exact acceptance cases, bounded changes, targeted tests, browser
  task verification and a short evidence update. Full regression at milestones.
- Keep implemented foundations distinct from unaccepted end-to-end capabilities.
- Do not reuse earlier calendar estimates: scope changed and client input/access
  dependencies are unresolved. Estimate each slice before starting it.
- The existing broader goal remains paused; when the user resumes work, align its
  objective to this scope rather than pursuing obsolete operational deliverables.

## Current position and preservation

3 October: order-aware sign-off and planning downloads now freeze reviewed quantities,
receiver policy and source evidence, with independent company approval rules and
separate local-demo status. See DEMAND_RELEASES.md. This completes the local final
review/export boundary; actual ERP transmission and receiving-system acceptance
remain open and require the client's system/export contract.

3 October: reviewed local factor-file connections now reuse scheduling, imports,
version storage and draft jobs. Changed exports wait for explicit review; source
changes never silently alter orders or published forecasts. See FACTOR_FOLDER_REFRESH.md.
The next substantial slice is a real-client monthly refresh/handoff contract,
not additional unrelated operational features. Live Iranian API, client source
reconciliation and production acceptance remain open.

Existing local demo and foundation evidence remain described in DEMO_GUIDE.md and
feature records. The 21 September checkpoint passed 222 Python / 16 JavaScript
tests and a frontend build. New order-aware calculations, dashboards and the agentic
assistant specified here were NOT certified by that checkpoint. The 23 September
slice adds new implementation/tests; live AI, client integrations and full acceptance
remain open. Source workbooks, saved forecasts and legacy plans are preserved.

Earlier scope records:
- archive/PRODUCT_REDESIGN_PRE_SALES_SCOPE.md
- archive/IMPLEMENTATION_CHECKLIST_PRE_SALES_SCOPE.md
- archive/DELIVERY_PLAN_PRE_SALES_SCOPE.md

Next client inputs: history plus order-line/schedule sample and definitions,
historical order snapshots if available, customer/product IDs and units,
MRP target contract, approved external/AI providers, privacy/identity and owners.

# DemandLab — implementation and acceptance checklist

## 9 October — Data tab interiors (follow-up)

- [x] One shared collection toolbar/body/table contract across Your files, Customers, Orders, Factors and Connections.
- [x] Shared controls, actions, forms and expandable sections; removed old tab-specific appearance rules and live-source stylesheet.
- [x] Orders Add/Edit in shared dialogs; cancel preserves values; version-checked saving unchanged.
- [x] Populated/empty-state rendering and narrow-screen long-name overflow repaired.
- [x] 235 frontend tests and production build passed; three backend route tests passed.
- [x] All five tabs checked on English/Persian mobile and desktop; no page overflow; test edits discarded.

See [DATA_TAB_UNIFICATION.md](DATA_TAB_UNIFICATION.md). The prior outer-page repair did not finish these internal tab layouts.

## 9 October — shared page structure and whole-app UX audit

- [x] Shared header/actions, controls/tabs and content structure across main destinations; global page tokens, not local spacing overrides.
- [x] Flush Home history sidebar; correctly placed toggle; compact quick actions.
- [x] Three-dot conversation actions: rename, pin, archive/restore, Trash/restore, private link, text export and search. No repeated chat icons.
- [x] Shared menu/dialog focus handoff; immediate rapid navigation; wizard step scroll reset inside the fixed modal.
- [x] Missing comparison values explicitly labelled; coverage action; single-month line points visible.
- [x] Main destinations and all Data/Settings sections inspected; English desktop, Persian mobile and narrow laptop checks.
- [x] Full suites: 673 backend and 226 frontend tests; frontend build passed. No paid provider calls or company data changes for this audit.

See [UI_UX_AUDIT_OCT09.md](UI_UX_AUDIT_OCT09.md) for actions, screenshots, browser journeys and limits. This does not close client accuracy, live-source permissions or secure deployment acceptance.

## 9 October — global motion

- [x] Central duration/easing/scale/distance tokens; one owner for all authored animations.
- [x] Shared hover/press/focus/disabled effects, dialogs, menus, tooltips, notices and disclosures.
- [x] Shared navigation, Settings, forecast/import/order steps, factor details, views and pagination.
- [x] Chat welcome/conversation transition; retain independent mascot motion.
- [x] Reduced-motion handling, browser fallback and once-only updates during rapid navigation.
- [x] Reuse Radix Presence for notification exits; no inline styles or new forecasting logic.
- [x] Full frontend tests/build and desktop/mobile browser checks; see `GLOBAL_MOTION.md`.

## 7 October — unified forecast inputs

- [x] Include customers, current orders and optional complete customer monthly
  requirements in the same new-forecast wizard, before calculation.
- [x] Reuse file readers, customer matching, review gates and order-consumption
  rules; no new forecasting formula or paid AI dependency.
- [x] Reuse compatible saved order books without changing their originals;
  reject newer source versions, changed history/factors and expired reviews.
- [x] Bind the same reviewed inputs to every selected method before publication;
  open combined demand directly and include a Combined demand workbook sheet.
- [x] Keep missing order coverage/missing customer history explicit and block
  misleading final exports. Keep customers without orders in the calculation.
- [x] Assistant-created new forecasts use the same input review, not an immediate
  history-only job; retain requested horizon, method and customer filter.
- [x] 171 interface tests/build, 26 unified-input/assistant tests and 81 existing
  sales/order/calendar/job/factor tests pass. Browser: two real factor-aware jobs,
  copied synthetic orders, immediate combined results; laptop and Persian mobile
  checks. See UNIFIED_FORECAST_WORKFLOW.md.
- [ ] Future task: refine/benchmark model selection, orders-as-features, factor
  relevance and uncertainty. Not part of this workflow change.


Scope revision: 22 September 2026. Authoritative requirements: PRODUCT_REDESIGN.md.
Only sales/demand forecasting is in scope. Implementation authorized 23 September
2026, including OpenAI with different models by job and a blank key placeholder.

Legend: checked = bounded existing foundation with evidence, not whole-product
acceptance; unchecked = unimplemented or not yet accepted for the revised scope.
Existing tests are not proof of new order-aware or assistant functionality.

## 7 October — user-directed interface rebuild (current priority)

- [x] Correct all Settings sections/forms using shared framework components; 169 interface tests and build pass.
- [x] Measure panel/field/button/type/spacing contracts across all five sections, both languages and desktop/mobile.
- [x] Migrate main active legacy page layouts to the shared framework and verify shared geometry; see the 9 October audit for the inspected routes and limits. Tokenized values alone are not acceptance evidence.

The user's eight UX objections supersede earlier cosmetic acceptance claims.
See INTERFACE_REBUILD.md for exact implementation and verification evidence.

- [x] AI-first Home, shared shell/footer, Vrolen green, no saved-calculation counter.
- [x] Tokenized React styles, no authored inline appearance and automated style guards.
- [x] Task-based Settings and compact mobile selection; retain monthly scheduling.
- [x] Clear New forecast entry, multiple real model jobs and individual results.
- [x] Four synthetic model runs verified; 165 frontend / 92 focused backend tests and build pass.
- [x] Direct live-factor selection/review inside the new start flow; freshness and exact-input review gates.
- [x] Persian and clutter audit of active destinations and shared dialogs; original source evidence preserved.
- [x] Retire static PoC fallback from both entry routes without deleting legacy files.
- [x] Desktop/mobile/RTL, keyboard pickers, centered dialogs and route checks for this interface release.
- [x] Immediate model results, shared customer/SKU/month filters, monthly view and reconciled filtered CSV.
- [x] No misleading accuracy/ranges for assumption-based runs; identifiers protected from translation.

The interface items above supersede the older partial-interface notes below.
They do not close real-client accuracy, external permission or deployment gates.

## 7 October — guided sales read recovery

- [x] Structured request failures, bilingual guidance, direct validation evidence,
  session/access/missing-version/rate-limit handling and no automatic write retry.
- [x] Demand failures do not masquerade as empty orders; saved-state reload for
  demand, order schema, monthly updates, live-source list and saved observations.
- [x] Role-aware expired-order guidance and readable source-access details;
  existing confirmation, freshness and export restrictions remain unchanged.
- [x] 143 interface / 65 focused backend tests and build pass. Synthetic browser
  recovery records zero writes; keyboard/Persian/mobile and unchanged demo checked.
  See SALES_RECOVERY_DELIVERY.md. No new package, model/backend or credentials.
- [ ] Full combined first-use/monthly-update bilingual pilot, including corrected
  uploads, interrupted saves/calculations, role restrictions and six exports.
- [ ] Wider navigation/layout revisions using the user's end-to-end feedback.
- [ ] Real-client accuracy, permitted live history, live AI/receiver acceptance
  and secure company deployment.

## 7 October — bilingual advanced workflow controls

- [x] Assistant/source picker/consent, factor preparation/profile/testing/batch
  controls, live-source status, saved-review and authentication/AI-settings labels.
- [x] Actual rendered review cards preserve identifiers, reader restrictions,
  expiry and explicit confirmation; source-status tests preserve freshness gates.
- [x] 129 interface tests, build and 39 focused backend tests pass. Desktop and
  390px assistant/source details, Escape/focus return and unchanged demo checked.
- [x] No new package, backend/model change, credential change or live AI request.
  See BILINGUAL_WORKFLOW_DELIVERY.md for evidence and boundaries.
- [ ] Complete deep admin/weather/order-reuse/comparison/scenario messages and
  structured errors. This is partial coverage, not a fully bilingual product.
- [ ] Next major chunk: guided exception handling and full bilingual sales-journey
  acceptance across roles, errors, reloads, keyboard use and exports.
- [ ] Real-client accuracy, provider/AI/receiver acceptance and secure deployment.

## 7 October — Persian/English sales interface

- [x] Existing header language switch and Settings choice; persisted en/fa preference.
- [x] Open-source i18next/react-i18next, existing Persian font, RTL layout and
  centered dialogs; chronology and numeric/date entries kept independent.
- [x] Primary sales labels, customer/order review, filters/views, draft exports
  and twenty authored Persian help topics. No data/identifier translation.
- [x] 121 interface checks and build; CSV byte identity, both calendar contracts,
  customer-filter state and unchanged export links checked across languages.
- [x] Reused demo; desktop, 390px export, 320px import/customer form, reload and
  mobile navigation inspected. See PERSIAN_INTERFACE_DELIVERY.md.
- [ ] Complete advanced factor/scenario/assistant/admin/authentication translation
  and structured errors; some English dynamic metadata remains.
- [ ] Complete bilingual first-use-to-export role/error/keyboard acceptance.
- [ ] Client accuracy, provider/AI/receiver acceptance and secure deployment.

## 7 October — normal customer/product sales journey

- [x] Customer/product grouping from separate columns, no prebuilt composite ID;
  stable exact keys, aliases/leading zeros, ambiguity and direct-route guards.
- [x] Same grouping used by factor scenarios, future inputs, AI evidence and
  repeat/monthly processing; old saved column-based inputs remain compatible.
- [x] Readable calculation labels, explicit pair counts and compatible AI mapping
  instructions. No new package, provider request or navigation destination.
- [x] Independent three-customer/same-SKU order accounting and all six
  demo-approved exports; factors and unchanged original source versions checked.
- [x] UI import to ten-month forecast, partial/cancelled orders, filtered monthly
  results, Excel download and reload; 390px mapping and centered export checked.
- [x] Full 612 backend / 114 interface checks and build; 25 focused backend checks
  after final AI mapping adjustment. See SALES_JOURNEY_ACCEPTANCE.md.
- [ ] Full Persian/English/RTL, role/error/keyboard and broader first-use acceptance.
- [ ] Real-client accuracy, live AI/provider acceptance and deployment/handoff gates.

## 7 October — release hardening and isolated sales pilot

- [x] Recovery pauses history/order/factor folder automation, live sources and
  recurring forecasts; accepted business records, source dates, permissions and
  quotas remain unchanged. Malformed schedules keep restore marked incomplete.
- [x] Stopped/missing monthly jobs show attention without duplicate calculation
  or breaking other schedule rows. Customer/order matching uses set membership.
- [x] Repeatable isolated real-import/model/job/order/export/recovery pilot; no
  OpenAI/provider call, client-record replacement or new package/UI page.
- [x] 120 series, 7,200 sales rows, 24,000 order lines and 1,440 forecast rows;
  independent baseline/order arithmetic and all six exports reconcile. A separate
  Persian-month run passes. Single-machine timings are not capacity promises.
- [x] Existing 10,000-relationship / 50,000-order validation boundary checked using
  a constructed baseline; this does not claim fitting 10,000 numerical models.
- [x] Full 606 backend / 111 interface checks and frontend build pass. README and
  local operating/recovery guide reflect current sales-only workflows.
- [x] Existing demo opens after restart; customer filters reconcile. Dark chart
  labels and first/last month visibility checked on desktop and 390px screens.
- [ ] Company/provider/receiver acceptance, real-client accuracy, intended-host
  concurrent load, off-device recovery and secure deployment remain open.
- [ ] Next major chunk: whole sales-journey product acceptance and remaining UX/
  workflow repairs, including first-time, role, error, reload and mobile states.

Evidence: RELEASE_PILOT.md and outputs/release-pilot-*/evidence.json.

## 7 October — recurring monthly drafts

- [x] Native APScheduler monthly draft orchestration reuses reviewed input versions,
  numerical jobs and the existing monthly-update workflow; no new package/AI call.
- [x] Persian/Gregorian month boundaries and Tehran time; exact optional history
  connection, latest completed-month records, missing-not-zero and source gates.
- [x] Explicit administrator confirmation, role/CSRF checks, owner-bound schedules,
  deterministic retries/restarts and no duplicate cycle or forecast calculation.
- [x] Compact Home status/attention rows, centered setup, optional change detail,
  existing review handoff and corrected Home navigation; no automatic orders/export.
- [x] 598 backend / 111 interface checks and build pass. Synthetic queued browser
  calculation reached factor review; desktop/mobile checks and demo left paused.
- [ ] Offline/cloud execution, complete permitted fresh external history, measured
  client accuracy, wider AI and receiving-system/deployment acceptance.
- [x] Local release hardening and realistic-volume pilot package; see the newer
  entry above for its bounded scope and company/deployment acceptance limits.

Evidence and boundaries: RECURRING_FORECAST_DELIVERY.md.

## 7 October — assistant-led customer/product factor batches

- [x] Existing Agents SDK can inspect exact groups, sources and saved profiles;
  preview complete user-provided assumptions or propose a restricted review handoff.
  No new dependency, model, navigation section or credential was introduced.
- [x] One explicit confirmation queues all complete groups through existing saves
  and calculations; owner/expiry/scope/source checks and idempotent retries remain.
  Missing or stale sources cannot be replaced by invented values or imported files.
- [x] Owner-bound progress exposes only the verified result; completion opens demand
  and order review. Factors never copy orders or publish an approved planning output.
- [x] 588 backend / 109 interface checks pass, including a confirmed two-group real
  engine calculation. Build and desktop/390px/320px browser review pass.
- [x] One bounded live OpenAI synthetic request produced the correct two-product
  handoff. Missing permission and stale actual feeds remained blocked in review.
- [ ] Broader live complete-proposal/provider acceptance, permitted full source
  history, independent client accuracy, receiving-system and deployment acceptance.
- [x] Next major build: recurring monthly draft refresh with a single exception
  review, reusing history/order connections, batch calculations and export gates.

Evidence: ASSISTANT_FACTOR_BATCH_DELIVERY.md. This is not whole-product completion.

## 7 October — customer/product monthly factor batches

- [x] Different reviewed factor sources, methods, timing and future assumptions per
  customer/product group; existing engine calculates each group separately.
- [x] Exact disjoint scope, same baseline, immutable source/settings/profile checks,
  matching months/units, finite values and chart/table reconciliation.
- [x] Unselected products retain their baseline; queued partial failures publish no
  combined result. Factor calculations never copy or modify current orders.
- [x] Centered review workflow, optional saved profiles, draft restoration without
  approval, compact mobile group cards, no new navigation and a short Help topic.
- [x] Monthly-update handoff to Orders/review/exports; existing CSV/Excel/JSON modes.
  No inherited global accuracy score or unsupported portfolio range.
- [x] 578 backend / 105 interface checks and build pass. Separate synthetic real-model
  browser demo and six exports; FACTOR_BATCH_DELIVERY.md records limits and evidence.
- [x] Assistant-led multi-customer monthly batch preparation, explicit confirmation,
  progress and results handoff using these same services.
- [ ] Permitted complete live history, successful stale-feed refresh, client accuracy,
  wider live assistant and deployment/operational acceptance.

## 7 October — saved customer/product factors and assistant handoff

- [x] Versioned customer defaults and exact product/unit overrides in Customers →
  Factors; clearing an override restores inheritance, without deleting audit history.
- [x] Exact canonical customer matching; inactive/unlinked/wrong-unit profiles ignored.
  Product exposure replaces the customer default; it is not silently combined.
- [x] Saved profile choices prepare sources for only that forecast series; changing
  context clears prepared inputs/approval, and profile-bound scope cannot be expanded.
- [x] Existing SDK tools inspect/preview/propose a factor-dialog handoff. Owner,
  expiry, forecast/profile/source changes checked; no automatic save, refresh or job.
- [x] Existing engine scoped calculation leaves the other customer's forecast
  identical. Actual middleware rejects viewer/reviewer writes and missing CSRF.
- [x] Desktop/390px/320px profile layout, saved choices, inherited suggestions,
  manual reset and unavailable-source blocks checked. 102 interface tests/build pass.
  568-test full backend suite passed; after adding/fixing the isolated security-test
  fixture, all 25 profile/security tests passed. See delivery note for run boundaries.
- [x] Monthly batch forecast with different factor profiles per customer/product,
  one reviewed demand plan and reconciled partial-order exports.
- [ ] Live-provider response acceptance for the new assistant tools, permitted
  complete source history, independent client accuracy and deployment acceptance.

Evidence and limitations: FACTOR_PROFILES_DELIVERY.md.

## 7 October — declared-exposure source preparation

- [x] Suggest existing Iran/global sources from explicit currency/supply/route/material
  exposure; no product-code guessing or claim of proven relevance.
- [x] Check raw evidence, history, stale observations, overdue capture and permission;
  unknown values stay unknown and cannot be used as zero.
- [x] Prepare selections in existing factor workflow, future assumptions blank,
  timing/calendar acknowledgments unset; recheck source-bound evidence before saving.
- [x] Record exposure and exact source versions in a derived scenario; no original
  history/order/forecast changes or paid calls. Manage connections opens Data → Factors.
- [x] 556 backend / 98 interface tests and build pass. Synthetic real-model calculation,
  partial orders and all six exports reconcile. Desktop/390px/320px dialog checked.
  See SOURCE_PREPARATION_DELIVERY.md for live-refresh and warning limitations.
- [x] Shared customer/product exposure defaults and assistant-driven source preparation;
  see the saved-profile delivery above for its one-profile-per-comparison boundary.
- [ ] Permitted complete live CPI/history, successful stale-feed refresh and measured
  client benefit; synthetic evidence does not close these acceptance dependencies.

## 7 October — automatic reviewed-factor testing

- [x] Opt-in customer/SKU choices: no factors, individual factors and combined set
  using existing statistical/sklearn models; bounded 1–8-factor search.
- [x] Earlier complete windows, practical 5% gate, separate frozen final check and
  short-history fallback; no claim of significance/causation or client accuracy.
- [x] Training-only transforms, no realized held-out factor leakage, required
  future assumptions, retrospective live scenarios blocked from automatic selection.
- [x] Visible method picker; collapsed filtered evidence and scoped package output.
- [x] Six synthetic cases/two seeds, real Persian boundaries, full saved six-month
  forecast/partial orders and six reconciled exports. 544-test backend suite /
  95 interface checks and build pass; 10 overlapping targeted checks cover the
  final fast-profile fix. Desktop/mobile and source-gap block verified;
  FACTOR_TESTING_DELIVERY.md records the limits.
- [x] Guided source preparation from declared exposure; bounded existing-source catalog.
- [ ] Prospective publication evidence and measured client benefit. Supplied factor
  release dates are not independently verified.

## 3 October — assistant-guided order and factor workflows

- [x] Order import/update proposal opens the existing reviewed workflow; exact
  forecast/order context checked, no model upload/save or carried approval.
- [x] Connected source inspection, read-only scenario preview and explicit
  customer/product scoped factor proposal; strict dated future assumptions.
- [x] Human review card and server confirmation; incomplete/corrupt/changed
  evidence blocks calculation; immutable save and idempotent queued job.
- [x] Calendar review bug, required note guidance and fulfilled quantity display
  fixed; sources/assumptions shown without adding a task-type selector.
- [x] 510 backend / 84 frontend checks and build pass. See
  ASSISTANT_GUIDED_WORKFLOWS.md for verification boundaries.
- [ ] AI order-column suggestions and human-evidenced value corrections;
  bounded formatting-only cell review is delivered in the 7 October section.
- [ ] Broader language/ambiguity/recovery and whole-route client acceptance;
  live CPI permission/history and independent client accuracy validation.

## 7 October — safe formatting and repeat history

- [x] Actual SDK tools inspect and propose bounded source-evidenced cell formatting.
- [x] Before/after approval, source hash recheck, retry-safe new input version;
  originals/quantities/leading-zero IDs retained; no guessed or missing values.
- [x] Repeat upload opens existing import flow; compares customer/product/period
  changes and missing months. Replacement, not automatic append; explicit review.
- [x] Old formatting overlays cannot carry into replacement files; factor-derived
  history applies them once. Existing forecasts and orders remain independent.
- [x] 522 backend / 89 interface checks, build, synthetic engine run and desktop/
  mobile upload review. Evidence and limits: INPUT_CORRECTION_DELIVERY.md.
- [x] Guided monthly history → live factors → forecast → current-order review →
  comparison/export journey, with bounded assistant continuation and recovery.
  Evidence and limits: MONTHLY_REFRESH_DELIVERY.md.
- [ ] Arbitrary human-evidenced corrections, ambiguity/large-file acceptance and
  live-model review of new tools; not claimed by the formatting-only delivery.

## 7 October — guided monthly forecast update

- [x] Durable owner-bound sessions, optimistic revisions, exact retries and
  explicit completion after the existing calculation queue; originals unchanged.
- [x] Comparable reviewed history choice/replacement, session-isolated upload
  recovery, no upload shortcut bypassing the forecast review step.
- [x] Source status distinct from model use; existing reviewed factor comparison
  handoff, no fabricated future values or automatic order copying.
- [x] Exact customer/product/month change review, missing values not zero;
  recheck latest/expired orders and report hashes on every export.
- [x] Minimal Home/dashboard/Assistant entry, one next step, centered order modal,
  restored progress without restored checkboxes, mobile table scrolling.
- [x] 532 backend / 93 interface checks, build, ten-month synthetic browser journey
  and six reconciled export formats. MONTHLY_REFRESH_DELIVERY.md records scope.
- [ ] Automatic per-series live-factor evaluation using held-out evidence,
  publication timing and explicit future assumptions: next major build.
- [ ] Sufficient client actual history, permitted commercial CPI capture, broader
  live-model/human workflow acceptance and secure deployment acceptance.

## 3 October — monthly Iran and regional live-data follow-up

- [x] Licensed provider-owned Hormuz AIS counts connected; six-hour checks,
  immutable selected-field capture/hash, no bundled IMF values retained/used,
  safe failures, partial-day/missing-month exclusion and stale-source warnings.
- [x] Actual capture: 166 complete days / five complete months. Reconstructed
  history, AIS omissions and regional-route relevance are explicit; insufficient
  history blocks linked forecasting, not silently filled.
- [x] Official IMF monthly Iran all-items CPI adapter, fixed measure/base/country,
  completed months, integrity-checked reviewed what-if link and admin permission
  gate. Research sample January–July 2026 checked; stale mirror not substituted.
- [ ] Written IMF commercial-use permission and real full-history/scheduled CPI
  acceptance. Connection remains disabled; administrator declaration is not a grant.
- [x] Monthly/relevant sources prioritized, annual data collapsed; centered source
  charts/access review, meaningful gaps, 1280px/390px coverage and no horizontal overflow.
- [x] 501 backend / 77 frontend tests and build pass; existing ten-month synthetic
  demand demo and six exports reconcile; no OpenAI call. REGIONAL_LIVE_FACTORS.md.
- [ ] Permitted longer regional shipping/trade series, scheduled location weather,
  prospective factor benefit, client history/quantity/order/export acceptance.
- [ ] Next major build: assistant-first order import and factor-scenario workflows.

## 3 October — assistant first-forecast delivery

- [x] Assistant starts without a forecast: add sales history through the existing
  reviewed import flow, choose saved sales inputs, inspect data and propose a
  customer-specific or all-customer forecast. No fake forecast values or task picker.
- [x] Supported mapping corrections save immutable input versions; Use these inputs
  continues in the assistant. Source choice/chat pointers survive reload, contain
  opaque IDs only and cannot silently follow another forecast/order/input version.
- [x] Exact customer names, readable individual model names, horizon/factor preflight,
  changed-file checks, actor ownership, expiry, and confirmation before calculation.
- [x] New forecasts can inspect compatible saved orders, preview consumption and
  propose a separate demand draft. Explicit full-month coverage confirmation is
  required server-side. Expired/newer orders and changed target evidence block saving.
- [x] Persian month labels in assistant/reuse tables; current orders consume only
  matching customer/SKU/month demand. No-order customers retain calculated demand.
- [x] Two live synthetic assistant requests: first forecast and order reuse, followed
  by separate draft save and dashboard. Run `df87c7ec00ae`; 20 rows / 10 months.
  Original orders unchanged; six CSV/Excel/JSON exports independently reconcile.
  11 provider calls, 17,354 reported input / 426 output tokens; no client data sent.
- [x] 489 backend / 73 frontend tests and build pass at this checkpoint. Desktop
  and small-screen acceptance recorded in ASSISTANT_ONBOARDING.md.
- [x] Source cooldown messages now include the actual retry time and retained failure;
  refresh is disabled during that interval. Old ready calculations collapse instead
  of occupying a full notification card indefinitely.
- [ ] Broader language/AI quality acceptance, approved cell-level data repairs,
  assistant-led first order-file import and factor-scenario creation.
- [ ] Remaining live monthly Iran/regional factor sources, client accuracy and
  operational delivery gates below. This checkpoint is not whole-product completion.

## 3 October — live external-factor connections

- [x] Direct World Bank commodity downloads (15 series), exact units and missing
  observations preserved, raw capture/hash retained; real download verified.
- [x] Existing GSCPI and Iran annual inflation fetched; bounded completed-year
  requests fix the World Bank date-range issue. Annual is not monthly inflation.
- [x] Opt-in persisted schedules, pause/resume, background fetch status, stale-data
  warnings, failure preservation, cooldown and interrupted-refresh recovery.
- [x] Data → Factors live-first; centered private key setup/details, secondary old
  file workflow; desktop and 390px list/modal checked.
- [x] Servix adapter with server-only macOS Keychain setup, rial quote validation,
  bounded history bootstrap, incremental overlap and durable daily quota.
  Security/reliability verified with mocks and an authorized real-source fetch.
- [x] Authenticated Servix catalog/history and actual Keychain save/read verified:
  666 quotes covering 3 October 2024–3 October 2026; automatic refresh enabled.
- [x] Existing secret files consolidated under ignored `secrets/`, directory 700,
  files 600; existing AI setup still loads. No key values printed or rotated.
- [ ] Servix quote-basis confirmation for the factory; complete day coverage and
  original historical release times are not inferred from the successful fetch.
- [ ] Iran industry API recovery; current failure explicitly visible.
- [ ] Monthly Iranian CPI, regional shipping/trade and scheduled location weather.
- [x] Live commodity/FX factors available as explicitly reviewed what-if scenarios:
  retained source integrity, lag/calendar alignment, Tehran future-capture cutoff,
  FX observed-day coverage, fixed factor-aware model, future assumptions, scopes,
  order reuse and clearly marked demand exports. Unsupported accuracy/ranges withheld
  before downloads are generated. 478 backend / 69 frontend tests and build pass.
- [ ] Original publication-time or prospective model-benefit validation. What-if
  scenarios are not validated accuracy evidence; annual macro figures remain context.
- [x] Full regression tests and frontend build; see LIVE_EXTERNAL_CONNECTIONS.md
  for the bounded acceptance and next substantial build.

## 23 September implementation checkpoint

3 October — AI provider controls:
- [x] Reused the official Agents/OpenAI SDK for configurable OpenAI or local
  OpenAI-compatible models; different settings for questions, review and decisions.
  Local mode requires explicit model IDs and a loopback endpoint. No cloud fallback.
- [x] Durable limits: 60 calls/workspace/day, 30/user/day, 6/request by default;
  100,000 UTF-8 input bytes/call and 2,500 output tokens. Limits are configurable
  within bounds. Failed/cancelled attempts remain counted across restarts.
  These are call/size safeguards, not a dollar cap; provider billing controls remain required.
- [x] Sharing permission identifies the provider and blocks changed destinations.
  Tracing/storage disabled, no automatic retries, proxies or redirects. No key
  is sent to local AI. Settings stay collapsed; no added assistant banners/pickers.
- [x] Mock transport verifies real SDK routing, strict structured outputs and a
  saved-demand tool call. No paid calls or client data were sent this checkpoint.
  Desktop/390px sharing dialog and mobile AI settings checked.
- [x] 450 backend / 68 frontend tests and production build pass. Existing build
  size and legacy resource/deprecation warnings remain; not whole-product acceptance.
- [ ] Installed local-model compatibility, hardware performance, licence/privacy
  approval and real provider quality/cost acceptance. No local model is installed
  or enabled by this build; existing OpenAI configuration is unchanged.
- [x] Assistant starts from reviewed sales inputs before a forecast exists, with
  mapping review → confirmed calculation → reviewed saved-order reuse → dashboard
  and reconciled exports. First order-file import and factors remain separate flows.

3 October — Iran sales onboarding (current build checkpoint):
- [x] Explicit Gregorian/Persian input dates and real planning-month boundaries;
  leap Esfand, Persian digits, Tehran day/month cutoffs, order matching, actual
  comparison and CSV/Excel/JSON labels/end dates tested. Persian/RTL interface not claimed.
- [x] Recorded sales / requested demand / shipped / invoiced meaning; reject,
  gross-exclude or period-net returns, source reconciliation and original evidence.
  Recognized client monthly totals cannot be converted into another calendar or
  daily/weekly figures. Requested versus promised order-date policy still needs input.
- [x] Persistent external customer IDs and reviewed aliases; conflicts roll back
  atomically. Opt-in exact matching for history/orders; no fuzzy or silent merging.
- [x] Saved-history Home entry, visible responsive factor actions, opt-in demo
  factors, collapsed public context and single demand-review approval entry.
- [x] Synthetic Persian run `422d36f6e1d2`: 10 months / 20 customer-SKU rows,
  mixed orders and three independently reconciled planning exports.
- [x] 439 backend / 66 frontend tests and production build pass. Selected 1280px
  and 390px demand/import/factor states checked; no whole-product acceptance inferred.
- [ ] Client-confirmed quantity/returns/units and order dates, longer actual history,
  archived orders/releases and real accuracy/range acceptance.
- [ ] Client-approved AI deployment and wider assistant actions. Local provider
  support and call/size safeguards are implemented above, not live deployment
  or billing acceptance. Live integration stays deferred.

3 October — market and workflow audit (current acceptance position):
- [x] Independent synthetic order/model/metric reconciliation and eight-view browser
  review; demo arithmetic verified, not client accuracy. See MARKET_AND_WORKFLOW_AUDIT.md.
- [x] Saved reviews now lists actual demand releases, stale/replaced state and
  approved downloads; demo separation and centered laptop/mobile review verified.
- [x] 426 backend / 62 frontend tests and build pass. No live integration or paid AI call.
- [x] Persian sales/order/export dates and digits; Tehran cutoffs. Follow-up build above.
- [ ] Optional Persian/RTL interface acceptance; English UI remains the current interface.
- [x] Sales-meaning controls, reviewed returns/corrections and customer aliases/IDs.
- [ ] Client-confirmed requested versus promised delivery-date policy and sales meaning.
- [x] Simpler returning-user entry/factor actions and single demand approval entry.
- [ ] Real-client history/order reconciliation, supported ranges and publication-time factor validation.
- [ ] Permitted Iran AI deployment path and wider assistant/action/cost acceptance.
  Live connectors remain deferred by user request. Earlier checked items are bounded
  foundations, not confirmation that these outstanding requirements are complete.

3 October — order-aware demand sign-off:
- [x] Fixed customer/SKU/month release with named receiver and order-consumption
  mode; existing calculation/exporter reused, delivered quantities excluded.
- [x] Independent company reviewer/admin gate; local sign-off stays explicitly
  demo-only. Source freshness/latest-version/closed-month guards, safe retry and
  approved-version replacement preserve originals; DEMAND_RELEASES.md.
- [x] Approved Excel/CSV/JSON with release, input/run hashes and approval provenance;
  shared-transaction order guards and reconciliation tests.
- [x] 426 backend / 61 frontend tests and build; desktop/390px synthetic submission,
  approval and reopening verified. No paid call or external transmission.
- [ ] Actual receiver/ERP reconciliation, transmission/acknowledgement/retraction,
  review-return workflow and live company-role/client acceptance.

3 October — reviewed factor export connections:
- [x] Approved local file, saved mapping, manual/scheduled staging, persistent
  connections and pause/resume; unchanged accepted bytes do not create versions.
- [x] Direct change review with before/after values and removed releases, explicit
  acceptance, immutable versions, stale/file-change guards and interrupted-save recovery.
- [x] Saved factor → preselected comparison inputs → reviewed draft job, real-engine
  historical comparison and Excel source alignment; originals/orders preserved.
- [x] 412 backend / 58 frontend tests and build pass. Browser desktop/390px
  refresh → changed-value review → save → draft → completed comparison verified.
  Synthetic result `0ea4a37ff8ef`; original baseline `0cfe066d816f` retained.
- [ ] Live client/provider connection and production acceptance. Scheduled checks
  never approve inputs or start calculations. See FACTOR_FOLDER_REFRESH.md.

3 October — Iran factor input conventions:
- [x] Persian calendar/digits with original period boundaries, gap/leap validation,
  explicit UTC/Tehran publication timing and original-value provenance.
- [x] FX market/quote basis, rial/toman and per-currency quantity normalization;
  inflation measure and CPI base-year controls, immutable definition/version guards.
- [x] Approved Persian-to-Gregorian forecast feature alignment, missing-month block,
  current imported freshness, real-engine matched comparison and exported source trail.
- [x] 401 backend / 58 frontend tests and build pass; desktop/390px synthetic import
  review checked. No live Iranian feed, paid call or original demo change.
- [x] Scheduled reviewed factor-file refresh; see FACTOR_FOLDER_REFRESH.md.
- [ ] Live factor API and real-client/provider acceptance; see IRAN_FACTOR_INPUTS.md.
  Client FX market not yet confirmed.

3 October — combined forecast factors:
- [x] One to eight monthly factors with separate lag/constant/monthly assumptions,
  shared customer/SKU scope and method selection; duplicate/missing-data gates.
- [x] Matched baseline/scenario historical accuracy, model-mix disclosure and Excel
  evidence. Real-engine calculations/source preservation tested; FACTOR_LINKS.md.
- [x] Compact centered factor modal and desktop/390px missing-data blocking checked.
  393 backend / 56 frontend tests and build pass; no new paid calls/packages.
- [ ] Verified Iranian CPI/FX acquisition, date/quote-unit normalization and refresh;
  broader combined/public-factor browser journey and real-client accuracy acceptance.

3 October — reusable order connections:
- [x] Compatible cross-forecast connection reuse, first reviewed order book on a new
  forecast, source provenance, concurrent source/target guards and exact retries.
- [x] Refresh → review → demand/save/export integration; 391 backend / 55 frontend
  tests and build pass. See ORDER_FOLDER_REFRESH.md.
- [ ] Live configured reuse/mobile journey and actual client export acceptance.

28 September — connected order exports:
- [x] Local full-order-book scheduled staging, saved mapping, immutable source reuse,
  changed-heading gate, explicit review and pause/resume; ORDER_FOLDER_REFRESH.md.
- [x] File refresh → mapped review → order-aware calculation → save/retry integration
  verified; 388 backend / 55 frontend tests and build pass.
- [ ] Complete configured-folder/mobile browser acceptance and actual client export
  reconciliation. Cross-run reuse implemented 3 October; ERP event connector pending.

27 September — substantive factor controls:
- [x] Reviewed folder refresh → validation → pinned draft-job dispatch, deduplicated requests; REFRESH_DRAFT_WORKFLOW.md.
- [x] Opt-in scheduled drafts after reviewed inputs; persistent outcomes, pause/resume,
  changed-data gates and deduplicated jobs. 384 backend / 55 frontend tests pass.
- [ ] Complete live folder-to-forecast UI acceptance, including scheduled draft control.
- [x] Combined scoped historical accuracy from matched held-out observations, saved evidence and workbook export; SCOPED_FACTOR_SCENARIOS.md.
- [ ] Portfolio uncertainty calibration for mixed scoped forecasts remains unavailable.
- [x] Exact customer/SKU output scope, immutable unaffected forecasts and reconciled CSV/Excel; SCOPED_FACTOR_SCENARIOS.md.
- [x] Validate combined historical accuracy for scoped scenarios (SCOPED_FACTOR_SCENARIOS.md).
  Mixed portfolio ranges remain withheld, not included in this checked item.
- [x] Per-month future factor assumptions, reviewed persistence and correct model-input transfer; MONTHLY_FACTOR_ASSUMPTIONS.md.
- [x] Apply linked factors selectively to customer/SKU series; delivered 27 September.

26 September — correction workflow (ORDER_CORRECTION_ACCEPTANCE.md):
- [x] Restore saved rows after an unsaved upload, block unread headings/incomplete mappings, and clear approval after edits.
- [x] Rejected corrections and customer-file replacement preserve originals; corrected retry is not duplicated.
- [ ] Complete small-screen error/re-upload acceptance and expired-order recovery.
- [x] Expired-order guidance and separate synthetic renewal verified; four JSON/CSV exports reconcile. Small-screen/re-upload acceptance remains open.
- [x] Bounded mobile upload/correction acceptance at 320px/390px; same-filename reselection and invalid-heading recovery verified. See ORDER_CORRECTION_ACCEPTANCE.md.

24 September — public data slice (EXTERNAL_DATA_SOURCES.md):
- [x] Benchmark Iranian and global sources; separate free/public access from commercial/AI permission.
- [x] GSCPI monthly context connector, original-response retention, immutable versions and attribution.
- [x] Validate schema, period/vintage dates, finite values, gaps, failure preservation and freshness.
- [x] Public-factor model comparison using explicitly accepted conservative vintage-month timing; tests/demo/export in PUBLIC_FACTOR_COMPARISON.md.
- [ ] Independently verify original public-source release dates; current timing remains an assumption.
- [x] Carry saved customer/order reviews into an order-aware factor comparison without re-entry or silent approval; ORDER_AWARE_SCENARIOS.md records tests/demo/export evidence.
- [x] Assistant can preview this comparison and save only after explicit approval; exact-scope, stale-version and retry tests plus a live synthetic demo passed. See ASSISTANT_SCENARIO_COMPARISON.md.
- [x] Bounded live assistant acceptance: customer lookup, horizon follow-up, ambiguous customer, clean-input review and unknown customer. Seven live requests; all three model roles; timing/usage recorded in ASSISTANT_ACCEPTANCE.md.
- [x] Proposal-stage forecast preflight and bounded model evidence. Missing-factor, warning and sanitized provider-recovery tests; 355 Python tests pass.
- [ ] Wider assistant acceptance: ambiguous scenarios, problematic input judgments, varied wording/languages, cost limits and production load.
- [x] New-horizon order reuse implemented: exact customer/SKU/unit matching, added/outside-period review, freshness preserved, explicit coverage approval and immutable retry-safe save. See ORDER_REUSE.md for automated evidence.
- [x] Live new-horizon reuse acceptance: approved synthetic ten-month calculation, centered desktop/mobile review, separate draft save, preserved Demo A filter and six reconciled exports. 365 Python / 45 JavaScript tests pass; see ORDER_REUSE.md.
- [x] Backend import-to-export acceptance: history, customers, mixed order states, dated factor scenario and exports through real route handlers; independent row-level order arithmetic. Fixed history identifier corruption. 369 Python / 45 JavaScript tests pass; see SALES_IMPORT_ACCEPTANCE.md.
- [ ] Complete click-by-click acceptance of that import journey at laptop/mobile widths, including correction and retry paths.
- [x] Visible history upload/mapping → calculation → order-file import/review → saved demand/export selection tested at laptop/mobile widths. Core customer/product mapping made visible; keyboard upload fixed; sample labeling and readable mobile export choices added. See IMPORT_UI_ACCEPTANCE.md.
- [ ] Remaining browser journey: dated-factor import/link/comparison, replacement customer files and broader correction/retry paths.
- [x] Dated-factor browser journey: three-step import, gap/revision review, incomplete-factor block, explicit future assumptions, separate scenario and order-aware draft/export reconciliation. Cleared assumptions when switching factors; collapsed unused commitments. 48 frontend tests/build pass; see FACTOR_UI_ACCEPTANCE.md.
- [ ] Next browser acceptance: replacement customer lists, duplicate/mismatched orders, corrected re-uploads and safe retries.
- [ ] Enable permission-cleared Iranian monthly CPI/FX connectors for the client's chosen market.


- [x] Saved-input assistant review: existing validation evidence, factor gaps and
  customer/SKU grouping checks; exact-column mapping proposals with before/after
  totals and warnings. Explicit approval creates an audited, idempotent child input
  version; source bytes, orders and forecasts remain unchanged. See ASSISTED_INPUT_REVIEW.md.
- [x] Input-review pass: 284 backend / 37 frontend tests and production build passed.
  Provider calls mocked/disabled; live AI quality is not established.
- [x] 24 September: first-upload mapping suggestions before any saved forecast,
  using the existing OpenAI SDK review model. Explicit sample-sharing consent,
  exact-column allowlist, before/after preview, draft-only approval, stale-response
  protection and manual fallback. No source cells, orders or runs are changed.
- [x] Shared manual/assisted save checks block mixed customer/SKU series; duplicate
  rows and unmapped identifiers require review. Warnings persist with saved inputs.
  298 backend / 40 frontend tests and build pass. Browser: synthetic first import
  saved, disabled-AI recovery, centered dialog and 390 px bounds checked.
- [ ] Live first-import AI judgment/latency/cost acceptance remains pending; the user's key is now configured and authenticated.
  Cell-level repairs and reversible transformations remain pending.
- [x] 24 September factor review/comparison: source import dates, historical blank
  counts/latest periods, provided versus filled future assumptions, declared
  location/unit, immutable without-factor comparison using the existing job/model
  stack, customer–SKU chart filtering and Excel evidence. See FACTOR_REVIEW.md.
- [x] Corrected holdout-factor leakage: test predictors now use last training-period
  values, not realized holdout values. Calendar retained; original release/revision
  dates remain unverified. Old-engine runs must be recalculated before comparison.
- [x] 307 backend / 42 frontend tests and build passed. Synthetic two-run numerical
  reconciliation, Excel export, browser confirmation/filtering and 390 px chart
  checked. Existing customer-order forecast retained unchanged.
- [x] 24 September: reusable dated factor imports, required unit/geography/source,
  separate period and publication dates, revision-aware cutoff preview, gaps and
  latest-period age, immutable reviewed versions and mapping reuse. Context-only;
  uploader dates are not verified release archives. See FACTOR_IMPORTS.md.
- [x] 315 backend / 42 frontend tests and production build pass. Synthetic import,
  cutoff date (original value rather than later revision), update mapping reuse,
  laptop alignment and 390 px layout checked in the browser.
- [x] Monthly factor link: explicit observation lag, historical values frozen at
  declared publication cutoff, previewed all-customer/SKU scope, blocked gaps/late
  releases, known future values versus explicit assumptions, separate model run,
  matched accuracy comparison and Excel source trail. See FACTOR_LINKS.md.
- [x] 322 backend / 43 frontend tests and build pass. Real model/API/export test;
  browser approval/queue/comparison, laptop and 390 px dialog checked. Synthetic
  factor worsened past error (12.51% → 13.11%); no improved-accuracy claim.
- [x] Selective customer/SKU factor links, per-month future curves and multiple
  linked-factor scenarios; delivered in the 27 September / 3 October checkpoints.
- [ ] Next: one approved public source adapter with documented release history,
  geographic coverage and source-specific freshness expectations.
- [x] Assistant continuity: actor-owned saved conversation, same forecast/order
  scope, bounded recent context for router and specialist, reload restore and New chat.
  Changed evidence blocks continuation; action expiry/consent remain enforced and
  confirmed action receipts persist. Existing SDK/journal reused; no live AI call.
- [x] Continuity regression: 274 backend / 36 frontend checks and build passed.
  Details, live-provider limits and the next input-review task: ASSISTANT_CONTINUITY.md.
- [x] Reviewed order revisions: retain the saved customer/order book, import changed
  lines or a full replacement, preview before/after, preserve old versions and source
  evidence. Cumulative line updates, cancellations and moved deliveries do not add
  orders twice; stale/concurrent saves are rejected. Details: ORDER_UPDATES.md.
- [x] Order-update verification: 264 backend / 32 frontend checks and production
  build passed. Sample import preview retained 8 orders/12 customer relationships
  and recalculated one changed line to 230 tonnes without rewriting the saved demo.
  Final build checked at 1280px and 390px: before/after fields readable, wide tables
  scroll within their container, no page overflow. Continue disabled during upload.
- [ ] Follow-on ingestion acceptance: source-specific IDs/status mapping, authenticated
  machine API, scheduled client-system refresh, corrections/returns and real-client
  reconciliation. Reviewed incremental files alone do not complete these items.
- [x] Continuation verification: 254 backend and 31 frontend checks passed;
  production build passed. Browser verified monthly/coverage views, no-order
  filtering, saved-view restoration, totals and 390px/laptop layouts. Live OpenAI
  execution and real-client acceptance were not performed.
- [x] Review-workspace continuation: customer × SKU × month grid with selectable
  quantity, matching review CSV and exact totals; coverage filter/table retains
  listed no-order customers and distinguishes stale, unknown and incomplete history.
- [x] User-owned saved filters/layouts pinned to a run and reviewed order snapshot;
  persisted in the existing sales database. Sample saved-view restore tested in UI.
- [x] Assistant job payload retains requested customer through retries; Open result
  selects that customer. Without reviewed orders the new run shows a clearly labelled
  customer-only model estimate, not an invented order-aware plan. Live AI still untested.
- [x] Local backup/restore regression now includes customer directory, sales inputs,
  saved views and AI journal. Off-device encryption/retention acceptance remains open.
- [x] Fixed populated customer-list and new-table empty-state rendering; added
  component-rendering tests alongside aggregation/coverage tests.
- [x] Focused clutter correction: remove assistant setup card, mode and source
  selectors; use current forecast/order context and automatic task routing.
  Provider readiness is checked only on send; explicit data consent remains.
- [x] Customers page: persistent independent directory, customer/product editing,
  inactive state, search, CSV/XLSX preview and atomic duplicate-safe import.
  Active links can be merged explicitly into a new real-data order review;
  existing saved snapshots and synthetic samples are not rewritten.
- [x] Compact forecast filters, bar/trend/table views, month/customer/SKU grouping,
  quantity sorting, clear filters and CSV of the filtered table. Unknowns remain
  unknown; planning exports remain separately labelled full-snapshot exports.
- [x] Help page with a short starting sequence and expandable explanations.
  Removed repeated instructional cards from Home. Uses existing UI libraries.
- [x] 250 backend and 24 frontend tests passed in this correction pass.
  Full AI-provider execution is still untested without a key; no live call made.
- [x] Forecast-first UX pass: Home with a clear start/resume action, separate sample
  exploration, four primary navigation destinations, chart/table switching,
  centered export dialog and model details separated from demand review. 21 JS
  checks/build passed; evidence and remaining UX work: WORKFLOW_UX_CHECKPOINT.md.
- [x] 245 Python / 16 JavaScript tests passed; frontend build and dependency check
  passed. No live OpenAI request; see release notes for remaining warnings.
- [x] Monthly customer/SKU/unit matching, full relationship-list input, partial
  orders, explicit complete commitments, fulfilled/cancelled quantities, unknown
  remainder, freshness gates and past-due export block (tests/test_sales_demand.py).
- [x] CSV/TSV/Excel/JSON customer/order/commitment import, positional column mapping,
  preview → meanings → demand review → immutable saved snapshot. Source cells/hashes.
- [x] Customer/SKU/month/unit filters, stacked demand chart, grouped/exact tables,
  source schedule and separate residual/combined CSV/Excel/JSON draft exports.
- [x] Supply navigation and production file prompt removed; legacy code/data retained.
- [x] Official OpenAI/Agents SDK installed. Configurable query/review/decision models,
  blank server key, disabled-by-default AI, explicit data-sharing consent.
- [x] Assistant page, local evidence tools, reviewed forecast/export proposals,
  existing calculation queue, actor-scoped expiring actions and bounded SDK turns.
- [x] No-key, routing, local evidence, consent, ownership and action tests use mocks;
  no live OpenAI call or fabricated reply. Real model access remains unverified.
- [x] Browser: synthetic run 431fed798551, 72 results, 8 order schedules, saved via
  the three-step review. Demand and disabled-AI screens checked at 1280 and 390 px.
- [ ] Key-enabled end-to-end AI quality/latency/cost/injection evaluation.
- [x] Customer-specific result navigation after an assistant-run forecast: queued
  job's Open result carries customer scope; verified in component/helper/action tests.
  Live provider-to-browser acceptance remains part of the key-enabled test above.
- [ ] Complete cell-repair preview, approved reversible fixes, scenario
  action tools and aggregate evidence for large runs. Bounded durable conversation
  history is implemented above; live-provider continuation acceptance remains open.
- [ ] Order-aware approval/publish integration and version-pinned expired snapshot
  replay. Current demand exports are drafts, not approved MRP publication.
- [ ] Incremental API/ERP adapters, cross-source deduplication, customer effective
  dates, Jalali/order-calendar handling, optional matching windows, client validation.
- [ ] Add new sales/AI databases to off-device recovery/retention acceptance.

The detailed boxes below remain open where their full scope exceeds this slice.
See SALES_DEMAND_RELEASE.md for setup, verified limits and remaining work.

## A. Requirements reset — completed documentation only

- [x] Define sales/demand forecasting as the sole product purpose.
- [x] Remove production, inventory, materials and purchasing planning from scope.
- [x] Specify confirmed orders, partial/complete commitments and forecast matching.
- [x] Specify pipelines, multi-view dashboard and action-capable assistant.
- [x] Specify AI approvals/privacy/evaluation and downstream no-double-count contract.
- [x] Preserve previous specification/checklist/plan under docs/archive/.
- [x] Mark old handoff and UX scope subordinate; preserve app/demo and source data.
- [ ] Confirm section 10 client decisions, especially order meanings and MRP mode.

## B. Reusable implemented foundations — do not rebuild indiscriminately

- [x] Client workbook audit, actual/plan separation, source hashes/cells and unit
  issues documented (CLIENT_WORKBOOK_FINDINGS.md). Only seven actual months.
- [x] Guided file preview/mapping, saved inputs and validation; repeat-input and
  source-role foundations. All-channel lifecycle acceptance remains open.
- [x] Scheduled reviewed local-folder ingestion (FOLDER_INPUTS.md), not ERP ingestion.
- [x] Statistical/ML library methods, manual selection, direct multi-step ML,
  same-window comparison and guarded blends (FORECAST_METHODS.md).
- [x] Later-period checks and empirical range foundation (PLANNING_RANGES.md);
  no real-client accuracy or coverage guarantee.
- [x] Explicit numeric factor assumptions/scenario comparison (FACTOR_SCENARIOS.md).
- [x] World Bank macro and NASA historical-weather context snapshots; not proven
  automated forecast drivers (WEATHER_CONNECTOR.md).
- [x] Forecast chart/table, exports, immutable reviewed plan versions and actuals
  comparison foundations (PLAN_STORAGE.md, ACTUAL_RESULTS.md).
- [x] React/Radix/Phosphor UI and bounded responsive/accessibility checks (UX_REBUILD.md).
- [x] Local persistent jobs, OIDC/role foundations and offline recovery
  (BACKGROUND_JOBS.md, ACCESS_CONTROL.md, WORKSPACE_RECOVERY.md).
- [x] Last demo checkpoint: 222 Python and 16 JavaScript tests; frontend build passed
  on 21 September. Not rerun for this documentation-only scope change.
- [ ] Revalidate reusable pieces against the sales-only workflow and new contracts.

## C. First release priority — orders plus forecast

- [ ] Define canonical history/order/customer/SKU/unit/calendar schemas and target.
- [ ] Import the full eligible customer master/list, not just customers with orders;
  preserve status/effective dates and valid customer–SKU relationships.
- [ ] Mix ordered and forecast demand per customer/SKU/period in the same run;
  customer with no order is retained, not assumed to have zero demand.
- [ ] Import confirmed customer sales orders, distinct from purchase receipts,
  customer forecasts, quotes and production orders.
- [ ] Preview mapping/status meanings and review source totals with client evidence.
- [ ] Persist source line/schedule IDs, snapshots, revisions, fulfillment and cancellations.
- [ ] Make imports/update/delete events idempotent; detect cross-source duplicates.
- [ ] Implement exact-scope matching and versioned optional consumption windows.
- [ ] Implement partial coverage versus explicitly complete commitments and expiry.
- [ ] Maintain baseline, confirmed orders, remaining expectation and final plan layers.
- [ ] Respect confirmed-order minimums; surface conflicts rather than silently trimming.
- [ ] Handle current-period fulfilled/open/remaining quantities and past-due orders.
- [ ] Treat missing/stale order sources as unknown rather than zero.
- [ ] Support no-order forecasting and unknown-remainder results with limited history.
- [ ] Freeze matching/input/assumption versions for reproducible review and export.

Required numerical acceptance cases:
- [x] F=10, confirmed O=16, same stream → total 16, not 26.
- [x] F=10, partial O=6 → booked 6 + expected 4 = total 10.
- [x] F=10, explicitly complete O=6 → total 6, original baseline retained.
- [x] Fresh order source with no orders → statistical estimate; stale source warns/blocks policy.
- [x] F unavailable, O=16 partial → 16 known, unknown additional demand disclosed.
- [x] F=10, fulfilled=3, open=5 → remaining expectation 2, still-to-serve 7.
- [ ] Duplicate file/event leaves quantities unchanged; partial cancellation revises
  the matching once; changed delivery dates reallocate without duplicate demand.
- [x] A: F10/O16; B: F8/O0; C: F5/O3 partial → 19 booked + 10 expected = 29;
  reject aggregate-max shortcut (23) and cross-customer consumption.
- [ ] No-order customer with insufficient history remains visible/flagged; explicit
  analog/manual policy, never invented zero or automatic all-SKU expansion.
- [ ] Two customers, split schedules, different units and backlog never consume
  another scope silently; unmatched/ambiguous records require review.
- [ ] Complete commitment below actual booked orders produces a review conflict.
- [ ] Approved additive one-off is distinct from ordinary matched demand.
- [ ] Manual adjustments do not silently edit or reduce confirmed order commitments.

## D. Data pipelines and AI-assisted quality

- [ ] Sales-only imports run without production/BOM/stock files.
- [ ] Reusable mappings, stable identifiers, unit aliases, mixed-calendar validation.
- [ ] Draft recovery, replacement-file remapping, failure/retry and session-expiry UX.
- [ ] Authenticated inbound/outbound API with schema versioning and incremental sync.
- [ ] Select first real connector from client systems; test actual ingestion,
  updates/deletes, rate limits, secrets, licences and freshness (not connectivity only).
- [ ] Evaluate Odoo/ERPNext/SAP/Dynamics/CRM candidates; do not promise all at launch.
- [ ] Preserve raw data and change log; reconcile source counts/quantities after imports.
- [ ] AI suggests mappings/repairs with evidence, confidence and before/after review.
- [ ] Approved repairs are reversible; uncertain IDs, amounts and dates never auto-fixed.
- [ ] Validate private-data permissions, malicious imported instructions and AI outages.

## E. Models, factors and performance

- [ ] Preserve selectable mathematical/ML methods and meaningful eligibility messages.
- [ ] AI recommendations use recorded numerical comparisons and approved policy.
- [ ] Backtest archived order books and factor vintages as known at each cutoff.
- [ ] Compare model-only, order-aware and reviewed plans at the same target/horizon.
- [ ] Customer/SKU/product-family reconciliation preserves fixed order commitments.
- [ ] Separate sparse/new-customer/new-product treatment from invented detailed history.
- [ ] Govern returns, stockout/lost-demand corrections and closed-period revisions.
- [ ] Seasonal calendar and cycle choices; clear short-history limitations.
- [x] Explicit Iran FX/rial-toman, inflation measure/base-year, calendar and release
  timezone controls with future assumptions; IRAN_FACTOR_INPUTS.md.
- [ ] Client-approved FX market/source and independently verified publication history.
- [ ] Relevant internal price/promotion/customer events and global supply/disruption inputs.
- [ ] Factor inclusion passes relevance, availability and improvement checks.
- [ ] Validate ranges for uncertain remainder and coherent aggregation on real-site data.
- [ ] Accuracy/bias/coverage by customer, SKU, horizon and unit; zero-demand handling.
- [ ] Versioned drift/retraining recommendations and controlled model promotion.
- [ ] Extensions: analogs, promotions/substitutions, order-arrival sensing and CRM scenarios
  only after core evidence and without double counting converted opportunities.

## F. Forecast-first UI and visual reporting

- [ ] Design/validate Overview, Forecast, Data, Assistant and secondary Settings.
- [ ] Remove Supply/material/capacity destinations from the sales workflow without
  deleting historical records or breaking existing saved runs.
- [ ] Filter/save views by SKU, customer, family, market, period, scenario and version.
- [ ] Customer × SKU × month pivot, exact table, history/forecast and booked/remaining charts.
- [ ] Customer coverage view shows no-order, partial, complete, stale/unknown and
  insufficient-history states; filters do not silently omit uncovered customers.
- [ ] Demand changes, contribution, exceptions and accuracy views answer clear questions.
- [ ] Every view/export agrees on scope, units, quantities, as-of date and target.
- [ ] Inspect any quantity's orders, matching, baseline, assumptions and changes.
- [ ] Separate estimated demand and constrained shipment views; do not imply supply feasibility.
- [ ] Short review/override/approval flow; preserve baseline and immutable published versions.
- [ ] Keyboard/screen reader, 1440/1280/1024/768/390 layouts, readable labels/help,
  empty/error/stale states; no modal navigation or duplicate/decorative elements.
- [ ] English/Persian, RTL, Jalali/Gregorian and Tehran date boundaries.

## G. Agentic assistant — partial implementation; live acceptance open

- [ ] Dedicated chat page with visible actions, job status and linked result views.
- [ ] "Forecast Customer A for the next 10 months" resolves identity, checks data,
  runs the normal service and opens the correct filtered result for review.
- [ ] Run method/scenario comparisons, suggest fixes and prepare exports through typed tools.
- [ ] Results and explanations cite saved data/run/assumption versions; no invented quantities.
- [ ] Respect company/role permissions, independent approval and order constraints.
- [ ] Confirm material edits, publication, external sends and new automation.
- [ ] Cancel/retry safely, enforce cost/time limits and communicate partial failures.
- [ ] Evaluate ambiguous names, missing history, bad tools, injection, unauthorized
  actions and reproducibility. Existing deterministic helpers do not satisfy this.
- [ ] Evaluate provider/local-model options with privacy, licence and hosting cost review.

## H. Publish and hand off to existing planning/MRP

- [ ] CSV/XLSX/JSON/API outputs with saved customer/SKU/period templates.
- [ ] PDF/print summary uses exactly the same selected results and labels.
- [ ] Output baseline, booked, matched, remaining, adjusted total and applicable ranges.
- [ ] Include identifiers, units, target/date basis, as-of, version, approval and provenance.
- [ ] Test residual-only mode for receiver already containing sales orders.
- [ ] Test combined-demand mode for receiver explicitly expecting combined quantities.
- [ ] Receiver reconciliation proves orders are not counted twice.
- [ ] Dry-run preview, role-gated publication, idempotent send, acknowledgement,
  failed-delivery retry, replacement/retraction and audit history.
- [ ] No purchasing, inventory, production or customer-order execution tools.

## I. Automation, deployment and client acceptance

- [ ] Configure refresh → checks → draft forecast → exception review → approved
  export; explicit opt-in, owners, failure notifications and pause controls.
- [ ] Establish measured targets for planner effort, freshness, forecast error and
  export acceptance with the client; no invented success percentages.
- [ ] Real identity-provider/HTTPS/tenant isolation and concurrent role acceptance.
- [ ] Database migrations, retention, encrypted off-device restore, load/recovery tests.
- [ ] Client pilot using real orders and longer history; compare later actual results.
- [ ] Full regression on preserved demo and no-order/short-history paths.
- [ ] Sign off on scope, numerical reconciliation, UX and downstream handoff.

## Removed from active delivery scope

Production scheduling/capacity, BOM/material requirements, purchase receipts,
inventory outlook, safety stock, replenishment and warehouse flows are NOT remaining
deliverables. Their existing implementation/evidence is retained for preservation,
not represented as progress toward the new scope. Do not continue those phases.

Completion rule: mark each new item only after implementation and appropriate
verification. A requirements document, successful AI response, passing legacy suite
or synthetic accuracy result does not prove operational readiness.

## Chat layout delivery — 7 October 2026

- [x] Centred new-chat composer, one heading and three clickable examples.
- [x] One + menu for existing data/tools; removed separate attachment/source controls.
- [x] Docked composer with independently scrolling messages; pending state and draft-preserving retry.
- [x] Enter sends; Shift+Enter adds a line; input-method composition does not send.
- [x] New chat resets messages, not saved forecasts; existing history/action review preserved.
- [x] Chat/menu appearance has one global owner, semantic tokens and no authored inline styles.
- [x] English/Persian/RTL; no copied voice/plugin/model controls.
- [x] Shared Radix dependencies aligned; data dialog closes without leaving clicks blocked.
- [x] Production build and 178 frontend tests pass. Browser checks use an isolated synthetic
  fixture for sends, long replies, retry, New chat and tools; no paid provider calls.

This completes the requested chat layout, not full production or model-engine acceptance.

### Conversation appearance correction — 7 October 2026

- [x] Shared message component for saved/new/pending messages; distinct avatars.
- [x] Dark user bubble on the end side; white assistant bubble on the start side.
- [x] Both sides mirror in RTL; message text determines its own reading direction.
- [x] Mobile wrapping, consistent padding/radii and visible background contrast.
- [x] 179 frontend tests pass; synthetic conversation checked at desktop and 390px mobile.
  No AI calls or forecasting calculations performed for visual testing.
  Evidence: `screenshots/chat-two-sided-desktop-synthetic.png` and
  `screenshots/chat-two-sided-mobile-rtl-synthetic.png`.

### Cartoon assistant avatar — 8 October 2026

- [x] Original green felt cartoon companion generated with built-in imagegen after
  reviewing Dots and Muse references; human portrait and lynx concepts rejected.
- [x] Shared saved/new/pending assistant avatar, global 44px token, no inline styles.
- [x] Production asset serves successfully; build and all 179 frontend tests pass.
- [x] Character loads at its actual chat size in an isolated synthetic conversation;
  no paid AI calls. Evidence: `screenshots/chat-cartoon-mascot-synthetic.png`.

Avatar refinement: replaced the felt rendering with `assistant-mascot-simple.png`:
flat green silhouette, curved eyes and smile, no fur or realistic detail. Shared
styles unchanged. Production build and 26 focused chat/framework tests pass.

### Smooth animated character — 8 October 2026

- [x] Native vector character retains the green curled silhouette and waving pose.
- [x] Curved eyes continuously morph to circles; blink, glances, hand waves and breathing
  use eased movement with calm holds, not frame/state swaps.
- [x] Light rounded shading, no fur texture or white disk; shared global tokens/styles.
- [x] Reduced-motion still version; offscreen/hidden-page animation pauses.
- [x] 182 frontend tests and production build pass. Actual browser halfway eye path
  and hand rotation verified; isolated synthetic test, no paid AI calls.
  Evidence: `screenshots/chat-mascot-mid-morph-synthetic.png`.

### Collapsible navigation and previous chats — 8 October 2026

- [x] Expand/collapse main sidebar; icons only when collapsed, accessible tooltips,
  active-page indication and remembered preference.
- [x] Separate conversation history column with New chat and newest-first titles.
- [x] Restore complete conversations and their original forecast/data/order context;
  starting a new chat never deletes history.
- [x] Migrate existing journal in place; per-user privacy, pagination and expiry checks.
- [x] Responsive full-width history view; English/Persian interface and RTL layout.
- [x] Shared global tokens/styles; production build, 187 frontend and 30 focused
  backend tests pass. Synthetic interactions and actual saved-chat reopening checked.
  Details: `CHAT_HISTORY_DELIVERY.md`.

### New-chat greeting refinement — 8 October 2026

- [x] Removed the redundant DemandLab/Help footer; Help remains in navigation.
- [x] Reused the animated character peeking over the greeting corner, without a
  background disk or extra text; mirrored placement in Persian.
- [x] Global tokens and component styles only. 188 frontend tests and production
  build pass; running app checked at desktop and 390px mobile width, no overflow.
  Evidence: `screenshots/new-chat-character-greeting.png`.

### Independent character motion — 8 October 2026

- [x] Shared 1.2 speed multiplier; smooth, staggered cycles for breathing, eyes,
  blinking, glances, left/right hands, head curl and mouth.
- [x] Per-instance phase variation; connected silhouette, reduced-motion fallback
  and offscreen pausing retained. No inline styles or new dependencies.
- [x] 191 frontend tests and production build pass. Live browser timings, morph
  interpolation and independent hand rotations checked without AI calls.

### Forecast creation modal — 9 October 2026

- [x] One manual New forecast button, on Forecast only; removed global, data-library,
  help and assistant-menu creation buttons. Plain-language assistant actions remain.
- [x] Centered shared dialog contains sales history, factors, customers/orders,
  methods and results; no separate creation page or new page-specific styles.
- [x] Unfinished setup survives closing; focus returns to the launch button;
  submission/open-result requests guard dismissal; results open back on Forecast.
- [x] Legacy #new links open the same dialog over Forecast. Hash navigation remains.
- [x] 206 frontend tests and production build pass. Browser checked at 1280px and
  390px: centered dialog, import within the dialog, no horizontal overflow,
  saved selection restored after reopening. No calculations or provider calls.
  Evidence: `screenshots/new-forecast-modal.png`.

### Clean page addresses — 9 October 2026

- [x] Pages use /today, /demand, /data, /customers, /settings, /plans, /help and
  /forecast instead of hash routes. Existing hash bookmarks migrate on opening.
- [x] Browser back/forward and direct page refresh work; New forecast stays a modal
  on /demand. Sidebar links and sign-in redirect use clean paths.
- [x] Server serves the current interface at explicit page routes only; missing APIs,
  assets and unknown page paths still return 404. Access checks are unchanged.
- [x] 210 frontend tests, 17 routing/access tests and production build pass.
  Running server restarted; /demand direct load, refresh, navigation, back/forward
  and modal checked in the browser. No forecasts or provider calls made.

### Consolidated inputs and method comparison — 9 October 2026

- [x] Data owns sales history, customers, orders, factors and connections; removed sample filters/badges and redundant storage/format copy.
- [x] Customer directory and reusable orders feed the same forecast wizard, with one review gate and optional order import.
- [x] Fixed-width/height forecast modal, internally scrolling content, scoped transitions and no nested calculation overlay.
- [x] Horizon/calendar settings edited inline; immutable source versions preserve original sales and order lineage.
- [x] One named multi-method forecast in the picker; method selection, filtered overlay chart/table and comparison CSV.
- [x] Rename chat; cheap background title role, manual-name protection, ownership/consent/budget checks.
- [x] 215 frontend and 52 backend tests, build and browser checks passed. AI provider calls mocked; no paid call made.
- [x] Full batch verification and boundaries recorded in `WORKFLOW_REFINEMENT.md`.

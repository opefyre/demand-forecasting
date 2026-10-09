# DemandLab — sales and demand forecasting requirements

Revision: 22 September 2026 — user-directed scope reset.
Status: implementation authorized 23 September 2026. First order-aware slice and
OpenAI orchestration implemented; not full production acceptance. See checklist.
This document supersedes the former operations-planning scope. The app and saved
demo still contain legacy features. Requirements are not claims of availability.
Implementation status lives in IMPLEMENTATION_CHECKLIST.md; delivery order in
DELIVERY_PLAN.md. Earlier versions are preserved under docs/archive/.

7 October interface revision: Home is the assistant, not a separate dashboard.
The primary action is New forecast: sales data → factors → one/multiple methods
→ results. All current app pages share one shell and centralized design tokens.
Settings are grouped by task; demand-export review is named Approvals.
Direct live-factor selection, future-assumption review and multiple-model results
are implemented in that journey. Model results are immediately visible, with
customer/SKU/month filters shared by chart, table and CSV; current orders are a
subsequent explicit review. Settings now uses shared framework components for its
panels, typography, forms, lists and actions. Remaining legacy page-specific layouts
still need migration; value tokenization alone is not acceptance of visual consistency.
See INTERFACE_REBUILD.md for evidence and the remaining client/deployment gates.
The older interface notes below are historical, not the current release status.

7 October recovery note: failed demand reads do not imply an empty order book;
read-only recovery now covers demand, order-import schema, monthly updates and
saved source information. Structured bilingual guidance retains source evidence,
permissions and explicit write confirmation; no automatic write retry. Combined
end-to-end acceptance and broader UX remain open; see SALES_RECOVERY_DELIVERY.md.

7 October advanced-interface note: assistant, factor preparation/review/batches,
live-source status, saved reviews and auth/AI-setting labels now have Persian
controls. Role, expiry, consent and freshness gates are preserved. Deep forms,
structured errors and full bilingual acceptance remain incomplete; see
BILINGUAL_WORKFLOW_DELIVERY.md. Next major delivery is guided exception handling
and full bilingual sales-journey acceptance, not additional planning modules.

7 October interface note: persisted English/Persian choice and RTL layouts use
the same sales workflow. Core sales screens and Persian help are delivered;
advanced factor/assistant/admin and structured-error translation remain open.
Language cannot change calendar choice, customer/SKU identity, quantities or
export contracts. Evidence and remaining scope: PERSIAN_INTERFACE_DELIVERY.md.

7 October sales-input note: users can choose a separate forecast for every
customer/product pair using ordinary mapped columns, without a composite ID.
Stable keys preserve identifiers and are used consistently by factors, orders,
calculations and exports. Existing group-column datasets remain compatible;
ambiguous mappings are blocked. Evidence: SALES_JOURNEY_ACCEPTANCE.md.

7 October release note: all current schedules pause on restore; stopped/missing
monthly calculations remain reviewable without duplicate work. The isolated
120-series/24,000-order and Persian-month pilots reconcile numerical forecasts,
partial orders, six exports and restored business records. This verifies synthetic
local workflow correctness, not client accuracy or company deployment. Details and
remaining gates: RELEASE_PILOT.md.

7 October implementation note: factor scenarios now suggest existing live sources
from declared currency/supply/route/material exposure, check historical coverage and
freshness, and prepare reviewed inputs. No inferred exposure, fabricated future values
or silent approvals. Shared customer/product profiles and assistant-led source-review
handoffs are now implemented; product overrides replace customer defaults and apply
only to exact customer/product/unit matches. Monthly multi-profile batches now reuse
separate existing calculations, combine disjoint groups and preserve unselected
products. Current orders remain a subsequent explicit review. Combined results do
not inherit unsupported global accuracy/range claims. Assistant-led multi-customer
batch preparation, explicit confirmation, calculation progress and demand-result
handoff are now implemented. Missing details open a restricted review workflow;
complete proposals require explicit values and connected, permitted, current sources.
See SOURCE_PREPARATION_DELIVERY.md, FACTOR_PROFILES_DELIVERY.md,
FACTOR_BATCH_DELIVERY.md and ASSISTANT_FACTOR_BATCH_DELIVERY.md for boundaries.
Recurring monthly baseline drafts now reuse reviewed sales versions and the normal
review journey, with Tehran/Persian/Gregorian timing and administrator confirmation.
Missing latest-month records and unreviewed connection inputs stop calculation.
Future factors/orders still require review; no automatic approved publication.
See RECURRING_FORECAST_DELIVERY.md; local execution needs the server running.

## 1. One purpose and boundary

Automate the sales/demand forecasting part of the client's S&OP process:
combine known customer demand with an evidence-based estimate of demand still
to come, review exceptions, and publish a usable demand plan.

**History + current orders + relevant factors → forecast → review → export.**

Users: sales and demand planners, account managers, managers and leadership.
Initial client: a Tehran factory; the product must remain reusable across industries.

In scope:
- Sales/demand inputs, order-book awareness, forecasting, scenarios, quality checks.
- Demand review/approval, customer collaboration, dashboards, assistant workflows.
- Demand exports and approved handoff to existing production-planning/MRP systems.

Out of scope:
- Production scheduling, machine/line planning, BOM explosion, material requirements.
- Inventory management/projection, purchasing, replenishment, safety stock,
  warehouse transfers and supplier-order management.
- Executing production, procurement or customer sales orders.
- Replacing the full cross-functional S&OP process or guaranteeing achievable supply.

Stockout, availability, lead-time or disruption information may explain observed
sales or support a demand scenario. It is an optional INPUT, never an obligation
to build the corresponding operational module. Separate estimated customer demand
from a constrained shipment/sales outlook; label the target and date meaning.
Do not reduce estimated demand merely because the factory lacks capacity.

## 2. Core quantities — orders first, forecast the unknown

Keep these visible, separate and reproducible:
1. Historical actuals: what really occurred, with returns/corrections identified.
2. Model baseline: expected demand before combining it with current commitments.
3. Confirmed customer orders: known demand, not a guess.
4. Remaining expected demand: estimated demand not already covered by orders.
5. Reviewed demand plan: confirmed orders plus remaining expectation, with a
   separately recorded adjustment layer and approval/version history.

A confirmed order is authoritative for its own line and delivery period. It does
not prove that the entire customer/SKU/month order book is complete. Explicitly
distinguish a partial order book, a complete customer commitment and no orders.

### 2.1 Order matching and calculation policy

Define a versioned policy at company/customer/segment level, overridable only
with permission and a reason. Match company, SKU, customer, unit and demand period;
include ship-to/channel when required. Do not let one customer's order consume
another customer's forecast silently. Anonymous or unmatched orders require review.
Split scheduled deliveries across their actual dates. Default to exact-period
matching; any backward/forward matching window must be explicit and auditable.

For a wholly future bucket, where orders represent part of the same demand stream:
- F = model baseline for that customer/SKU/period.
- O = eligible confirmed, outstanding order quantity for that scope.
- Matched amount = the part of O covering F, never more than either quantity.
- Remaining expected demand = max(0, F − matched amount).
- Total expected demand = O + remaining expected demand.
- With complete matching in one bucket, this equals max(F, O), NOT F + O.
  This shortcut is not universal across customers, periods or demand streams.

When the customer explicitly confirms its COMPLETE quantity for that bucket,
use that quantity, even if below the historical baseline; remaining expectation
is zero for that scope. A smaller partial order does not mean demand is complete.
Completion must have an owner, evidence, scope, timestamp and expiry/review rule.
If orders exceed that complete commitment, show a conflict for review; do not
discard an order or publish an unexplained total.

| Model estimate | Current confirmed orders | Coverage | Planned demand |
|---|---|---|---|
| 10 tonnes | 16 tonnes | Partial, same demand stream | 16, not 26 |
| 10 tonnes | 6 tonnes | Partial | 6 booked + 4 expected = 10 |
| 10 tonnes | 6 tonnes | Explicitly complete | 6, with the 10 baseline retained |
| 10 tonnes | None | Fresh source, no orders | 10 estimated |
| Unavailable | 16 tonnes | Partial | At least 16 known; unknown remainder flagged |

These are proposed business defaults requiring client confirmation before coding.
Clearly additional one-off orders may sit outside the baseline, but only through
an explicit reviewed classification. No blanket additive rule. Lowering the model
estimate never lowers a valid confirmed commitment. Planner edits act on the
remaining expectation; order corrections follow the source/order-review process.

### 2.2 Customer coverage — mixed orders and estimates in the same run

This is NOT an all-orders versus all-forecast switch. Maintain an explicit customer
master/list, including active customers with no current orders, customer aliases,
account owner, status/effective dates and eligible customer–SKU relationships.
Do not generate the customer list solely from this month's orders, or silently
drop customers with no orders. Do not forecast every SKU for every customer.

Calculate each customer × SKU × period separately, then reconcile the totals.
Coverage/completeness decisions apply only to their exact customer/SKU/period,
not the entire SKU or company. An order for Customer A cannot erase Customer B's
forecast merely because it exceeds the aggregate SKU forecast.

Example for ONE SKU and ONE month:
- Customer A: baseline 10, confirmed orders 16 → 16 booked, 0 remaining.
- Customer B: baseline 8, fresh order source with none → 0 booked, 8 expected.
- Customer C: baseline 5, partial orders 3 → 3 booked, 2 expected.
- Total: 19 booked + 10 expected = 29 tonnes.
- Applying max(total baseline 23, total orders 19) would give 23 and is WRONG:
  consumption must happen at the matched customer level before aggregation.

A customer with neither orders nor enough history remains visible as insufficient
evidence; use a reviewed analog/pooled estimate or a documented manual assumption,
not a fabricated zero. Dormant/discontinued customers and new customers need
explicit inclusion policy. Missing customer assignments are shown as unallocated
demand requiring review, not silently spread across named customers.
Expose no-order, partially booked, fully committed, stale/unknown and insufficient-
history states in a customer coverage view. "No orders" is not "no demand".

### 2.3 Order lifecycle and as-of date

Required source semantics:
- Stable source/order/line/schedule identifiers, customer, SKU, unit, status.
- Ordered, cancelled, fulfilled and outstanding quantities with source definitions.
- Booking date, requested demand/delivery date, promised date where available.
- Source modification time, ingestion time and historical snapshot/as-of time.
- Do not treat quotes, opportunities, blanket contract ceilings, cancelled lines
  or duplicate snapshots as confirmed orders. Released contract schedules may count.
- Preserve date revisions, partial deliveries, cancellations and corrections;
  re-importing the same line must not add it twice. Unknown statuses are quarantined.
- Backlog remains visible with original dates; move it only under a documented
  policy. A promised delay must not silently move customer-requested demand.
- Missing/stale order feed means "orders unknown", not zero orders.

For a current partial period, distinguish fulfilled-to-date, open commitments and
remaining expectation. Fulfilled quantities must not reappear in an outstanding
MRP handoff. Illustratively, baseline 10, fulfilled 3, open orders 5 leaves 2
expected: full-period demand 10, still-to-serve 7. Matching must prove these are
the same demand stream; imports must not count both shipment and invoice as sales.
Cancellation or date movement releases/reallocates matched expectation according
to the same policy. Audit each quantity back to its source and matching decision.

## 3. Data inputs and pipelines

### Required to calculate a statistical forecast
- Historical date, SKU, quantity and unit; customer for customer-level forecasting.
- Agreed target: orders requested, shipped sales, or invoiced sales; distinguish
  gross demand and returns. Currency/revenue must not replace physical quantities.
- Complete eligible customer list, including customers with no current orders;
  product/customer identifiers, aliases, relationships, status and effective dates.
- Horizon, daily/weekly/monthly period, calendar and data-as-of cutoff.

Confirmed 3 October: support both Persian and Gregorian planning months, with
actual month boundaries rather than label conversion. Date format in each sales,
order, factor and actual-results file is explicit and separate from the planning
calendar. Dated transactions can be regrouped; monthly totals cannot be reliably
split across another calendar or into finer daily/weekly periods. The recognized
client sales workbook is Gregorian monthly totals. Its “actuals” label does not
prove requested demand, shipments or invoicing; default to recorded sales with
meaning unconfirmed until source evidence establishes the target. Keep explicit,
reviewed gross/net returns treatment and the original source unchanged.

Monthly updates must be a recoverable guided journey from reviewed history to
calculation, optional factor comparison, current orders, changes and exports.
Reuse existing services; no parallel calculation path hidden in uploads. Saved
progress does not imply approval. Compare exact overlapping customer/product/month
rows and show added/removed periods separately. Every final download rechecks
current orders, expiry and the exact reviewed report. Connected source status
must never imply that a factor was used or improved accuracy.

### Required for an order-aware plan
- Fresh reviewed open sales order lines/schedules and coverage policy from section 2.
- Archived order snapshots for honest testing of order-aware improvements.
- Customer commitments/forecasts as a separate source, never silently treated as
  actuals or confirmed orders.

### Optional explanatory inputs
- Prices, promotions, contracts, customer forecasts, sales opportunities, lifecycle.
- Stockouts/unfulfilled demand evidence, outages and sales restrictions.
- Holiday/working-day effects; inflation, FX, commodity prices, freight, global
  supply disruptions and relevant sector/customer-market indicators.
- Future factor values or explicitly named assumptions. Never silently extend them.

### Ingestion channels
- Guided XLSX/CSV/TSV/JSON import with preview, mappings, issue resolution and recovery.
- Reusable mapping templates, scheduled file/folder refresh and incremental updates.
- Versioned inbound/outbound REST API; webhooks where source systems support them.
- Read-only database ingestion with least privilege.
- Built-in connectors prioritized by actual client systems. Candidates for evaluation:
  Odoo, ERPNext, SAP, Microsoft Dynamics, Salesforce and HubSpot. These are NOT
  implemented connectors or promises of free access; ERP and CRM play different roles.
- Authenticate, scope, paginate, retry safely, handle updates/deletions, log source
  freshness and failures, and retain raw + normalized snapshots and mapping versions.
- Private data is not sent to external AI without approved provider/data-sharing policy.

AI can suggest columns, aliases, duplicates and repairs. Deterministic rules enforce
dates, types, quantities, units and totals. Show proposed before/after changes and
reasons; financial/quantity/customer identity changes require human approval.
Keep original data unchanged, make transformations reversible, and report uncertain
matches. A general forecasting run should not require production or inventory tables.

First-import implementation boundary (24 September): optional consented AI column
suggestions, exact-field/column checks, before/after preview and explicit draft
application are implemented. Manual and assisted imports share save validation;
source cells stay unchanged. Live AI judgment and reversible cell repairs are not
yet accepted. See ASSISTED_INPUT_REVIEW.md for evidence and limits.

## 4. Forecast engine, model choice and validation

Reuse maintained open-source statistical/ML packages first. Existing StatsForecast,
scikit-learn, LightGBM, calendar and unit foundations should be retained where fit.
Build only the product-specific orchestration and business policy that reuse cannot
provide. Record licensing, deployment cost, maintenance and benchmarks.

24 September boundary: comparisons can remove extra factors while preserving sales
history/calendar, forecast periods and the selected method policy. Original runs and
orders remain unchanged. Historical factor tests use last-training-period values;
they do not consume realized holdout-period factor values. Uploaded release dates
and revisions are not verified, so this is not certified point-in-time replay.
See FACTOR_REVIEW.md. Public annual country data is not silently converted into a
monthly Tehran feed. More factors are not assumed to mean better accuracy.

Method families:
- Last observation, seasonal repeat, moving/weighted average benchmarks.
- Holt/Holt-Winters, ETS, Theta, ARIMA/seasonal ARIMA.
- Croston/SBA/TSB for intermittent demand.
- Regression/Ridge/Elastic Net and tree-based ML with approved drivers.
- Multiple-seasonality methods where the data supports them.
- Blends only when tests show improvement over their best eligible member.
- New-product analogs, promotion/substitution effects and pooled sparse-customer
  models as evidence-gated extensions. Deep learning is not a default requirement.

AI may recommend a candidate set, invoke comparisons and explain results. Numerical
tests, eligibility and versioned policy determine the recommendation, not an LLM's
opinion. Users can choose methods, with evidence warnings and saved provenance.
Keep single-model, automatic selection and blended modes clearly distinguished.

Automatic factor testing is opt-in: compare no external factors, each reviewed
factor separately and the combined set per customer/SKU, using existing models.
Require complete earlier test windows covering the requested horizon and at least
5% lower earlier error; otherwise keep history-only. Reserve a final window after
selection and display deterioration honestly. This is a practical guardrail, not
significance or causation. Unverified retrospective live captures cannot support
automatic best-factor claims. Future values remain explicit reviewed assumptions.
Automatic discovery/preparation of relevant live sources is a separate capability,
not implied by this bounded supplied-factor test.

Validation requirements:
- Test rolling historical cutoffs at the requested horizon; fit cleaning/transforms
  only on training data. Separate model selection, range fitting and later evaluation.
- Reconstruct orders and factor releases as known at each cutoff. Today's order
  book or revised economic series must not leak into historical test periods.
- Evaluate model-only AND order-aware final plans, plus planner-adjusted plans.
- Accuracy/bias by SKU/customer/period/horizon and sample coverage. A large total
  must not hide poor small-customer forecasts; handle zero demand explicitly.
- Compare against simple baselines; retain reasons for exclusions or model failures.
- Short histories show limited evidence. Seven months does not establish annual
  seasonality; exact customer-level detail cannot be inferred without customer data.
- Reconcile customer/SKU/family/company totals while preserving confirmed order
  commitments; do not rescale known orders to force an aggregate statistical total.
- Ranges describe the uncertain remainder, not the certainty that an order will
  never cancel. Model order cancellation separately only with evidence.
- Approved stockout/lost-demand corrections and closed-period actual revisions.
- Monitor changing performance, propose retraining and require approval policy
  before promoting a replacement model. No silent auto-publishing of weak results.

## 5. Iran and external factors

Tehran is confirmed; exact coordinates are not. Keep company/site scope separate
from customer market, trade route and country/global scope.
- Iran holidays, Nowruz, Ramadan/Eid where relevant, reviewed closure calendars.
- Persian/English, RTL, Jalali/Gregorian and Asia/Tehran period boundaries.
- Explicit rial/toman/currency and FX market (not an ambiguous "USD rate").
- Inflation/price data with publication/revision dates and appropriate frequency.
- Weather only when relevant with an approved location; historical weather is not
  known future weather. National annual inflation is not a daily live signal.
- Global supply, sanctions, conflict, logistics and energy disruptions as approved
  measured inputs or dated scenarios, never invented event-to-demand multipliers.
- Source, geography, units, observation/publication/retrieval times, licence,
  freshness and future-value policy for every factor.
- World Bank/NASA foundations are context connections, not automatically proven
  model drivers. Local/global sources require availability, commercial-use and
  reliability verification before promises.
- Retain factors only where business relevance and testing justify them. Show
  association, not causal certainty; compare with and without the factor.

## 6. Simple product experience

Proposed primary destinations: **Overview · Forecast · Data · Assistant**.
Reviewed versions/scenarios/exports live within Forecast; Settings stays secondary.
Final navigation is a design task, not an implemented change.

Overview: only actionable demand information — plan changes, orders above expected
demand, missing/stale inputs, reviews due and forecast quality. No supply metrics.

Forecast workspace:
- Saved filters for customer, SKU/family, market, date range, unit, scenario and version.
- Total and detailed views, drill-down and customer × SKU × month pivot table.
- History/forecast chart with separate booked and remaining-expected quantities.
- Customer coverage view includes customers with no orders and missing-history warnings.
- Monthly stacked order/expectation view, change comparison, customer/product
  contribution and accuracy views. Every chart answers a question; no decoration.
- Exact numbers beneath charts; visible as-of date, scope, units, target and method.
- Consistent totals between chart, table and export; distinguish missing from zero.
- Preserve the real change from final actual to first prediction. Connect the
  timeline visually without altering values to make the chart look smooth.
- Click a quantity to inspect source orders, baseline, matching, assumptions and edits.
- Review queue focused on exceptions; clear owner/reason and immutable publication.
- Side-by-side scenarios; separate quantity and revenue views with explicit price/FX.
- Friendly empty/error/stale states; progressive disclosure of technical information.

Retain premium black/white surfaces, minimal borders, readable professional fonts,
Phosphor icons with labels, accessible controls/tooltips and centered short dialogs.
Navigation opens pages, not dialogs. Verify keyboard/screen-reader, RTL and layouts
at 1440/1280/1024/768/390 widths. Avoid duplicate actions, small text and excess copy.

## 7. Agentic assistant — a first-class workflow page

A visual conversation workspace with run progress, reviewable actions and linked
interactive result pages, not a decorative chat box.

Example: "Give me the forecast for Customer A for the next 10 months."
The assistant resolves the customer, period/unit and approved data, checks readiness,
shows material assumptions, invokes the same forecasting service as the normal UI,
tracks the job, and opens the filtered result for review. If data is insufficient,
it explains the limitation or asks the minimum necessary clarification.

Supported scope: locate data, suggest/validate mappings, run saved-input forecasts,
compare methods, investigate changes, create draft scenarios, propose data fixes,
prepare exports and guide review. Outputs contain sources, run IDs and exact
quantities obtained from services; the assistant does not invent numerical results.

Controls:
- Initial provider: OpenAI, explicitly requested 23 September. Separate configurable
  models for query/filter/export tasks, data review, and forecast/model decisions.
  Never route every task through one expensive model. Use the official Agents SDK;
  reuse the numerical services. Leave the key blank until configured server-side.
  Disabled AI must make no provider calls or simulated claims. Live AI acceptance
  requires the real key, model access, privacy review and representative evaluations.
- Tool allowlist, typed/validated inputs, per-user/company permissions, audit events.
- Treat uploaded cells/documents/API text as untrusted data, not instructions.
- Authorized read/analysis and draft forecasts can execute without repetitive prompts.
- Confirm meaningful data changes, applying repairs/overrides, publication, outbound
  transmission and enabling new automation. Existing approval separation applies.
- Never bypass order floors, source validation, independent approvals or permissions.
- Preview scope and impact; recoverable jobs, cancellation, safe retry and budget caps.
- Ground explanations in saved evidence; distinguish facts, assumptions and suggestions.
- Pluggable provider/local-model option; no unapproved external upload, provider lock-in
  or assertion that a free model/service has zero hosting/privacy cost.
  The implemented local option uses the existing SDK's Chat Completions transport,
  explicit model IDs and a loopback-only endpoint. Tools and strict structured
  outputs remain required; no automatic cloud fallback. Installing and accepting
  a particular local model is a separate deployment task.
- Persistent daily/per-user call limits, per-request step limits, bounded input
  size and output tokens. Count failed/unknown attempts rather than treating them
  as free. Keep usage information in Settings, not the main forecast workflow.
  Call/size limits do not replace a provider billing limit or cost acceptance.
- Evaluate arithmetic fidelity, ambiguous requests, permission denial, malicious
  spreadsheet instructions, failed tools and incomplete-data behavior before release.

AI validation supplements deterministic checks at ingestion, pre-run and publication;
it may flag anomalies or inconsistencies, not certify correctness by saying "valid".

## 8. Outputs and downstream contract

Forecast exports:
- CSV/XLSX plus versioned JSON/API, with PDF/print summaries for presentation.
- Customer × SKU × period rows; alternative aggregated views and saved templates.
- Company/market scope, identifiers, calendar/period, unit, target and as-of time.
- Baseline, confirmed outstanding orders, matched amount, remaining expectation,
  reviewed total, adjustments, ranges where supported, scenario/version/approval.
- Separate actual-to-date/full-period and still-to-serve quantities when applicable.
- Method/engine/input versions, source freshness, assumptions and issue flags.
- Quantity reconciliation, safe rounding and Excel-formula-injection protection.

MRP handoff must choose a named mode:
1. **Remaining forecast only:** for an ERP/MRP that already has customer orders.
2. **Combined demand:** where the receiver explicitly expects orders plus remainder.

Never deliver combined demand as additional forecast to a receiver that already
adds the same orders. Record receiving-system policy and test reconciliation.
Use dry-run/preview, explicit publication, immutable version, idempotent delivery,
acknowledgement/failure history and replacement/retraction policy. No purchase or
production orders are created by DemandLab.

## 9. Automation and digital-transformation opportunities

Prioritize measurable reduction of manual work, not the number of AI features.
Core roadmap: recurring ingestion → deterministic checks + AI-assisted triage →
order-aware recalculation → exception-only review → approved handoff → later-actual
comparison. Configure who may automate what; stale inputs stop unsafe publication.

Optional after core acceptance:
- Customer commitment portal or structured response templates with expiry/sign-off.
- Learn normal order-arrival timing from archived snapshots for short-term demand
  sensing; use only if it improves beyond the order-consumption baseline.
- Connect CRM opportunities as a separately labelled likelihood-based scenario,
  never confirmed demand and never duplicated after conversion to a sales order.
- Natural-language saved views, scheduled summaries and plain-language change alerts.
- Reusable industry/customer mapping packs and explainable data-readiness guidance.

Measure planner time saved, manual touches, source freshness, correction frequency,
like-for-like forecast error/bias, order reconciliation and export acceptance.
Do not invent percentage targets before establishing a client baseline.

## 10. Acceptance and client decisions

The new release must prove:
- Orders/no orders/partial/complete commitments yield the quantities in section 2.
- Duplicate imports, partial fulfillment, cancellations, changed delivery dates,
  stale feeds, units, backlog and current-month handling reconcile without double count.
- Mixed customer case in section 2.2 yields 29 tonnes, with 19 booked and 10
  expected; customer-level matching precedes every aggregate.
- Requested customer/SKU/month totals agree across all views and exports.
- Identical versioned inputs/settings reproduce numerical outputs.
- AI can complete the example request, show a real result and obey permission gates.
- No production/inventory information is required to complete a sales-only workflow.
- No unapproved data sharing or automatic changes to customer orders.
- Real-client historical testing and a reviewed pilot precede accuracy claims.
- The existing synthetic demo remains labelled; 4.6% sample error is not client evidence.

Client decisions needed before implementation: order export/API and status meanings,
quantity/fulfillment definitions, chosen demand target/date basis, completeness policy,
matching scope/windows, historical order snapshots, downstream MRP consumption mode,
more sales history, customer/SKU identifiers, units, source licences/AI privacy policy,
deployment/identity/approval owners. Missing information may be explicit/unknown;
it must not be fabricated.

## 11. Scope transition and references

Keep existing source code, client files, saved forecasts and legacy supply records
unchanged in this documentation-only revision. In the later build, remove legacy
Supply navigation and operational dependencies from the sales journey with regression
tests and a migration/archive plan; deletion of stored records is not authorized.
Historical implementation evidence remains useful but cannot claim the new order-aware
workflow or agentic assistant is complete. DELIVERY_PLAN.md is the new execution order.

Benchmark principle, not copied product scope:
- [SAP forecast consumption](https://help.sap.com/docs/SAP_INTEGRATED_BUSINESS_PLANNING/c1fb60cb1e9c49d99ada277ae57e9e6c/4d3429bbdaac417dbe16af9886fa15fc.html):
  incoming orders reduce remaining forecast instead of being added twice.
- [Oracle forecast consumption](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/25d/faupc/forecast-consumption.html):
  matching scope and consumption buckets require explicit rules.
These references motivate order matching only; they do not establish implemented
connectors, free licences or client-specific business rules.
# 7 October — one forecast workflow (current instruction)

Starting a forecast follows one sequence: **sales history → factors → customers
and current orders → methods → combined results**. Customers and orders are not
a separate first-use process after calculation. The assistant prepares the same
wizard, preserving its requested horizon, method and customer result filter.

Orders are reviewed and saved before a model is queued. Each selected method
uses the selected history/factors and the same reviewed customer/order inputs.
Before publication, the existing order-consumption rules combine confirmed
orders with the remaining calculated demand at customer/SKU/month level. This
is one workflow, not a claim that orders are statistical training observations.

Known orders above the estimate take precedence; partial orders consume the
estimate, not add to it twice. Customers without orders retain their calculated
demand. A customer without history remains explicitly unknown unless a reviewed
complete monthly requirement is supplied. Missing orders are not zero orders.
Expired or changed inputs require renewed review; incomplete coverage blocks
final totals/export. A complete order book does not mean every customer ordered.

When factors are selected, the wizard offers methods that actually use them.
No forecasting equations or model optimizations changed in this delivery.
Those remain a separate future task.

## Chat layout — 7 October 2026

Home opens with one short heading, a centred composer and three forecast-related
examples. Examples fill the input; they never send a request automatically.
One + menu contains the existing import, data selection, factors, connections
and unified forecast wizard actions. No model picker, invented plugins or voice tools.
Once a message is sent, the composer docks below a separately scrolling conversation.
New chat returns to the centred layout without changing saved forecasts.
Appearance belongs to shared chat/menu components in the global framework and
token registry; English/Persian and RTL use the same structure. Provider consent
and review/confirmation of forecast actions remain mandatory.

## Connected forecast workflow — 9 October 2026

Data is the single home for sales history, the customer directory, reusable orders,
external factors and connections. Customer creation is a simple row form, not a
mandatory file-import step. The forecast wizard loads these connected inputs and
asks for one review before running methods. Unattributed history is never allocated
to named buyers without evidence; new customers without history remain unknown.

New forecast uses a fixed-size centred dialog with an internally scrolling body.
Horizon and calendar are edited there; no Edit inputs detour into the import flow.
Selecting multiple methods creates one named forecast with separate internal model
receipts. Users can select one or several methods for the same filtered chart/table
and export that comparison; method values are never added together.

Chat titles are editable. The first message starts a short, inexpensive title task
in parallel with the answer, under the same provider consent and server call limits.
Its output cannot overwrite a name edited by the user. Development badges and
local-storage statements are omitted; truthful data classification stays in metadata.

# Sales demand + OpenAI checkpoint — 23 September 2026

This is a working local slice, not a claim that the entire product checklist is
finished or that client forecast accuracy has been established.

Latest continuation (23 September): customer directory and Help pages; compact
monthly grid and coverage views; private saved views pinned to reviewed order
versions; customer-scoped assistant job-result navigation; reviewed incremental
order updates with change preview, retry and stale-edit protection; scoped assistant
conversation continuity and reload restoration; saved-input review and approved
mapping corrections to a new input version. Current checks: 284
backend / 37 frontend passing and successful build. The older checkpoint notes
below describe earlier delivery evidence; current limitations remain in the main
checklist. Live AI remains untested; see ASSISTANT_CONTINUITY.md for memory limits
and ASSISTED_INPUT_REVIEW.md for mapping-review scope and next steps.

## Try the demo

Open http://127.0.0.1:8010/#today for Home, then choose Explore sample. Demand
results are now at `#demand`; the Home starting flow is documented in
WORKFLOW_UX_CHECKPOINT.md. The saved sample belongs to forecast
`431fed798551` (Synthetic range verification - 6 months): 12 customer/SKU
relationships, 8 synthetic order schedules and 72 monthly demand rows.
These are synthetic customer segments, not the client's real customer master.

Demand → customer/SKU/month filters → chart/grouped table → inspect order references.
Exports offer Excel, CSV and JSON:
- Expected demand only: use when the receiving ERP already includes orders.
- Orders + expected demand: open orders plus the remaining estimate, excluding
  already fulfilled quantities. Never add this on top of the same ERP orders.
Exports cover the whole selected snapshot, not only the on-screen filters.
They carry a draft label and are not an approval/publication or an external send.

## Inputs and calculation

Data still imports historical actuals and optional factors through the existing
forecast engine. Demand adds three separately typed inputs:
- Customers: customer, SKU, unit and optional saved individual series ID. Download
  the prefilled template, extend it with eligible missing relationships, then upload.
- Orders: unique line/delivery reference, customer, SKU, unit, due date, ordered,
  fulfilled, cancelled and status (confirmed/unconfirmed/cancelled).
- Optional complete commitments: full-month quantity, owner, reason and expiry.

Import accepts CSV, TSV, Excel and JSON records. Choose sheet/header, match columns,
confirm source date/completeness, inspect calculated results, then save. Formulas
are rejected: export reviewed values. No automatic ID, unit or calendar conversion.
Initial uploads establish a full snapshot. Update orders retains the saved inputs
and supports changed lines or full replacement; changes use stable references and
full current quantities, not deltas. See ORDER_UPDATES.md for retry, concurrency and
fulfilled-quantity safeguards. No fuzzy cross-source deduplication, automated ERP
connector or customer lifecycle/effective-date logic is claimed. Source files are
retained and imports re-read on the server at save.

Matching is exact customer + SKU + unit + Gregorian month, before aggregation.
Partial orders: remaining = max(0, baseline − fulfilled − open confirmed orders).
Full-month demand = fulfilled + open orders + remaining. Explicit complete
commitments replace the full-month expectation; quantities below known orders
are conflicts. Customers with no orders retain their forecast. Missing history
means unknown additional demand, not zero. Cancelled remainder is excluded but
fulfilled quantities retained. Stale/unknown sources, unmapped series, unresolved
history and past-due open orders block demand export. Past-due orders need reviewed
dates; they are not automatically shifted into the next month.

No new forecasting algorithm was invented. Existing statistical/ML methods and
numerical model comparisons remain authoritative. The order layer is explicit
business logic using Decimal/Pydantic and immutable local SQLite snapshots.

## OpenAI setup (blank key for now)

Copy `.env.example` to `.env.local` locally. Both actual env files are ignored by
Git; never send the key in chat or add it to frontend code. Fill `OPENAI_API_KEY`,
set `DEMANDLAB_AI_ENABLED=true`, then restart `run.py`. Environment variables already
set by the shell take precedence. No real key has been added or tested.

Defaults, verified against official OpenAI documentation at implementation time:
| Job | Model setting | Default |
|---|---|---|
| Routing, simple lookup/export | DEMANDLAB_AI_QUERY_MODEL | gpt-5.6-luna |
| Evidence/data-quality review | DEMANDLAB_AI_REVIEW_MODEL | gpt-5.6-terra |
| Forecast/model decisions | DEMANDLAB_AI_DECISION_MODEL | gpt-6-astra |

All are independently configurable to models available to the API project.
The official open-source `openai-agents` SDK runs a small typed-tool workflow,
not a custom agent framework. The chat uses automatic routing through the small
router first; technical mode overrides are not shown as chat controls. Model tests, quantities and forecasts come from the
local services, not language-model arithmetic.

Assistant tools read selected forecast/order evidence and saved method comparisons,
propose a 1–24 month draft forecast from a saved monthly dataset, or prepare a
local demand export. A separate click executes proposals. Forecast actions reuse
the normal persisted queue, preserve dataset lineage, strip legacy operations
inputs, detect changed source versions and block newly introduced data warnings.
The current action fits the saved dataset, not a newly isolated customer model;
after completion Open result selects the requested customer and shows their SKUs.
A new calculation without reviewed orders is explicitly model-only; an older order
snapshot is not silently reused. This navigation is covered by local action/data
tests, not a live provider-to-browser acceptance run.

OpenAI calls require both server enablement and user consent. They may include
customer names and selected numerical evidence. SDK tracing is disabled and
provider response storage requested off; this is not a zero-retention guarantee.
The local journal stores questions, answers and proposals. Actions are actor-bound,
expire after an hour, and respect existing role/CSRF checks. No shell/SQL, order
mutation, inventory, production, approval or external-send tools exist. Chat now
retains bounded recent exchanges for the same forecast and order version. New chat
starts fresh; changed evidence requires a new conversation. Local action receipts
persist across reload, without renewing the one-hour proposal expiry.

Bounds: one active request per actor/process, 150-second timeout, 5 agent turns,
2,500 output tokens per agent response and a 300-token routing response. Both
router and worker usage are counted. No organization-wide spend cap is claimed;
configure an API project budget before enabling. Read tools return at most 120
rows with explicit truncation; large-run aggregation tools remain to be added.

## Verification and honest limits

Final check: 245 Python tests and 16 JavaScript tests passed; frontend production
build and dependency consistency check passed. Existing NumPy deprecation/SQLite
resource warnings and the large frontend bundle warning remain technical cleanup,
not reported as resolved by this release.

Automated tests cover numerical consumption cases, units/customer isolation,
no-history/stale/backlog gates, imports/source cells/formulas, immutable saves,
baseline fingerprints and residual/combined exports. AI routing/consent/tools/
ownership/forecast proposals are tested with mocks and no live API calls.
Browser sample review/save and dashboard/disabled-assistant layout were exercised.

Still required for the full product: live key/model-access/evaluation tests;
AI-assisted mapping and reversible repairs; richer agent scenario actions; real
client order semantics and 24–36 months of actuals; Iran FX/inflation/calendar
licensing and point-in-time factor validation; one real ERP connector; order-aware
approval and MRP reconciliation; snapshot replay independent of current freshness;
multi-user deployment and new-database backup/retention acceptance.

The supplied client sales workbook has only seven actual months. Nothing in this
release turns that into validated annual seasonality or a guaranteed accurate plan.

References: [official Agents SDK](https://developers.openai.com/api/docs/guides/agents/sdk),
[OpenAI models](https://developers.openai.com/api/docs/models).

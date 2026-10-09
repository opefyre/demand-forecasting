# Assistant onboarding and demand handoff

3 October 2026. Sales/demand only.

## Delivered

The Assistant no longer requires a calculated forecast. Its compact attachment
control opens the same reviewed import flow used by Data. Saving sales history
returns to the assistant with that input version selected. A centered searchable
picker chooses saved sales history or the current forecast; it is a data-context
choice, not a task/type-of-help selector. Missing data leads to brief guidance.

The official Agents SDK is reused, with query/review/decision routing and existing
recipient consent, tracing/storage restrictions and durable call limits. Numerical
results come only from existing local services. No production/inventory actions.

The assistant can inspect declared inputs, propose supported mapping corrections,
save a new input version after approval and continue using it. It can propose a
1–24 month monthly forecast for an exact customer or all customers, using a method
family or an individual installed model. Actual availability is validated by the
existing engine; listing a method is not evidence of measured accuracy.

Forecast actions re-check files, input version and horizon/factor readiness before
submission. Changed evidence, unknown customer names and unreviewed new warnings
block the run. Approval does not send sales orders automatically into a new result.

On the new forecast, the assistant can list compatible saved order books, check
coverage/consumption and propose a separate all-customer demand draft. Source/target
evidence and latest versions are checked again. Saving needs an explicit coverage
checkbox and a server-side true confirmation. Reuse never edits orders, renews their
dates, erases excluded orders or copies publication approval. Expired sources block.

Opening the draft leads to the existing filtered customer/SKU/month dashboard and
draft CSV/Excel/JSON exports. Orders consume matching demand; no-order customers
retain model demand. Delivered quantities are excluded from planning exports.

Input selection and conversational pointers survive reload using opaque IDs only.
Server history is bound to actor, input/forecast/order version and evidence hash;
no tool calls are replayed as actions. Changed data needs a new chat/proposal.

## Verified synthetic journey

- Source: `972f7cba21c75d40997d17213fee2c6b`, 36 Persian history months,
  two customer/SKU series, no client data.
- Live assistant asked to inspect history and prepare ten months with Weighted
  recent average. It inspected inputs, retrieved model names and proposed the
  canonical method; nothing ran until confirmation.
- Confirmed job `6eb5840c811f41d488c908608cd89e97` succeeded:
  run `df87c7ec00ae`, 10 future Persian months / 20 rows.
- Second live assistant request selected the original baseline's exact saved
  order book, previewed it and prepared a coverage-review card, not the unrelated
  Aluminum scenario. Separate saved demand draft `442abf470d3665729101f774d273853a`.
- Open orders 140 tonnes; fulfilled 20; expected not ordered 2,232.62;
  future still to serve 2,372.62. Total including fulfilled 2,392.62.
- All six exports (two modes × CSV/Excel/JSON) reconcile to the complete local
  rows. Persian labels/calendar retained; source orders/customers/dates unchanged.
- Two live questions used 11 provider calls, 17,354 reported input tokens and 426
  output tokens. These are observed usage, not a cost cap or reliability benchmark.
  Exact individual model names now normalize locally to avoid the unnecessary
  naming retry observed in the first request. That improvement is offline-tested.

Read-only repeat verification:
`scripts/verify_assistant_onboarding.py df87c7ec00ae` (no AI calls).

489 backend tests, 73 frontend tests and production build pass. Existing large
frontend bundle and legacy dependency/resource warnings remain. Desktop and 390px
controls, sharing permission, order coverage and result navigation checked.
The long source-name composer overflow was measured at 484px on a 390px screen,
fixed with bounded grid/flex sizing and rechecked at exactly 390px page width.
The attachment opens the reviewed import flow and returns to Assistant; the back
label follows that context instead of incorrectly saying Data library.

## Still required for whole-product completion

First order-file import and connected factor-scenario creation are now assistant
tools; see ASSISTANT_GUIDED_WORKFLOWS.md. File selection and uncertain meanings
still require the existing human review. Update, 7 October: formatting-only cell
review is implemented (INPUT_CORRECTION_DELIVERY.md); arbitrary value repairs remain pending;
source values are never silently changed. Broader languages, ambiguity, large-data
load and real-client acceptance remain. Monthly Iran/regional live factor gaps and
client accuracy/receiver/deployment checks are tracked in DELIVERY_PLAN.md.

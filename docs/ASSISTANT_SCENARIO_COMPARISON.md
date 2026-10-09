# Assistant scenario comparison

24 September 2026 — bounded sales/demand-only delivery slice.

## Brief and acceptance

Confirmed: the app already has saved baselines, linked-factor scenarios, customer
order snapshots, deterministic order-consumption arithmetic and approval-gated
comparison saves. The existing OpenAI Agents SDK and three job-specific models
are retained; no new forecasting algorithm or agent framework is introduced.

Design choice: extend that same workflow through plain-language requests. The
assistant may read and propose, but the application, not the model, performs all
arithmetic and writes. A comparison-only request must not create a saved draft.

Open limits: only linked-factor children of the selected baseline are supported;
scenario creation itself, selective-customer saves, publication approval, and ERP
transmission are not part of this slice. Client accuracy and production readiness
are not implied by a successful assistant demo.

## Implemented

- Inspect exact scenario choices belonging to the current baseline. No arbitrary
  run lookup; missing order context and non-baseline context return guidance.
- Preview the same order book against both forecasts. Optional exact customer/SKU
  filters. Full-population monthly and horizon totals are computed by local code,
  never by the model. Units stay separate; any unknown makes that aggregate unknown.
- Prepare an all-customer/SKU draft with a compact before/after review card. Filtered
  previews do not silently narrow the save. Ambiguous scenario names must be clarified.
- Explicit **Approve & save draft** reuses the existing review token, source hash,
  latest-version checks and transaction guard. Changed inputs require a fresh proposal.
- Existing actor ownership and one-hour proposal expiry apply. Stable action request
  IDs protect retries, including a lost response or missing assistant receipt.
- Orders, cancellations, deliveries, original baseline and approvals are unchanged.
- Saved receipt offers **Open forecast**, full-scenario Excel and residual-only CSV.
  Exports exclude delivered quantities. Nothing is sent to a downstream system.

## Verification

- 349 Python tests and 45 JavaScript tests pass; production frontend build passes.
- Seven additional tests cover scope isolation, filtered/full totals, mixed units,
  unknown values, read/propose-only tools, ownership, idempotency, changed forecasts,
  newer orders, expired inputs, absent context and originating-context validation.
- OpenAI authentication and model listing succeeded with the user-supplied local
  key. Query, review and decision models are listed as available. This read-only
  check does not prove all three roles' generation quality or production suitability.
- Live assistant check passed using only the existing synthetic sales/order demo
  and public GSCPI scenario. Query routing selected the decision model; five API
  requests used 7,489 input and 280 output tokens. Live review-model generation
  has not yet been checked. Client data was not sent.
- Proposal did not save anything automatically. Reload restored the review card;
  clicking approval created draft `f985c98c21ac24d8e18ff9f8b6a2e8db` from source
  `37d0646991260d00a76812640c96d2a4`, for scenario `4cb719fe31fb`.
- All 36 rows and JSON/Excel/CSV quantities reconciled: orders 203.388 tonnes,
  baseline total 2268.1998242737664, scenario total 2270.7808763607954,
  scenario remaining forecast 2067.3928763607955. Source hash unchanged; draft only.
- Laptop (1366 px) and phone (390 px) layouts checked. Tables scroll internally;
  no horizontal page overflow. Saved receipt has working result navigation.
- Added existing open-source `react-markdown` and `remark-gfm` to render replies
  correctly. Raw HTML, model-supplied images and clickable model-supplied links are
  disabled; authorized result/export links come only from application receipts.
- Secret remains server-side in ignored `.env.local`, owner-only permissions.
  AI is enabled locally, but every new browser chat still requires sharing consent.

## Next task

Broaden live assistant acceptance with a small synthetic test set: customer/horizon
requests, ambiguous scenario choice, input review, missing data and refusal to invent
quantities. Check role routing, cost/latency, concise responses and failure recovery.
Then close any issues before adding more tools. Iranian CPI/FX feeds still require
market definition, source permission and usable dated historical observations.

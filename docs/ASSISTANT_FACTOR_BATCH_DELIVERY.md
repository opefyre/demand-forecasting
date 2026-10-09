# Assistant-led customer/product factor batches — 7 October 2026

## Delivered

Choose an existing forecast in Assistant and request a batch for named customers
and products. The assistant resolves exact saved series IDs. If sources, methods,
timing or future values are missing, a single action opens the existing centered
review dialog restricted to the requested products. Saved profiles remain optional.
No new sidebar section, task-type picker or provider-status banner was added.

For complete, explicit user-provided inputs, existing SDK tools preview each group
and prepare one confirmation card. Future assumptions and source checks are inside
an optional disclosure; scope and methods are visible. Explicit approval queues the
existing numerical calculations. Progress leads to the verified demand result,
where current orders still require their own review before exports.

Up to 20 disjoint groups are supported, with at most 100 exact series per group.
The adapter reuses factor alignment, reviewed immutable saves, batch calculations,
public-history factor testing, background jobs, existing providers and demand views.
AI does not generate forecast quantities. No new dependency, model, account or
credential was introduced; the previously approved OpenAI key was reused securely.

## Safeguards

- Tool calls inspect, preview or propose only. They cannot save, refresh a provider,
  run a job, alter orders or publish a planning output.
- Complete proposals require connected, current and permitted saved source versions.
  Missing values, stale observations and commercial-permission gaps block them.
  Imported factor files are not an automatic AI fallback for live external data.
  Explicit manual choices remain in the separately reviewed existing workflow.
- Every group uses exact disjoint customer/product scope and the same baseline.
  Only user-declared future values are accepted. Automatic methods retain existing
  publication-timing gates; recently downloaded history remains what-if evidence.
- Confirmation rechecks forecast/source bytes and inputs. Changes require fresh
  review. Owner, expiry, role/CSRF middleware and strict boolean approval gates
  remain. Repeated requests reuse the same saved inputs and job.
- The connected-source requirement is retained in the queued batch and checked by
  calculation, not only when the assistant creates the proposal.
- Progress is bound to the assistant owner, saved dataset and original baseline.
  It returns only status and a verified result ID, not private job fields.
  A failed or interrupted batch does not publish a combined result.
- Orders are not automatically copied. Unselected products preserve the baseline;
  combined accuracy and ranges are not inferred from the original portfolio.
- Reopening a scoped review uses its own browser draft; it does not overwrite the
  broader manual batch draft or restore an approval.

## Verification

588 backend checks and 109 interface checks pass; the production build passes.
Ten new backend checks exercise real SDK tools, exact scope, missing/stale inputs,
permissions, changed sources, expiry/ownership, idempotency and result binding.
A confirmed two-group request runs the actual existing forecasting engine with
distinct assumptions. Mocked provider transport is explicitly a test fixture,
not evidence that a live source refreshed successfully. Four new interface checks
cover scope, Persian month labels, approval, expiry and completion/error receipts.
Existing batch tests continue to reconcile partial orders and all six exports.

One bounded live OpenAI request used synthetic baseline `d729c16c0f56`, requesting
Demo Tehran A products 0001 and 0002 for its existing six forecast months, without
inventing values or calculating. Turn `f88272f4854d45a0b084e936b0c0e019` produced
the correct `factor_batch_review` action. Existing automatic routing selected the
review model `gpt-5.6-terra`. Recorded usage: four provider requests, 16,702 input
tokens and 190 output tokens. No additional live AI request was made for this slice.

The browser action opened the exact two-product picker. The profile's missing CPI
permission and overdue supply/commodity sources correctly remained disabled.
Desktop, 390px and 320px review were checked; the 320px dialog stayed within the
viewport (x=15, width=290, document width=320). Cancelling returned to the same chat.
Temporary viewport changes were reset. Screenshots are in outputs/assistant-factor-
batch-desktop.png, assistant-factor-batch-mobile.png and assistant-factor-batch-
smallest.png. The local server was restarted at `http://127.0.0.1:8010/`.

Existing database-cleanup/deprecation/numerical library warnings remain, as does the
large frontend-bundle advisory. This is not a zero-warning or whole-product UX audit.

## SDK design brief

Confirmed: this app already uses the open-source Agents SDK with caller-owned tools,
storage, task-specific models, cost limits and a human-confirmed action journal.
The OpenAI skills guided reuse of that architecture and separation of read-only AI
proposals from confirmed numerical execution. The official reference is the
[Agents SDK guide](https://developers.openai.com/api/docs/guides/agents/sdk).
No hosted Agents API deployment or broader key access was introduced.

Inference: exact identity resolution needs ambiguity checks and must never expand
a request to unrelated customers. Instructions and validation enforce this; one
successful live request is not exhaustive acceptance of every phrasing/model.

Open: live complete-proposal/calculation acceptance over permitted, fresh real
sources, wider assistant adversarial testing and independent client accuracy.
Synthetic arithmetic/workflow tests cannot establish real forecasting accuracy.

## Next major build

Recurring monthly draft refresh with one exception review: reuse existing sales/
order connections, live-source checks, customer/product batches and immutable jobs.
Show what changed, missing inputs and material demand changes in a single review,
then require explicit order coverage and approval before planning exports. Recurring
configuration itself needs administrator confirmation. Do not auto-publish forecasts
or fabricate future assumptions when a source changes or becomes unavailable.

Permitted full live history and source freshness, actual client history and measured
benefit, receiving-system reconciliation and secure deployment acceptance remain
required before claiming the entire product complete.

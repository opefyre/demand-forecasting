# Assistant acceptance checkpoint

## AI provider controls added on 3 October 2026

OpenAI remains the existing default. A local OpenAI-compatible service can now be
selected server-side using `.env.example`: set `DEMANDLAB_AI_PROVIDER=local`,
configure the loopback `/v1` endpoint and supply installed model IDs for each job.
No model installation, switch or credential change was performed in this build.
Local models must support function tools and strict JSON schema output. The
transport is reused from the official [Agents SDK model integration](https://openai.github.io/openai-agents-python/models/).
Configuration alone is not a connectivity or model-quality check.

Default limits are 60 model calls per workspace/day, 30 per user/day and six per
request. Each call includes at most 100,000 UTF-8 evidence bytes and requests at
most 2,500 output tokens. The daily counters reset at midnight UTC, survive server
restarts and include failed/cancelled attempts. Oversized evidence is rejected,
not silently truncated. Unreported usage stays unknown, not a confirmed free call.
These controls are not a dollar cap; billing limits must be set with the provider.

Local requests use no OpenAI key, ambient proxy or redirect. There is no cloud
fallback or automatic retry. Tracing and provider storage are disabled. Sharing
permission names the actual recipient; a changed endpoint needs renewed permission.
Existing confirmation and company approval gates still apply to business actions.

Offline checks use the real SDK with a fake HTTP transport, including strict role
classification, an exact saved-order-aware-demand tool call, errors and redirects.
No paid call or client-data transmission was made. The desktop and 390px sharing
dialog, cancellation and mobile Settings were checked; controls stay collapsed
and no assistant banner or task selector was added. Live installed-model quality,
performance, privacy/licence approval and client deployment remain unaccepted.

Next major build: assistant onboarding from uploaded inputs before a forecast
exists, with validation, draft calculation, matching orders and filtered outputs.

## Earlier live evidence

24 September 2026. Sales/demand only; no production or inventory actions added.

## Brief

Confirmed foundation: job-specific OpenAI models, local numerical services, saved
conversation context, review-before-save actions and order-aware scenario tools.
This slice checks actual assistant behavior with synthetic data, not client data.
The existing Agents SDK, dataset validators and forecast queue are reused.

Design inference: checking input readiness before showing an approval card should
avoid dead-end approvals. Keeping only decisive model-test evidence should reduce
AI context cost without changing any forecasting calculation.

Open questions: broader varied-language accuracy, missing-factor judgment in live
conversations, multilingual behavior, production load and client-data permission
still need acceptance. Seven successful live requests are not a general AI guarantee.

## Live checks

| Request | Observed result | Role | Seconds |
| --- | --- | --- | ---: |
| Saved monthly demand for Demo A | Correct customer/SKU/month quantities; no action | Query | 9.02 |
| Prepare 10 months for Demo A | Correct customer, horizon and method; proposal only | Decision | 8.91 |
| Change that to 8 months | Kept the customer and changed the horizon; proposal only | Decision | 7.75 |
| “Demo customer”, without choosing one | Asked A, B or C; no proposal | Decision | 3.11 |
| Check selected inputs | Used input evidence; reported no verified issues in clean demo | Review | 5.98 |
| Customer NeverExists | Reported no match; no invented quantities or action | Query | 4.74 |
| Repeat 10-month request after changes | Preflight passed; correct proposal; no execution | Decision | 7.30 |

The query/review/decision models all returned live responses. This is a single
run per case, not a statistically representative reliability or latency benchmark.
The initial six checks used 18 provider requests, 53,626 input and 939 output
tokens. The final recheck used 3 requests, 2,525 input and 171 output tokens.
The test script requires explicit `--live`; normal tests do not call OpenAI.
Original order snapshot contents were checked unchanged. No proposals from these
acceptance checks were approved, and no forecast jobs or exports were launched.

## Improvements and verification

- Forecast preparation now reuses the same input checks as approval: missing
  future factor values, new warnings, and changing a linked scenario's horizon
  are rejected before offering a save/run card. Approval checks them again.
- Model comparison keeps model names, measured errors, later-period confirmation
  errors, failure counts, weights, evidence limitations and warnings. Bulky row-level
  and horizon traces remain in Accuracy instead of being sent to the assistant.
  The demo payload decreased from 44,020 to 9,772 JSON characters (about 78%).
  This is a payload comparison, not a claim of a fixed token/billing reduction.
- Assistant receipts now record tool names used, without arguments or credentials.
- Six new offline tests cover successful/no-write proposals, missing factor data,
  warning review, scenario restrictions, bounded model evidence and sanitized
  provider failure followed by a successful retry.
- 355 Python tests pass. No frontend changes in this slice; the preceding 45
  JavaScript tests and frontend build remain the latest UI verification.
- Reproducible script: `scripts/verify_assistant_live.py --live`. Test evidence:
  `outputs/assistant-live/suite.json` and `outputs/assistant-live/horizon.json`.

## Next bounded task

Complete the changed-horizon journey: let an approved new forecast reuse the
existing reviewed customer/order book, show which future months have valid order
coverage, and require review before saving a separate order-aware draft. Never
invent future factor values or assume an absent order means zero demand. The
current assistant's horizon action creates a new statistical forecast only;
customer orders are not silently copied to that new run.

After this, test the full history → orders → factors → customer/SKU/month output
journey with client-like imports. Live Iranian CPI/FX integration still requires
the client's FX market definition, permitted sources and dated historical data.

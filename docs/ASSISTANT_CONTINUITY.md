# Assistant conversation continuity — 23 September 2026

## Scope and implementation

Confirmed: the product is sales/demand forecasting only. Existing local tools
inspect forecasts, compare recorded methods and propose forecast/export actions.
The user requested OpenAI with different models by job and a placeholder key.
No live call, credential creation or provider activation was authorized in this pass.

Previously every question was independent. This pass adds follow-up context and
reload recovery using the existing open-source OpenAI Agents SDK, SQLite journal
and React components. No new agent framework or model was built. SDK typed-message
input was checked against the installed package and its [official guide](https://developers.openai.com/api/docs/guides/agents/sdk).

- The client submits the previous saved turn ID, never a client-supplied transcript.
- The server checks ownership and exact forecast/order-snapshot scope for every
  turn it retrieves. Stored forecast/evidence fingerprints prevent continuing when
  the underlying evidence or order readiness changes. Start a new chat in that case.
- Both the small routing model and the selected specialist receive recent user
  questions and assistant answers. Numerical answers still require fresh tool reads.
- Context includes at most six whole exchanges within 18,000 characters including
  the new question. Older exchanges are omitted, not replayed indefinitely. Tool
  calls and old proposals are never replayed as executable history. Ambiguous
  references should trigger clarification, not guessed customers or dates.
- Reload recovery restores up to six exchanges for the same browser's saved head.
  Only an opaque turn ID is held in browser storage; messages remain server-side.
  The backend rechecks identity, including when a different person uses that browser.
- New chat clears that browser pointer, not forecasts or stored audit records.
  Conversation continuation expires after 30 days; this is not a data-retention purge.
- Proposal expiry remains one hour. Reopening a conversation cannot renew it.
  Confirmed action receipts survive reload. Forecast jobs remain subject to existing
  idempotency, role, source-validation and approval gates.
- Consent now explicitly covers recent conversation messages as well as the new
  question and selected forecast evidence. AI remains disabled without a configured
  key and enablement. No setup card, new sidebar item or task-type dropdown added.

## Verification and limits

274 backend tests and 36 frontend tests passed, plus production build. Added
ownership/scope, changed-evidence, expiration, bounded-context, new-conversation,
reload-history and execution-receipt checks. Routing and specialist context use
mocked provider execution: **not proof of live model quality, latency or cost**.
Provider-enabled follow-up accuracy and malicious-content evaluation remain open.
Browser smoke covers the real disabled-provider screen; synthetic test replies
are not inserted into the user's demo journal.

No automatic file repair, conversation search, cross-device conversation picker,
live job-state tool, data-import tool or scenario-editing tool is claimed here.

## Next task: assisted input review

Deliver one bounded import-review workflow, not a broad agent expansion:

1. Expose existing validation evidence for the selected sales/order/factor inputs
   to the assistant: missing periods, duplicate lines, customer/SKU mismatches,
   units, suspicious values and factor coverage for the requested horizon.
2. Let the review model explain issues and propose column mappings or safe fixes.
   Distinguish confirmed rules from suggestions; never invent sales or factor values.
3. Show a compact before/after review. Apply only explicitly approved changes to a
   new dataset version, retain the original source and rerun deterministic validation.
4. Verify the cleaned inputs can feed the existing method comparison and customer/
   SKU/month demand flow without changing confirmed-order floors or export semantics.

After that: one real source integration and timestamped Iran/global factor data,
followed by order-aware approvals and controlled downstream export acceptance.

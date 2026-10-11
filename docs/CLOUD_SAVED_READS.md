# Private cloud read performance — 11 October 2026

Bounded delivery. This does not close first-load performance, advanced scenario
consolidation or whole-app acceptance.

## Delivered

- Reopening chat lists can reuse a completed engine response from private company
  storage rather than enqueue another engine job. Lifetime: 12 hours; any company
  input revision change invalidates it. Exact actor, company, issuer, role,
  authentication/key kind, full permission set, path, search, folder and pagination
  must match. Current authentication/permissions are checked on every request.
- Only full-access administrator/planner lists qualify. Restricted report readers
  and company/service keys cannot reuse private chat history. Conversation bodies,
  proposed actions and exports are excluded.
- Factor-link and exposure-profile choices may reuse completed reads for 30
  seconds. Preview/save still recompute source freshness, alignment and approval
  evidence. Neither an approval token nor a calculation is cached.
- Successful jobs receive a completion timestamp. Old records without one,
  failures, missing objects and expired/foreign/malformed results miss safely and
  retain the existing queued-read path. Recovery records cannot revive the saved
  principal's authority. Browser responses remain `no-store`.
- Simultaneous opening screens share one company-revision lookup. Requests and
  mutations remain independent. Writes are never automatically replayed, and an
  old concurrent read cannot rewind the session's current revision.

## Design and recovery

Chat-list failures now retain the actual request error and use the existing
RequestRecovery component. Read-only reload, permission failures and translated
guidance behave like the other screens. Technical details remain collapsed.
No new page, setting, banner, authored inline style or CSS rule was added.

Healthy cloud Home was checked in English and Persian. Persian direction was RTL,
page and scroll widths were both 1512px, and the main area contained zero inline
style attributes. These are desktop checks, not full mobile or every-page acceptance.
Temporary language changes were restored; forecasts, orders and inputs were not
changed. Local screenshots: `/private/tmp/demandlab-cloud-saved-reads-fa.jpg` and
`/private/tmp/demandlab-cloud-saved-reads-en.jpg`.

## Verification

- Cloud policy/recovery tests: 57 pass.
- Native Workers/R2/SQLite storage tests: 2 pass. A repeated private list and factor
  choice produce status 200 without increasing the fake engine call count. A
  different actor and a changed revision require new work. This tests the actual
  storage runtime; it is not a measured real-container sleep/wake test.
- Interface: 320 tests pass; production build and whitespace checks pass.
- Python company API/cloud workflow tests: 22 pass. No model equations changed.
- Live private cloud: initial list requests returned 202 and completed through
  their saved operations. Subsequent identical chat-list requests returned direct
  200 responses; those cannot take the queued list path. Home shows a completed
  empty list, not a loading/error state. Fresh workspace reload also succeeded.
- During deployment, the first browser read failed and later succeeded on explicit
  retry. Its cause was not conclusively identified. No cold-start speed guarantee
  is claimed, and synthetic tests do not replace real cloud error-path acceptance.
- Independent local demo health: 200. No provider refresh or OpenAI call.
- Existing bundle-size, Radix/dependency and Python resource warnings remain.

Dedicated deployments only: storage `4a8cef7d-7f71-4846-93b3-1ba4bb4b9654`;
edge/interface `1338eb44-61c1-49a4-9c29-42ac711d5bd1`. Closed owner-only access,
five-minute engine inactivity shutdown, identity, domain, storage bindings,
credentials, engine image and other services remain unchanged. One nullable ledger
column was added; no records were deleted or rewritten for migration.

## Next substantial slice

Consolidate advanced factor scenarios/batches into the same pre-calculation
forecast review, with saved orders and selected methods together. Verify desktop,
Persian mobile, pending operations, stale evidence and safe reload paths. Reduce
remaining cold calculation/checkpoint/projection work only with result-equivalence
tests. Then complete the entire bilingual input → forecast → comparison → approval
→ export acceptance audit, including the remaining legacy screens.

Real-client accuracy, provider/AI eligibility and a multi-person pilot remain
separate acceptance gates.

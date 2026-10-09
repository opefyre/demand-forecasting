# Sales workflow recovery

7 October 2026. Bounded recovery delivery; not full UX or production acceptance.

## Changes

- Shared request handling preserves HTTP status, retry deadlines and validation
  field paths. CSRF headers, file payloads, request IDs and session-expiry behavior
  remain intact. No automatic request retry was introduced.
- Shared error presentation gives a short next step for interrupted connections,
  unreadable responses, expired sessions, forbidden actions, missing versions,
  changed versions, input errors, request limits and server failures.
- Original validation reasons are visible directly. Longer server details remain
  collapsed. Authored guidance is English/Persian; source/customer evidence remains
  exact and escaped. Validation input values/context are not retained.
- Demand read failures no longer display an empty-order setup or suggest creating
  replacement orders. Read-only reload recovers saved demand; run-switch guards
  prevent a late reload from replacing another run's inputs.
- Order-import schema reads can be retried without re-uploading or resaving orders.
  File/mapping validation and demand-export failures retain structured evidence.
- Monthly-update read failure no longer leaves a permanent loading message. Reload
  reads the saved session and rechecks referenced runs; it does not calculate or save.
- Live-source list and saved-observation reads have separate failure/reload states.
  These retries read local saved information; they do not refresh a provider or
  accept permissions. Readers can inspect permission-gated source details.
- Expired-order guidance directs planners to the existing review action and readers
  to a planner. No duplicated order-review button or new navigation destination.

## Verification

- All 143 interface tests pass; production frontend build passes. Existing bundle
  size warning remains. No backend/model change or new package was required.
- 65 focused backend tests pass: sales demand, order revisions, monthly refresh,
  demand releases, normal sales-import journey and durable jobs. This is not a new
  full-backend-suite run. Existing resource/deprecation warnings remain.
- Request tests preserve quantities, IDs, methods, multipart uploads and CSRF;
  test one-attempt writes, uncertain save results, validation privacy, status/role
  restrictions and exact cooldown expiry. Actual rendered error-component tests
  check Persian guidance, original evidence, escaping and disabled/absent retries.
- Bundled synthetic browser fixture uses actual SalesDemand, MonthlyRefresh,
  LiveSources and RequestRecovery components with an isolated fake API. Demand,
  order-version, monthly-update and source-list failures recover after user action.
  Forbidden reader access offers no retry. All checked recoveries recorded zero
  writes; no client record or provider/AI request was involved.
- English and Persian keyboard retry restores independently specified synthetic
  3 booked + 7 expected = 10 tonnes. Persian recovery fits a 390px viewport.
- Existing local demo still has 93 booked, 1,199.06 expected and 1,304.06 total
  tonnes including fulfilled quantities. Customer 001 has 90 / 461.08 / 563.08;
  language switching preserves that filter and these quantities. Production browser
  console returned no errors. Original language and all-customer view restored.
- Diagnostic entry `frontend/recovery-fixture.html` is development-only and not
  included in production output or navigation. Temporary diagnostic servers stopped.
  Screenshot: `screenshots/sales-recovery-persian.png` (synthetic test, not client data).

## Remaining and next substantial chunk

Full first-use and monthly-update acceptance remains open: corrected uploads,
interrupted saves, missing periods, no-order customers, mixed calendars, restricted
roles, outdated factors, interrupted calculations, filtered review and all export
forms in one repeatable realistic pilot. Existing backend tests cover many of these
contracts separately; they are not proof of the entire browser journey.

Next: build that end-to-end acceptance package, repair failures it exposes and
finish remaining user-facing messages within those routes. Broader navigation and
layout revisions will incorporate the user's forthcoming end-to-end feedback.
Real-client accuracy, complete permitted live history, wider live AI/receiver
acceptance and secure company deployment remain separate gates.

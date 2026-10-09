# Company workflows — 9 October 2026

Completed this plan milestone. Authenticated company mode is still not enabled
on the existing local demo; deployment and remaining integrations are separate work.

## Delivered

- Advanced assistant tools: customer/product factor profiles, source preparation,
  factor comparisons and multi-group scenarios, order comparisons, saved-order
  reuse and monthly-update proposals. Tools and confirmed actions check current
  permissions; assistant context never falls back to shared stores.
- Monthly updates: history → calculation → factor review → current order review
  → change review → Excel/CSV/JSON draft exports. Saved orders are explicitly
  reviewed against the new months, not silently copied from an old result.
- Administrator recurring drafts: company-owned schedules, edit/pause/check,
  durable monthly cycle history, site time zone and Gregorian/Persian calendars.
  Each cycle and queued calculation rechecks the owner's live verified company
  membership, administrator role and enabled two-factor authentication.
  Lost access or an unavailable identity service stops work, rather than using
  a cached grant. Schedules retain no browser cookie or API credential.
- Existing forecasting engine, OpenAI Agents SDK, Huey, APScheduler, Better Auth
  and shared interface components reused. No new mathematical engine, page CSS
  or paid AI call introduced. Public coverage now includes 131 v1 operations.

## Boundaries

Monthly updates and schedules are personal within their company. Other companies
and other users cannot read or modify them. Planners can use advanced drafts and
monthly updates; only administrators manage schedules. Viewers receive no draft
tools or write actions. Service keys cannot own personal updates or schedules.

Recurring work starts only when the latest completed month is available for all
required customer/product series. It prepares a draft and stops for factor/order
review; it never approves, releases, sends or exports a forecast automatically.
External observations do not supply unknown future values: assumptions remain
explicit and reviewed. Missing orders do not mean zero expected demand.

Factor comparison jobs validate their saved source evidence again before math.
New factor batches no longer inherit baseline order/job/group identifiers.
Monthly retries preserve the reviewed inputs; scheduled retries retain the live
owner authorization check. Original forecasts and order versions remain unchanged.

## Verification

- Full backend suite: 735 checks, 734 passed, one opt-in identity integration skipped.
- Ten new workflow tests exercise actual calculations, factor groups, source
  changes, order review, all three exports, stale revisions, retries, company/user
  isolation, permission loss and stopped scheduled workers. Saved-order picker
  contract regression also passed after the browser-discovered fix.
- All 249 interface tests, production build and identity-service type checks passed.
  Identity unit suite: four passed, one opt-in PostgreSQL integration skipped;
  schedule membership grants and denials tested with a mocked database.
- Final focused backend rerun after browser fixes: 36 passed.
- Disposable browser fixture: four customers, two products and 36 months of
  synthetic history; monthly update through current-order review and CSV download.
  Persian view checked at 390px, with internal table scrolling and no page overflow.
  Administrator schedule settings saved and checked; unavailable authorization
  stopped the draft. The second company's schedule list remained empty, and
  viewers had no schedule management controls.

No client records, real account permissions or provider credentials were changed.
AI responses were mocked; synthetic data tests demonstrate workflow correctness,
not an accuracy guarantee for the client's future demand.

## Next chunk

Finish useful API lifecycle operations and company-owned ingestion: SFTP, Odoo
18/19, Google Sheets and safe HTTP, with preview, mapping, validation, repeat-safe
sync and shared management UI. Then notifications and deployment acceptance.

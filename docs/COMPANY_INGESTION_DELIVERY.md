# Connected inputs and scheduled fetching

Implemented in authenticated company mode. The existing 8010 local demo is not
switched to company mode or replaced with these disposable tests. No client
account, source workbook, paid AI call or real external provider was used.

## Workflow

Data → Connections → Sales data. Admin selects HTTPS, SFTP, Google Sheets, Odoo 18
or Odoo 19 and the input type. Planner fetches → maps columns → reviews → saves.
Customers and orders use the existing Data tabs, directory and order books. A
saved receipt links directly back to Customers or Orders. Connection details,
setup, row review and schedules reuse shared fixed dialogs, forms and tables;
there is no dedicated CSS or inline style. Labels/errors have Persian entries.

Customer captures update by external ID or unambiguous saved name/alias. Existing
canonical names, product links and unmapped active status are preserved. Missing
buyers are not deleted; explicitly mapped inactive status can deactivate a buyer.
Identity collisions fail atomically. Odoo directory imports need product links
reviewed in Customers before those buyers can participate in forecasting.

Orders require owned sales history, known customer/product/unit pairs, stable line
references, delivery dates, ordered/delivered/cancelled quantities and known status.
Changed lines update absolute quantities, keep omitted orders and reset complete
coverage to unknown. A full-book replacement is explicit; an empty full export
requires separate confirmation. Complete coverage is never inferred. The planner
sets source-as-of and review-again dates. Gregorian/Persian source dates are explicit.
Unconfirmed orders remain distinct, not counted as confirmed demand by default.

All rows are validated; the review table shows the first 30 and declares that limit
when applicable. Worksheet/header changes require updating column labels again.
Directory/order-book changes invalidate an earlier review. Exact source hash,
mapping, calendar and import evidence are stored. Mutations and acceptance receipts
commit together; retry/crash recovery does not double-apply quantities or buyers.
The normal forecast wizard freezes a reviewed order snapshot for model results.
Fetching/saving a source never retroactively changes an existing forecast/release.

## Provider setup and limitations

- **Sheets:** enable Sheets API in the client's Google project; create a dedicated
  service account, share only the intended spreadsheet with it as Viewer, and add
  its JSON key in the admin connection dialog. Specify spreadsheet ID and whole
  worksheet name, not a partial range. Only spreadsheets.readonly is requested.
  The official google-auth library signs/authenticates; token destinations are
  fixed and key-file delegation/custom token URLs are ignored. This is a server
  service-account connector, not user Google OAuth or Drive discovery. Formatted
  values are captured as CSV and pass the normal explicit column/date/unit review.
- **Odoo 18:** HTTPS base address, database, selected company ID, read-only login
  and API key; JSON-RPC authenticate/execute_kw with search_read only.
- **Odoo 19:** HTTPS base address, database, selected company ID and read-only API
  key; JSON2 search_read only. Hosted API availability depends on Odoo's plan;
  this adapter is not a promise of free access on every Odoo subscription.
  Both versions paginate stable IDs, restrict allowed-company context and read
  customers/orders/Sales lines/products/units. They reject a changing two-pass
  export; this reduces inconsistency but is not an atomic remote transaction.
  Every exported order line needs commitment_date and a unique product default_code;
  absent dates/codes are not guessed. Units are preserved, never silently converted.
  UTC commitment times convert to the selected delivery timezone (default Tehran).
  Version 18 product_uom and version 19 product_uom_id are handled separately.
  Odoo imports customers/orders, not historical invoice/shipments data in this
  milestone. Use Sheets/HTTPS/SFTP for reviewed historical sales exports.
- Existing HTTPS/SFTP network, host-key, full-export and Keychain rules still apply.
  Credentials never appear in API responses, SQLite config or failure messages.
  Each company has separate credential namespaces, captures, books and receipts.
  Private targets require that company's operator allowlist; redirects/unsafe
  destinations are rejected and DNS is checked/pinned with hostname TLS verification.
  Captures cap at 20 MB; Sheets at 1M cells/500 columns, Odoo at 50k records per model
  and 120 seconds per export. Exceeding limits fails, not silently truncates.

## Schedules

Connection Details → Refresh schedule. Admin explicitly enables hourly, six-hourly
or daily fetching and confirms review-before-use. APScheduler checks due work every
five minutes, only while the company application is running. It is not a separate
always-on hosted worker. Claims persist across restarts/concurrent workers.

The saved owner is checked with the live identity service before and after fetching;
no stored cookie/token grants background access. Revocation, company mismatch,
changed connection settings or missing authorization pause/stop work. Pausing/editing
in flight discards new data. An identity outage fails closed. Retry uses durable
request IDs; unchanged content reuses its capture. Failures are visible in Details
and retry at the next due cycle or by manual fetch. A crash after claiming can skip
that interval; the next interval/manual fetch remains available.

Schedules prepare captures for human review. They do **not** apply old mappings to
changed data, change order coverage, start forecasts, send messages or publish.
Recurring forecast drafts are a separate existing, reviewed workflow. Public API
supports schedule configure/pause/check, within admin access; integration keys cannot
delegate themselves as the background human owner. Schedule owner internals are
not returned in public configuration.

## Verification and remaining work

- Full backend: **780 checks, 779 passed, one optional identity integration skipped**.
  The scheduler-lifecycle assertion now verifies all three company workers start
  and stop, including the new bounded capture worker.
- Focused connection/provider/ingestion suite: **45 passed**.
- Full interface suite: **254 passed**; production build passed. The pre-existing
  large-bundle advisory remains. No new page-specific stylesheet or inline styles.
- Disposable browser: four customers imported without duplicates/lost product
  links; four orders including an unconfirmed line reviewed and saved; direct
  navigation back to Customers/Orders; daily schedule saved; details-to-schedule
  opens one dialog, not stacked dialogs. Setup shows Sheets and Odoo 18/19 choices.
- Persian Odoo order setup at 390×844: fixed 358×680 dialog with internal scroll,
  no page overflow. Cancel returns focus. Second-company planner has its own
  unaccepted captures, no first-company schedule and no admin actions. No browser
  console errors observed. Test tab closed and temporary viewport reset.
- Staged secret scan passed. Its only baseline adjustment beyond the generated
  bundle filename was the line number of an already-reviewed synthetic test value.
  Temporary 8013 fixture stopped; original 8010 health check passed unchanged.

Synthetic provider tests cover real google-auth JWT creation/read-only scope,
fixed token target, both Odoo HTTP protocols and joins, versioned unit fields,
pagination/moving exports, Tehran midnight dates, exact cancellation arithmetic,
duplicate SKUs and sanitized provider failures. Company API/store tests cover four
customers, changed/full orders, coverage, aliases/IDs, Persian dates, stale review,
receipt interruption, restricted scopes and two-company isolation. Reviewed connected
orders reach real grouped model calculations and exportable demand without duplication.
Schedule tests cover concurrent claims, admin-only controls/versioning, revoked access,
mid-fetch revocation/pause, redacted ownership and no automatic acceptance/forecast.

Live provider-account verification is still required, as are hosted vault/Google/mail
setup, backup/restore, company-mode activation and receiving-system acceptance. No
client accuracy claim follows from synthetic tests.

Next chunk: complete input/forecast naming, archive/restore and revision navigation.
Then admin-only Slack/Teams/Telegram/eligible WhatsApp notifications with outbound
consent, scoped access and delivery history. Production provider credentials remain
a separate deployment acceptance step.

Primary references: [Google values API](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/get),
[Google service-account authentication](https://google-auth.readthedocs.io/en/latest/reference/google.oauth2.service_account.html),
[Odoo 18 API](https://www.odoo.com/documentation/18.0/developer/reference/external_api.html),
[Odoo 19 API](https://www.odoo.com/documentation/19.0/developer/reference/external_api.html).

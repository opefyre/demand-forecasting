# Company input connections — 9 October 2026

This records the earlier HTTPS/SFTP milestone. Customer/order, Sheets/Odoo and
scheduled-capture extensions are now implemented; see
[current ingestion delivery](COMPANY_INGESTION_DELIVERY.md). The verification below
belongs to the earlier milestone, not live-provider acceptance.

Implemented in authenticated company mode, not activated in the existing local
demo. Only sales/demand inputs are in scope. No client account, original spreadsheet,
saved demo quantity or paid OpenAI call was changed.

## Delivered workflow

Data → Connections → Sales data. An administrator defines a read-only HTTPS export
or SFTP file and confirms permission. A planner fetches it, reviews its columns,
customer/product grouping, units, sales meaning and Gregorian/Persian calendar,
then saves a new input version. The normal forecast wizard still reviews customer
orders and external factors before models run. Fetching never calculates or
publishes a forecast.

Connection setup/edit/archive/restore uses optimistic versions. Existing captures
remain recoverable after archiving. Each fetch has a receipt and safe error/status;
the same request ID returns the same receipt, and unchanged bytes within one
connection version reuse the capture. Stable source IDs recover interruption
between file capture and receipt save. Dataset acceptance is repeat-safe and binds
exact source IDs, content hashes and parent revision. Changed inputs cannot borrow
an old import receipt. Row-level corrections are not carried to a replacement file.

History and future-factor exports are supported. Future inputs must reference owned
sales history. Future values are assumptions requiring review, not automatically
fetched predictions or guaranteed improvements. Source calendars and shipment vs
customer-demand semantics are never inferred from the provider name.

## Access and network rules

- Company-owned SQLite/files and Keychain namespaces; no legacy store fallback.
- Admin: configure/edit/archive/restore. Planner: fetch/review within input scopes.
  Viewer/approver: no connection management or input reads/writes.
- Credentials never appear in provider configuration JSON, public responses,
  job payloads, validation errors or provider failure messages. Invalid public API
  requests now return field locations without echoing input values/context.
- HTTP: HTTPS on port 443, GET only, no redirects, proxy environment or URL
  credentials/query/fragment. Optional Bearer token is stored separately. DNS is
  checked and pinned; Host/TLS verification/SNI retain the original hostname.
- Private targets require an operator-controlled per-company environment setting:
  `DEMANDLAB_CONNECTOR_PRIVATE_TARGETS={"company_id":["erp.example:443","sftp.example:22"]}`.
  This does not grant other companies access to the same private destination.
  Loopback, link-local/cloud metadata, multicast and reserved addresses remain
  blocked even when allowlisted; every returned DNS address is checked.
- SFTP: exact absolute file path, supplied public host key, RejectPolicy, no SSH
  agent or discovery of machine keys. Password authentication only in this chunk.
  Size/time caps and before/after file stats reject changing exports.
- Nonempty inputs up to 20 MB, with expanded-XLSX caps. Redirects, HTTP partial
  responses and recognizable pagination are rejected. The administrator must
  configure a **complete export**, not a paginated application endpoint. Arbitrary
  pagination protocols cannot be inferred reliably.

Credentials currently require macOS Keychain. Other deployments need a proper
vault before activation; there is no plaintext fallback. Old version credentials
are retained in Keychain for recoverable configuration/receipts; archive stops
future fetches but is not a credential purge. Rotate/revoke access at the source
when retiring an account. No real credentials were used for tests.

## Verification

- Full backend suite: 760 checks, 759 passed and one optional identity integration
  skipped. No backend failures.
- Focused scoped API/store/engine run: 55 checks passed before final documentation.
- Full interface suite: 250 checks passed; production build passed. The existing
  large-bundle advisory remains; no new dedicated stylesheet or inline style.
- Provider tests include an actual encrypted Paramiko/SFTP socketpair exchange,
  changed-host-key rejection and a changing remote file; no client server required.
- HTTP mock transport checks DNS pinning/TLS hostname, unsafe destinations,
  redirects/partial data/pagination/size, sanitized errors and credentials.
- API checks cover two companies, roles, stale edits, archive/restore, repeated and
  concurrent pulls, capture/receipt crash recovery, exact-source acceptance and
  immutable parent preservation. Fetched history reaches real grouped models,
  reviewed orders and exportable demand for four customers/two products.
- Disposable browser journey: create HTTPS connection → fetch → review columns and
  calendars → validate → save. Saved receipt shows Inputs ready/View saved data.
  Persian SFTP setup checked at 390×844: 358×680 fixed dialog, internal scroll,
  no page overflow; cancel/focus return works. No browser console errors observed.
- Switching to the second company's planner shows only its connection; setup,
  edit and archive controls are absent. The first company's accepted inputs remain
  separate. The temporary browser tab and fixture server were closed afterwards.
- Staged secret scan passed. Three reviewed false positives were a translated
  password-field label and disposable invalid URL/password test fixtures.
  Existing 8010 demo health check passed without restart or reconfiguration.

This is synthetic acceptance, not evidence of client forecast accuracy or a live
provider-account verification. Existing 8010 demo remains untouched; the disposable
8013 test server is stopped after acceptance.

## Remaining work, in order

1. Remaining source/dataset/forecast naming/archive/revision presentation lifecycle.
2. Admin-only outbound notifications/consent/history; deployment vault, Google/mail,
   real provider setup, backup/restore and company-mode activation acceptance.

Public OpenAPI now covers **140 v1 operations**, including nine new connection and
ingestion operations. Full useful-route coverage remains unfinished; see
[route inventory](PUBLIC_API_COVERAGE.md) and [active plan](PUBLIC_PLATFORM_DELIVERY.md).

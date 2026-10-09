# Connected order exports — 28 September 2026

3 October follow-up: saved connections can now be reused across compatible monthly
forecasts, including a forecast with no saved orders yet. Compatibility checks exact
customer/SKU series, unit and sample/real classification. New connections start with
manual checks. The source connection and its schedule remain independent.

The review uses the latest source snapshot and, when present, the target's latest
snapshot. Saves retain source snapshot/hash evidence; concurrent source/target
changes require a fresh review. Exact retries return the saved result even after
later revisions, while changed content with the same request ID is rejected.
Cross-run refresh validates fulfilled/cancelled revisions against the source book
and shows before/after changes. Customer coverage and source validity dates remain
explicit review inputs. A narrower or longer forecast still requires period review.

391 backend / 55 frontend tests and build pass. New isolated integration tests
exercise reusable connection → refresh → review → real demand routes → save →
JSON export, proving A13 + B8 + C5 = 26 still to serve with A2 already fulfilled.
Scope mismatch, stale source, concurrent target and altered retry cases pass.
Browser verified the setup dialog on the existing demo; live configured reuse and
mobile acceptance remain pending. Real-client ingestion is not verified.

Implemented: an administrator can connect one local full-order-book export per
forecast, using a previously saved order-file mapping. The file is checked manually
or every 15/60/360/1440 minutes while the app is running. Pause/resume and settings
survive restarts. Existing APScheduler, SQLite, source storage, import validation
and demand revision calculations are reused; no new package or paid service.

## Workflow

1. Import and save an order file through the normal order review.
2. In Sales forecast, choose **Connect order export**. Select an approved local
   folder, exact filename and interval. Export the full order book, not a delta.
3. Checks retain immutable source bytes and validate columns/line quantities.
4. **Refresh & review** loads the latest saved customer/order version and new file
   into the normal before/after review. Confirm dates, mappings and changes.
5. Save creates a new order-aware demand snapshot; the baseline stays unchanged.

No automatic approval, publication or freshness extension. A changed filename is
not evidence of a current order book. Old as-of/valid-until dates remain until the
reviewer changes them. Full-file omission is a removal, shown before saving; empty
files require manual review instead of automatic replacement. Stable line references
are required, and existing cumulative fulfillment/cancellation safeguards apply.

Failed checks cannot present an older candidate as current. Changed headings require
remapping. Exact unchanged bytes reuse the same staged source. Save retries reuse
the original snapshot; stale concurrent saves are rejected by the existing store.
The user can replace a connection without deleting historical snapshots/sources.

## Verification and remaining limits

- 388 backend tests, 55 frontend tests and production build pass.
- Isolated integration tests exercise file refresh → mapped review → real demand
  calculation → saved version → retry, including fulfilled/cancelled quantities.
- Failure/empty-file/headings/path checks, unchanged-source reuse and persisted
  pause are covered. Original order snapshots remain unchanged.
- Browser: connection dialog opens on the preserved demo; spacing inspected/fixed.
  Complete configured-folder and mobile browser acceptance remains pending.
- No live client connector or watched folder was enabled. This is local-file
  ingestion, NOT authenticated inbound ERP events or a vendor ERP connector.
- Current setting is per forecast and admin-only. Cross-run connection reuse is
  implemented as described above. Owner notifications, status-code translation, actual client-system credentials,
  archived-event replay and downstream acknowledgements remain unfinished.

Next major delivery: combine several reviewed drivers (Iran inflation, chosen FX
market, global supply and customer events) in one scenario, compare methods on the
same historical periods, and expose a clear before/after result with source dates.
Client export contract and real ingestion acceptance remain required before launch.

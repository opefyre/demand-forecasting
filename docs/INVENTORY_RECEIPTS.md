# Expected deliveries in stock planning

Implemented 21 September 2026. Supply → Inventory supports reviewed delivery
schedules for an immutable stock snapshot. Uses existing SQLAlchemy/SQLite,
React/Radix and Pint; no new dependency or forecasting algorithm.

## Calculation and review

Each line has a unique order-line/delivery reference, exact product code,
outstanding quantity, original unit, usable-from date, purchase/production type
and confirmed/unconfirmed/cancelled status. Split deliveries need distinct refs.
Dates must follow closing stock. A note and confirmation that receipts are not
already included in stock or other lines are required; software cannot prove
external orders have not already been received.

Only confirmed receipts enter the result. Excluded, unmatched and out-of-range
lines stay visible in the full-schedule disclosure, deliberately independent of
product/period table filters. The saved run's daily/weekly/monthly frequency
defines buckets; next-period-boundary arrivals enter the next period. Missing
product demand periods are rejected rather than absorbing receipts silently.

Closing = opening + included receipts − demand. Negative balances carry forward
as unmet demand, not lost sales. Unknown stock/status stays unknown with receipts;
held stock stays unavailable. Positive period-end stock does not prove continuous
service; the UI warns about shortages before a delivery arrives. Supplied
production completions are not claimed to be capacity-feasible.

Pint/reviewed unit definitions convert at the receipt usable date. Missing or
expired conversion rules block the result. Conversion quantities and evidence are
retained. Real/sample mixing is rejected. Schedules inherit stock classification
and cannot be applied to another snapshot. Approved-plan quantities use the
existing shared resolver; forecasts, stock snapshots and plans remain unchanged.

## Versions and access

Saves are immutable with parent, timestamp, note and server-supplied actor (or
Local session). Select one version; versions replace, never sum with, each other.
Branches are allowed without a mutable latest pointer. Request identifiers make
identical concurrent retries return one version; changed payloads are rejected.
Viewer/reviewer writes are denied by existing access controls.

## Evidence

37 targeted receipt/inventory/unit/access tests pass, including six new receipt
tests: retry/concurrency/restart, unchanged versions, period boundaries, excluded
receipts, unknown stock, invalid values, incompatible units, API save/select/reset,
classification and existing approved-plan behavior. Frontend build passes.

Browser-created sample `144526e97ed952dc812243e3880bcb7f`, snapshot
`65dddb08a3c64cf7a791c47d164b74ca`, forecast `431fed798551`: PKG-KRAFT-120,
September 2026, 50 opening + 200 receipts − 183.7 displayed demand = 66.3 closing
(unrounded internally); no-receipt deficit 133.7. Saved schedule survives restart.
Browser testing caught/fixed a saved-run frequency-path mismatch; tests now use
the actual `run_settings.frequency` structure.
Final browser checks passed at 1280×850 and 390×844 for the affected stock result
and receipt-entry controls. Spacing/alignment defects found during review were
fixed. Returning to No future receipts restores the 133.7-tonne shortage, without
changing demand. The browser error log was empty. This is bounded visual and
interaction verification, not full keyboard or assistive-technology acceptance.

## Reviewed file import — demo checkpoint

CSV/TSV/JSON/Excel upload, worksheet/heading selection, positional mapping,
explicit type/status meanings, validation and confirmed save are now implemented.
Server-side reparse, source hashes/cells and mapping evidence accompany the saved
schedule. Six import tests and the full 222-test Python suite pass; 16 JavaScript
tests and the frontend build pass.

Browser-imported `sample_data/receipts_demo.csv` saved version
`821ad3776d465f419c08378221ebcc93`, **Demo · imported deliveries**. The confirmed
200-tonne purchase is included and the unconfirmed 50-tonne production completion
excluded, yielding the same 66.3-tonne September closing balance described above.
Affected laptop/phone views were checked. See DEMO_GUIDE.md for the walkthrough.

## Open work

Scheduled receipt/ERP ingestion, receipt lifecycle reconciliation, warehouse-level
transfers, feasible production, service targets, intra-period availability and
replenishment policies remain open. Form drafts do not yet recover after closing,
navigation or session expiry. Saved import mappings are retained as evidence but
do not yet have a reusable mapping selector. Full keyboard/assistive-technology and multi-user
deployment acceptance remain open. No client order, stock date or quality meaning
has been invented. This is not production certification.

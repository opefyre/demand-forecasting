# Reviewed order updates — 23 September 2026

Sales/demand scope only. This extends reviewed file/JSON ingestion; it is not an
automated ERP connector, approval workflow or machine-to-machine API release.

## User flow

Forecast → Update orders starts from the selected saved version, retaining
customers, history links, orders and commitments. Review confirmation and note
are cleared; dates are not silently renewed. A complete saved order book offers:

- **Only changed order lines**: replace matching references with complete current
  line values, add new references, retain all other lines.
- **Full order book**: replace the list; omitted lines are removed in the new
  version and shown in the preview. Current-month fulfilled lines cannot disappear.

The review shows changed fields before/after and the recalculated demand. Save
creates an immutable new version with actor, source/cell hashes, parent snapshot
and a change record. Reopening an old version is supported; updating it after a
newer version exists is rejected rather than silently overwriting newer work.
Continue is blocked while files are reading or an upload has failed.

## Existing session-protected API

POST `/api/sales/validate` previews without saving a demand snapshot. POST
`/api/sales/inputs` saves the reviewed version. Both accept:

```json
{
  "base_snapshot_id": "saved-snapshot-id",
  "order_mode": "changes",
  "request_id": "unique-stable-id-for-this-submission",
  "inputs": {"...": "complete DemandInputs object; orders contains changed lines"},
  "imports": {"...": "optional existing role/file mapping configuration"}
}
```

The example is an envelope sketch, not a runnable payload. `/api/sales/schema`
and customer/order templates expose the supported fields. Customer/commitment
imports still replace their complete lists, not partial events. Existing role,
session and CSRF protections apply; there is no new authentication bypass.

## Rules and limits

- `reference` identifies a delivery line, not just an order header. For multiple
  systems, supply namespaced stable references such as `ERP/order/line/schedule`.
  No fuzzy cross-source duplicate detection is claimed.
- Quantities are cumulative current values, never positive/negative deltas.
  Duplicate references within a submission are rejected. The same reference
  cannot be reassigned to another customer, SKU or unit in a revision.
- Cancelled units consume no forecast; fulfilled units remain counted. A fully
  cancelled line must account for every unit as fulfilled or cancelled.
- A changed due month moves an unfulfilled line once. Already fulfilled demand
  cannot move months or decrease through this interface; split the remaining
  delivery into a new reference. Corrections/returns need a separate reviewed
  correction policy and are not yet implemented.
- Changed lines require a previously complete order book. The user must verify
  the combined book is current, including all intervening changes. An old or
  incomplete source is not made fresh merely by uploading a partial file.
- Save checks the parent is still the latest version for that forecast inside
  the same SQLite write transaction. Stale saves return HTTP 409. Replaying the
  same request ID and content returns the original version; changed content
  under that ID is rejected. Retries never add quantities again.
- Existing snapshot exports remain draft, full-snapshot CSV/Excel/JSON. This does
  not add downstream acknowledgements, publication or background synchronisation.

## Evidence

`tests/test_order_revisions.py`: preview has no snapshot writes; changed-line file
mapping retains other lines and source evidence; higher quantities and cancellations
consume the baseline once; moved deliveries leave no duplicate in the old month;
duplicate/reassigned references rejected; fulfilled-demand protection; full-book
removal preview; immutable parent; idempotent retry; concurrent writers have one
winner; incomplete/backdated updates rejected.

Browser sample: 12 customer/SKU relationships and 8 orders retained. Changing one
220.482-tonne order to 250 ordered / 20 cancelled produces 230 open demand, with
the 183.735 model estimate fully consumed and other lines retained. Preview only;
the saved sample was not replaced. Laptop and narrow-screen layout checks accompany
the implementation checklist.

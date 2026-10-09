# Order-aware demand sign-off and planning exports

3 October 2026. A bounded sales/demand release feature, not full client acceptance.

## User workflow

**Sales forecast → Export demand → For planning.**

1. Name the receiving system and confirm whether it already contains the orders.
2. Review monthly export quantities; expand customer/product/month detail if needed.
   This covers all rows, not just the dashboard's current filters.
3. Submit a fixed version for review.
4. A different signed-in company reviewer/admin approves it.
5. Download approved Excel, CSV or JSON. No external system is contacted.

The ordinary draft download remains available separately. Both use the existing
demand calculation and exporter, not a second forecasting algorithm.

## Quantities and approval

- Receiver already has orders: export **remaining expectation only**.
- Receiver expects combined demand: export **open orders + remaining expectation**.
- Already fulfilled quantities never enter either planning quantity.
- Customer/SKU/month matching occurs before totals. The A=16 booked, B=8 expected,
  C=3 booked+2 expected acceptance case exports 10 remaining or 29 combined, not
  an aggregate max and not 42 from adding orders to the entire forecast.
- Submitted/approved versions retain exact order snapshot, forecast and input hashes,
  selected receiver/mode, quantities, engine, method, dataset and factor scenario.
- Approvals cannot edit quantities or switch mode. A policy change requires a new
  reviewed version. Approved downloads cannot override the mode through a URL.
- Local sessions permit **demo approval only**, explicitly confirmed and labelled
  `demo_approved` in every exported row. This is not independently verified company
  sign-off. Company reviewers cannot upgrade local-demo submissions to real approvals.

## Guards and reuse

Reuses DemandStore's SQLite database, the existing order-aware engine, Decimal,
Pydantic, authentication/CSRF middleware, React/Radix/Phosphor and CSV/openpyxl
exports. No package, model, provider or subscription added; no OpenAI call.

Shared database transactions serialize submission/approval/export source guards
with order updates. Exact submissions/approval retries do not duplicate versions.
Changed inputs, newer order reviews, expired source/commitments, missing history,
unmapped customers, unresolved warnings and closed-month source dates block sign-off.
Monthly closure checking currently uses UTC, like the saved sales-input engine;
company-calendar/Tehran business-boundary acceptance remains a separate requirement.

Newly approved versions replace older planning downloads for that receiver/forecast,
including changes to the receiver's order-consumption mode. Old records remain
inspectable and numerically unchanged. A newer pending draft does not revoke an
otherwise valid approved version. A newer approved version cannot be displaced by
approving an older pending draft. An old approval never refreshes expired inputs.

Exports carry release/version, receiver/mode, approval/actor/time, order/forecast
hashes and dataset/method/engine references. CSV/Excel formula-like strings are
neutralized without changing saved identifiers. JSON retains raw identifiers.

## Evidence

- 13 focused release tests: mixed-customer math, fulfilled exclusion, residual/
  combined modes, independent reviewer and local-demo separation, stale/changed
  input guards, expiry and closed months, safe retries, policy replacement,
  immutable history, persistence/API and CSV/Excel/JSON agreement.
- Reviewer/admin-only approval permission test added to the authentication suite.
- 426 backend / 61 frontend tests and frontend build pass. Existing dependency/
  resource/bundle-size warnings are not claimed resolved.
- Browser desktop/390px submission → demo approval → saved review reopening verified.
  Checkbox/field spacing, dialog scroll reset and mobile quantity-column priority
  adjusted from actual browser inspection.
- Separate synthetic order review `bb2099e0b5930871b82ed78d85c3623d` on factor run
  `0ea4a37ff8ef`: 14 customer/SKU relationships, two orders, 28 October/November rows.
  Release `aed6a0c394afa0c54fd3f7fd5d68535f` exports 2,259.3952281996612 tonnes of
  remaining expectation; 168 open and 20 fulfilled tonnes are not in that quantity.
  Excel/JSON agreement verified. The original baseline/order snapshots are retained.

## Remaining big work

One real-client monthly cycle: agreed sales target and order semantics, actual
ERP/export schema, IDs/units and full customer coverage, longer actual history,
approved Iran FX/CPI definitions and acquisition, real company reviewers, then
receiver reconciliation and a read-only connector plus controlled outbound adapter.

No ERP transmission, acknowledgements/retractions, real-provider licence acceptance,
client accuracy guarantee, live identity-provider acceptance, multi-tenant isolation,
review-return/comment workflow or Persian-calendar sales handoff is delivered here.
These remain distinct from the completed local sign-off/export functionality.

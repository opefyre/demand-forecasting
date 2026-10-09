# Order-aware factor comparisons — 24 September 2026

## Delivered slice

In a baseline forecast's Scenarios view, choose a linked-factor scenario and
**Compare with orders**. The latest saved baseline customer/order review is reused
without re-entry. A centred comparison shows open orders, remaining expectation,
combined totals and change by month. Customer and SKU filters intersect; All resets
the population. The same original order book is used on both sides.

After an explicit review, **Save scenario draft** creates a separate order snapshot
for the linked forecast. Existing orders, baseline inputs and approvals are untouched.
All customers/SKUs are saved; filters are display-only, clearly stated in the review
checkbox. Export links explicitly export the full scenario, not the filtered subset.
Excel combined-demand and CSV residual-forecast use existing export services; JSON
is available through the existing API. Both modes exclude already delivered quantity
from the quantity sent to downstream planning.

This is not production, stock or purchasing planning and does not send anything to
the client's MRP. Draft creation is not publication approval.

## Safeguards and provenance

- Only linked-factor scenarios with the exact parent forecast qualify in this slice.
- Match series, months, units and real/sample classification; validate customer/SKU
  relationships against the target forecast's metadata. Missing customers remain
  visible as unknown, not zero. No automatic remapping or unit conversion.
- Verify the baseline run hash recorded in the source review. Carry customer list,
  order lines, commitments, source date, expiry and completeness unchanged.
- Record source snapshot ID/hash, original source evidence, both run provenance,
  review token and the current saving actor. No approval identity is inherited.
- Preview/save reject an older source review; changed forecast or review invalidates
  the token. Transactional guards reject an intervening source or target order review.
- Identical retries return the existing saved draft; conflicting retries fail.
- Unknown/expired order feeds, overdue orders, unmapped series and unresolved demand
  block saving/export through the existing demand rules. The comparison may still
  show available quantities with unknown totals and warnings.
- Total = delivered + open orders + remaining expectation. Current-month fulfillment
  consumes the estimate; cancellations and confirmed complete commitments preserve
  the existing reviewed rules. Orders above the estimate are not added twice.

## Verification

342 backend tests and 45 frontend tests pass; production build passes. Existing
dependency/resource and build-size warnings remain. Added checks cover partial
fulfillment, cancellation, complete commitments, customers/months without orders,
stale feeds, unknown demand, mismatched runs, source/target update races, retries,
draft exports and filter reconciliation. Dashboard-skill guidance influenced the
same-population comparison, null handling and compact paired-value table; the
existing application/components were preserved, not replaced with a new shell.

Browser acceptance: open comparison; filter Demo A then Demo SKU 1 (orders exceed
both model estimates); reset to All; explicitly save the separate draft; verify
success/export links. Desktop and 390px layouts inspected, with narrow tables
scrolling within the modal rather than widening the page.

Synthetic demo only:
- Baseline forecast: `58df6ab41b1f`; factor scenario: `4cb719fe31fb`.
- Source order review: `37d0646991260d00a76812640c96d2a4`.
- Saved scenario review: `74bbeb8eecb117625410f5ea4747661e`.
- 3 customers × 2 SKUs × 6 months = 36 rows; four synthetic order lines.
- Open orders: 203.388 tonnes, unchanged.
- Baseline combined demand: 2268.199824 tonnes.
- Scenario remaining expectation: 2067.392876 tonnes.
- Scenario combined demand: 2270.780876 tonnes.
- No delivered quantities in this demo; separate automated tests cover fulfillment.
- Orders as of 24 September, expire 1 October 2026. Do not silently extend expiry
  when replaying later: refresh/review sample orders through the usual workflow.

Reproduce saved checks with `scripts/verify_order_comparison.py --verify
74bbeb8eecb117625410f5ea4747661e` while the local server is running. Client forecasts
and the older demos were not edited. These results prove workflow/reconciliation,
not accuracy on real client sales.

## Next bounded task

Expose this same read/preview/reviewed-save workflow to the assistant, using the
existing deterministic services and model routing. A plain-language scenario request
should resolve the right baseline/order version, present the comparison and request
approval before saving; never mutate orders from chat. Test ambiguity, stale versions,
retries, cancellations and scope restrictions without a live key first. Live OpenAI
acceptance still needs the user's locally configured key and provider eligibility.

Still outside this slice: order-aware comparison across arbitrary independent runs,
per-filter comparison export, independently verified GSCPI release dates, actual
Iranian CPI/FX provider access, longer client history/orders and approved MRP delivery.

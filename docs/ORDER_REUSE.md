# Reuse orders when the forecast period changes

24 September 2026 — sales/demand only. No paid AI requests or new dependencies.

## Implemented

On a calculated forecast without its own order review, **Use saved orders** offers
compatible reviewed sources. Matching is exact: monthly frequency, series IDs,
customer/SKU identities, units and sample/real classification. Unlabelled or
different customer series are not inferred or remapped automatically.

A centered review shows order-source dates, all forecast months, added months,
confirmed open quantities, remaining expectation and total demand. Open order lines
outside a shortened/moved horizon are separately disclosed. They remain in the
saved order book but are not included in that forecast's totals or exports.

The planner must confirm that the source includes all known orders for every
displayed month, including added months, and acknowledge any excluded orders.
This is an explicit coverage declaration, not proof that an upstream ERP feed is
complete. No-order months retain the mathematical forecast; they are not zero demand.

**Save demand draft** creates a separate snapshot and opens the existing filtered
sales dashboard. All customers/SKUs are saved, even if the initiating assistant
request selected one customer. Customer filters remain presentation filters.

## Preserved safeguards

- Existing deterministic order-consumption calculation and source validation reused.
- Original orders, fulfillment, cancellation, commitments and original forecasts unchanged.
- Source date and expiry preserved. Reuse never makes stale orders fresh.
- Missing demand, stale sources, incomplete feeds and overdue orders block save.
- Source forecast hash and latest source/target order versions checked again on save;
  the existing transaction guard protects competing reviews.
- Exact review-token match, explicit coverage confirmation and stable retry ID required.
- Draft only: no copied publication approval, no ERP/MRP transmission.
- Future factors are not extended or invented here. This workflow uses an already
  calculated target; the forecast input checks still govern whether it can be run.

## Verification

Ten targeted reuse tests cover expansion, shortening, known orders above forecast,
customers without orders, missing customer forecasts, cancellation/fulfillment,
expiry, mismatched identities/units/classification, unlabeled series, changed
forecasts, competing source/target versions, explicit approval, retries and exports.
Final regression: 365 Python tests and 45 JavaScript tests passed; production
frontend build and diff whitespace checks passed. Python reported unclosed SQLite
connection ResourceWarnings at shutdown; no test failures.

After explicit user approval, the prepared synthetic ten-month forecast completed
as run `c32ed4959808`. Browser review selected the original order book, displayed
four added months, required the coverage checkbox and saved separate draft
`5611447fffe7759d41f063d965c14538`. Demo A stayed selected after save.
The centered modal was inspected at desktop and 390 px widths; its table scrolls
sideways on mobile, the confirmation/save actions are reachable, and the page has
no horizontal overflow. The temporary viewport override was reset.

Read-only `scripts/verify_order_reuse.py c32ed4959808` reconciled all 60 rows across
10 months, including all six combinations of JSON/CSV/XLSX and combined/residual
demand exports. Confirmed open orders: 203.388 tonnes. Total demo demand:
4,038.1525484952103 tonnes. Source order records, dates and hash stayed unchanged;
all exports remain drafts. No OpenAI call was made for this acceptance check.

## Next task

Test the complete client-like import journey: historical sales, customers,
current orders and dated factors through to
customer/SKU/month exports. Record missing inputs and correct workflow failures
before expanding connector coverage. Live Iranian CPI/FX still requires a chosen
market, permitted source and useful historical data. Broader release acceptance
and production deployment remain unfinished.

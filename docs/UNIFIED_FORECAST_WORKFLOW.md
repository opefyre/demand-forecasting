# Unified forecast workflow — 7 October 2026

## Delivered

New forecast has five steps: sales history, factors, customers/orders, methods,
results. Existing import/mapping and live-factor review are retained. Customer
lists, order files, the customer directory and compatible saved order books are
available before fitting. Customer-confirmed complete monthly requirements are
optional, not a second required workflow.

`forecast_orders` reuses an input-only context: dates and identities, no fitted
or fabricated numbers. Existing validation checks customers, products, units,
order statuses, fulfilled/cancelled quantities, unique delivery references and
the planning calendar. The reviewed input version is bound to a dataset/context
hash. Changes or expiry invalidate it.

Every selected model job receives that version's identifier. Before the worker
publishes a result it applies existing order reconciliation, saves a run-bound
review version and includes its identifier and combined-demand summary in the
result. Its evidence hash includes worker/job identity. The ordinary result
page loads that saved review directly. Combined demand is also a distinct sheet
in the model workbook; original model numbers are not overwritten.

The assistant prepares the selected horizon/method and hands off to this same
wizard rather than calculating first and asking for orders later. Existing order
update actions remain for changing a previously calculated forecast.

## Boundaries

This changes input workflow and publication orchestration, not model equations.
Orders currently consume/override the calculated baseline at the exact
customer/SKU/month level; they are not yet learned statistical features. Future
engine work can improve order-arrival modelling and forecast accuracy separately.

Monthly Gregorian and Persian calendars use the existing calendar rules. This
combined customer-order flow is monthly; weekly/daily order reconciliation is
not claimed. Real forecast accuracy still needs adequate real client history.
The remaining whole-app framework migration is not closed by this change.

## Verification

- Isolated synthetic public-route tests cover two real methods, input review
  before any fit, orders above forecast, partial orders, customers with no orders,
  new customers with no history, unknown orders, blocked exports, stale input
  reviews, guarded order reuse and worker publication hashes.
- Existing sales/order/calendar/job/factor tests remain applicable.
- Assistant action tests use mocked responses: no OpenAI calls.
- Browser checks use separate synthetic results and reuse copied demo orders;
  original inputs and earlier results are not changed.

Final checks: 171 interface tests and production build; 26 unified workflow and
assistant tests; 81 existing sales/order/calendar/jobs/factor tests pass. Tests
mock assistant responses and do not invoke OpenAI. Model methods were not edited.

Browser demo reuses existing synthetic history/factor assumptions and a copied
four-line order book for two customers/four customer-product pairs over ten months.
Both methods receive input review `b481534ee1f9b4b4ced99686318234ea`.

| Method | Run | Combined demand | Open orders | Rows |
| --- | --- | ---: | ---: | ---: |
| Ridge + factors | 43110e88adff | 1032.0090052891799 t | 93 t | 40 |
| Elastic Net + factors | ca2a0604c2e8 | 1041.1936028305486 t | 93 t | 40 |

The API summary equals the sum of the customer/product/month rows; both saved
demand views permit draft export. These are synthetic, assumption-based figures,
not real-client accuracy evidence. The input review remains before fitting.
The Persian mobile method screen has content width equal to the 390px viewport.

# Private sales workflow acceptance — 10 October 2026

## Verified in the real private cloud workspace

Created one separate **Tehran · Sales workflow comparison** forecast through the
existing five-step wizard. Reused the fictional Tehran history and reviewed order
book: 804 history rows, five customers, four products, 18 customer/product series
and 79 order lines. Existing saved forecasts were not replaced or archived.
The horizon is October 2026–March 2027, Gregorian months and tonnes.

- Recent average and Same season both completed under that single forecast name.
  They are selectable separately and appear together in the comparison chart/table;
  their estimates are not added together.
- The comparison CSV has six monthly rows. Its method totals are 4,090.989666666667
  tonnes (Recent average) and 3,845.19 tonnes (Same season), matching the displayed
  results after rounding.
- Customer, product and month filters apply to both methods. For **Aftab Printing /
  FOOD-110 / November 2026**, Same season gives 26.34 tonnes and Recent average gives
  26.494666666666664 tonnes. The Recent average dashboard shows zero confirmed open
  orders and 26.49 tonnes of expected demand. No orders does not imply no demand.
- The filtered demand-view CSV contains exactly that one monthly result and the same
  unrounded quantity, with zero open orders/fulfilled quantities. Changing the
  interface to Persian did not change the business identifiers or exported values.
- The mobile cloud screen was observed at 390 × 844. Page width remains 390; the
  shared new-forecast dialog fits within it, approximately 358 pixels wide, with
  approximately 44-pixel inputs. Tables scroll within their own region instead of
  widening the page. Persian results, mobile navigation and dialog closure were
  checked in the browser.

These are fictional acceptance scenarios, not measured accuracy on client data.
No AI request, provider credential setup, live invitation or approval release was
performed. Other Cloudflare services, permissions and numerical engine deployment
were not changed.

## Issues found and fixed

1. The forecast order step rendered 79 full edit forms simultaneously. It now reuses
   a compact **OrderTable**, also used by Data → Orders. Ordered, fulfilled,
   cancelled and status values remain visible. Editing expands only the selected
   row using the existing global form/grid/action components.
2. Unapplied order edits could be skipped. Continue is disabled until changes are
   applied or cancelled, including the second Continue action when revisiting
   previously reviewed inputs. Adding then cancelling an order does not add a zero row.
3. Back navigation could leave the order step during asynchronous validation.
   The wizard now includes child order-validation activity in its working state;
   Back and dismissal remain blocked while that operation runs.
4. Confirmed and Unconfirmed status labels lacked Persian translations. Both are
   now translated centrally; submitted status codes and business names stay intact.

The separate loopback-only company fixture verified add/apply/cancel, review and
linked customer/product/unit preservation. A 15-tonne order with two tonnes already
fulfilled and one cancelled remains correct after applying. Cancelling a proposed
999-tonne edit preserves the 15-tonne original. No new CSS or inline appearance
styles were added; the shared table, spacing, fields, actions, fonts and brand colour
remain the visual source of truth.

## Automated verification

- Interface: **278 passing tests**, including large order books, shared Data/wizard
  table structure, permission-aware actions, pending edits, validation navigation
  and Persian statuses.
- Cloud controllers: **46 passing tests**.
- Cold cloud API/workflow/state suite: **21 passing tests**; includes grouped
  models, partial orders, checkpoint restoration, independent approvals and exports.
- Company sales/factor review suite: **23 passing tests**; includes frozen,
  company-scoped factor inputs, Persian month boundaries, wrong-company denial,
  unknown coverage, independent review and rejection of future-observation leakage.
- Production build and whitespace checks pass. Existing bundle-size and package
  directive warnings remain; they are not new failures.

Published only `demandlab-forecast-edge`, version
`cdadff6f-b1f1-4e2f-9696-f70b36f766ab`. Its owner-only/closed-access settings and
identity/storage/engine bindings are unchanged.
The final shared Data order table displays all 79 rows without 79 input forms;
Persian Confirmed/Unconfirmed statuses were verified in the real cloud screen.
The unchanged local demo's `/api/health` returns 200; anonymous cloud company
customer access returns 401.

## Still open — do not treat this as full-product acceptance

- The live cloud workspace currently reports **no connected monthly factors**.
  This comparison therefore did not use a live inflation/exchange/supply feed.
  Factor-engine behaviour is tested with controlled data, not certified against a
  real provider here. Connecting and verifying appropriate cloud feeds is next.
- Full cloud correction/revision, monthly-update, reload/error and all release-export
  UI journeys still need a combined acceptance run. Their automated coverage does
  not replace that browser walkthrough.
- Independent approval is exercised in isolated role tests. The owner-only cloud
  cannot demonstrate a real second-person approval until that access is explicitly
  authorised; do not bypass self-approval checks or add another live user silently.
- Client-specific accuracy, performance across larger histories and a multi-person
  pilot remain separate acceptance gates. Do not open public access automatically.

## Next substantial task

Connect and verify the cloud's relevant live factor feeds, including dated history,
freshness, geographic/unit coverage and reviewed future assumptions. Then run the
combined correction → updated orders → factor-aware grouped models → review/export
journey in English and Persian, keeping live access owner-only.

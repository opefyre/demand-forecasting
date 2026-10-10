# Unified order updates — 10 October 2026

## Delivered

- Manual Update orders and the assistant's order-import action use the same
  customer/order editor as the forecast wizard, inside the shared fixed dialog.
  The forecast or chat remains mounted behind the overlay; no replacement page.
- Inline editing, customer addition, optional order/commitment imports, full-book
  versus changed-line handling, coverage and source dates remain available.
  Existing customer relationships and monthly commitments are preserved.
- Review the per-customer/product/month calculation before explicitly saving a
  revision. Editing invalidates the receipt; save carries the review token,
  original revision, request ID, import evidence and connected-source guard.
- Read-only permissions, concurrent-revision rejection and original snapshots
  remain authoritative in the existing API. No forecasting mathematics changed.
- Reused global Modal/Panel/Stack/Grid/Field/Actions/Disclosure/Table components.
  No new CSS, appearance overrides or authored inline styles. Quantities, units
  and authored controls use English/Farsi; imported identifiers stay unchanged.
  Results paginate rather than dropping rows beyond the first page.
- Before/after order-change evidence remains available in a shared, collapsible
  receipt, including removed lines; longer change lists paginate.

## Verification

- Production build, 317 interface tests, 40 focused backend tests and 53 cloud
  service tests passed. Existing bundle/deprecation/database-close warnings remain.
- Disposable local company fixture: real stores/APIs/calculation, four customers,
  two products and 36 months of synthetic history. Identity, providers and AI are
  mocked; no OpenAI calls or real provider refreshes.
- Changed Mehr ordered quantity from 16 to 30: 28 open + 2 fulfilled = 30;
  no calculated residual added twice. Pars, with no orders, retained expected
  demand of 5 tonnes per month. Review/cancel left the original unchanged.
- Explicit save created an order revision: total outlook changed from 135 to
  149 tonnes; open orders from 20 to 34; expected residual stayed 113.
- The second company's orders retained their original 16 tonnes. Viewer order
  write returned 403; its interface offered no draft/order-update controls.
- Incomplete order coverage displayed unknown residual/final totals and the
  export-blocking warning, not zero demand. This preview was cancelled.
- Persian 390×844: RTL, document width 390px, dialog 358×680 before and after
  review; internal scrolling. Desktop uses the same dialog/table framework.
  Local screenshots under `docs/screenshots/shared-order-update-fa-*.png` are ignored.

## Deployment and boundaries

Only `demandlab-forecast-edge` updated: version
`77488f3d-d4ba-4cb2-a242-27cea66b84eb`. Owner-only access/MFA, engine sleep,
identity/storage/engine deployments and other services remain unchanged.
Unsigned company API returns 401; the independent local demo `/demand` returns 200.
The signed-in cloud owner opened the migrated editor with the existing saved
orders, including cancelled/unconfirmed lines. Warm opening was observed complete
by 8.0 seconds, not an exact latency measurement. The first reload also completed
after waiting for the workspace; cold state and precise completion time were not
verified. These observations do not establish acceptable cloud responsiveness.
The cloud order preview succeeded and exposed all 108 results across five pages;
the last page disabled Next. Completion was observed by 45.6 seconds, including
time between browser observations, not a precise benchmark. It was cancelled
without saving. Review latency is a flagged follow-up, not declared resolved.

This completes the active standalone order-editor migration, not full app or
forecast-accuracy acceptance. The unused legacy import component remains for
compatibility; neither active entry point uses it. Backend revision/retry checks
are automated; every import provider was not retested in the browser.

Next substantial task: migrate advanced factor scenarios/batches into the grouped
wizard so customers/orders/factors are reviewed before calculation. Preserve
existing saved scenarios and schedules, then verify the complete bilingual
forecast-to-approval/export journey. Cloud calculation latency and real-client
accuracy remain separate acceptance work.

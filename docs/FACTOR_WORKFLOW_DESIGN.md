# Factor workflow and shared design checkpoint — 10 October 2026

This is a bounded delivery checkpoint, not completion of all design or live-source
acceptance. Only the dedicated private forecast interface was deployed.

## Changes

- Advanced factor comparisons, grouped comparisons, preparation recommendations
  and customer/product exposure profiles now use the shared Stack, Grid, Panel,
  Actions, FieldGroup and Disclosure components. Dialogs use the existing fixed
  dimensions and internal scrolling. Fifty-two legacy CSS lines were removed;
  no inline styles or new page-specific appearance rules were added.
- Group editing/removal controls use global buttons and translated accessible
  names. Group tables follow the shared horizontally scrolling table contract,
  rather than a separate mobile-card stylesheet.
- The shared Disclosure supports controlled expansion without another styled
  wrapper. Existing callers retain their uncontrolled behavior.
- Factor review/saving now reports work to the forecast wizard. Back, Continue,
  closing and planning-setting changes are locked while work is pending. Parent
  refresh remains locked after the factor component unmounts. Regression checks
  cover these guards; this is not an injected-latency browser acceptance test.
- The disposable loopback fixture can provide 40 months of synthetic factor
  history. Its incomplete-history mode remains available. Neither mode calls
  live providers or seeds production; identity and AI are mocked.
- Source action conflicts now offer the same read-only reload as failed reads;
  successful reload clears the stale action warning. Already-enabled sources do
  not issue another enable write after refresh. Initial connections still fetch
  first, enable second; failed writes are never replayed.

## Browser acceptance

English desktop and Persian 390×844 customer-profile forms were checked with the
real company API and synthetic data. Profile changes save without changing orders
or existing forecasts. Mobile dialog: 358×680, internal scrolling, 44px controls,
16px input text, and no page-width overflow. The temporary viewport was reset.

The incomplete factor history blocks approval/continuing and does not fabricate
past values. With complete synthetic history, the wizard reviewed a Brent price
reference, two-month observation lag and explicit future assumption; reused saved
orders; then calculated Ridge and Elastic Net under one forecast group.

Four customers and two products are present. Two customers have orders; two do
not. The saved group includes fulfilled, outstanding and calculated quantities.
Customer Pars still has positive calculated demand without orders: displayed
5.07 tonnes for Elastic Net and 5 tonnes for Ridge in each of three months.
Downloaded `forecast-methods (1).csv` contains the same filtered months and
full-precision values; displayed rounding matches all six values. Browser
download-event observation timed out, but the actual downloaded file and its
timestamp were inspected independently. Reload preserves the saved group.

The generated history is deliberately simple. This verifies workflow and export
consistency, not forecast accuracy or realistic client performance. The source
history's release dates are not verified, so the result correctly remains a
what-if forecast rather than claiming validated accuracy.

## Actual cloud source acceptance

After the existing cooldowns expired, World Bank commodity prices were captured
at approximately 18:41 UTC and New York Fed supply pressure at 18:44 UTC. Both
source rows report successful fetches. Their saved observations render in the
private interface, with latest period **2026-09-30**. The commodity view inspected
Nickel ($/mt); the supply view inspected the GSCPI series. Both are global
references, not Tehran measurements. This is actual cloud provider/readback
evidence, distinct from the synthetic workflow above.

Concurrent refresh/revision activity produced an explicit conflict rather than
overwriting a newer revision. No rejected write was replayed, no cooldown was
reset and no historical observation was invented. Remaining Hormuz/annual Iran
sources were left on their existing cooldowns. Servix remains unconnected in
cloud and IMF commercial permission remains unrecorded. Existing forecasts and
client sales/orders were not replaced by these external captures.

Source capture receipts and use of these actual captures in a complete grouped
cloud forecast/export are still next-step acceptance work, not claimed here.

## Verification and scope

- Interface: 284 tests pass; production build passes.
- Focused company workflow, factor alignment/batch and sales-import tests: 30 pass.
- Factor alignment after extending the fixture generator: seven pass.
- `git diff --check` passes.
- Final edge/interface version: `2f91ee41-54ad-489b-836b-72e5ab1a8aa4`.
  Private access remains closed and owner-only acceptance remains enabled.
- No identity, controller, numerical image, storage configuration, domain, secret
  or other service change. Only company external-source captures changed cloud
  data. The independent local demo is not replaced and responds HTTP 200.
- Existing bundle-size/Radix and dependency warnings remain.

Shared-component tests cover the migrated advanced screens. The grouped advanced
factor editor itself has not had a complete desktop/mobile browser walkthrough.
This does not claim every legacy screen is now globally unified or fully translated.

## Next substantial task

Verify capture receipts and complete a private factor-aware grouped cloud
forecast using these actual monthly sources, saved orders and matching
exports. Finish input corrections/revisions and advanced grouped-factor mobile,
error and reload paths using the same shared design system. Servix credentials,
IMF usage permission, cloud AI eligibility, real-client accuracy and an explicitly
authorised multi-person pilot remain separate gates.

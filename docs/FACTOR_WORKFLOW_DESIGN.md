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

## Follow-up: actual cloud factor-aware forecast — 10 October

Completed **Tehran · Live market comparison** in the real private cloud workspace:
the existing fictional Tehran history (804 rows, five customers, four products,
18 series), all 79 saved order lines and October 2026–March 2027. Original
forecasts and input/order records are preserved.

Reviewed downloaded New York Fed GSCPI and World Bank Brent with two-month lags.
Explicit future assumptions: GSCPI 0 and Brent 100 USD/bbl. Review showed GSCPI
1.06 for October from a saved observation; later GSCPI periods and all Brent
future periods used assumptions. Brent's downloaded history was acknowledged as
what-if evidence. This does not prove factory exposure, original-release dates
or client forecast accuracy.

Ridge and Elastic Net completed under one forecast group. The full six-month CSV
(`forecast-methods (2).csv`) totals **4070.5619980699475 tonnes** for Linear model +
factors and **4030.236969004698** for Selective linear model. All six monthly
quantities match the rendered comparison after rounding. Aftab Printing / FOOD-110
/ November yields 29.318714413537293 and 29.808453061194214 respectively; the
filtered CSV contains exactly that month. Persian single-model results show zero
open orders and 29.32 tonnes expected demand. Reload preserves the saved group.

### Design / workflow

- The long factor picker extended above the screen because root tokens referenced
  component-local Radix measurements. These now resolve on the shared menu with
  a tokenized height ceiling and scrolling. All picker appearance has one global
  owner; 42 competing CSS lines removed, no authored inline appearance added.
- Desktop menu boundaries: approximately 150–483px within a 736px viewport.
  Picking GSCPI/Brent opened the intended forms.
- Review clears old approval and shows Checking…. Actual preview/save locked
  Back, Continue, dismissal and planning edits. The additional Change factors
  guard is regression-tested; its slow-write browser path was not re-injected.
- Mobile results dialog: 358×680 within 390×844, internal scrolling, no page
  overflow. Persian RTL results/customer picker fit (menu x199–371). Temporary
  viewport/language changes were reset. Shared brand and motion contracts retained.

### Verification / remaining boundaries

Interface **287 tests**, forecast-input/live-alignment **44 tests** (including
inherited factor-link tests), production build and whitespace checks pass.
Existing dependency/deprecation warnings remain. Edge only, version
**5fb55812-0580-4f32-bc91-2cff97e3e053**; closed access and owner-only acceptance
unchanged. Anonymous company API: 401; independent local demo: 200. No identity,
storage configuration, numerical engine image, secret or other service changed.
Local evidence: `screenshots/cloud-live-factor-comparison.jpg` and
`screenshots/cloud-live-factor-persian-mobile.jpg`.

Cloud review/save/calculation had noticeable waits. Company projections are rebuilt
after writes and grouped models execute synchronously: profiling candidates, not
proven attribution of the entire delay. No pending write was replayed.
Raw cloud-capture receipt inspection remains open: direct browser API navigation
was blocked, not bypassed. Passing integrity tests are not independent inspection
of cloud raw objects.

Next: measured cloud latency reductions with unchanged calculations/security,
then corrections/revisions and advanced grouped-factor mobile/error/reload
acceptance. Provider, AI, real-client accuracy and multi-person pilot gates remain.

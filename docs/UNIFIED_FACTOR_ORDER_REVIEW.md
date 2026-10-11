# Reviewed factors → reviewed orders → calculation

11 October 2026. Local development milestone; not a whole-app acceptance or cloud deployment.

## Delivered

- Manual factor batches, factor-file drafts and the assistant's factor preparation/review editors hand off to the existing fixed forecast dialog.
- One flow: saved history → recorded factors/assumptions → customers/orders → recorded methods → one named result. No calculation before customer/order review.
- Preserve the reviewed customer/product scope, calendar, horizon, factor sources and methods. Keep unaffected series on their recorded baseline; do not replace an individual customer's missing orders with zero demand.
- Reuse the existing order-consumption arithmetic and grouped jobs, company stores, permissions, review tokens and forecast libraries. No new forecast formula or live AI dependency.
- Changed factor inputs/baselines and newer order reviews are rejected before dispatch and publication; original forecasts remain unchanged.
- Fix result links opening the old baseline, revision drafts reopening completed results, all-customer factor summaries failing, and dialog content changing while it closes.
- Shared framework components only: no new CSS or authored inline styles. Friendly method names, localized labels/counts and expandable assumptions.

## Verification

- 44 focused backend checks pass: single/batch factors, four customers, customers without orders, reviewed order totals, original preservation, company/role separation, stale review rejection and three export formats.
- 325 frontend checks and production build pass.
- 87 additional regression checks pass across jobs, grouped monthly updates,
  forecast inputs, factor links/public factor routes and assistant factor batches.
- Real browser journey on an isolated disposable company fixture: assistant editor → factor assumption review → fixed forecast dialog → saved order reuse/review → recorded method → calculation → new grouped demand result. Provider response is a test fixture; the calculator is real. No live AI or external-source calls.
- Result reconciles to 20 tonnes of open orders + 112.98 expected demand + 2 fulfilled = 134.98 total (rounded). This is synthetic test evidence, not a client accuracy claim.
- Create revision starts a fresh factor review; closing and reopening resumes the correct prepared draft. English desktop and Persian 390px checks: page width stays 390px, dialog body scrolls internally, framework controls remain localized. Proof screenshots: `/private/tmp/demandlab-factor-wizard-en.png` and `/private/tmp/demandlab-factor-wizard-fa-mobile.png`.

## Still open

- Complete AI-proposal confirmation cards and legacy factor exclusion/percentage/monthly advanced scenarios still have separate execution paths. Migrate their review/confirmation without silently changing their semantics.
- Deploy frontend/backend together to the dedicated private cloud app and measure cold/repeated review and calculation latency. No cloud service changed in this milestone.
- Complete the whole-app bilingual end-to-end design/workflow audit; these checks cover this flow only.
- Real-client data, actual provider availability and forecast accuracy remain separate acceptance gates.

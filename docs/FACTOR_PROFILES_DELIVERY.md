# Saved factor profiles — 7 October 2026

## Delivered

Customers → Factors saves declared currency, overseas-supply, Hormuz-route and
material exposure. A customer default applies to that customer's forecast series;
an exact product/unit profile replaces it, rather than adding both sets together.
Clearing a product override restores the customer default. Revisions remain stored.
No product code, customer name or AI answer is treated as evidence of exposure.

The forecast's factor dialog offers matching saved profiles. Matching uses the
canonical customer name, product and unit; no fuzzy match or unit conversion.
Only the selected series receives the prepared factors. Choosing another profile
or manual exposure clears earlier prepared selections and approvals. Profile-bound
scope cannot be expanded in the review screen or by changing an API request.

The assistant can inspect profiles, preview their sources and prepare a review
button opening the same factor dialog. It cannot save a profile, refresh a source,
fill future assumptions, approve inputs or calculate through these new tools.
Existing approved forecast tools remain separate. The handoff is bound to the
owner, forecast, current profile revision, source evidence and proposal expiry.
Changed evidence requires a new review. Existing query/review/decision model
routing is preserved; no one-model-for-everything replacement.

Existing SQLite, Pydantic, React/Radix controls, Phosphor icons, source adapters,
factor alignment, forecasting models and OpenAI Agents SDK are reused. No new
dependency or secret is introduced. Blank future values and unaccepted timing
remain blank/unaccepted. Stale, incomplete or unlicensed observations stay blocked.

## Verification

- Store/API tests cover persistence, defaults/overrides, clearing, concurrent-edit
  rejection, active customers, exact names/units and linked product constraints.
- Actual existing-engine calculation changes only the selected customer/product;
  the other customer's numerical forecast remains identical. Downloaded retrospective
  factors do not gain past-accuracy or forecast-range claims.
- Actual SDK tool invocation and proposal endpoints are tested without a provider
  call: unknown profiles, repeated proposals, owner isolation, expiry and changed
  profiles/source evidence. Opening the workflow creates no job or forecast.
- Viewer/reviewer profile writes and missing-CSRF writes are rejected by the actual
  app middleware; a planner's authenticated, CSRF-protected save succeeds.
- Browser checks cover saved defaults, product overrides, exact forecast choices,
  different suggestions for the two products, manual reset and unavailable-source
  blocks. Desktop, 390px and 320px profile dialogs have no horizontal overflow.
  Repeated unchanged saves are disabled; source explanations are collapsed.
- 568-test full backend suite, 102 interface tests and production build passed.
  A subsequent 569-test run passed those existing checks but failed the newly added
  security test because its fixture patched a global instead of the route's captured
  store. The fixture was corrected to install isolated routes; all 25 profile/security
  tests then passed. The whole suite was not rerun after that test-only correction.
  Existing resource, dependency and bundle-size warnings remain.

The local demonstration adds one explicitly synthetic customer, `Demo Tehran A`,
with product `0001` in tonnes. Its customer default is currency exposure; the product
override is overseas supply plus aluminum. Product `0002` in the existing synthetic
forecast inherits the customer default. Existing forecasts, histories and orders are
unchanged. No paid OpenAI call, new credential, external upload or source-limit bypass.

Evidence: tests/test_factor_profiles.py, tests/test_security.py, frontend exposure /
assistant / preparation tests; outputs/factor-profiles-desktop.png,
factor-profiles-mobile.png, factor-profiles-320.png and factor-profile-sources-desktop.png.
The final screenshots show the saved profile's canonical demo name. Connections
handoff and an empty browser error log were also checked; viewport overrides reset.

## Boundaries and next major build

This is one profile per reviewed factor comparison, not a batch of differently
configured products in one run. The new tools have not been tested against a live
OpenAI response this turn. Synthetic engine/provider fixtures prove behavior, not
client accuracy or successful current external-service refresh.

Next major build: a monthly batch forecast that applies different customer/product
profiles, reviews missing assumptions together, and produces one reconciled demand
plan with partial orders and all six planning exports. Reuse the existing models,
source checks, job queue and exports; do not add production/inventory features.

Whole-product acceptance still requires permitted, complete live source history,
sufficient client actuals, measured predictive benefit, broader assistant-language
acceptance and deployment checks. These are not closed by dummy data.

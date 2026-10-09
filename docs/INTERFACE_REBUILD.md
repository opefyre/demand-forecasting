# Interface rebuild — 7 October 2026

Correction after user testing: the earlier Settings/unified-style acceptance below
was too broad. Value tokenization did not prove consistent component appearance.
All Settings sections and forms have now been migrated to shared framework
components and their rendered styles measured. See UI_FRAMEWORK.md. Migration of
remaining legacy page-specific layouts is not complete; do not claim otherwise.

This replaces cosmetic audit tasks with the structural issues raised by the user.
Do not mark the whole interface ready until every item below is verified.

- [x] AI-first Home; no separate Assistant navigation destination. Existing links still work.
- [x] Clear New forecast journey: sales inputs → reviewed factors → one/multiple methods → results.
- [x] Shared sidebar, header, main content and footer for current React app destinations.
- [x] Remove the global saved-calculations counter. Only active, failed or freshly finished jobs appear.
- [x] Replace Saved reviews with Approvals and explain the demand-export purpose.
- [x] Settings grouped by task; obsolete integration diagnostics and misleading instructions removed.
- [x] Current React visual values centralized in design tokens; no authored inline styling.
- [x] Use Vrolen signal green #5EE800 (peer landing project's signal.500 token).
- [x] Audit Persian labels across active pages, dialogs, errors and dynamic interface messages.
- [x] Desktop/mobile and RTL checks, plus regression tests. Preserve calculations and saved data.

Third-party chart libraries generate geometry/style attributes internally. The no-inline
requirement applies to our authored code; chart appearance must still use shared tokens.

## Implemented and checked

- New forecast: choose/import sales history, select connected live factors, review
  their timing and explicit future assumptions, choose one or multiple methods,
  queue distinct real calculations and view each result. Unavailable/stale factors
  are blocked; changing reviewed inputs requires another review.
  Twelve choices include automatic selection, statistical and machine-learning models.
- Existing saved files are loaded before editing their inputs. Original data is not changed.
- Journey IDs survive reload in the current browser session. Model totals use only the
  portfolio series; they exclude customer orders and never double-count product series.
- Single stylesheet entry point, centralized visual registry, normalized font-weight,
  font-size, radius and spacing scales, centralized chart appearance. Automated guards
  cover every frontend CSS/JSX file, missing variables and accidental inline styling.
- Settings: workspace/location/language, product units, AI, schedules and access.
  Mobile uses a section picker. Monthly scheduling was relocated, not removed.
- Both entry URLs now serve only the current shell. A missing frontend build reports
  an explicit error rather than silently serving the old PoC. Legacy files are preserved.
- Persian catalogue expanded across imports, orders, factors, connections, units,
  assistant reviews, calculation details and schedules. Imported customer/source
  names, unknown original messages and source evidence remain unchanged. Regression
  guards prohibit translating model/status identifiers used in application logic.
- 165 frontend tests and 92 focused backend tests pass. Production build passes.
  No live OpenAI calls or credential changes.
- Browser: Persian Home/Settings/new forecast, 1280px desktop and 390px mobile.
  Mobile Settings and results have no horizontal overflow. Reload restores completed jobs.
- Final browser check: editing saved inputs loads their actual 144-row history;
  the compact 12-method picker translates into Persian; closing returns to AI-first Home.
- Synthetic 10-period, four customer/product-series verification:
  Last observed: run a461a0f7f55d, 1122.1 tonnes.
  Recent average: run 85eaaa4958c9, 1024.0233333333 tonnes.
  Both succeeded with their exact requested method. Original run/order book unchanged.

- Data's New forecast action now enters the same guided journey. Importing saves
  inputs before method selection; it no longer silently starts an automatic model.
- Finished forecasts immediately show a filterable chart/monthly table. Orders
  remain a subsequent explicit review, not a gate hiding the model result.
- Customer/SKU/month filters apply consistently to totals, chart, table and CSV.
  Non-overlapping leaf series prevent double counting. Unknown totals stay unknown.
  Filtered ranges are shown only where calculated; bounds are never summed.
- Fresh live-factor synthetic verification: World Bank lead history with a reviewed
  two-month lag and an explicit fictional future assumption of USD 2,000/tonne.
  Ridge run 6c9aa593c182: 970.2438945749593 tonnes over ten months.
  ElasticNet run bc6f2c38a954: 981.5822347961417 tonnes over ten months.
  Both are marked assumption-based; accuracy scores/ranges are deliberately absent.
- The filtered CSV for Demo customer 001 contains 20 customer/SKU/month rows and
  independently reconciles to 382.4952368314315 tonnes. Original demo untouched.
- Completed-job notices are scoped to Data/Home, not unrelated destinations.
  Failed wizard jobs have a retry action. AI Settings has one ordinary section,
  schedules have no duplicated heading, and mobile customer product fields fit.
- Public-source factors now retain their external-factor label despite generated
  column identifiers. Live-source pause/resume labels use translated source captions.
  This changes attribution labels, not numerical model calculations.
- Final build checked at 1280×720 and 390×844: no page overflow. Mobile factors,
  connections, customer/product form, approvals, help and calculation details
  were checked. Customer product fields remain usable inside a centered dialog.

## Release boundary

The eight reported structural interface issues are addressed in this release.
This is not a claim of production forecasting accuracy or exhaustive coverage of
every external failure. Synthetic tests verify workflow/calculation consistency,
not performance on the client's unseen history. Real-client accuracy, authorized
provider history, live AI/ERP receiver acceptance and company deployment remain
separate delivery gates. No credentials or paid AI calls were used in this pass.

The old static PoC styles/script were inspected and retained as inactive legacy files;
they are no longer a frontend fallback. Packaged Phosphor font styles are third-party
assets, not authored app styling.

Screenshots: docs/screenshots/interface-home-persian.png,
interface-settings-mobile.png, interface-results-mobile.png,
interface-forecast-filtered-mobile.png and interface-forecast-desktop.png.

# Market, requirements and workflow audit
3 October 2026. Scope: sales/demand only. No real integration, paid AI call or external transmission was performed.

## Verdict
**Demo: share with caveats. Tehran operations: needs revision. Review completeness: partial.**
The main product exists and the sampled calculations are sound. That is not proof that every requested capability is finished, that client forecasts are accurate, or that first-time users find every workflow obvious.

### 3 October follow-up build

The initial findings below are preserved as the audit trail. The following gaps
are now repaired within the tested local sales scope:

- True Persian/Gregorian planning months, explicit sales/order/actual-results
  input calendars, Persian digits and Tehran month/day cutoffs. Exports include
  calendar, planning-month label and exact ISO boundaries. Cross-calendar order
  reuse is rejected. The recognized client workbook remains Gregorian monthly
  totals; the app will not pretend those totals can be split into Persian months.
- Explicit quantity meaning and returns policies with reconciliation receipts,
  original-file preservation and negative period-total rejection. Unknown source
  meaning stays recorded sales, never silently called unconstrained demand.
- Stable directory IDs, optional ERP IDs and reviewed alternative names; exact
  opt-in import mapping. Name/alias/ID conflicts block the complete customer batch.
- Returning users can reuse saved data from Home. Factor actions are responsive
  cards, demo factors opt-in and public data sources collapsed. The model-only
  approval button now opens demand review; saved legacy records are preserved.

Synthetic run `422d36f6e1d2`, order snapshot
`35faac5891c28694803d6ba7d8c804b2`: 36 months of generated Persian-month history,
two customers, one SKU, 10 future months beginning `1405-07`, 20 demand rows.
One customer has orders above its estimate; the other still receives a calculated
estimate. Actual Gregorian month boundaries and all CSV/Excel/JSON planning
quantities reconcile independently. No client data or paid AI call was used.

439 backend / 66 frontend tests and production build pass. Selected 1280px and
390px states were checked after rebuilding; this remains sampled UI acceptance.
Evidence: [Persian-month customer/SKU view](../outputs/market-audit/persian-demand-laptop.jpg).

This does not resolve client meaning/unit evidence, real accuracy, historical
factor publication replay, optional Persian/RTL interface, broader assistant
actions or Iran-compatible AI deployment. Live integrations remain deferred.

This bounded review sampled eight main pages, key laptop/mobile journeys, source code and independent arithmetic. It did not inventory every hidden state or run a human usability study. Counts below describe observed unresolved defects, not verification percentages; unknown denominators are deliberate.

## Requirement coverage
| Requested capability | Current state | Remaining |
|---|---|---|
| History and current orders together | Working monthly customer/SKU demand; partial orders consume only matching estimates | Confirm what actual sales represent, returns, requested versus promised dates |
| Customer list | Add/import customers and product relationships | Stable external identifiers and aliases, including Persian/English spelling |
| Multiple mathematical/ML methods | Existing StatsForecast, scikit-learn and LightGBM methods; automatic comparison and manual selection | Client-specific eligibility, long-horizon and accuracy acceptance |
| Seasonality and external/internal factors | Iran holiday/workday features; one to eight dated monthly factors, scope, lag and future assumptions | Verified release archives; real client definitions and effect validation |
| Iran conventions | Persian factor dates/digits, FX market/rial-toman/basis, CPI measure/base year | Equivalent support for sales, orders and outputs; Tehran month cutoffs; optional Persian/RTL UI |
| Flexible results | Customer/SKU/month filters; chart, trend, table, monthly and coverage views; saved views | Wider real-client usability/performance acceptance |
| Export | CSV/Excel/JSON demand releases with order-consumption mode and approval evidence | Actual receiving-system reconciliation; transmission explicitly deferred |
| Pipelines | File mapping/import, reviewed local-file refresh and reusable mappings | Full machine/API and ERP ingestion deferred; connection diagnostics are not a complete connector |
| AI assistant | Plain-language context, different model roles, guarded forecast/review/comparison actions | Cell-level cleanup, wider actions/language evaluation, spend limits and Iran-compatible deployment |
| Simple navigation | Main sidebar opens pages; centered action dialogs; Help | Simplify returning-user entry and external-factor actions; finish legacy review retirement |

Production/inventory implementation remnants are not part of the current sales navigation or active requirements. This review did not remove old files or user records.

## Prioritized findings
1. **Fixed — demand approvals were hidden behind the wrong review page.** Saved reviews now lists actual submitted/approved demand releases across forecasts, shows current stale/replaced state and opens the saved quantities/downloads. Demo records are opt-in. Older model-only reviews remain in a collapsed archive; their final retirement is still proposed.
2. **Fix proposed — Iran onboarding is incomplete.** Persian/calendar support currently applies to factors, not the whole history/order/export journey. English/Gregorian sales and order controls and UTC-based month boundaries need a consistent local contract. Client language preference remains a choice, not an assumed need for every portfolio customer.
3. **Needs input, then build — sales meaning and identity.** The app does not fully record requested demand versus shipped/invoiced actuals; negative returns/corrections are rejected rather than handled as a separate reviewed layer. Customer matching uses exact names. The client workbook includes negative values and incomplete unit evidence. Agree the target, returns policy, customer IDs and delivery-date meaning before treating these as real demand.
4. **Needs input — client accuracy and factor validity.** Seven months of client actuals cannot validate annual seasonality. Use 24–36 months if available, historical order snapshots and dated factor releases. Inflation/FX/global pressure are candidate signals, not automatic tonnage multipliers; compare them against a baseline and keep them only when justified.
5. **Deployment decision + proposed UX cleanup.** OpenAI does not list Iran as supported, and warns about access/offering access outside supported countries. Do not assume the current assistant can be deployed to a Tehran factory; evaluate a permitted provider or local open-source option without bypassing restrictions. Separately, Home's main entry still starts import for returning users, and long factor tables push actions offscreen. Those are genuine workflow improvements, not reasons to add more dashboard panels.

[OpenAI supported-country policy](https://help.openai.com/en/articles/5347006-openai-api-supported-countries-and-territories).
The [NY Fed global supply-pressure source](https://www.newyorkfed.org/research/policy/gscpi) is global context, not a Tehran factory measurement.
The [IMF Iran inflation study](https://www.imf.org/-/media/files/publications/wp/2022/english/wpiea2022181-print-pdf.pdf) supports considering FX/import-price context, not a direct demand coefficient or a claim about today's currency regime.

## Independent calculation checks
Synthetic run `0ea4a37ff8ef`, orders `bb2099e0b5930871b82ed78d85c3623d`, release `aed6a0c394afa0c54fd3f7fd5d68535f`; originals preserved.

All 28 released customer/SKU/month rows were recalculated from saved model estimates and source order lines, without the application's shared order helper:
- Open orders = ordered − fulfilled − cancelled.
- Still expected = max(0, model estimate − fulfilled − open orders).
- Still to serve = open orders + still expected.

No row mismatches. Open orders: **168 tonnes**; fulfilled: **20**; still expected: **2,259.3952282**; still to serve: **2,427.3952282**. The dashboard total includes fulfilled quantities (**2,447.3952282**); planning exports exclude them.
Lumen October: order 180, fulfilled 20, open 160; the lower estimate adds nothing. November still forecasts 66.29. Browser filter/monthly view and reset agreed.

Independently matched 42 held-out actuals to the uploaded synthetic CSV: displayed weighted error **7.941631763%**, mean absolute error **4.694903612**, root mean squared error **6.329362511**, bias **−1.184391953%**. Last-value, recent-average, weighted-average and seasonal-repeat predictions and saved blended outputs agreed with independent computations.
These results apply to the sample only. Other mathematical methods were not independently reimplemented in this audit.

Limitations: current calibration has too few residuals for supported ranges; unavailable bounds remain blank. Factor testing holds the last training-period value and is not a verified historical publication replay. The secondary percentage-error metric excludes zero/zero periods; its definition needs clearer documentation for intermittent demand.

## Browser and regression evidence
Visited Home, Forecast, Data/external context, Customers, Assistant, Saved reviews and Help. Sampled centered customer/review dialogs, order-update steps, chart/table/monthly/coverage and customer filter/reset. Laptop widths 1280/1024 and mobile 390 were used for selected states, not every page at every width.
Repaired review inbox and record dialog were checked after rebuilding; no page overflow in those final checked states.

**426 backend tests, 62 frontend tests and production build passed.** Existing database resource warnings and large-bundle build warnings remain. Tests support regressions, not whole-product acceptance. No new package or paid service was needed.
Evidence: [laptop review inbox](../outputs/market-audit/review-inbox-laptop.jpg).
Local server was restarted with the rebuilt app on http://127.0.0.1:8010/.

## Dashboard best practices and quality
| Category | Observed defects | Assessment |
|---|---|---|
| Dashboard usefulness and completeness | 3 / unknown | Core workflow exists; Iran operations and full assistant actions remain partial. |
| Analytical clarity | 1 / unknown | Orders, expected demand and fulfilled quantities are separated; sales meaning is not recorded. |
| Visual and interaction consistency | 2 / unknown | Eight main views sampled at laptop/mobile sizes; factor actions and returning-user entry need simplification. |

## Analytical correctness and robustness
| Category | Observed defects | Assessment |
|---|---|---|
| Source authority and confidence | 0 / unknown | Synthetic calculations are traceable; client accuracy and historical factor-release timing are not established. |
| SQL/value accuracy | 0 / unknown | Order release, monthly totals, simple methods and confirmation metrics independently recomputed. |
| Within-chart agreement | 0 / unknown | Demand chart/labels and filtered monthly values agree in the sampled run; not every plot was audited. |
| Complete source details | 0 / unknown | Saved inputs and factor/export provenance inspected; historical publication archives remain unverified. |
| Cross-artifact consistency | 0 / unknown | Review inbox repaired; saved release quantities agree with source orders and the dashboard. |
| Data-quality controls | 3 / unknown | Stale orders and missing factors are guarded; Persian sales/order dates, returns and customer aliases remain gaps. |
| Conclusion support | 0 / unknown | Demo error is not client accuracy; current sample lacks supported forecast ranges. |

Inventory/check gaps remain: real client accuracy, historical publication replay, all hidden/legacy interactions and first-time human usability. No overall completion percentage is inferred.

## Next substantial build — Iran-ready sales onboarding
1. One explicit sales/demand definition, units, delivery-date meaning and returns policy.
2. Reviewed Persian/Gregorian sales and order imports, Persian digits and Tehran cutoffs, preserving originals.
3. Stable customer/SKU IDs and reviewed alias matching; no silent merging.
4. One clear returning-user path: reuse saved history → update orders/factors → calculate → inspect customer/SKU/month → export.
5. Retire competing model-only approval entry points without deleting old records.
6. Verify with representative client exports and sufficient history. Decide permitted AI deployment separately. Live connectors stay deferred.

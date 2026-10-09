# Automatic factor testing — 7 October 2026

## Delivered

The existing factor scenario now offers **Test which factors help**. For each
customer/product, compare history-only methods, each reviewed factor separately,
and all reviewed factors together. Use a factor candidate only when earlier tests
reduce error by at least 5%. A separate final historical window is reported after
the choice is frozen. It does not silently change the choice, even when it worsens.
Short/incomplete evidence falls back to history-only methods with an explanation.

Existing StatsForecast methods and sklearn Ridge, Elastic Net and histogram
gradient boosting are reused. Statistical models work per series; ML models pool
the catalog but include series identity and select a candidate per customer/SKU.
Search is bounded to 1–8 factors, not every possible subset; no new forecasting
algorithm, paid call, dependency or external service was added.

Forecast → Update forecast → optional factor comparison uses the existing reviewed
factor workflow. The calculation selector is visible rather than hidden in customer
scope settings. Results have a collapsed **Which factors helped?** table; customer
and product filters apply. Historical error is not filtered by future month.
The forecast package includes Factor choices/Factor test policy sheets and a
separate factor_evaluation.json. Scoped scenarios retain other baseline series and
export only the tested scope's factor-choice rows.

## Verification

- 544-test backend suite, 10 targeted factor tests after the final fast-profile
  fix, 95 interface tests and build passed. Targeted tests overlap the suite;
  these are not 554 distinct checks. Existing dependency,
  SQLite resource and bundle-size warnings remain; this is not a clean-warning claim.
- Six deterministic synthetic cases, two seeds: useful/irrelevant factors, mixed
  customers, changed relationship, sparse demand and short history. 1,776 history
  rows in saved fixtures. Gregorian and actual Persian-month boundaries tested.
- Changing the reserved actual quantities or realized factor values cannot change
  earlier selection. Training-only transforms and last-training factor values are
  used during each test forecast. History-only refits ignore changed future factors.
- Missing factors are not filled with zero; retrospective live-download scenarios
  cannot opt into automatic score-based factor selection. The reviewed link route
  saves the new method without changing the source dataset.
- Full existing-model saved demo: `27bafe7c16d5`, dataset
  `65af580e197d478a852fc73031e26fd2`, order review
  `7e687da9cb5ef411c918fb9387583ce9`. Six forecast months, four customer/SKU series,
  two factors, 25 candidates (24 complete on selection periods).
- A/0001 selected exchange-rate input; A/0002 selected both inputs; B/0001 and
  C/0003 retained history-only choices. Final average quantity errors: 24.26→20.69,
  15.61→12.67, 18.17→18.17 and 2.08→2.08 tonnes respectively. Synthetic evidence only.
- Partial order demo: 240 ordered, 20 fulfilled, 220 open. Calculated total
  4,628.24 tonnes; expected/unordered 4,388.24; still to serve 4,608.24. Independently
  parsed CSV/Excel/JSON each have 24 rows and equal totals for both output modes.
- Original client datasets, saved calculations and prior order reviews preserved.
- Browser: all four factor-choice rows, customer A's two rows, SKU 0001's two
  rows and reset verified. 1280px desktop table fits; 390px/320px have no page-wide
  overflow, with keyboard-accessible sideways scrolling inside the evidence table.
  Centered factor modal offers the automatic option and canonical follow-up methods.
  Incomplete synthetic source shows 80 missing values and disables calculation.
  No new scenario was saved during that negative check. Screenshots:
  outputs/factor-test-desktop.png, factor-test-mobile.png, factor-test-source-gap.png.
- Fast model catalogs now use the extra historical windows needed for this
  opt-in factor test; speed settings cannot silently disable factor eligibility.

Evidence: outputs/factor-test-demo-evidence.json, six factor-test-demo exports,
sample_data/factor_testing and tests/test_factor_evaluation.py.

## Boundaries and next build

This evaluates supplied/reviewed factors; it does not discover every relevant
external source or independently verify imported historical release dates.
Downloaded/revised live history without valid past-availability evidence remains
what-if only. Archived public timing still has its existing explicit assumptions.
Future factors remain reviewed assumptions, not known or AI-invented facts.
Intervals do not measure future exchange-rate/inflation uncertainty.

The 5% guardrail is a practical policy, not statistical significance or causation.
An irrelevant factor can be retained in a combined candidate by chance. The final
window is one limited check, not real-client accuracy or operational acceptance.
No model is guaranteed strongest or more accurate for the factory without data.

Next substantial build: **source-to-factor preparation and recommendations**.
Reuse the existing live adapters/alignment/assistant services to propose relevant
factors for a product/customer, explain coverage and timing limitations, and
prepare reviewed assumptions in the monthly update. Automatic selection must stay
disabled for sources whose historical availability cannot be established; build
prospective snapshots for later honest evaluation. No new account is needed for
already configured permitted sources. Client acceptance and commercial CPI rights
remain external dependencies, not completed coding tasks.

Method references: [rolling historical tests](https://otexts.robjhyndman.com/fpp3/tscv.html),
[predictor selection](https://otexts.com/fpptr/selecting-predictors.html),
[future predictor assumptions](https://otexts.com/fpp3/forecasting-regression.html).

# Forecast method expansion and selection safeguards

Verified 21 September 2026. Current engine revision: `2026-09-method-catalog-3`.
This extends the approved method catalog without replacing existing models or
reducing the remaining product scope.

## Implemented choices

| Choice | Existing library | Policy and limitation |
|---|---|---|
| Weighted recent average | NumPy weighted average | Last three periods, weights 1:2:3 oldest to newest; the resulting level repeats at every horizon. No invented trend. |
| Holt trend | StatsForecast Holt | Additive error, nonseasonal level/trend; at least six training periods. |
| Holt-Winters seasonal | StatsForecast HoltWinters | Additive error/trend/seasonality; requires two complete cycles in every training window. Monthly cycle 12, weekly 52, daily 7. |
| MSTL weekly + yearly | StatsForecast MSTL with nonseasonal AutoETS trend | Daily data only, periods 7 and 365; at least 731 training days in every test window. Not a movable-holiday model. |
| Elastic Net + drivers | scikit-learn ElasticNet | Direct multi-horizon predictions, fold-local numeric scaling; alpha 0.1, l1 ratio 0.5, maximum 10,000 iterations. Fixed candidate settings, not user-tuned hyperparameters. |

Library APIs were checked against the installed implementation and official
references: [StatsForecast models](https://github.com/Nixtla/statsforecast/blob/main/python/statsforecast/models.py),
[Elastic Net](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.ElasticNet.html)
and [NumPy weighted average](https://numpy.org/doc/stable/reference/generated/numpy.average.html).
No new paid dependency or reimplementation of smoothing/decomposition/regression
was introduced. The small weighted-average policy uses NumPy's primitive.

The recent three-period moving average, naive/seasonal-naive, AutoETS,
AutoARIMA (seasonal when eligible), Theta, intermittent methods and other ML
models remain available. More methods do not imply that each one improves a
forecast. They compete on the same historical keys; unavailable candidates
cannot be selected under a misleading successful-model name.

## Reliability behavior

- Each historical fit sees only its training window. Elastic Net's numeric scaler
  remains unchanged when predicting new values/categories.
- Convergence warnings become explicit failed candidates, not silent successes.
  Full-fit failures retain their actual reason rather than a generic substitute.
- Both automatic and family selections keep an ensemble only if its selection
  error improves on the best eligible member. A family fallback stays within that
  family. The run's method description uses the models actually assigned to items.
- The later confirmation window does not influence automatic weights. The UI
  explains that choosing manually after inspecting the later-check column is
  not an independent test of that human choice; new actuals are needed.
  Summary and accuracy labels therefore say **Later-period error**, not unseen
  error; their help repeats this distinction for manually selected methods.
- Minimum history gates apply inside every test window, not merely to the total
  uploaded history. Seven actual months cannot qualify annual Holt-Winters or
  establish annual seasonality.
- `result.json` and Excel capture engine/library versions and the new methods'
  settings. Existing saved runs remain unchanged. Assumption scenarios reject
  mismatched engine versions and require a new baseline.
- Ranges are still indicative. This phase does not independently calibrate them
  or establish that stockouts, war, FX changes or other causes have been modelled.

## Workflow and UI verification

Run saved inputs, open Forecast → Methods, compare earlier selection evidence,
read a method's help if needed and choose **Use method**. A short centred
confirmation starts a separate saved run. The active method is visible under
the version selector; its row says **Current method** instead of offering an
unnecessary duplicate action. Unavailable methods are disabled with a reason.

Verified in the running app at 1280×850 and 390×844: new rows/help, unavailable
daily method on monthly data, centred confirmation, background run, Open result,
selected-method label and contained horizontal table scrolling. The scroll hint
now appears before wide tables so it is not hidden below a long list. These are
bounded checks, not acceptance of every UI workflow or viewport.

## Sample evidence

All runs below use the existing **synthetic** 12-item, 60-month manufacturing
dataset `8cfb2da761a840bc8b4404ea7b337773`, with 12 future months and mapped
production data. None are client accuracy claims.

- Expanded automatic comparison: job `9d5b038b330842c2a839e4fde161e580`, run
  `5d6320f4d264`; all five additions represented; MSTL correctly unavailable on
  monthly data. Later-period WAPE 4.7177888955%.
- Holt-Winters selected through the browser: job
  `3cdbf8b3381246ce81b622e0fbf840c5`, run `2c94a1cc0dff`. All 144 forecasts use
  that exact method with weight one. Later-period WAPE 4.5656935424%; forecast
  total 15,490.5664985443 tonnes. Earlier selections, source hashes and test-period
  signatures match the automatic comparison. This run predates the final
  family-ensemble guard revision; its explicit single-method path is unchanged.
- Final guarded seasonal-family run: job `d1fa675ebff64ff18a6babe19253bd1b`, run
  `b32a512ba35c`, engine revision 3. Ten items fall back to their better single
  eligible model, two retain improving blends. Later-period WAPE 4.6867270009%;
  total 15,449.7819691471 tonnes. All item forecasts reconcile to the recorded
  model weights; source hashes and evaluation keys match the prior comparison.
- Independent September PULP-HW requirement for the final family run:
  475.3699579875 tonnes, saved as 475.370. Usable opening 678, no receipts;
  saved closing 202.630. Recipe/mapping preserved.
- Both manual and final-family Excel packages include matching Engine and Method
  settings sheets and 144 forecast rows.
- Twelve new automated cases: library parity, weighted arithmetic, minimum
  history/grain, two-season synthetic daily forecasts, separate daily confirmation,
  fold-local scaling, nonconvergence, failure reasons, selection-period isolation,
  family guard and export metadata. Full suite: 138 Python tests passing; four
  existing chart-data tests remain separate. Frontend build passes with existing
  bundle-size/dependency warnings.

Read-only verifiers: `scripts/verify_method_sample.py` (manual run by default;
pass `b32a512ba35c` for the guarded family) and
`scripts/verify_production_sample.py b32a512ba35c`.

## Open requirements

User-configurable seasonal periods and hyperparameter tuning; genuinely unseen
client validation; more than one independent confirmation window where practical;
independently calibrated intervals; richer hierarchy reconciliation; lifecycle,
stockout/substitution/promotion workflows; governed factor vintages and input
pipelines; production deployment controls. A fixed 365-day pattern is only an
approximation and does not replace the Iranian holiday/Jalali calendar features.
Neither this catalog nor its synthetic benchmark proves operational accuracy.
# Percentage-error convention

The secondary symmetric percentage error averages `200 × |actual − forecast| /
(|actual| + |forecast|)` over pairs whose denominator exceeds `1e-9`.
Zero/zero pairs are excluded, not counted as perfect-demand observations; if
every pair is zero/zero, this secondary metric is zero. Use absolute error and
weighted error alongside it for sparse sales. Weighted error is unavailable
when there is no actual quantity. Do not interpret these diagnostics as proof
of future accuracy.

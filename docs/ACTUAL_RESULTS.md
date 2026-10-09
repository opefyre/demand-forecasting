# Reviewed actual results and comparable evidence

Implemented locally on 21 September 2026. This is a reviewed local comparison
workflow, not authenticated multi-user approval or automated model retraining.

## Planner workflow

Forecast → Accuracy → Actual results → Add actual results.

1. Upload Excel, CSV, TSV or record-oriented JSON. Choose a worksheet and heading
   row where necessary. Original bytes are saved with a SHA-256 hash.
2. Match the forecast item ID, period-start date and actual quantity. Confirm the
   forecast's exact unit, fully closed period-end date and reviewer. Choose a
   specific approved plan, or leave Forecast only selected.
3. Review source values and coverage. Invalid values, repeated item-period keys,
   unmatched IDs, nonmatching dates and unclosed periods block saving. Missing
   expected results require explicit acceptance of a partial comparison.
4. Save an immutable comparison. Corrections become another saved version; they
   never rewrite a forecast or previous comparison. Repeated browser save requests
   return their original version rather than duplicating it.
5. Inspect item, period, horizon-step, product-family or customer breakdowns and
   download exact compared rows from Source and review.

Actual-results sources cannot silently become training history. Update forecast
inputs starts the reviewed-history import, not an automatic append or promotion.

## Calculation and timing contract

- Grain: one forecast item × forecast period. Item IDs retain customer/location
  wherever the original forecast separated those series. No SKU-only merge.
- Forecast quantities come from the saved series shown in the app. Approved
  quantities use the shared plan resolver; original quantities remain unchanged.
- WAPE = sum of absolute errors / sum of actual demand × 100. Bias = (sum of
  forecast − sum of actual demand) / sum of actual demand × 100. Rates are
  recomputed from totals, never averaged across items. MAE stays in source units.
- Zero total actual demand makes WAPE and percentage bias undefined, not 0%.
  Historical public metrics follow the same rule; model selection can still use
  source-unit MAE on an all-zero window, recorded as its selection loss.
- Missing actuals are excluded and counted. Invalid, infinite or negative values
  are not dropped, clipped, summed with duplicates, or replaced with zero.
- Real actuals must represent fully closed dates before today's date in the site
  timezone. Monthly dates use first-of-month and month-end closure. Weekly periods
  span seven days from their stored start; daily periods one day.
- Prospective scores require an aware `issued_at` timestamp before the period
  started in the site timezone. Legacy runs without issue times remain diagnostic;
  no timestamps are retrospectively invented.
- Plan improvement uses identical paired records, additionally requiring the
  latest approval to predate each period. Draft, late, undated and wrong-run plans
  cannot claim an improvement score.
- Samples stay paired with samples and visibly labelled. Future-dated sample
  actuals are permitted for demonstration only, never as live accuracy evidence.
- Reports retain exact rows, source cells/hash, run hash, plan hash, configuration,
  reviewer and save time. CSV exports neutralize spreadsheet formula-like text.

## Historical run comparison

New backtests record a signature of the exact evaluated item/date/step/actual
tuples. Monitoring compares only matching signatures, units, site, frequency,
classification, requested horizon and evaluation type. Missing legacy evidence
does not count as a match. Scenarios are excluded. Changes are historical
comparisons, not model drift. Unrelated-run deltas and automatic retraining
recommendations are no longer produced.

## Live sample evidence

Run `01e6aa772eba` issued at `2026-09-21T11:37:18.164730+00:00` used the existing
synthetic manufacturing dataset. Comparison `69010504070840f19733140bf7b7d352`
was imported and saved through the UI using `iran_actuals_followup_3m.csv` and a
sample closed date of 30 November 2026.

All 36 records match. Independent CSV arithmetic gives 3,490.52 actual tonnes and
1,190.5241507375085 absolute error: 34.107357950606456% WAPE, exactly matching the
report. Only the 24 October/November records have forecasts issued before their
period began; September is diagnostic only. These synthetic results are separate
from the 5.6587% historical confirmation error, not evidence of client accuracy.

Manual Last observed run `e338f48fe987` was also calculated using the same saved
sample inputs. The monitoring API matched its exact evaluation signature to
`01e6aa772eba` and returned a +12.218810691791887-point historical WAPE difference.
It correctly left model drift and retraining recommendation unset. The active
forecast was not silently switched to this comparison run. The actual-results CSV
download was read back: 36 rows, 3,490.52 actual tonnes, 24 timing-eligible records,
and source cells retained on every row.

## Still open

Authenticated reviewers and period locks; reasoned correction/supersession policy;
transaction-to-period actuals pipelines; service/inventory outcome monitoring;
configured drift thresholds and champion/challenger promotion; reviewed training
updates and automatic retraining with rollback; real-site outcome validation.

# Planning ranges — implementation and evidence

21 September 2026. Engine revision `2026-09-range-check-2`.

## What changed

The old weighted blend of global/item errors and model disagreement is replaced
by an inspectable absolute-residual order statistic. NumPy supplies the numerical
operation; no new package or custom numerical algorithm is required. The policy
works with the existing library forecasts and the actual saved ensemble weights.

Deep analysis adds up to five non-overlapping, requested-horizon windows when
there is sufficient history without losing the first two seasonal cycles. The
first two select methods, the middle one or two fit ranges, and the last checks
accuracy and coverage. Shorter histories keep the existing selection/confirmation
split and disclose when range fitting reuses selection errors. Confirmation
actuals never set widths or method weights.

For each item/step, use at least five same-step absolute residuals; otherwise pool
steps for that item only. The half-width is the sorted residual at one-based rank
`ceil((n + 1) * 0.8)`. NumPy partition selects the exact rank, avoiding a floating
quantile-index shift found at n=36, 78 and 136. Bounds are mean ± half-width, with
the lower bound floored at zero. Missing evidence or steps beyond the tested
horizon produce null bounds, not a guessed square-root extension. Percentage
scenarios scale both means and widths; their historical check remains explicitly
about the original baseline, not scenario probabilities.

Portfolio residuals sum signed item errors for the same date **before** taking
absolute values. Incomplete item coverage excludes that total period. This
retains observed co-movement; it does not assume independent errors or add item
percentiles. Tests include same-direction and exactly offsetting item errors.

These are nominal 80% empirical planning ranges, not guaranteed conformal
coverage: time dependence, pooling across horizons, model refitting and changing
conditions violate assumptions needed for a general distribution-free promise.
One later window is not operational certification. Hierarchy-level ranges,
long-run coverage monitoring and real-site acceptance remain open.

References checked: [NumPy quantiles](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html)
and [StatsForecast conformal intervals](https://nixtlaverse.nixtla.io/statsforecast/docs/tutorials/conformalprediction.html).
The latter provides the existing-library benchmark; the app does not claim to
call its per-model conformal interface for a cross-model ensemble.

## User workflow and audit trail

Forecast → Accuracy has a collapsed **Did the range cover later demand?** section.
It separates individual item observations from portfolio periods, shows counts
and step-level coverage/widths, and explains missing evidence. Detailed caveats
are in help rather than a new settings page. Chart bounds remain null where
unsupported. Older saved runs keep their old range explanation and are not
retroactively credited with the new check.

Each new forecast exports Range fitting, Range parameters, Range check and Range
policy worksheets. Saved JSON contains the same actuals/predictions, parameters,
counts and inclusive coverage checks. Interval scores penalise both wide ranges
and missed actuals; they are audit evidence, not a new composite quality badge.

## Verification

- 11 new tests cover exact rank, own-item scale, same-step preference, insufficient
  samples, untested horizons, zero-floor/scenario scaling, correlated totals,
  incomplete totals, duplicates/nonfinite fitting values, coverage/score arithmetic,
  holdout perturbation, separate fitting and JSON/export nulls.
- 149 backend tests pass; frontend production build passes with existing bundle
  and dependency warnings. No new test count is claimed as client accuracy.
- Synthetic dataset `cf685f57887d4ebeaa8fcb6d5ea3b324` is a separate six-month copy
  of existing saved synthetic inputs; source files and prior dataset unchanged.
- Initial browser sample `25ad55031c82`: 12 items, 60 months of history, 6 forecast
  months; 12 selection months, 12 separate range-fitting months (144 item rows),
  and 6 later check months. Item coverage 67/72 (93.0556%); portfolio 6/6. Portfolio
  half-width 63.9050192829 tonnes. This run uses revision 1; the exact-rank correction
  does not change its n=12 widths.
- Final revision-2 rerun `431fed798551`, job `1f1f5c4f23074d00819f7e307b4a93bf`,
  reproduces the same counts, widths and coverage. The independent saved-run
  verifier passes on this final run. Four chart-data checks also pass.
- `scripts/verify_range_sample.py` independently sorts residuals, reconstructs
  joint errors, checks all bounds/counts and reconciles every exported check row.
- Browser checks: saved result → Accuracy → disclosure, sample counts and help,
  small-screen contained scrolling at 390 px. These checks do not certify other
  workflows or every required viewport.

Next acceptance focus: complete the primary planning journey and its UI states;
do not add optional model families before that workflow is verified.

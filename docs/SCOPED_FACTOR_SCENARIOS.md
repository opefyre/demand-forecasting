# Customer/product factor scope — 27 September 2026

Implemented: factor-link dialog can select exact customer–SKU series. Empty,
duplicate or unknown IDs are rejected. Scope is frozen in the review token and
scenario provenance; changing it requires another preview and approval.

Calculation reuses the existing full-data model fitting pipeline. Selected series
take its factor-aware output; unselected series are copied exactly from the saved
baseline. Shared models still learn across history. This is output scoping, not
separate isolated model training for each customer. No orders are changed.

Portfolio totals are recomputed from the composed series. JSON result, forecast CSV
and workbook Forecast sheet agree. Workbook Factor scope identifies the source of
each series. Original baseline remains unchanged. Obsolete whole-refit model scores,
driver reports and portfolio ranges are withheld for the composed result rather than
claimed as evidence for it. Selected/unselected individual series retain their own
source ranges. Combined accuracy/range calibration remains an explicit limitation.

Verification:
- Full backend regression: 377 tests pass (existing dependency/database warnings).
- Frontend: 55 tests pass; production build passes with existing chunk-size warning.
- Real-engine route test calculates a baseline and scoped scenario, confirms B stays
  identical while A uses the scenario, checks Excel values and unchanged saved baseline.
- Unit checks cover invalid scope/periods, recomputed totals, omitted aggregate ranges,
  CSV/Excel agreement and stale approval.
- Browser: selected Lumen / COA-135-70X100; preview reports exactly one series and
  zero missing periods. Empty selection blocks preview. Cancelled without saving.
- Local server updated; existing demo retained. No paid calls or new dependencies.

Next build: combined historical accuracy for composed scenarios using matching
held-out predictions, followed by the automated refresh-to-draft workflow. Client
connectors and approved Iran CPI/FX source access remain separate dependencies.

## Combined accuracy delivered — 27 September

New scoped scenarios now rebuild error metrics from reserved historical observations:
selected series take scenario predictions and other series take baseline predictions.
No averaging of series percentages. Existing NumPy and engine metric functions are
reused. Engine, units, evaluation signature, observation keys, actual quantities,
confirmation dates and coverage must match. Missing, duplicate, non-finite or
unverified evidence withholds scores. Zero actual totals leave WAPE undefined.

Evidence is retained in `scoped_accuracy` and workbook sheets `Scoped accuracy`
and `Scoped accuracy evidence`; the existing comparison chart consumes the rebuilt
metrics. Editing old saved results is not performed. Rerun a scenario to obtain the
new evidence. Portfolio uncertainty ranges remain unavailable.

Validation guidance influenced the exact-population matching and independent
hand-calculated test: A actual 10/predicted 11 plus B actual 90/predicted 80 gives
11% WAPE, not an average of customer percentages. This is a synthetic acceptance
fixture, not a client accuracy claim. Real-engine route acceptance confirms evidence
availability and independently recomputes the error. Full regression: 380 backend
tests; 55 frontend tests/build pass. Final stricter unit/date gates also pass the
14-test targeted suite. Existing dependency/SQLite resource warnings remain.

UI score rendering was not rechecked in a new live browser calculation this slice;
the existing chart binding and saved JSON/workbook path were inspected/tested.
Historical factor availability caveats and post-test scenario selection still apply:
these scores do not establish causal impact or guarantee future improvement.

Next build: automate the existing saved-input refresh → validation → draft forecast
workflow with explicit source selection and safe retry. Do not auto-publish results.

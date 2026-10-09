# Monthly factor assumptions — 27 September 2026

Implemented in the existing factor-link scenario workflow, using the existing
models and pandas pipeline. No new dependency or paid service.

Users can choose a constant future assumption or enter different values for each
forecast month. The values describe the factor input used by that forecast month,
after the selected lag—not necessarily the observation month itself. Units and
location remain visible. Published observations available at forecast start take
priority; unfilled months remain missing, never zero or automatically interpolated.

API: `future_values` maps exact forecast month dates (`YYYY-MM-01`) to finite
numbers. It cannot be combined with a non-null `future_value`. Unknown dates,
booleans, strings and non-finite numbers are rejected. Existing constant payloads
remain supported. Monthly values are part of the frozen alignment and review token;
edits invalidate approval. Saved future inputs carry each month's value to each
series using the existing model calculation path. Orders and baseline stay unchanged.

Verification:
- 17 factor-link/public-factor tests pass; tests cover different values reaching
  saved future inputs, known-observation priority, blank blocking, invalid inputs,
  saved evidence and stale approval rejection.
- 55 frontend tests pass; production build passes (existing bundle-size warning).
- Local browser preview on the synthetic 14-series demo: September uses published
  129.086 despite assumption 140; October uses 150, November 160. No missing periods.
- Preview was cancelled; saved demo and customer orders were not changed.
- Local server restarted with updated code. No paid AI calls or new external feed.

Limits: applies to all series; does not forecast CPI/FX itself or establish causal
impact/accuracy improvement. Browser calculation of a new full scenario was not
repeated; persistence and model-input transfer were tested in isolated fixtures.
Next build: exact customer/SKU factor scope, preserving unaffected series.

# Public-factor comparison acceptance — 24 September 2026

## Delivered

Saved GSCPI snapshots can now be chosen under Forecast → Calculation details →
Scenarios → Link saved factor. Existing CSV/pandas/httpx, factor review, forecasting
models, scenario charts and Excel export are reused. No new dependency, paid account,
API key or client-data transmission was needed.

The planner explicitly accepts conservative vintage-month timing before previewing.
The model and baseline remain unchanged; the linked result is a separate scenario.
Each customer–SKU sales row is preserved. Future assumptions are explicit and
different from observations. Source attribution/terms accompany the saved evidence.

## Timing boundary — important

The NY Fed publishes revised histories; its [FAQ](https://www.newyorkfed.org/research/policy/gscpi)
explains that past readings can change. The retained CSV includes monthly versions.
Exact original release timestamps are still unverified.

For this comparison only, each nonempty vintage cell is treated as available at
23:59:59.999999 UTC on the last day of its labelled vintage month. A version whose
month has not ended at capture time is excluded. This is an **explicit conservative
assumption**, not verified release history. Raw snapshots remain context-only and
are not silently rewritten with fabricated publication dates.

For a historical target month, select only eligible revisions of the chosen lagged
observation before that month began. For future targets, freeze eligibility at the
first forecast month's start. Unknown future values require the approved constant
assumption; missing historical values block saving. The app does not trim history,
interpolate factors or backfill earlier months with today's revised column.

Historical model tests continue to hold the last training factor value constant
through each held-out window. This is not a full real-time forecast-origin replay
of all exogenous values. Timing assumptions and `release_dates_verified=false`
remain visible in saved evidence; no production accuracy claim follows from this.

The initial archive column is January 2022. Earlier sales periods can fail coverage.
The new demo deliberately starts February 2022; existing history was not shortened.
Public observations keep their real classification even when compared with sample
sales. Sample outputs stay labelled synthetic, with the mixed-provenance warning.

## Verification

- 334 backend tests, 43 frontend tests and production build pass. Existing build-size,
  font-path and dependency deprecation/resource warnings remain.
- New tests cover explicit timing consent, revisions excluded before their vintage
  cutoff, incomplete current vintage exclusion, missing data, raw-file tampering,
  immutable/idempotent saves, unchanged history, matching test periods and exports.
- Order-matching checks use the actual linked model output: orders above the estimate
  win; smaller orders consume part of the estimate; no-order months retain expected
  demand. Input order rows are unchanged.
- This does **not** automatically transfer a user's saved order review to the new
  scenario. That end-to-end order-aware comparison is the next bounded task.
- Browser flow completed consent → preview → approval → calculation → visible
  scenario chart and error comparison. Six future months and exact-value exports
  reconcile against all individual series.

## Demonstration results (not client accuracy)

Baseline `58df6ab41b1f`, comparison `4cb719fe31fb`; dataset
`c6c24b253d3a407182e890db687595f1`. Public snapshot
`01dd7f007895406db5d6cef198cf6520`.

Three synthetic customers × two SKUs, 55 months (330 sales rows), six-month horizon.
Same Ridge method and historical evaluation periods. Lag: two months; future
assumption: index value 1, clearly an assumption, not a predicted public reading.

September uses July's 0.79 from the August vintage, not the later 0.94 revision.
October–February use the approved assumption, since eligibility is frozen before
September began. Sales history and original baseline are untouched.

| Result | Baseline | With GSCPI |
| --- | ---: | ---: |
| Later-period error | 2.6434% | 2.8629% |
| Six-month model estimate, tonnes | 2245.6809 | 2248.1927 |

The factor worsened this sample's error. It was not promoted as the better forecast.
The test proves workflow and arithmetic, not a relationship in the client's business.
Reproduce with `scripts/verify_public_factor.py --verify 4cb719fe31fb` against the
running local app. `--seed` creates a separate labelled synthetic baseline.

## Next bounded task

Carry a reviewed customer list and order snapshot into a linked-factor comparison
without re-entry, while preserving source IDs, freshness, units and approval status.
Show booked / remaining / combined demand side by side per customer/SKU/month.
Require a separate review before publishing the changed result; no automatic order
mutation or promotion. Test partial fulfillment, cancellation, no-order customers,
stale feeds and exports. Then return to permission-cleared Iran CPI/FX inputs and
live AI acceptance when provider access and keys are available.

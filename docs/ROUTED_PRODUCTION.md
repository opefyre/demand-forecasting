# Product routes and machine workload

Implemented locally on 21 September 2026. This extends the existing monthly
tonne-based production workflow; it does not replace or reinterpret saved runs.

## What works

In Data → Match columns → Production data, choose **Product routes and machine
hours**. Match recipes, material stock, monthly capacity and production steps.
Expected deliveries remain optional. Each table can use a different worksheet and
heading row. Source cells, the reviewed mapping and source hashes stay with the run.

- Recipes declare both the product unit and material unit. Standard physical
  conversions use Pint. Packaging or product-specific conversions require an
  explicitly selected, reviewed unit-definition version with exact SKU, direction
  and effective dates. Sample definitions cannot be applied to real forecasts.
- Each product can pass through several machines. The route supplies step number,
  machine, hours per good finished-product unit and effective dates. Optional batch
  size and setup hours must be supplied together. Unmapped setup means no allowance,
  explicitly acknowledged during review.
- Customers for the same product are summed before rounding up batch counts.
  Machine load includes run hours and setup hours across all products using it.
- Available hours are already net of losses. Downtime or efficiency metadata is
  not deducted again. Missing machines/months, missing steps, overlapping versions,
  invalid quantities and incompatible units block the calculation.
- Monthly versions start on a month's first day and end on its last day. A blank
  end is open-ended. Date strings must be ISO dates; numeric date guesses and
  ambiguous regional date strings are rejected.
- Supply → Capacity shows required hours, available hours, utilization and
  shortfall. Expand the product steps to see run/setup hours. The details follow
  the same machine, period and attention filters as the overview.
- Plan-adjusted quantities recalculate the routes; exports include machine units
  and production-step details. The statistical forecast remains unchanged.

## Verified synthetic example

Files: `sample_data/routed_history_demo.csv` and
`outputs/01a0a5ce-routing/synthetic_routed_production.xlsx`. All values are invented
test inputs, not client recipes, capacity or conversion definitions. The workbook
was created with the bundled spreadsheet library and each sheet visually checked.

Saved dataset: `3689ddcebcd842a5975f9385243de3fa`. Successful retry:
`4baa070c7a944eb590feb644d53955e6`; run: `2557f6cc50ac`.
The earlier failed attempt remains recorded; it exposed stale background workers,
now addressed with app-owned worker shutdown (`BACKGROUND_JOBS.md`).

36 months of constant history, three customer/product series, three-month forecast
using Last observed. This intentionally simple fixture tests operational arithmetic,
not forecast skill. Zero error on this fixture is not client accuracy evidence.

Each month has A=150 KBlank and B=40 KBlank. Independent reconciliation gives:

| Measure | Calculation | Result |
|---|---|---:|
| Board requirement | 150 × 0.5 kg + 40 × 100 g ÷ 1,000 | 79 kg |
| Cutter | 150 × 0.2 + 2 batches × 2 + 40 × 0.5 + 1 setup | 55 h |
| Press | 150 × 0.1 + 2 batches × 1 | 17 h |
| Cutter shortfall | 55 required − 50 available | 5 h |
| September usable closing stock | 100 total − 10 held − 79 demand | 11 kg |

September's minimum-stock target is 20 kg and order multiple is 10 kg, producing
a 10 kg replenishment proposal. This is a proposal, not an assumed confirmed receipt.
The independent check is `scripts/verify_routed_sample.py --run 2557f6cc50ac`.

Automated checks include effective route changes, shared machines, batch rounding,
zero-demand setups, source isolation, invalid values, missing capacity and adjusted
plan exports (A=250 produces Cutter=77h and Press=28h). The full suite has 108 passing
checks. The import also now handles valid Excel exports without worksheet dimensions.

Browser checks: saved dataset review exposes all routed mappings and source
previews; the production-table menu fits 1280×850 and 390×844. Supply shows 55/50/5
hours for Cutter and 17/20/0 for Press. Searching Press filters the step detail to
its matching step. At 390px the document stays 390px wide; tables scroll within
their own surfaces, show a scroll hint when needed and can receive keyboard focus.
Horizontal scrolling exposed the available-hours and shortfall columns. The final
download endpoint returned all nine production-step rows with exact source cells.
The new sample was uploaded through the local API; the browser file-chooser
automation timed out, so a new-file browser upload is not claimed for this phase.

## Limits still open

- This is aggregate monthly workload from demand, **not** a feasible job sequence,
  production order release or inventory-netted production schedule. It does not
  prove within-month step precedence, available shifts, due-date feasibility or
  simultaneous resource constraints. Step numbers identify routes, not start times.
- Rates are per good finished-product unit and must already reflect process losses.
  Multi-level recipes, intermediate units, explicit yields, alternate-machine
  allocations, changeover matrices and versioned additions/removals of route steps
  are not inferred. All recorded step numbers must have coverage for the horizon.
- One production workbook; independent-file refresh pipelines remain open.
  Purchase quantities use the material master's unit. Forecast history itself is
  not converted by these production-unit rules.
- Client stock date, Warehouse-status meaning, packaging factors, recipes and
  machine definitions still require confirmation. No MPS field was invented.

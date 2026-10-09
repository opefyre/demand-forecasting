# Production workbook mapping

Implemented locally on 21 September 2026. The import no longer requires factory
worksheets or headings to match the sample template. The original tonne-based
workflow below is now extended by `ROUTED_PRODUCTION.md` for unit-aware monthly
multi-step machine workload. Finite production scheduling remains open.

## Workflow

Data → import/review dataset → Match columns → Production data. Select a table,
worksheet, heading row and exact columns for product recipes, material stock,
monthly capacity and optional expected deliveries. Preview original rows before
confirming. Known template headings get suggestions, never automatic approval.
Map the production-line column in history and confirm material stock's closing
date. These settings are saved with the dataset and each run's input manifest.

Required material units, balances, targets and order multiples are explicit.
Missing required cells produce errors with worksheet/cell references. Optional
unmapped holds and allowances mean zero only under the visible review confirmation;
invalid mapped values are not converted to zero. Expected delivery statuses must
be open/confirmed or explicitly closed/cancelled/received; unknown status blocks.

The calculation requires closing stock immediately before the first forecast
month. An open delivery due on or before stock date blocks, avoiding possible
double-counting. Receipts and capacity outside the forecast horizon do not create
misleading extra forecast periods. Formula-backed fields retain cached-result
counts and require acknowledgment that Excel was recalculated before export.

Existing sources remain unchanged. Leading-zero text identifiers are preserved.
Normalized tables retain source sheet, exact source cells, stock date and formula
counts. Baseline, scenario and approved-plan supply paths read saved mappings.
The plan supply path also verifies original source bytes against the saved hash.

## Verification

- Eight new checks, 95 total automated checks passing. They cover mapping review,
  mandatory fields, overlapping column assignments, source coordinates, stock
  dates, optional-value validity, holds, delivery status, horizon exclusions,
  positional previews and reuse of mappings in approved-plan supply.
- Browser: reopened the existing synthetic dataset without replacing it, reviewed
  recipe/material/capacity/delivery mappings, saved a new dataset, queued the normal
  forecast and opened its result and material outlook. Laptop 1280×850 and mobile
  390×844 checked; mobile page width remained 390 pixels.
- New synthetic dataset `8cfb2da761a840bc8b4404ea7b337773`; job
  `3a7541470bd94684bfb64b7efb355d2d`; run `e847b7a5adf5`.
- Result has 72 material-period and 60 line-period records. Independent calculation
  in `scripts/verify_production_sample.py` reproduced September PULP-HW requirements
  of 475.11774655062277 tonnes (saved as 475.118), usable opening 678 tonnes,
  no receipts that month, and closing 202.882 tonnes.

## Original mode limits and subsequent extension

- In the original tonne-based mode, finished-goods demand and capacity use tonnes. A product recipe's
  numerator is the material master's declared unit. Stock-unit definitions do not
  convert purchase-order or forecast-history quantities. The new routed mode uses
  explicit recipe/route product units and selected definitions.
- The original mode needs one confirmed line per item. Historical line changes block rather than choosing
  the last line. The routed extension covers multiple stages and machines; alternate
  allocations, explicit yields and detailed calendars still need further work.
- Four operational table types in the original mode; five in routed mode. Relationships/promotions sheets
  are not interpreted by this mapper; promotion factors use the separate factor
  workflow. No relationship effect is inferred.
- One workbook per production input. Separate-file operational pipelines and
  scheduled refresh remain open.
- Legacy saved runs retain their earlier parsing behavior and lack newly confirmed
  stock-date evidence. New dataset saves require the mapped review; old provenance
  is not retroactively upgraded.
- No client-specific MPS routing, unit conversions, stock dates or Warehouse-status
  meanings were invented. The client's material master and routing definitions
  remain needed. The synthetic result is not operational acceptance.
- Full delivery scope, authenticated approval, integrations and factory pilot
  remain incomplete.

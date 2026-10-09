# Dated factor imports — 24 September 2026

## Delivered

Data → External context → Import factor. A focused in-page flow reuses the existing
pandas/openpyxl parser and Radix controls: upload, match columns, identify source,
review, save. Other context cards are hidden while importing. No new navigation,
AI dependency or production/inventory feature was introduced.

- Excel (.xlsx/.xlsm), CSV, TSV and record-list JSON; worksheet and heading selection.
- One series per file: name, unit, geographic/market scope, provider/reference,
  daily/monthly/annual frequency, real versus sample classification.
- Separate period end, publication date, import timestamp, retained source hash and
  source row. Dates are Gregorian; no guessed Jalali or IRR/toman conversion.
- Monthly and annual observations require calendar period ends. Future observations,
  publication before period end, nonfinite/missing values, ambiguous dates, duplicate
  period/release pairs and mapped formulas are blocked. Negative values are allowed
  (e.g. deflation or negative growth).
- Missing periods remain missing; review shows gaps, latest period and its age.
  No guessed freshness threshold or annual-to-monthly conversion.
- Multiple releases for the same period are retained. The date check selects the
  latest release eligible by the chosen cutoff; date-only releases become eligible
  at the end of their UTC day, conservatively rather than at its start.
- Explicit review and exact-input token required at save, with source hash recheck.
  Save retries are idempotent and atomic publication never overwrites a snapshot.
- Update file reuses mapping and metadata, checks column identities, saves a new
  complete-file version and retains older copies. It does NOT infer an incremental
  merge. Version selection is available in the factor's details.
- Existing sales history, forecasts, scenario assumptions and order book unchanged.

## Evidence

315 backend tests and 42 frontend tests pass; production build succeeds. Eight new
factor-import tests cover revisions/cutoffs, gaps, invalid rows, required metadata,
review approval/tampering, source hash changes, retry identity, version preservation,
Excel date cells/formulas and preview/save/read API paths.

Browser sample: `sample_data/factor_observations_demo.csv`, explicitly saved as
**Synthetic price index · import demo**. Four periods, one revision, one missing
month (April 2025). The date check at 2025-02-28 shows January = 100, not the later
March revision of 101. Update-file UI restores all three mappings and fixed metadata.
Checked at 1366×900 and 390×844; narrow-screen page width remains 390px with stacked
controls. Date control input and button alignment were corrected during verification.

## Not yet delivered by this step

Importing these snapshots alone does not attach them to calculations. The subsequent
reviewed monthly linking workflow is now implemented; see FACTOR_LINKS.md. The
limitations below describe what the import step itself does not provide.
Uploader-declared publication dates are not independent proof of original releases.
No new live feed, client-system access, real-time FX claim, new forecast accuracy
claim or live AI provider call was added. The existing annual World Bank adapter
retains its first-local-capture limitation.

Follow-up implemented in FACTOR_LINKS.md: reviewed monthly alignment, frozen historical
release eligibility, explicit future assumptions, separate input/scenario versions,
numerical reconciliation and regression checks on existing order consumption.
Selective customer/SKU links and per-month future assumption curves remain pending.
Next, connect one approved public source through this contract with documented
publication/freshness behavior and appropriate licensing. Broad live connectors,
source-specific stale thresholds, Jalali conversion and live AI acceptance remain
separate work.

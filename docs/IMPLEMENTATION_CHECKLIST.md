# DemandLab delivery checklist

The earlier completion claim is withdrawn. The approved product direction remains in `PRODUCT_REDESIGN.md`; the latest UI acceptance criteria are in `UX_REBUILD.md`. A passing sample is not production certification.

## Working local workflow

- [x] Four primary pages: Forecast, Data, Plans and Supply; Settings is separate.
- [x] React, Radix UI, Phosphor Icons, Recharts and locally served fonts.
- [x] Visible laptop navigation labels, centered action dialogs and surface-based visual separation.
- [x] Guided file upload, selected Excel worksheet, column mapping, settings and validation.
- [x] Persist source bytes and input snapshots; reopen without re-uploading.
- [x] Retain unfinished import mappings and progress.
- [x] Reject invalid quantities/dates and missing required future factors before fitting.
- [x] Reusable saved-input forecast runs and individual mathematical method selection.
- [x] Connected history/forecast chart, exact period table and historical test metrics.
- [x] Explicit percentage scenarios tied to the exact originating forecast.
- [x] Local plan states, owner/reason records, comments and approval history.
- [x] Prevent quantity edits after approval/publication; open a plan's exact forecast.
- [x] BOM/material projection, quality holds, purchase receipts, MOQ and lead time.
- [x] Fix repeated material-order proposals and sum customers sharing the same SKU.
- [x] Validate production schemas, forecast SKU coverage and capacity line/month coverage.
- [x] Synthetic Iran manufacturing sample, saved baseline, selected-method rerun and scenario.
- [x] Local CSV/Excel run packages and explicit sample labels.
- [x] 27 automated checks plus browser checks at desktop/laptop/mobile sizes.

## Forecast reliability — implemented foundations, further validation needed

- [x] Expanding historical windows, requested-horizon evaluation and evidence warnings.
- [x] Seasonal, trend, intermittent and driver-aware candidates using open-source libraries.
- [x] Direct multi-step ML training and benchmark comparisons.
- [x] WAPE, bias, per-item metrics, interval coverage and demand diagnostics.
- [x] Explicit missing-future-value policies; no default silent extrapolation.
- [x] Period alignment before aggregation so mid-month observations are not discarded.
- [ ] Validate model selection on genuinely unseen site data, including selection bias and drift.
- [ ] Audit imputation/outlier treatment inside each validation fold to avoid leakage.
- [ ] Validate uncertainty independently, including correlated errors across products.
- [ ] Implement and validate richer hierarchy reconciliation and saved hierarchy views.
- [ ] Turn stockout/lost-sales flags into a governed correction workflow.
- [ ] Add new-product analogs, substitutions, cannibalisation and promotion modelling.

## Remaining operational product work

- [ ] Real connector ingestion, mapping, credential handling, provenance and freshness. Existing adapters only test availability.
- [ ] Approved Iranian/local/global factor sources with geographic coverage and user-reviewed future assumptions.
- [ ] Advanced factor scenarios and comparisons across materials, service, capacity and financial impact.
- [ ] Approved-plan supply recalculation and export; current Supply and Export use the statistical forecast.
- [ ] Editable production-data mapping, arbitrary unit conversion, service targets and validated days-of-cover.
- [ ] Like-for-like monitoring, closed-period actuals governance and an implemented retraining workflow.
- [ ] Validated AI-assisted explanations and mapping; deterministic helpers are not a complete AI assistant.
- [ ] Persian UI translation, complete RTL interaction testing and Jalali input/display selection.
- [ ] Real identity, role permissions, independent approval enforcement and tenant isolation.
- [ ] Durable production database, migrations, backups and retention controls.
- [ ] Queued, cancellable, recoverable forecast jobs with concurrent-user testing.
- [ ] Real-site pilot and user acceptance testing of every operational workflow.

## Completion rule

Do not call the app 100% complete or ready for live operational deployment while these items remain open. Missing functionality must be absent or labelled honestly in the UI, never represented by decorative cards or simulated connection status.

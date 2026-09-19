# DemandLab forecasting design

## Goal

Produce decision-grade demand forecasts that remain understandable to planners. Every forecast must expose the data treatment, validation design, model mix, external assumptions, uncertainty, and any commercial adjustment.

## Implemented reliability checklist

- [x] Canonical long-format ingestion for CSV, TSV, JSON, and Excel
- [x] Automatic recognition of the supplied wide commercial forecast workbook
- [x] Separate actual workbook rows from pre-existing forecast rows during training
- [x] Smart gap repair, negative-demand handling, duplicate aggregation, and robust outlier capping
- [x] Monthly, weekly, and daily calendar features with multiple seasonal harmonics
- [x] Statistical, intermittent-demand, linear, tree, and gradient-boosted models
- [x] Real ARIMA order selection and Theta forecasting
- [x] Horizon-matched expanding-window model evaluation
- [x] Per-series model ensembles with weak-model exclusion
- [x] WAPE, sMAPE, MAE, RMSE, bias, and interval coverage
- [x] Per-series and per-horizon residual-calibrated 80% planning intervals
- [x] Demand classification: smooth, erratic, intermittent, and lumpy
- [x] Internal/external signal classification with user correction
- [x] Future covariate files and an audited baseline-preserving scenario adjustment
- [x] Coherent bottom-up aggregation and variance-aware aggregate uncertainty
- [x] Model, driver, diagnostic, forecast, and run-setting exports
- [x] Premium monochrome shadcn-inspired planner interface
- [x] Automated reliability tests and end-to-end smoke test

## Architecture

1. `app/data.py` reads and canonicalizes source data, validates grain and cadence, repairs configured quality issues, and creates calendar features.
2. `app/forecast_engine.py` creates time-safe features, performs expanding-window validation, selects per-series ensembles, calibrates uncertainty, and creates audit artifacts.
3. `app/main.py` exposes the local API used by both the browser and future ERP/CRM/warehouse integrations.
4. `app/static/` provides the planner workflow: import, mapping, signal roles, settings, scenario adjustment, portfolio review, reliability diagnostics, comparison, and export.

## Benchmark rationale

The design follows established open-source forecasting patterns: rolling cross-validation at the prediction horizon, lag and rolling transformations, explicit future exogenous inputs, conformal/residual interval calibration, specialized intermittent-demand methods, and coherent hierarchy aggregation.

Primary references:

- MLForecast cross-validation: https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/cross_validation.html
- MLForecast exogenous variables: https://nixtlaverse.nixtla.io/mlforecast/docs/how-to-guides/exogenous_features.html
- StatsForecast model and interval patterns: https://nixtlaverse.nixtla.io/statsforecast/src/core/core.html
- HierarchicalForecast reconciliation: https://nixtlaverse.nixtla.io/hierarchicalforecast/methods.html

## Production follow-ons

These are deployment concerns rather than forecast-model gaps: authenticated connectors, scheduled runs, a shared database, planner approval workflows, role-based access, monitoring, and optional MinTrace reconciliation when independent forecasts are introduced at multiple hierarchy levels.

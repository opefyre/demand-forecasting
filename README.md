# DemandLab

A local forecasting workspace for manufacturing demand, consumption and sales. The core workflow has been rebuilt; this is **not yet a production multi-user SaaS**. The previous completion claim was withdrawn. See [the corrective checklist](docs/UX_REBUILD.md).

## Start

Run `./scripts/setup_mac.sh` once, then `./scripts/start_mac.sh`. Open http://127.0.0.1:8010.

The built React interface is included under `app/static/client`. To rebuild after interface changes:

```bash
cd frontend
npm ci
npm run build
```

## Everyday workflow

1. **Data → Import data**: upload actual history. CSV, TSV, JSON and Excel are supported. For Excel, choose the worksheet.
2. **Match columns**: choose the date, quantity and item identifier. The preview shows values from your file.
3. **Forecast settings**: choose units, interval, horizon and method. Extra factors are optional and need historical and future values.
4. **Review**: dates, quantities and future coverage are checked before saving. Any automatic data adjustments require acknowledgment.
5. **Forecast**: inspect the connected actual/forecast chart. Methods and Accuracy contain the model comparisons and historical test results. A saved dataset can be rerun without re-uploading.
6. **Scenarios**: create an explicitly named percentage change to the current forecast. This preserves the original forecast and does not refit a different model.
7. **Plans**: save a draft, record reasoned changes, review, approve and publish. Approved/published quantities cannot be changed in place.
8. **Supply**: inspect material requirements and capacity when a monthly, tonne-based operations workbook is supplied.

Files, selected worksheets and mappings are saved on this computer under `data/datasets`. Unfinished imports also preserve their progress in the browser. Saved datasets are immutable snapshots; changed settings create a new version.

## Required data

Minimum history: a date and nonnegative actual quantity in a consistent unit. An item column produces separate forecasts. At least six periods per item are needed; substantially more history is needed for meaningful seasonal evaluation.

Actual sales are not automatically unconstrained demand: stockouts, lost sales and missing periods require business interpretation. Net returns should be handled explicitly before importing a nonnegative demand target.

Extra factors must be columns in the historical data. Future files supply corresponding values for the forecast horizon. The default blocks incomplete future values; explicitly repeating the latest value or using a historical middle value are available assumptions. The app does not discover future macroeconomic conditions.

Production workbooks use the named sheets and columns in `sample_data/iran_operations_master.xlsx`. The BOM specifies quantity per tonne, so the forecast must use tonnes. Material proposals account for previous proposed orders without repeatedly ordering the same deficit. They are recommendations, not actual purchase orders. Capacity uses the available tonnes supplied in the file; downtime is contextual, not automatically deducted again.

## Iran and external data

Settings save the installation's site name, province and time zone. The reference profile is Qazvin, Iran. These labels do not fetch location-specific factors.

The Iran sample contains synthetic history, future assumptions, holidays and production data. It is a test fixture, **not a live economic feed**. Supply actual values from approved Iranian, regional or global sources through imports.

Connection diagnostics only test availability. They do not yet synchronise forecast-ready datasets. Source ingestion, field mapping, freshness and provenance need further implementation before connections can be called operational integrations.

## Open-source foundation

The interface uses React, Radix UI dialogs/selects/tooltips, Phosphor Icons, Recharts and locally served Instrument Sans/Vazirmatn fonts. Vite builds the client.

Forecasting and data handling reuse pandas, NumPy, statsmodels, scikit-learn, optional LightGBM, openpyxl, holidays and persiantools. Supported methods include seasonal naive, ETS, ARIMA, Theta, Croston, TSB, Ridge and tree-based learners. The application handles orchestration and business workflow.

## Verification and remaining work

```bash
.venv/bin/python -m unittest discover -s tests -v
```

On September 16, 27 tests passed, covering existing forecasting checks plus saved-source persistence, selected Excel worksheets, invalid-input rejection, monthly date alignment, material netting and exact quantity scenarios. Browser checks exercised a saved sample forecast, method rerun after refresh, a 10% scenario, responsive layouts and help/dialog controls.

Sample baseline `0a92b9d6b63c`: 720 rows, 12 items, 12-month horizon, 5.23% historical WAPE, 432 held-out predictions over three windows. Selected AutoETS run `7409b082a757`: 5.34% historical WAPE. These synthetic results are not a promise of live operational accuracy.

Still required for deployment: multi-user identity and permissions, production storage/backups, queued/cancellable jobs, operational connector ingestion, like-for-like monitoring, causal/relationship modelling, and validation with the site's real data. Local plan history is not authenticated approval enforcement. Product-relationship records and deterministic assistant responses are not presented as working AI modelling in the new interface.

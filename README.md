# DemandLab

Sales/demand forecasting for a Tehran manufacturing site, with reusable workflows
for other industries. History, relevant external factors and current customer
orders become a monthly demand forecast. Production, inventory and MRP execution
are not part of this product; their planning systems receive the exports.

This is a working local app, not a certified production multi-user SaaS.
See the [current checklist](docs/IMPLEMENTATION_CHECKLIST.md),
[pilot and operating guide](docs/RELEASE_PILOT.md).
Client workbook analysis and private demo outputs are kept outside the public repository.

Public-platform work: [delivery status](docs/PUBLIC_PLATFORM_DELIVERY.md),
[auth setup](docs/AUTH_PLATFORM_SETUP.md), [API coverage](docs/PUBLIC_API_COVERAGE.md).
The new company-auth mode is not enabled in the local demo; business migration
and connector delivery are still in progress.

## Start

Run `./scripts/setup_mac.sh` once, then `./scripts/start_mac.sh`.
Open http://127.0.0.1:8010. The launcher keeps the listener on this computer and
starts the forecast worker. Do not expose local evaluation mode to other users.

The React build is included under `app/static/client`. To rebuild:

```sh
cd frontend
npm ci
npm run build
```

## Everyday workflow

1. **Data**: maintain customers/products and orders, import sales history, and
   connect relevant external sources. Review units, calendar and what sales means.
2. **Forecast → New forecast**: use the single modal to choose sales history,
   horizon/calendar and factors, then review customers and orders. Include
   customers without orders, fulfilled/cancelled quantities and delivery dates.
   Reuse saved orders where compatible; missing data is not zero.
3. **Methods**: select one or more methods, or Automatic, then run. All selected
   methods belong to one named forecast and use the same reviewed inputs.
   Calculations run in a durable queue without overwriting earlier results.
4. **Review demand**: compare methods, filter customer, SKU and month; inspect charts, trends,
   tables, monthly grids and order coverage. Save useful views.
5. **Export demand**: download Excel, CSV or JSON. Export remaining expectation
   if the receiver already has orders; otherwise export open orders plus remaining
   expectation. Fulfilled quantities are excluded. Draft downloads are distinct
   from independently approved company planning releases.

In local mode, monthly updates guide history → calculation → factors → orders → changes → export.
Optional **Home → Monthly draft settings** prepares a baseline on a chosen
Persian/Gregorian day, on Tehran time. Only reviewed inputs are used; factors,
orders and approval still require review. Automation runs only while the server
is running. Help explains these flows in the app.
Advanced monthly/scenario automation is not yet migrated to company-auth mode;
those routes remain blocked rather than using shared demo stores.

Assistant accepts plain-language requests and uses existing calculation,
import-review and export services. Different model roles handle queries, data
review and decisions. Confirm proposed changes and any sharing with OpenAI.
AI does not replace numerical calculations or invent missing sales/factors.

## Inputs and quantities

Historical actuals need dated quantities in one consistent unit. Separate customer
and SKU mappings are needed for customer/product demand. At least six periods are
required per series; longer history is needed for meaningful annual-seasonality
testing. The client sales workbook has only seven actual months; this does not
establish annual seasonality or operational accuracy.

Sales, shipments, invoices and unconstrained demand are not interchangeable.
Review returns, missing periods and stockout effects. Monthly totals cannot be
redistributed into another calendar; dated transactions can be grouped into either.

At customer/SKU/unit/month level:

`remaining expectation = max(0, calculated forecast − fulfilled − open confirmed orders)`

Partial orders consume part of the estimate; orders above the estimate are retained.
An explicitly reviewed complete commitment can replace the full-month expectation.
Missing history, unknown/stale order books, mismatches and overdue open orders
block planning exports rather than inventing a value.

## Live external information

Data → Factors manages existing Iranian/global adapters, including Servix reference
FX, World Bank context, commodities, supply pressure, regional shipping, weather
and permission-gated Iranian CPI. Exact scope and limitations are in
[live sources](docs/LIVE_EXTERNAL_CONNECTIONS.md) and
[regional factors](docs/REGIONAL_LIVE_FACTORS.md).
Not every provider has complete, fresh, permission-cleared monthly history.
A quote is not an agreed factory FX basis; annual inflation is not monthly inflation.
No feed predicts future war, FX or inflation: future values remain explicit assumptions.

Factor selection uses numerical evidence and separate test periods.
Where publication-time evidence is unavailable, scenarios are labelled what-if
and unsupported accuracy scores are suppressed. Connecting a factor does not
guarantee that it improves accuracy.

## Open-source foundation

React, Radix UI, Phosphor Icons, Recharts, Vite, Instrument Sans and Vazirmatn;
StatsForecast, pandas, NumPy, scikit-learn, optional LightGBM, openpyxl, holidays
and persiantools; Huey, APScheduler and SQLite; Authlib and OpenAI Agents SDK.
Application code coordinates these tools and the sales workflow.

Methods include recent/weighted averages, seasonal reuse, Holt, Holt-Winters,
AutoETS, AutoARIMA, Theta, Croston variants, TSB, Ridge, Elastic Net and tree-based
learners. Eligibility depends on history, frequency and profile; an unavailable
chosen method is not silently replaced. See [methods](docs/FORECAST_METHODS.md).

## Operation and verification

Secrets remain server-side under the ignored `secrets/` folder or existing secure
credential storage. `run.py` loads `secrets/.env.local`; shell settings take precedence.
Never place keys in frontend code or chat. Company deployment requires OIDC/HTTPS,
real-account role acceptance and independent demand-release approval.
Local demo approval is not company approval.

```sh
.venv/bin/python -m unittest discover -s tests
cd frontend
node --test src/*.test.mjs
```

Repeat the isolated, no-AI/no-provider synthetic pilot from the project root:

```sh
.venv/bin/python scripts/verify_release_pilot.py --destination outputs/new-pilot
```

Choose a new output directory every time. It checks real imports/models/jobs,
customer-level order accounting, six exports and backup/restore without replacing
client records. Synthetic correctness and machine timings do not prove client
accuracy or company deployment readiness. Current evidence and remaining gates
are recorded in [the pilot guide](docs/RELEASE_PILOT.md).

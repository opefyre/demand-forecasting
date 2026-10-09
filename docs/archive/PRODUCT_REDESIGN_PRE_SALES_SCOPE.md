# Superseded scope — preserved 22 September 2026

Historical evidence only. The active sales/demand requirements and checklist in
../ supersede this operations-planning scope. Do not use this as a build backlog.

# DemandLab product redesign

Status: Approved scope; implementation is incomplete. See DELIVERY_PLAN.md and IMPLEMENTATION_CHECKLIST.md.  
Target: an operations-ready planning product for an Iran-based manufacturing site

## 1. Product promise

DemandLab should answer five questions without making the user understand forecasting jargon:

1. What is likely to happen?
2. What needs my attention today?
3. Why did the plan change?
4. What happens if an assumption changes?
5. What should purchasing, production, inventory, and sales do next?

The calculation engine can be sophisticated. The daily workflow must remain simple.

## 2. What is wrong with the current version

The current app is a useful technical proof, but it is not safe or clear enough for operations.

- The navigation is component-led. Some navigation items open dialogs instead of going to real pages.
- Screens do not have a consistent hierarchy, density, spacing system, or primary action.
- Forecasting, scenarios, data preparation, and settings compete for attention instead of forming one planning cycle.
- The chart visually separates history and forecast and does not communicate assumptions, method, or evidence clearly.
- The latest 18-month run used only one historical validation window. That is insufficient evidence for a production confidence claim.
- Only six future months of driver values were supplied; later driver values were silently held constant.
- Recursive machine-learning forecasts can drift toward their learned average over longer horizons.
- Aggregate uncertainty is simplified and does not account properly for correlated errors across products.
- External and internal factors are inferred partly from column names, not governed as traceable business signals.
- The user cannot deliberately choose and compare mathematical methods on the same test periods.

## 3. The operating model

The application will follow one visible cycle:

**Connect data → Check readiness → Create a plan → Compare methods → Resolve exceptions → Approve → Publish**

Every major navigation item opens a full page. Dialogs are reserved for small actions such as confirmation, naming a plan, or editing one assumption. There will be no page-sized slide-over panels.

## 4. Information architecture

### Today

The operational landing page, not a decorative dashboard.

- Current site, plan, time grain, and “data as of” date
- A short decision queue: shortages, unusual demand, missing inputs, forecast changes, and approvals
- Four decision metrics at most: forecast quality, service risk, excess risk, and data freshness
- Recent plan activity and ownership
- One primary action: **Review decisions**

### Plans

The system of record for planning cycles.

- Draft, under review, approved, and published plan versions
- Site, product/material scope, horizon, currency, units, calendar, and owners
- Comparison against last approved plan and actuals
- Approval trail, comments, and change reasons

### Forecast

The main workbench.

- Product/location hierarchy and saved views
- Exception queue on the left or above; selected series in the main area
- One continuous chart where the final actual point anchors the forecast
- Actual, baseline, adjusted plan, approved plan, and uncertainty shown only when relevant
- A compact table below the chart for exact monthly/weekly values
- Plain-language explanation of the chosen method, the strongest drivers, and the evidence quality
- Overrides require a reason and never overwrite the statistical baseline

### Method comparison

A full page reached from Forecast, never a modal.

- Same historical test periods for every candidate
- Side-by-side accuracy, bias, stability, and business impact
- Overlay chart and errors by horizon
- Clear winner explanation and warnings when evidence is weak
- User can accept the recommendation or select a method deliberately

### Supply & materials

Turns demand into operational consequences.

- Inventory projection, safety stock, service target, and days of cover
- Material requirements through bills of material
- Supplier lead times, open purchase orders, minimum order quantities, and shortages
- Production capacity, line calendars, planned downtime, and constraints
- Recommended action with owner and due date

### Scenarios

A full workspace for comparing assumptions.

- Base, optimistic, pessimistic, and custom scenarios
- Exchange rate, price, promotion, capacity, lead time, material availability, energy disruption, and weather assumptions
- Demand, revenue/cost, inventory, service, and capacity impact in one comparison
- Assumptions are explicit, dated, sourced, and owned

### Data & integrations

- ERP/MRP, database, API, spreadsheet, CSV, and scheduled-folder connections
- Source health, last refresh, row counts, missing fields, and failures
- A guided column mapper using business language
- Data-quality issues must be resolved or explicitly accepted before a run

### Performance

- Forecast accuracy and bias by site, family, item, method, and horizon
- Forecast value add: whether manual changes improved or worsened the result
- Model drift, data drift, override quality, and service/inventory outcomes

### Administration

- Sites, calendars, units, currencies, roles, approvals, integrations, and model policy
- Kept out of daily planning navigation

## 5. Forecast method experience

The default control uses understandable choices:

- **Recommended** — the system selects a proven winner for each series
- **Seasonal pattern** — for repeating weekly, monthly, or annual demand
- **Trend** — for demand that is steadily rising or falling
- **Intermittent demand** — for slow-moving materials and spare parts
- **Driver-aware** — uses approved internal and external factors
- **Advanced comparison** — exposes individual mathematical methods

The advanced list will include:

- Naive and seasonal naive baselines
- Moving and weighted moving averages
- Holt and Holt-Winters exponential smoothing
- ETS, Theta, ARIMA, and SARIMA
- Croston, SBA, and TSB for intermittent demand
- Regression, Ridge, and Elastic Net with business drivers
- LightGBM or CatBoost for nonlinear driver relationships
- Multiple-seasonality methods such as MSTL/TBATS where the data supports them
- Ensembles only when they beat the baseline on honest backtests

Deep-learning models will not be used merely to make the product sound advanced. They become candidates only when data volume and cross-series evidence justify them.

## 6. Reliability rules

1. Every candidate must beat or meaningfully complement a simple baseline on identical rolling test windows.
2. Use at least three rolling validation windows when the history allows it. Otherwise label the result **Limited evidence**, reduce automation, and explain why.
3. Validate at the requested forecast horizon. A good one-month model is not automatically a good eighteen-month model.
4. Prefer direct multi-horizon forecasting for long horizons; do not rely blindly on recursive predictions that can collapse toward an average.
5. Never silently extend future factor values. Ask for assumptions, use a named scenario, or exclude that factor beyond its known range.
6. Detect stockouts, lost sales, one-off orders, missing periods, outliers, lifecycle changes, and structural breaks before fitting.
7. Keep baseline, factor adjustment, planner override, and approved plan as separate auditable layers.
8. Calibrate uncertainty by horizon and account for cross-series relationships when aggregating.
9. Reconcile forecasts across product, material, customer, warehouse, and site hierarchies.
10. Store model version, input snapshot, metrics, assumptions, warnings, owner, and approval state for every published plan.
11. Use champion/challenger monitoring and forecast-value-add reporting after actuals arrive.
12. Block automatic publication when critical data is stale or forecast evidence is inadequate.

## 7. Iran manufacturing context

### First-class location model

`Company → Iran site → warehouse → production line → product family → SKU/material → customer/market`

Signals are attached to their real geographic scope:

- Site coordinates: temperature, precipitation, power/energy exposure, and local disruption
- Province/region: logistics, labour, local weather, and infrastructure
- Iran: exchange rates, inflation, producer prices, regulation, holidays, and import conditions
- Middle East and neighbouring trade corridors: freight and geopolitical/logistics risk
- Global: commodity inputs, shipping, supplier countries, and world macro conditions

### Local product requirements

- Persian and English interface, including right-to-left readiness
- Jalali and Gregorian calendars
- Iran public holidays, Nowruz, Ramadan/Eid effects where relevant, and plant-specific shutdown calendars
- Asia/Tehran time zone
- Rial and toman display without ambiguity
- Local units of measure and conversion rules
- Offline-friendly imports, retryable synchronisation, and cached source snapshots

### Signal hierarchy

**Plant and ERP signals — highest authority**

- Orders, shipments, consumption, inventory, stockouts, returns, prices, promotions
- Production orders, output, yield/scrap, downtime/OEE, capacity, maintenance
- Bills of material, open purchase orders, supplier lead times, shortages, and quality holds

**Iran official signals**

- Central Bank of Iran: exchange rates, inflation/price indicators, industrial and economic time series
- Statistical Center of Iran: population, labour, household, and sector indicators
- Iran Mercantile Exchange: relevant commodity and input prices
- Energy and infrastructure authorities: electricity or fuel constraints where accessible
- Customs and trade data where legally and technically accessible

**Global signals**

- World Bank and IMF macroeconomic series
- NASA POWER or a licensed weather provider using exact site coordinates
- Global commodity, freight, and trade indicators relevant to the bill of materials

The engine will not ingest every available signal. Each signal needs a source, refresh date, geographic scope, future availability, business meaning, and demonstrated forecast value. Correlation will not be presented as causation.

## 8. Visual and interaction system

- Premium black-and-white foundation with colour reserved for status and risk
- A distinctive professional type family with Persian-compatible fallback
- Minimum 16 px body text; small labels used sparingly
- One page title, one clear primary action, and predictable secondary actions
- Consistent 4/8/12/16/24/32 spacing scale
- Consistent control heights and table density
- Full keyboard navigation, visible focus, sufficient contrast, and no information conveyed by colour alone
- Responsive designs explicitly verified at 1440, 1280, 1024, 768, and 390 px
- Tables for operational work; charts for patterns, comparison, and uncertainty
- Progressive disclosure: common decisions first, technical detail on demand
- Every empty, loading, error, stale-data, and limited-evidence state is designed deliberately

## 9. Where AI helps—and where it does not

AI may:

- Map imported columns and explain data-quality problems
- Summarise what changed and identify items that deserve review
- Suggest relevant signals or scenario assumptions with traceable evidence
- Explain model selection and draft planner comments
- Answer questions about the current approved data and plan

AI must not silently alter the forecast, invent external data, approve a plan, or replace the numerical forecasting engine. Published values always remain reproducible.

## 10. Delivery sequence

### Phase 1 — trustworthy planning foundation

- Rebuild navigation, page hierarchy, responsive layout, and design system
- Replace modal-based navigation with real pages
- Add plan/site context and a usable Today queue
- Rebuild forecast chart and method comparison
- Correct long-horizon validation, missing future-factor behaviour, and confidence labels
- Add explicit method selection, plan versions, overrides, and audit history
- Run a complete sample from import to published forecast

### Phase 2 — manufacturing operations

- Inventory, safety stock, bills of material, material requirements, lead time, capacity, and shortage views
- Scenario comparison and approval workflow
- ERP/database connectors and scheduled file ingestion
- Iran calendars, currencies, localisation, and official-data adapters

### Phase 3 — scale and intelligence

- Hierarchical reconciliation and probabilistic aggregation
- Lifecycle, substitution/cannibalisation, promotions, and new-product forecasting
- Champion/challenger monitoring and automated retraining policy
- AI planning assistant with strict source and approval controls

## 11. Acceptance gates for Phase 1

- A user can complete the planning cycle without training or forecasting jargon.
- No navigation item opens a modal.
- The last actual point and first forecast segment are visually and numerically continuous.
- No forecast is labelled reliable without sufficient historical validation.
- Unknown future factor values are visible and require a stated treatment.
- Recommended and manually selected methods can be compared on the same historical windows.
- Every manual change has an owner, time, reason, and reversible history.
- The main workflow works at laptop, tablet, and mobile widths without clipped controls or unreadable text.
- A sample Iran-site planning cycle includes demand, at least one plant signal, at least one Iran-level signal, uncertainty, an override, approval, and export.

## 12. Benchmark principles adopted

- SAP IBP: planner workspaces, alerts, versions, simulations, notes, drill-down, and change history
- Oracle: user-configurable forecasting profiles, multiple demand streams, causal factors, exceptions, and supply-planning consequences
- Netstock: exception-based planning that leaves stable items alone and directs attention to risk, bias, stockout, and excess
- Anaplan/Kinaxis: explicit scenarios, cross-functional inputs, approvals, and closed-loop demand/supply decisions

The redesign deliberately avoids copying their complexity. It keeps their operational discipline while reducing the daily interface to the decisions a planner must make.

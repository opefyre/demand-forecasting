# Company-separated forecasting API — 9 October 2026

Delivered backend milestone. **Not activated in the local demo.** The assistant,
remaining business screens and connection management still need migration before
company mode can be enabled. Legacy business routes continue to fail closed in
company mode; existing local mode is unchanged.

## What is implemented

- Separate company stores for sales files/datasets, customer directory, order
  books/reviews, factors, unit rules, forecast results/jobs and approval records.
  The request identity chooses the company; request bodies cannot override it.
- Public file upload/list/inspection and dataset preview/save/read. Editing
  history or settings means saving an immutable revision with `parent_dataset_id`.
- Customer/product directory remains connected to the order book. Orders use
  version checks, followed by an exact reviewed snapshot before calculation.
- Factor observation review and linking reuse the existing publication-date,
  lag, future-assumption and freshness checks. Linked inputs are a new dataset;
  old history and factor evidence are preserved. Provider refresh/configuration
  endpoints are **not yet migrated**; this milestone makes no live-source claim.
- One forecast request records all selected methods atomically under one name.
  Existing Huey workers calculate each method with explicit company stores.
  Repeated submissions return the same group; conflicting reuse is rejected.
- Job status/cancellation, grouped method results, customer/SKU/month demand
  filters, CSV/Excel/JSON demand exports and original model/accuracy workbooks.
- Separate draft and approved-report permissions. Viewers cannot inspect
  history, orders, factors, jobs or draft results. A different authorized approver
  must approve a release; expired/changed/superseded releases cannot be exported.
- Queue recovery on worker restart. Partial/staged results are not public, and
  company workers cannot fall back to the legacy demo's order store.

No forecasting formulas, new model packages, AI calls or credentials were changed.
The existing StatsForecast/scikit-learn engine, SQLAlchemy, Huey, Pandas and
openpyxl implementations are reused. Company order-aware preparation currently
supports monthly planning with Gregorian or Persian month boundaries.

## API workflow

All paths below are relative to `/api/v1`. Use a company-bound Bearer key;
browser-session mutations additionally need the session's CSRF header.

1. `POST /customers` for customer/product records, if not already present.
2. `POST /sources` (multipart file + role) and `POST /datasets/preview` to review
   mappings/conventions. `POST /datasets` saves the reviewed input version.
3. `GET /datasets/{id}/factors`, then preview/save selected factors if required.
   This may return a derived dataset; use its ID for the remaining steps.
4. `GET /datasets/{id}/orders` joins the directory and existing order book.
   `PUT` saves a version-checked order book; explicit review is still required.
5. `POST /datasets/{id}/orders/preview`, then `/orders/snapshots` with the exact
   review token, reviewed inputs and unique request ID. Mark incomplete order
   coverage as unknown, not zero; final demand export will remain blocked.
6. `POST /forecasts` with name, dataset ID, reviewed snapshot ID, methods and
   request ID. `GET /forecast-methods` lists library-supported methods; actual
   availability still depends on history/factors. `GET /forecasts/{id}` shows
   every selected method's job/result together.
7. `GET /runs/{id}/demand` or `/export` to review/filter drafts. Specify the
   receiving-system mode: remaining forecast if its orders are already present,
   or combined demand otherwise. Fulfilled quantities are not planned twice.
8. Preview/submit `/releases`; a different approver confirms the frozen review
   token. Read-only users then access `/releases/{id}` and its approved export.

OpenAPI describes payloads, response codes, Bearer/session authentication and
CSRF. [Source-derived route inventory](PUBLIC_API_COVERAGE.md) distinguishes
delivered routes from legacy work still blocked in company mode.

## Verification

`tests/test_platform_sales.py` exercises two companies, four customers, two SKUs,
36 historical months, excess/partial/no orders, multiple methods, factor linking,
Gregorian/Persian calendars, filtered exports, independent approval, concurrent
retries, failed-transaction rollback, cancellation, recovery and path guards.
Data is synthetic and disposable; no client records or live providers are used.

`tests/test_platform_access.py` additionally exercises the sales upload/read
routes through the identity bridge, CSRF middleware and restricted Bearer access.
Final test counts are recorded in [the delivery checklist](PUBLIC_PLATFORM_DELIVERY.md).

## Next substantial work

Finish company-scoped assistant/conversations, views, settings, actual-vs-forecast
checks and frontend routing. Then complete remaining useful resource lifecycle
operations and SFTP/Odoo/Sheets/HTTP ingestion, notifications and schedules.
Google/mail/provider setup and deployment acceptance remain separate final gates.

# Public API coverage

Generated from source decorators by `scripts/audit_public_api.py`; no application stores are opened.

56 implemented v1 operations. The rest of the useful business API is not delivered yet.

New company authentication deliberately blocks unscoped legacy business routes. Existing local mode remains unchanged.

The Better Auth identity service supplies library-managed login, Google callback, verification, recovery and factor endpoints behind `/api/login/*`. These are not business CRUD.

Delivered business resources: customers/products, sales sources/datasets, versioned orders/reviews, factor preparation, grouped forecasts/jobs/results/exports and independent releases. Pending: complete archive/revision lifecycle, live feeds/assumptions, actual-vs-forecast checks, personal chats/views, company settings/units, connections/ingestion runs and schedules. Immutable source evidence is never destructively overwritten.

| Method | Route | Delivery | Source |
|---|---|---|---|
| GET | `/api/actual-results/{evaluation_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:980` |
| GET | `/api/actual-results/{evaluation_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:988` |
| POST | `/api/actuals/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:929` |
| POST | `/api/actuals/sources/{source_id}/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:937` |
| GET | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:975` |
| POST | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:966` |
| POST | `/api/actuals/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:956` |
| POST | `/api/ai/chat` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:780` |
| GET | `/api/ai/conversations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:740` |
| GET | `/api/ai/conversations/{turn_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:744` |
| GET | `/api/ai/conversations/{turn_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:769` |
| POST | `/api/ai/conversations/{turn_id}/manage` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:763` |
| POST | `/api/ai/conversations/{turn_id}/rename` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:758` |
| POST | `/api/ai/import-mapping` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:714` |
| GET | `/api/ai/status` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:710` |
| POST | `/api/ai/turns/{turn_id}/actions/{index}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:874` |
| GET | `/api/ai/turns/{turn_id}/actions/{index}/progress` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:853` |
| GET | `/api/ai/turns/{turn_id}/history` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:731` |
| POST | `/api/assistant/mapping` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1007` |
| POST | `/api/assistant/query` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:998` |
| GET | `/api/auth/callback` | Account bridge; existing OIDC routes also retained | `app/security.py:264` |
| GET | `/api/auth/login` | Account bridge; existing OIDC routes also retained | `app/security.py:256` |
| POST | `/api/auth/logout` | Account bridge; existing OIDC routes also retained | `app/security.py:288` |
| GET | `/api/auth/providers` | Account bridge; existing OIDC routes also retained | `app/security.py:252` |
| GET | `/api/auth/session` | Account bridge; existing OIDC routes also retained | `app/security.py:229` |
| GET | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:134` |
| POST | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:138` |
| POST | `/api/customers/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:146` |
| PUT | `/api/customers/{customer_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:142` |
| GET | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:88` |
| PUT | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:93` |
| GET | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1035` |
| POST | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1318` |
| POST | `/api/datasets/validate` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1306` |
| GET | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1536` |
| POST | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1554` |
| POST | `/api/datasets/{dataset_id}/forecast-factors/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1545` |
| GET | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1748` |
| POST | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1800` |
| POST | `/api/datasets/{dataset_id}/forecast-orders/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1791` |
| GET | `/api/datasets/{dataset_id}/forecast-orders/template/{role}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1768` |
| POST | `/api/datasets/{dataset_id}/forecast-settings` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1345` |
| POST | `/api/decisions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:674` |
| GET | `/api/export/{run_id}/{kind}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:594` |
| POST | `/api/factor-imports` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1247` |
| POST | `/api/factor-imports/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1237` |
| POST | `/api/factor-imports/table` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1228` |
| GET | `/api/factor-imports/{snapshot_id}/available` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1257` |
| GET | `/api/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1219` |
| POST | `/api/factors/{factor_id}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1295` |
| GET | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:320` |
| POST | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:323` |
| GET | `/api/forecast-updates/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:326` |
| GET | `/api/forecast-updates/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:332` |
| POST | `/api/forecast-updates/{key}/steps` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:329` |
| POST | `/api/fva/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:924` |
| GET | `/api/health` | Health check; not a business API | `app/main.py:306` |
| GET | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:841` |
| POST | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:899` |
| GET | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:199` |
| POST | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:204` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/accept` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:222` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:210` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:217` |
| GET | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:846` |
| POST | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:851` |
| GET | `/api/integrations/folders/candidates/{identifier}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:877` |
| POST | `/api/integrations/folders/candidates/{identifier}/forecast` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:889` |
| POST | `/api/integrations/folders/{identifier}/auto-draft` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:883` |
| POST | `/api/integrations/folders/{identifier}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:861` |
| POST | `/api/integrations/folders/{identifier}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:867` |
| GET | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:137` |
| POST | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:150` |
| POST | `/api/integrations/order-folders/{run_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:156` |
| POST | `/api/integrations/order-folders/{run_id}/reuse` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:145` |
| POST | `/api/integrations/order-folders/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:163` |
| POST | `/api/integrations/{connector_id}/sync` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:907` |
| GET | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1085` |
| POST | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1133` |
| POST | `/api/inventory/sources` | Out of sales/demand scope; do not publish | `app/main.py:1039` |
| POST | `/api/inventory/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1047` |
| POST | `/api/inventory/sources/{source_id}/values` | Out of sales/demand scope; do not publish | `app/main.py:1067` |
| POST | `/api/inventory/validate` | Out of sales/demand scope; do not publish | `app/main.py:1058` |
| GET | `/api/inventory/{snapshot_id}` | Out of sales/demand scope; do not publish | `app/main.py:1142` |
| GET | `/api/inventory/{snapshot_id}/projection` | Out of sales/demand scope; do not publish | `app/main.py:1150` |
| GET | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1166` |
| POST | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1211` |
| POST | `/api/inventory/{snapshot_id}/receipts/validate` | Out of sales/demand scope; do not publish | `app/main.py:1201` |
| GET | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1622` |
| POST | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1628` |
| GET | `/api/jobs/{job_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1663` |
| POST | `/api/jobs/{job_id}/cancel` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1672` |
| POST | `/api/jobs/{job_id}/retry` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1680` |
| GET | `/api/live-sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:471` |
| PUT | `/api/live-sources/servix/credential` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:475` |
| PUT | `/api/live-sources/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:498` |
| PUT | `/api/live-sources/{key}/permission` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:505` |
| POST | `/api/live-sources/{key}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:512` |
| GET | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:248` |
| POST | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:248` |
| GET | `/api/monitoring` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:918` |
| POST | `/api/operations/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:336` |
| GET | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:89` |
| PUT | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:94` |
| GET | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:647` |
| POST | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:686` |
| POST | `/api/plans/{plan_id}/comments` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:816` |
| GET | `/api/plans/{plan_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:765` |
| POST | `/api/plans/{plan_id}/overrides` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:793` |
| POST | `/api/plans/{plan_id}/overrides/{override_id}/revert` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:826` |
| GET | `/api/plans/{plan_id}/quantities` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:742` |
| PATCH | `/api/plans/{plan_id}/status` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:776` |
| GET | `/api/plans/{plan_id}/supply` | Out of sales/demand scope; do not publish | `app/main.py:734` |
| POST | `/api/plans/{plan_id}/versions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:752` |
| POST | `/api/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:327` |
| GET | `/api/production/schema` | Out of sales/demand scope; do not publish | `app/main.py:1095` |
| GET | `/api/production/sources/{source_id}` | Out of sales/demand scope; do not publish | `app/main.py:1114` |
| POST | `/api/production/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1103` |
| POST | `/api/receipts/sources` | Out of sales/demand scope; do not publish | `app/main.py:1174` |
| POST | `/api/receipts/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1182` |
| GET | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:194` |
| POST | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:196` |
| POST | `/api/recurring-forecasts/{key}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:198` |
| POST | `/api/run` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:345` |
| GET | `/api/run-list` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1693` |
| POST | `/api/run-saved` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1371` |
| GET | `/api/runs/latest` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:624` |
| GET | `/api/runs/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1497` |
| GET | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1501` |
| POST | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1581` |
| POST | `/api/runs/{run_id}/factor-batch` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1611` |
| POST | `/api/runs/{run_id}/factor-batch/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1604` |
| POST | `/api/runs/{run_id}/factor-comparison` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1518` |
| GET | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1527` |
| POST | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1572` |
| POST | `/api/runs/{run_id}/factor-links/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1563` |
| POST | `/api/runs/{run_id}/factor-preparation` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1589` |
| GET | `/api/runs/{run_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1598` |
| GET | `/api/runs/{run_id}/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1509` |
| POST | `/api/sales/inputs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:232` |
| GET | `/api/sales/inputs/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:254` |
| GET | `/api/sales/inputs/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:268` |
| GET | `/api/sales/inputs/{key}/outlook` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:261` |
| GET | `/api/sales/releases` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:217` |
| POST | `/api/sales/releases` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:227` |
| POST | `/api/sales/releases/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:225` |
| GET | `/api/sales/releases/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:229` |
| POST | `/api/sales/releases/{key}/approve` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:231` |
| GET | `/api/sales/releases/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:233` |
| GET | `/api/sales/runs/{run_id}/inputs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:176` |
| POST | `/api/sales/runs/{run_id}/order-comparison` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:142` |
| POST | `/api/sales/runs/{run_id}/order-comparison/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:132` |
| POST | `/api/sales/runs/{run_id}/order-reuse` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:122` |
| GET | `/api/sales/runs/{run_id}/order-reuse/choices` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:102` |
| POST | `/api/sales/runs/{run_id}/order-reuse/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:115` |
| GET | `/api/sales/runs/{run_id}/sample` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:204` |
| GET | `/api/sales/runs/{run_id}/starter` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:195` |
| GET | `/api/sales/runs/{run_id}/template/{role}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:182` |
| GET | `/api/sales/schema` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:97` |
| POST | `/api/sales/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:154` |
| POST | `/api/sales/sources/{key}/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:166` |
| POST | `/api/sales/validate` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:225` |
| GET | `/api/sales/views` | Pending company-scoped v1 migration; blocked in new auth mode | `app/forecast_views.py:60` |
| POST | `/api/sales/views` | Pending company-scoped v1 migration; blocked in new auth mode | `app/forecast_views.py:65` |
| GET | `/api/sample/{name}` | Local demo helper; do not publish | `app/main.py:1702` |
| PUT | `/api/site` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:133` |
| POST | `/api/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1012` |
| GET | `/api/sources/{source_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1020` |
| POST | `/api/sources/{source_id}/sheet` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1026` |
| GET | `/api/today` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:652` |
| GET | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1090` |
| POST | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1125` |
| GET | `/api/v1/access-options` | Implemented; company-scoped | `app/platform_api.py:121` |
| GET | `/api/v1/api-keys` | Implemented; company-scoped | `app/platform_api.py:117` |
| POST | `/api/v1/api-keys` | Implemented; company-scoped | `app/platform_api.py:125` |
| DELETE | `/api/v1/api-keys/{key_id}` | Implemented; company-scoped | `app/platform_api.py:133` |
| PATCH | `/api/v1/api-keys/{key_id}` | Implemented; company-scoped | `app/platform_api.py:129` |
| POST | `/api/v1/api-keys/{key_id}/rotate` | Implemented; company-scoped | `app/platform_api.py:137` |
| GET | `/api/v1/audit-events` | Implemented; company-scoped | `app/platform_api.py:170` |
| GET | `/api/v1/customers` | Implemented; company-scoped | `app/platform_api.py:72` |
| POST | `/api/v1/customers` | Implemented; company-scoped | `app/platform_api.py:79` |
| DELETE | `/api/v1/customers/{customer_id}` | Implemented; company-scoped | `app/platform_api.py:95` |
| GET | `/api/v1/customers/{customer_id}` | Implemented; company-scoped | `app/platform_api.py:85` |
| PUT | `/api/v1/customers/{customer_id}` | Implemented; company-scoped | `app/platform_api.py:89` |
| GET | `/api/v1/customers/{customer_id}/products` | Implemented; company-scoped | `app/platform_api.py:103` |
| PUT | `/api/v1/customers/{customer_id}/products` | Implemented; company-scoped | `app/platform_api.py:107` |
| GET | `/api/v1/datasets` | Implemented; company-scoped | `app/platform_sales_api.py:155` |
| POST | `/api/v1/datasets` | Implemented; company-scoped | `app/platform_sales_api.py:167` |
| POST | `/api/v1/datasets/preview` | Implemented; company-scoped | `app/platform_sales_api.py:160` |
| GET | `/api/v1/datasets/{dataset_id}` | Implemented; company-scoped | `app/platform_sales_api.py:175` |
| GET | `/api/v1/datasets/{dataset_id}/factors` | Implemented; company-scoped | `app/platform_sales_api.py:229` |
| POST | `/api/v1/datasets/{dataset_id}/factors` | Implemented; company-scoped | `app/platform_sales_api.py:243` |
| POST | `/api/v1/datasets/{dataset_id}/factors/preview` | Implemented; company-scoped | `app/platform_sales_api.py:236` |
| GET | `/api/v1/datasets/{dataset_id}/orders` | Implemented; company-scoped | `app/platform_sales_api.py:179` |
| PUT | `/api/v1/datasets/{dataset_id}/orders` | Implemented; company-scoped | `app/platform_sales_api.py:185` |
| POST | `/api/v1/datasets/{dataset_id}/orders/preview` | Implemented; company-scoped | `app/platform_sales_api.py:191` |
| POST | `/api/v1/datasets/{dataset_id}/orders/snapshots` | Implemented; company-scoped | `app/platform_sales_api.py:198` |
| GET | `/api/v1/factors` | Implemented; company-scoped | `app/platform_sales_api.py:209` |
| POST | `/api/v1/factors/imports` | Implemented; company-scoped | `app/platform_sales_api.py:219` |
| POST | `/api/v1/factors/imports/preview` | Implemented; company-scoped | `app/platform_sales_api.py:213` |
| GET | `/api/v1/factors/{snapshot_id}` | Implemented; company-scoped | `app/platform_sales_api.py:225` |
| GET | `/api/v1/forecast-methods` | Implemented; company-scoped | `app/platform_sales_api.py:282` |
| GET | `/api/v1/forecasts` | Implemented; company-scoped | `app/platform_sales_api.py:293` |
| POST | `/api/v1/forecasts` | Implemented; company-scoped | `app/platform_sales_api.py:251` |
| GET | `/api/v1/forecasts/{forecast_id}` | Implemented; company-scoped | `app/platform_sales_api.py:298` |
| POST | `/api/v1/invitations` | Implemented; company-scoped | `app/platform_api.py:145` |
| DELETE | `/api/v1/invitations/{invitation_id}` | Implemented; company-scoped | `app/platform_api.py:149` |
| GET | `/api/v1/jobs/{job_id}` | Implemented; company-scoped | `app/platform_sales_api.py:303` |
| POST | `/api/v1/jobs/{job_id}/cancel` | Implemented; company-scoped | `app/platform_sales_api.py:307` |
| GET | `/api/v1/me` | Implemented; company-scoped | `app/platform_api.py:49` |
| GET | `/api/v1/members` | Implemented; company-scoped | `app/platform_api.py:141` |
| DELETE | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:162` |
| PATCH | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:153` |
| POST | `/api/v1/members/{member_id}/revoke-sessions` | Implemented; company-scoped | `app/platform_api.py:166` |
| GET | `/api/v1/order-snapshots/{snapshot_id}` | Implemented; company-scoped | `app/platform_sales_api.py:205` |
| GET | `/api/v1/releases` | Implemented; company-scoped | `app/platform_sales_api.py:363` |
| POST | `/api/v1/releases` | Implemented; company-scoped | `app/platform_sales_api.py:375` |
| POST | `/api/v1/releases/preview` | Implemented; company-scoped | `app/platform_sales_api.py:370` |
| GET | `/api/v1/releases/{release_id}` | Implemented; company-scoped | `app/platform_sales_api.py:380` |
| POST | `/api/v1/releases/{release_id}/approve` | Implemented; company-scoped | `app/platform_sales_api.py:385` |
| GET | `/api/v1/releases/{release_id}/export` | Implemented; company-scoped | `app/platform_sales_api.py:391` |
| GET | `/api/v1/runs/{run_id}` | Implemented; company-scoped | `app/platform_sales_api.py:313` |
| GET | `/api/v1/runs/{run_id}/demand` | Implemented; company-scoped | `app/platform_sales_api.py:340` |
| GET | `/api/v1/runs/{run_id}/export` | Implemented; company-scoped | `app/platform_sales_api.py:346` |
| GET | `/api/v1/runs/{run_id}/files/{kind}` | Implemented; company-scoped | `app/platform_sales_api.py:319` |
| GET | `/api/v1/sources` | Implemented; company-scoped | `app/platform_sales_api.py:144` |
| POST | `/api/v1/sources` | Implemented; company-scoped | `app/platform_sales_api.py:124` |
| GET | `/api/v1/sources/{source_id}` | Implemented; company-scoped | `app/platform_sales_api.py:135` |
| GET | `/api/weather` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1271` |
| POST | `/api/weather/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1276` |
| GET | `/api/weather/{snapshot_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1286` |
| GET | `/api/workspace` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:632` |

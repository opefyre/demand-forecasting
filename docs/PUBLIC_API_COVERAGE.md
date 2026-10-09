# Public API coverage

Generated from source decorators by `scripts/audit_public_api.py`; no application stores are opened.

131 implemented v1 operations. The rest of the useful business API is not delivered yet.

New company authentication deliberately blocks unscoped legacy business routes. Existing local mode remains unchanged.

The Better Auth identity service supplies library-managed login, Google callback, verification, recovery and factor endpoints behind `/api/login/*`. These are not business CRUD.

Delivered business resources: customers/products, sales sources/datasets, versioned orders/reviews, factor preparation and comparisons, grouped forecasts/jobs/results/exports, independent releases, personal chats/views, advanced assistant scenarios, monthly updates, administrator recurring drafts, actual-vs-forecast checks, company settings/units and external factor connections. Pending: complete archive/revision lifecycle, business-system connections/ingestion runs and notifications. Immutable source evidence is never destructively overwritten.

| Method | Route | Delivery | Source |
|---|---|---|---|
| GET | `/api/actual-results/{evaluation_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:982` |
| GET | `/api/actual-results/{evaluation_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:990` |
| POST | `/api/actuals/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:931` |
| POST | `/api/actuals/sources/{source_id}/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:939` |
| GET | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:977` |
| POST | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:968` |
| POST | `/api/actuals/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:958` |
| POST | `/api/ai/chat` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:799` |
| GET | `/api/ai/conversations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:754` |
| GET | `/api/ai/conversations/{turn_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:759` |
| GET | `/api/ai/conversations/{turn_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:787` |
| POST | `/api/ai/conversations/{turn_id}/manage` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:780` |
| POST | `/api/ai/conversations/{turn_id}/rename` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:774` |
| POST | `/api/ai/import-mapping` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:726` |
| GET | `/api/ai/status` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:721` |
| POST | `/api/ai/turns/{turn_id}/actions/{index}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:897` |
| GET | `/api/ai/turns/{turn_id}/actions/{index}/progress` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:875` |
| GET | `/api/ai/turns/{turn_id}/history` | Pending company-scoped v1 migration; blocked in new auth mode | `app/ai_workspace.py:744` |
| POST | `/api/assistant/mapping` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1009` |
| POST | `/api/assistant/query` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1000` |
| GET | `/api/auth/callback` | Account bridge; existing OIDC routes also retained | `app/security.py:269` |
| GET | `/api/auth/login` | Account bridge; existing OIDC routes also retained | `app/security.py:261` |
| POST | `/api/auth/logout` | Account bridge; existing OIDC routes also retained | `app/security.py:293` |
| GET | `/api/auth/providers` | Account bridge; existing OIDC routes also retained | `app/security.py:257` |
| GET | `/api/auth/session` | Account bridge; existing OIDC routes also retained | `app/security.py:229` |
| GET | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:134` |
| POST | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:138` |
| POST | `/api/customers/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:146` |
| PUT | `/api/customers/{customer_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:142` |
| GET | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:88` |
| PUT | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:93` |
| GET | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1037` |
| POST | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1320` |
| POST | `/api/datasets/validate` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1308` |
| GET | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1549` |
| POST | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1567` |
| POST | `/api/datasets/{dataset_id}/forecast-factors/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1558` |
| GET | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1761` |
| POST | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1813` |
| POST | `/api/datasets/{dataset_id}/forecast-orders/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1804` |
| GET | `/api/datasets/{dataset_id}/forecast-orders/template/{role}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1781` |
| POST | `/api/datasets/{dataset_id}/forecast-settings` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1347` |
| POST | `/api/decisions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:676` |
| GET | `/api/export/{run_id}/{kind}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:596` |
| POST | `/api/factor-imports` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1249` |
| POST | `/api/factor-imports/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1239` |
| POST | `/api/factor-imports/table` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1230` |
| GET | `/api/factor-imports/{snapshot_id}/available` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1259` |
| GET | `/api/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1221` |
| POST | `/api/factors/{factor_id}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1297` |
| GET | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:322` |
| POST | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:325` |
| GET | `/api/forecast-updates/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:328` |
| GET | `/api/forecast-updates/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:334` |
| POST | `/api/forecast-updates/{key}/steps` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:331` |
| POST | `/api/fva/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:926` |
| GET | `/api/health` | Health check; not a business API | `app/main.py:308` |
| GET | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:843` |
| POST | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:901` |
| GET | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:200` |
| POST | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:205` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/accept` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:223` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:211` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:218` |
| GET | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:848` |
| POST | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:853` |
| GET | `/api/integrations/folders/candidates/{identifier}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:879` |
| POST | `/api/integrations/folders/candidates/{identifier}/forecast` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:891` |
| POST | `/api/integrations/folders/{identifier}/auto-draft` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:885` |
| POST | `/api/integrations/folders/{identifier}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:863` |
| POST | `/api/integrations/folders/{identifier}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:869` |
| GET | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:138` |
| POST | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:151` |
| POST | `/api/integrations/order-folders/{run_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:157` |
| POST | `/api/integrations/order-folders/{run_id}/reuse` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:146` |
| POST | `/api/integrations/order-folders/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:164` |
| POST | `/api/integrations/{connector_id}/sync` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:909` |
| GET | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1087` |
| POST | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1135` |
| POST | `/api/inventory/sources` | Out of sales/demand scope; do not publish | `app/main.py:1041` |
| POST | `/api/inventory/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1049` |
| POST | `/api/inventory/sources/{source_id}/values` | Out of sales/demand scope; do not publish | `app/main.py:1069` |
| POST | `/api/inventory/validate` | Out of sales/demand scope; do not publish | `app/main.py:1060` |
| GET | `/api/inventory/{snapshot_id}` | Out of sales/demand scope; do not publish | `app/main.py:1144` |
| GET | `/api/inventory/{snapshot_id}/projection` | Out of sales/demand scope; do not publish | `app/main.py:1152` |
| GET | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1168` |
| POST | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1213` |
| POST | `/api/inventory/{snapshot_id}/receipts/validate` | Out of sales/demand scope; do not publish | `app/main.py:1203` |
| GET | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1635` |
| POST | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1641` |
| GET | `/api/jobs/{job_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1676` |
| POST | `/api/jobs/{job_id}/cancel` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1685` |
| POST | `/api/jobs/{job_id}/retry` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1693` |
| GET | `/api/live-sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:472` |
| PUT | `/api/live-sources/servix/credential` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:476` |
| PUT | `/api/live-sources/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:499` |
| PUT | `/api/live-sources/{key}/permission` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:506` |
| POST | `/api/live-sources/{key}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:513` |
| GET | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:253` |
| POST | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:253` |
| GET | `/api/monitoring` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:920` |
| POST | `/api/operations/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:338` |
| GET | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:89` |
| PUT | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:94` |
| GET | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:649` |
| POST | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:688` |
| POST | `/api/plans/{plan_id}/comments` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:818` |
| GET | `/api/plans/{plan_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:767` |
| POST | `/api/plans/{plan_id}/overrides` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:795` |
| POST | `/api/plans/{plan_id}/overrides/{override_id}/revert` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:828` |
| GET | `/api/plans/{plan_id}/quantities` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:744` |
| PATCH | `/api/plans/{plan_id}/status` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:778` |
| GET | `/api/plans/{plan_id}/supply` | Out of sales/demand scope; do not publish | `app/main.py:736` |
| POST | `/api/plans/{plan_id}/versions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:754` |
| POST | `/api/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:329` |
| GET | `/api/production/schema` | Out of sales/demand scope; do not publish | `app/main.py:1097` |
| GET | `/api/production/sources/{source_id}` | Out of sales/demand scope; do not publish | `app/main.py:1116` |
| POST | `/api/production/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1105` |
| POST | `/api/receipts/sources` | Out of sales/demand scope; do not publish | `app/main.py:1176` |
| POST | `/api/receipts/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1184` |
| GET | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:196` |
| POST | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:198` |
| POST | `/api/recurring-forecasts/{key}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:200` |
| POST | `/api/run` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:347` |
| GET | `/api/run-list` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1706` |
| POST | `/api/run-saved` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1373` |
| GET | `/api/runs/latest` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:626` |
| GET | `/api/runs/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1510` |
| GET | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1514` |
| POST | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1594` |
| POST | `/api/runs/{run_id}/factor-batch` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1624` |
| POST | `/api/runs/{run_id}/factor-batch/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1617` |
| POST | `/api/runs/{run_id}/factor-comparison` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1531` |
| GET | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1540` |
| POST | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1585` |
| POST | `/api/runs/{run_id}/factor-links/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1576` |
| POST | `/api/runs/{run_id}/factor-preparation` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1602` |
| GET | `/api/runs/{run_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1611` |
| GET | `/api/runs/{run_id}/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1522` |
| POST | `/api/sales/inputs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:236` |
| GET | `/api/sales/inputs/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:258` |
| GET | `/api/sales/inputs/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:272` |
| GET | `/api/sales/inputs/{key}/outlook` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:265` |
| GET | `/api/sales/releases` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:217` |
| POST | `/api/sales/releases` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:227` |
| POST | `/api/sales/releases/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:225` |
| GET | `/api/sales/releases/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:229` |
| POST | `/api/sales/releases/{key}/approve` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:231` |
| GET | `/api/sales/releases/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/demand_releases.py:233` |
| GET | `/api/sales/runs/{run_id}/inputs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:180` |
| POST | `/api/sales/runs/{run_id}/order-comparison` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:146` |
| POST | `/api/sales/runs/{run_id}/order-comparison/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:136` |
| POST | `/api/sales/runs/{run_id}/order-reuse` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:126` |
| GET | `/api/sales/runs/{run_id}/order-reuse/choices` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:106` |
| POST | `/api/sales/runs/{run_id}/order-reuse/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:119` |
| GET | `/api/sales/runs/{run_id}/sample` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:208` |
| GET | `/api/sales/runs/{run_id}/starter` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:199` |
| GET | `/api/sales/runs/{run_id}/template/{role}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:186` |
| GET | `/api/sales/schema` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:101` |
| POST | `/api/sales/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:158` |
| POST | `/api/sales/sources/{key}/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:170` |
| POST | `/api/sales/validate` | Pending company-scoped v1 migration; blocked in new auth mode | `app/sales_api.py:229` |
| GET | `/api/sales/views` | Pending company-scoped v1 migration; blocked in new auth mode | `app/forecast_views.py:80` |
| POST | `/api/sales/views` | Pending company-scoped v1 migration; blocked in new auth mode | `app/forecast_views.py:85` |
| GET | `/api/sample/{name}` | Local demo helper; do not publish | `app/main.py:1715` |
| PUT | `/api/site` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:135` |
| POST | `/api/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1014` |
| GET | `/api/sources/{source_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1022` |
| POST | `/api/sources/{source_id}/sheet` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1028` |
| GET | `/api/today` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:654` |
| GET | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1092` |
| POST | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1127` |
| GET | `/api/v1/access-options` | Implemented; company-scoped | `app/platform_api.py:121` |
| GET | `/api/v1/actuals/{evaluation_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:331` |
| GET | `/api/v1/actuals/{evaluation_id}/export` | Implemented; company-scoped | `app/platform_workspace_api.py:337` |
| POST | `/api/v1/ai/chat` | Implemented; company-scoped | `app/ai_workspace.py:799` |
| GET | `/api/v1/ai/conversations` | Implemented; company-scoped | `app/ai_workspace.py:754` |
| GET | `/api/v1/ai/conversations/{turn_id}` | Implemented; company-scoped | `app/ai_workspace.py:759` |
| GET | `/api/v1/ai/conversations/{turn_id}/export` | Implemented; company-scoped | `app/ai_workspace.py:787` |
| POST | `/api/v1/ai/conversations/{turn_id}/manage` | Implemented; company-scoped | `app/ai_workspace.py:780` |
| POST | `/api/v1/ai/conversations/{turn_id}/rename` | Implemented; company-scoped | `app/ai_workspace.py:774` |
| POST | `/api/v1/ai/import-mapping` | Implemented; company-scoped | `app/ai_workspace.py:726` |
| GET | `/api/v1/ai/status` | Implemented; company-scoped | `app/ai_workspace.py:721` |
| POST | `/api/v1/ai/turns/{turn_id}/actions/{index}` | Implemented; company-scoped | `app/ai_workspace.py:897` |
| GET | `/api/v1/ai/turns/{turn_id}/actions/{index}/progress` | Implemented; company-scoped | `app/ai_workspace.py:875` |
| GET | `/api/v1/ai/turns/{turn_id}/history` | Implemented; company-scoped | `app/ai_workspace.py:744` |
| GET | `/api/v1/api-keys` | Implemented; company-scoped | `app/platform_api.py:117` |
| POST | `/api/v1/api-keys` | Implemented; company-scoped | `app/platform_api.py:125` |
| DELETE | `/api/v1/api-keys/{key_id}` | Implemented; company-scoped | `app/platform_api.py:133` |
| PATCH | `/api/v1/api-keys/{key_id}` | Implemented; company-scoped | `app/platform_api.py:129` |
| POST | `/api/v1/api-keys/{key_id}/rotate` | Implemented; company-scoped | `app/platform_api.py:137` |
| GET | `/api/v1/audit-events` | Implemented; company-scoped | `app/platform_api.py:170` |
| GET | `/api/v1/connections/external-sources` | Implemented; company-scoped | `app/platform_workspace_api.py:342` |
| PUT | `/api/v1/connections/external-sources/servix/credential` | Implemented; company-scoped | `app/platform_workspace_api.py:360` |
| PUT | `/api/v1/connections/external-sources/{key}` | Implemented; company-scoped | `app/platform_workspace_api.py:346` |
| PUT | `/api/v1/connections/external-sources/{key}/permission` | Implemented; company-scoped | `app/platform_workspace_api.py:350` |
| POST | `/api/v1/connections/external-sources/{key}/refresh` | Implemented; company-scoped | `app/platform_workspace_api.py:354` |
| GET | `/api/v1/customers` | Implemented; company-scoped | `app/platform_api.py:72` |
| POST | `/api/v1/customers` | Implemented; company-scoped | `app/platform_api.py:79` |
| POST | `/api/v1/customers/imports` | Implemented; company-scoped | `app/platform_workspace_api.py:105` |
| POST | `/api/v1/customers/imports/preview` | Implemented; company-scoped | `app/platform_workspace_api.py:87` |
| DELETE | `/api/v1/customers/{customer_id}` | Implemented; company-scoped | `app/platform_api.py:95` |
| GET | `/api/v1/customers/{customer_id}` | Implemented; company-scoped | `app/platform_api.py:85` |
| PUT | `/api/v1/customers/{customer_id}` | Implemented; company-scoped | `app/platform_api.py:89` |
| GET | `/api/v1/customers/{customer_id}/factor-profiles` | Implemented; company-scoped | `app/platform_workspace_api.py:111` |
| PUT | `/api/v1/customers/{customer_id}/factor-profiles` | Implemented; company-scoped | `app/platform_workspace_api.py:117` |
| GET | `/api/v1/customers/{customer_id}/products` | Implemented; company-scoped | `app/platform_api.py:103` |
| PUT | `/api/v1/customers/{customer_id}/products` | Implemented; company-scoped | `app/platform_api.py:107` |
| GET | `/api/v1/datasets` | Implemented; company-scoped | `app/platform_sales_api.py:156` |
| POST | `/api/v1/datasets` | Implemented; company-scoped | `app/platform_sales_api.py:168` |
| POST | `/api/v1/datasets/preview` | Implemented; company-scoped | `app/platform_sales_api.py:161` |
| GET | `/api/v1/datasets/{dataset_id}` | Implemented; company-scoped | `app/platform_sales_api.py:176` |
| GET | `/api/v1/datasets/{dataset_id}/factors` | Implemented; company-scoped | `app/platform_sales_api.py:239` |
| POST | `/api/v1/datasets/{dataset_id}/factors` | Implemented; company-scoped | `app/platform_sales_api.py:253` |
| POST | `/api/v1/datasets/{dataset_id}/factors/preview` | Implemented; company-scoped | `app/platform_sales_api.py:246` |
| POST | `/api/v1/datasets/{dataset_id}/forecast-settings` | Implemented; company-scoped | `app/platform_workspace_api.py:135` |
| GET | `/api/v1/datasets/{dataset_id}/orders` | Implemented; company-scoped | `app/platform_sales_api.py:180` |
| PUT | `/api/v1/datasets/{dataset_id}/orders` | Implemented; company-scoped | `app/platform_sales_api.py:190` |
| POST | `/api/v1/datasets/{dataset_id}/orders/preview` | Implemented; company-scoped | `app/platform_sales_api.py:196` |
| POST | `/api/v1/datasets/{dataset_id}/orders/snapshots` | Implemented; company-scoped | `app/platform_sales_api.py:203` |
| GET | `/api/v1/datasets/{dataset_id}/orders/template/{role}` | Implemented; company-scoped | `app/platform_workspace_api.py:151` |
| GET | `/api/v1/factors` | Implemented; company-scoped | `app/platform_sales_api.py:219` |
| POST | `/api/v1/factors/imports` | Implemented; company-scoped | `app/platform_sales_api.py:229` |
| POST | `/api/v1/factors/imports/preview` | Implemented; company-scoped | `app/platform_sales_api.py:223` |
| GET | `/api/v1/factors/{snapshot_id}` | Implemented; company-scoped | `app/platform_sales_api.py:235` |
| GET | `/api/v1/forecast-methods` | Implemented; company-scoped | `app/platform_sales_api.py:292` |
| GET | `/api/v1/forecast-updates` | Implemented; company-scoped | `app/platform_workflow_api.py:157` |
| POST | `/api/v1/forecast-updates` | Implemented; company-scoped | `app/platform_workflow_api.py:162` |
| GET | `/api/v1/forecast-updates/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:167` |
| GET | `/api/v1/forecast-updates/{key}/export` | Implemented; company-scoped | `app/platform_workflow_api.py:178` |
| POST | `/api/v1/forecast-updates/{key}/steps` | Implemented; company-scoped | `app/platform_workflow_api.py:172` |
| GET | `/api/v1/forecasts` | Implemented; company-scoped | `app/platform_sales_api.py:303` |
| POST | `/api/v1/forecasts` | Implemented; company-scoped | `app/platform_sales_api.py:261` |
| GET | `/api/v1/forecasts/{forecast_id}` | Implemented; company-scoped | `app/platform_sales_api.py:308` |
| POST | `/api/v1/invitations` | Implemented; company-scoped | `app/platform_api.py:145` |
| DELETE | `/api/v1/invitations/{invitation_id}` | Implemented; company-scoped | `app/platform_api.py:149` |
| GET | `/api/v1/jobs` | Implemented; company-scoped | `app/platform_workspace_api.py:193` |
| GET | `/api/v1/jobs/{job_id}` | Implemented; company-scoped | `app/platform_sales_api.py:313` |
| POST | `/api/v1/jobs/{job_id}/cancel` | Implemented; company-scoped | `app/platform_sales_api.py:317` |
| POST | `/api/v1/jobs/{job_id}/retry` | Implemented; company-scoped | `app/platform_workspace_api.py:199` |
| GET | `/api/v1/me` | Implemented; company-scoped | `app/platform_api.py:49` |
| GET | `/api/v1/members` | Implemented; company-scoped | `app/platform_api.py:141` |
| DELETE | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:162` |
| PATCH | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:153` |
| POST | `/api/v1/members/{member_id}/revoke-sessions` | Implemented; company-scoped | `app/platform_api.py:166` |
| GET | `/api/v1/order-snapshots/{snapshot_id}` | Implemented; company-scoped | `app/platform_sales_api.py:210` |
| GET | `/api/v1/order-snapshots/{snapshot_id}/demand` | Implemented; company-scoped | `app/platform_workspace_api.py:231` |
| GET | `/api/v1/order-snapshots/{snapshot_id}/export` | Implemented; company-scoped | `app/platform_workspace_api.py:258` |
| GET | `/api/v1/orders/schema` | Implemented; company-scoped | `app/platform_workspace_api.py:146` |
| GET | `/api/v1/recurring-forecasts` | Implemented; company-scoped | `app/platform_workflow_api.py:189` |
| POST | `/api/v1/recurring-forecasts` | Implemented; company-scoped | `app/platform_workflow_api.py:194` |
| DELETE | `/api/v1/recurring-forecasts/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:210` |
| GET | `/api/v1/recurring-forecasts/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:199` |
| PUT | `/api/v1/recurring-forecasts/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:204` |
| POST | `/api/v1/recurring-forecasts/{key}/check` | Implemented; company-scoped | `app/platform_workflow_api.py:222` |
| GET | `/api/v1/releases` | Implemented; company-scoped | `app/platform_sales_api.py:373` |
| POST | `/api/v1/releases` | Implemented; company-scoped | `app/platform_sales_api.py:385` |
| POST | `/api/v1/releases/preview` | Implemented; company-scoped | `app/platform_sales_api.py:380` |
| GET | `/api/v1/releases/{release_id}` | Implemented; company-scoped | `app/platform_sales_api.py:390` |
| POST | `/api/v1/releases/{release_id}/approve` | Implemented; company-scoped | `app/platform_sales_api.py:395` |
| GET | `/api/v1/releases/{release_id}/export` | Implemented; company-scoped | `app/platform_sales_api.py:401` |
| GET | `/api/v1/runs` | Implemented; company-scoped | `app/platform_workspace_api.py:161` |
| GET | `/api/v1/runs/{run_id}` | Implemented; company-scoped | `app/platform_sales_api.py:323` |
| GET | `/api/v1/runs/{run_id}/actuals` | Implemented; company-scoped | `app/platform_workspace_api.py:308` |
| POST | `/api/v1/runs/{run_id}/actuals` | Implemented; company-scoped | `app/platform_workspace_api.py:326` |
| POST | `/api/v1/runs/{run_id}/actuals/preview` | Implemented; company-scoped | `app/platform_workspace_api.py:321` |
| GET | `/api/v1/runs/{run_id}/demand` | Implemented; company-scoped | `app/platform_sales_api.py:350` |
| GET | `/api/v1/runs/{run_id}/export` | Implemented; company-scoped | `app/platform_sales_api.py:356` |
| POST | `/api/v1/runs/{run_id}/factor-batch` | Implemented; company-scoped | `app/platform_workflow_api.py:94` |
| POST | `/api/v1/runs/{run_id}/factor-batch/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:88` |
| POST | `/api/v1/runs/{run_id}/factor-comparison` | Implemented; company-scoped | `app/platform_workflow_api.py:106` |
| GET | `/api/v1/runs/{run_id}/factor-links` | Implemented; company-scoped | `app/platform_workflow_api.py:59` |
| POST | `/api/v1/runs/{run_id}/factor-links` | Implemented; company-scoped | `app/platform_workflow_api.py:71` |
| POST | `/api/v1/runs/{run_id}/factor-links/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:65` |
| POST | `/api/v1/runs/{run_id}/factor-preparation` | Implemented; company-scoped | `app/platform_workflow_api.py:77` |
| GET | `/api/v1/runs/{run_id}/factor-profiles` | Implemented; company-scoped | `app/platform_workflow_api.py:83` |
| GET | `/api/v1/runs/{run_id}/factors` | Implemented; company-scoped | `app/platform_workflow_api.py:100` |
| GET | `/api/v1/runs/{run_id}/files/{kind}` | Implemented; company-scoped | `app/platform_sales_api.py:329` |
| POST | `/api/v1/runs/{run_id}/order-comparison` | Implemented; company-scoped | `app/platform_workflow_api.py:151` |
| POST | `/api/v1/runs/{run_id}/order-comparison/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:145` |
| POST | `/api/v1/runs/{run_id}/order-reuse` | Implemented; company-scoped | `app/platform_workflow_api.py:139` |
| GET | `/api/v1/runs/{run_id}/order-reuse/choices` | Implemented; company-scoped | `app/platform_workflow_api.py:122` |
| POST | `/api/v1/runs/{run_id}/order-reuse/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:133` |
| GET | `/api/v1/runs/{run_id}/order-snapshots` | Implemented; company-scoped | `app/platform_workspace_api.py:223` |
| POST | `/api/v1/runs/{run_id}/order-snapshots` | Implemented; company-scoped | `app/platform_workspace_api.py:249` |
| POST | `/api/v1/runs/{run_id}/order-snapshots/preview` | Implemented; company-scoped | `app/platform_workspace_api.py:244` |
| GET | `/api/v1/runs/{run_id}/orders/starter` | Implemented; company-scoped | `app/platform_workspace_api.py:173` |
| GET | `/api/v1/runs/{run_id}/orders/template/{role}` | Implemented; company-scoped | `app/platform_workspace_api.py:184` |
| POST | `/api/v1/scenario-jobs` | Implemented; company-scoped | `app/platform_workflow_api.py:112` |
| PUT | `/api/v1/settings/site` | Implemented; company-scoped | `app/platform_workspace_api.py:75` |
| GET | `/api/v1/sources` | Implemented; company-scoped | `app/platform_sales_api.py:145` |
| POST | `/api/v1/sources` | Implemented; company-scoped | `app/platform_sales_api.py:125` |
| GET | `/api/v1/sources/{source_id}` | Implemented; company-scoped | `app/platform_sales_api.py:136` |
| POST | `/api/v1/sources/{source_id}/preview` | Implemented; company-scoped | `app/platform_workspace_api.py:123` |
| POST | `/api/v1/sources/{source_id}/sheet` | Implemented; company-scoped | `app/platform_workspace_api.py:129` |
| GET | `/api/v1/units` | Implemented; company-scoped | `app/platform_workspace_api.py:79` |
| POST | `/api/v1/units` | Implemented; company-scoped | `app/platform_workspace_api.py:83` |
| GET | `/api/v1/views` | Implemented; company-scoped | `app/platform_workspace_api.py:276` |
| POST | `/api/v1/views` | Implemented; company-scoped | `app/platform_workspace_api.py:287` |
| DELETE | `/api/v1/views/{view_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:303` |
| GET | `/api/v1/views/{view_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:292` |
| PUT | `/api/v1/views/{view_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:298` |
| GET | `/api/v1/workspace` | Implemented; company-scoped | `app/platform_workspace_api.py:69` |
| GET | `/api/weather` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1273` |
| POST | `/api/weather/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1278` |
| GET | `/api/weather/{snapshot_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1288` |
| GET | `/api/workspace` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:634` |

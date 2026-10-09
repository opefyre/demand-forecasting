# Public API coverage

Generated from source decorators by `scripts/audit_public_api.py`; no application stores are opened.

150 implemented v1 operations. The rest of the useful business API is not delivered yet.

New company authentication deliberately blocks unscoped legacy business routes. Existing local mode remains unchanged.

The Better Auth identity service supplies library-managed login, Google callback, verification, recovery and factor endpoints behind `/api/login/*`. These are not business CRUD.

Delivered business resources: customers/products, sales sources/datasets, versioned orders/reviews, factor preparation and comparisons, grouped forecasts/jobs/results/exports, independent releases, personal chats/views, advanced assistant scenarios, monthly updates, administrator recurring drafts, actual-vs-forecast checks, company settings/units, external factors, read-only HTTPS/SFTP/Google Sheets inputs, Odoo 18/19 customers/orders, reviewed ingestion receipts, permission-checked scheduled captures and company-scoped resource naming/archive/restore/revisions. Lifecycle routes accept sources, datasets, forecasts and runs; grouped methods share one metadata record. Pending: notifications and deployment acceptance. Immutable source evidence is never destructively overwritten.

| Method | Route | Delivery | Source |
|---|---|---|---|
| GET | `/api/actual-results/{evaluation_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:983` |
| GET | `/api/actual-results/{evaluation_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:991` |
| POST | `/api/actuals/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:932` |
| POST | `/api/actuals/sources/{source_id}/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:940` |
| GET | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:978` |
| POST | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:969` |
| POST | `/api/actuals/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:959` |
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
| POST | `/api/assistant/mapping` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1010` |
| POST | `/api/assistant/query` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1001` |
| GET | `/api/auth/callback` | Account bridge; existing OIDC routes also retained | `app/security.py:269` |
| GET | `/api/auth/login` | Account bridge; existing OIDC routes also retained | `app/security.py:261` |
| POST | `/api/auth/logout` | Account bridge; existing OIDC routes also retained | `app/security.py:293` |
| GET | `/api/auth/providers` | Account bridge; existing OIDC routes also retained | `app/security.py:257` |
| GET | `/api/auth/session` | Account bridge; existing OIDC routes also retained | `app/security.py:229` |
| GET | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:176` |
| POST | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:180` |
| POST | `/api/customers/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:188` |
| PUT | `/api/customers/{customer_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:184` |
| GET | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:88` |
| PUT | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:93` |
| GET | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1038` |
| POST | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1321` |
| POST | `/api/datasets/validate` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1309` |
| GET | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1554` |
| POST | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1572` |
| POST | `/api/datasets/{dataset_id}/forecast-factors/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1563` |
| GET | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1766` |
| POST | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1818` |
| POST | `/api/datasets/{dataset_id}/forecast-orders/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1809` |
| GET | `/api/datasets/{dataset_id}/forecast-orders/template/{role}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1786` |
| POST | `/api/datasets/{dataset_id}/forecast-settings` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1348` |
| POST | `/api/decisions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:677` |
| GET | `/api/export/{run_id}/{kind}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:597` |
| POST | `/api/factor-imports` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1250` |
| POST | `/api/factor-imports/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1240` |
| POST | `/api/factor-imports/table` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1231` |
| GET | `/api/factor-imports/{snapshot_id}/available` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1260` |
| GET | `/api/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1222` |
| POST | `/api/factors/{factor_id}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1298` |
| GET | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:322` |
| POST | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:325` |
| GET | `/api/forecast-updates/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:328` |
| GET | `/api/forecast-updates/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:334` |
| POST | `/api/forecast-updates/{key}/steps` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:331` |
| POST | `/api/fva/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:927` |
| GET | `/api/health` | Health check; not a business API | `app/main.py:309` |
| GET | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:844` |
| POST | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:902` |
| GET | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:200` |
| POST | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:205` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/accept` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:223` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:211` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:218` |
| GET | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:849` |
| POST | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:854` |
| GET | `/api/integrations/folders/candidates/{identifier}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:880` |
| POST | `/api/integrations/folders/candidates/{identifier}/forecast` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:892` |
| POST | `/api/integrations/folders/{identifier}/auto-draft` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:886` |
| POST | `/api/integrations/folders/{identifier}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:864` |
| POST | `/api/integrations/folders/{identifier}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:870` |
| GET | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:138` |
| POST | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:151` |
| POST | `/api/integrations/order-folders/{run_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:157` |
| POST | `/api/integrations/order-folders/{run_id}/reuse` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:146` |
| POST | `/api/integrations/order-folders/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:164` |
| POST | `/api/integrations/{connector_id}/sync` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:910` |
| GET | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1088` |
| POST | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1136` |
| POST | `/api/inventory/sources` | Out of sales/demand scope; do not publish | `app/main.py:1042` |
| POST | `/api/inventory/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1050` |
| POST | `/api/inventory/sources/{source_id}/values` | Out of sales/demand scope; do not publish | `app/main.py:1070` |
| POST | `/api/inventory/validate` | Out of sales/demand scope; do not publish | `app/main.py:1061` |
| GET | `/api/inventory/{snapshot_id}` | Out of sales/demand scope; do not publish | `app/main.py:1145` |
| GET | `/api/inventory/{snapshot_id}/projection` | Out of sales/demand scope; do not publish | `app/main.py:1153` |
| GET | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1169` |
| POST | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1214` |
| POST | `/api/inventory/{snapshot_id}/receipts/validate` | Out of sales/demand scope; do not publish | `app/main.py:1204` |
| GET | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1640` |
| POST | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1646` |
| GET | `/api/jobs/{job_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1681` |
| POST | `/api/jobs/{job_id}/cancel` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1690` |
| POST | `/api/jobs/{job_id}/retry` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1698` |
| GET | `/api/live-sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:472` |
| PUT | `/api/live-sources/servix/credential` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:476` |
| PUT | `/api/live-sources/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:499` |
| PUT | `/api/live-sources/{key}/permission` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:506` |
| POST | `/api/live-sources/{key}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:513` |
| GET | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:253` |
| POST | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:253` |
| GET | `/api/monitoring` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:921` |
| POST | `/api/operations/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:339` |
| GET | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:105` |
| PUT | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:110` |
| GET | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:650` |
| POST | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:689` |
| POST | `/api/plans/{plan_id}/comments` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:819` |
| GET | `/api/plans/{plan_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:768` |
| POST | `/api/plans/{plan_id}/overrides` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:796` |
| POST | `/api/plans/{plan_id}/overrides/{override_id}/revert` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:829` |
| GET | `/api/plans/{plan_id}/quantities` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:745` |
| PATCH | `/api/plans/{plan_id}/status` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:779` |
| GET | `/api/plans/{plan_id}/supply` | Out of sales/demand scope; do not publish | `app/main.py:737` |
| POST | `/api/plans/{plan_id}/versions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:755` |
| POST | `/api/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:330` |
| GET | `/api/production/schema` | Out of sales/demand scope; do not publish | `app/main.py:1098` |
| GET | `/api/production/sources/{source_id}` | Out of sales/demand scope; do not publish | `app/main.py:1117` |
| POST | `/api/production/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1106` |
| POST | `/api/receipts/sources` | Out of sales/demand scope; do not publish | `app/main.py:1177` |
| POST | `/api/receipts/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1185` |
| GET | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:196` |
| POST | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:198` |
| POST | `/api/recurring-forecasts/{key}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:200` |
| POST | `/api/run` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:348` |
| GET | `/api/run-list` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1711` |
| POST | `/api/run-saved` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1374` |
| GET | `/api/runs/latest` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:627` |
| GET | `/api/runs/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1515` |
| GET | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1519` |
| POST | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1599` |
| POST | `/api/runs/{run_id}/factor-batch` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1629` |
| POST | `/api/runs/{run_id}/factor-batch/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1622` |
| POST | `/api/runs/{run_id}/factor-comparison` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1536` |
| GET | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1545` |
| POST | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1590` |
| POST | `/api/runs/{run_id}/factor-links/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1581` |
| POST | `/api/runs/{run_id}/factor-preparation` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1607` |
| GET | `/api/runs/{run_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1616` |
| GET | `/api/runs/{run_id}/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1527` |
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
| GET | `/api/sample/{name}` | Local demo helper; do not publish | `app/main.py:1720` |
| PUT | `/api/site` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:135` |
| POST | `/api/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1015` |
| GET | `/api/sources/{source_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1023` |
| POST | `/api/sources/{source_id}/sheet` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1029` |
| GET | `/api/today` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:655` |
| GET | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1093` |
| POST | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1128` |
| GET | `/api/v1/access-options` | Implemented; company-scoped | `app/platform_api.py:121` |
| GET | `/api/v1/actuals/{evaluation_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:338` |
| GET | `/api/v1/actuals/{evaluation_id}/export` | Implemented; company-scoped | `app/platform_workspace_api.py:344` |
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
| GET | `/api/v1/connections/external-sources` | Implemented; company-scoped | `app/platform_workspace_api.py:349` |
| PUT | `/api/v1/connections/external-sources/servix/credential` | Implemented; company-scoped | `app/platform_workspace_api.py:367` |
| PUT | `/api/v1/connections/external-sources/{key}` | Implemented; company-scoped | `app/platform_workspace_api.py:353` |
| PUT | `/api/v1/connections/external-sources/{key}/permission` | Implemented; company-scoped | `app/platform_workspace_api.py:357` |
| POST | `/api/v1/connections/external-sources/{key}/refresh` | Implemented; company-scoped | `app/platform_workspace_api.py:361` |
| GET | `/api/v1/connections/imports/{import_id}` | Implemented; company-scoped | `app/platform_connections_api.py:95` |
| POST | `/api/v1/connections/imports/{import_id}/accept` | Implemented; company-scoped | `app/platform_connections_api.py:113` |
| POST | `/api/v1/connections/imports/{import_id}/rows/accept` | Implemented; company-scoped | `app/platform_connections_api.py:108` |
| POST | `/api/v1/connections/imports/{import_id}/rows/preview` | Implemented; company-scoped | `app/platform_connections_api.py:102` |
| GET | `/api/v1/connections/inputs` | Implemented; company-scoped | `app/platform_connections_api.py:54` |
| POST | `/api/v1/connections/inputs` | Implemented; company-scoped | `app/platform_connections_api.py:61` |
| DELETE | `/api/v1/connections/inputs/{connection_id}` | Implemented; company-scoped | `app/platform_connections_api.py:80` |
| GET | `/api/v1/connections/inputs/{connection_id}` | Implemented; company-scoped | `app/platform_connections_api.py:67` |
| PUT | `/api/v1/connections/inputs/{connection_id}` | Implemented; company-scoped | `app/platform_connections_api.py:71` |
| POST | `/api/v1/connections/inputs/{connection_id}/fetch` | Implemented; company-scoped | `app/platform_connections_api.py:90` |
| POST | `/api/v1/connections/inputs/{connection_id}/restore` | Implemented; company-scoped | `app/platform_connections_api.py:85` |
| DELETE | `/api/v1/connections/inputs/{connection_id}/schedule` | Implemented; company-scoped | `app/platform_connections_api.py:131` |
| PUT | `/api/v1/connections/inputs/{connection_id}/schedule` | Implemented; company-scoped | `app/platform_connections_api.py:125` |
| POST | `/api/v1/connections/inputs/{connection_id}/schedule/check` | Implemented; company-scoped | `app/platform_connections_api.py:140` |
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
| GET | `/api/v1/datasets` | Implemented; company-scoped | `app/platform_sales_api.py:163` |
| POST | `/api/v1/datasets` | Implemented; company-scoped | `app/platform_sales_api.py:177` |
| POST | `/api/v1/datasets/preview` | Implemented; company-scoped | `app/platform_sales_api.py:170` |
| GET | `/api/v1/datasets/{dataset_id}` | Implemented; company-scoped | `app/platform_sales_api.py:185` |
| GET | `/api/v1/datasets/{dataset_id}/factors` | Implemented; company-scoped | `app/platform_sales_api.py:250` |
| POST | `/api/v1/datasets/{dataset_id}/factors` | Implemented; company-scoped | `app/platform_sales_api.py:264` |
| POST | `/api/v1/datasets/{dataset_id}/factors/preview` | Implemented; company-scoped | `app/platform_sales_api.py:257` |
| POST | `/api/v1/datasets/{dataset_id}/forecast-settings` | Implemented; company-scoped | `app/platform_workspace_api.py:135` |
| GET | `/api/v1/datasets/{dataset_id}/orders` | Implemented; company-scoped | `app/platform_sales_api.py:190` |
| PUT | `/api/v1/datasets/{dataset_id}/orders` | Implemented; company-scoped | `app/platform_sales_api.py:201` |
| POST | `/api/v1/datasets/{dataset_id}/orders/preview` | Implemented; company-scoped | `app/platform_sales_api.py:207` |
| POST | `/api/v1/datasets/{dataset_id}/orders/snapshots` | Implemented; company-scoped | `app/platform_sales_api.py:214` |
| GET | `/api/v1/datasets/{dataset_id}/orders/template/{role}` | Implemented; company-scoped | `app/platform_workspace_api.py:154` |
| GET | `/api/v1/factors` | Implemented; company-scoped | `app/platform_sales_api.py:230` |
| POST | `/api/v1/factors/imports` | Implemented; company-scoped | `app/platform_sales_api.py:240` |
| POST | `/api/v1/factors/imports/preview` | Implemented; company-scoped | `app/platform_sales_api.py:234` |
| GET | `/api/v1/factors/{snapshot_id}` | Implemented; company-scoped | `app/platform_sales_api.py:246` |
| GET | `/api/v1/forecast-methods` | Implemented; company-scoped | `app/platform_sales_api.py:312` |
| GET | `/api/v1/forecast-updates` | Implemented; company-scoped | `app/platform_workflow_api.py:157` |
| POST | `/api/v1/forecast-updates` | Implemented; company-scoped | `app/platform_workflow_api.py:162` |
| GET | `/api/v1/forecast-updates/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:167` |
| GET | `/api/v1/forecast-updates/{key}/export` | Implemented; company-scoped | `app/platform_workflow_api.py:178` |
| POST | `/api/v1/forecast-updates/{key}/steps` | Implemented; company-scoped | `app/platform_workflow_api.py:172` |
| GET | `/api/v1/forecasts` | Implemented; company-scoped | `app/platform_sales_api.py:323` |
| POST | `/api/v1/forecasts` | Implemented; company-scoped | `app/platform_sales_api.py:273` |
| GET | `/api/v1/forecasts/{forecast_id}` | Implemented; company-scoped | `app/platform_sales_api.py:330` |
| POST | `/api/v1/invitations` | Implemented; company-scoped | `app/platform_api.py:145` |
| DELETE | `/api/v1/invitations/{invitation_id}` | Implemented; company-scoped | `app/platform_api.py:149` |
| GET | `/api/v1/jobs` | Implemented; company-scoped | `app/platform_workspace_api.py:200` |
| GET | `/api/v1/jobs/{job_id}` | Implemented; company-scoped | `app/platform_sales_api.py:335` |
| POST | `/api/v1/jobs/{job_id}/cancel` | Implemented; company-scoped | `app/platform_sales_api.py:339` |
| POST | `/api/v1/jobs/{job_id}/retry` | Implemented; company-scoped | `app/platform_workspace_api.py:206` |
| GET | `/api/v1/me` | Implemented; company-scoped | `app/platform_api.py:49` |
| GET | `/api/v1/members` | Implemented; company-scoped | `app/platform_api.py:141` |
| DELETE | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:162` |
| PATCH | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:153` |
| POST | `/api/v1/members/{member_id}/revoke-sessions` | Implemented; company-scoped | `app/platform_api.py:166` |
| GET | `/api/v1/order-snapshots/{snapshot_id}` | Implemented; company-scoped | `app/platform_sales_api.py:221` |
| GET | `/api/v1/order-snapshots/{snapshot_id}/demand` | Implemented; company-scoped | `app/platform_workspace_api.py:238` |
| GET | `/api/v1/order-snapshots/{snapshot_id}/export` | Implemented; company-scoped | `app/platform_workspace_api.py:265` |
| GET | `/api/v1/orders/schema` | Implemented; company-scoped | `app/platform_workspace_api.py:149` |
| GET | `/api/v1/recurring-forecasts` | Implemented; company-scoped | `app/platform_workflow_api.py:189` |
| POST | `/api/v1/recurring-forecasts` | Implemented; company-scoped | `app/platform_workflow_api.py:194` |
| DELETE | `/api/v1/recurring-forecasts/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:210` |
| GET | `/api/v1/recurring-forecasts/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:199` |
| PUT | `/api/v1/recurring-forecasts/{key}` | Implemented; company-scoped | `app/platform_workflow_api.py:204` |
| POST | `/api/v1/recurring-forecasts/{key}/check` | Implemented; company-scoped | `app/platform_workflow_api.py:222` |
| GET | `/api/v1/releases` | Implemented; company-scoped | `app/platform_sales_api.py:395` |
| POST | `/api/v1/releases` | Implemented; company-scoped | `app/platform_sales_api.py:407` |
| POST | `/api/v1/releases/preview` | Implemented; company-scoped | `app/platform_sales_api.py:402` |
| GET | `/api/v1/releases/{release_id}` | Implemented; company-scoped | `app/platform_sales_api.py:412` |
| POST | `/api/v1/releases/{release_id}/approve` | Implemented; company-scoped | `app/platform_sales_api.py:417` |
| GET | `/api/v1/releases/{release_id}/export` | Implemented; company-scoped | `app/platform_sales_api.py:423` |
| GET | `/api/v1/runs` | Implemented; company-scoped | `app/platform_workspace_api.py:164` |
| GET | `/api/v1/runs/{run_id}` | Implemented; company-scoped | `app/platform_sales_api.py:345` |
| GET | `/api/v1/runs/{run_id}/actuals` | Implemented; company-scoped | `app/platform_workspace_api.py:315` |
| POST | `/api/v1/runs/{run_id}/actuals` | Implemented; company-scoped | `app/platform_workspace_api.py:333` |
| POST | `/api/v1/runs/{run_id}/actuals/preview` | Implemented; company-scoped | `app/platform_workspace_api.py:328` |
| GET | `/api/v1/runs/{run_id}/demand` | Implemented; company-scoped | `app/platform_sales_api.py:372` |
| GET | `/api/v1/runs/{run_id}/export` | Implemented; company-scoped | `app/platform_sales_api.py:378` |
| POST | `/api/v1/runs/{run_id}/factor-batch` | Implemented; company-scoped | `app/platform_workflow_api.py:94` |
| POST | `/api/v1/runs/{run_id}/factor-batch/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:88` |
| POST | `/api/v1/runs/{run_id}/factor-comparison` | Implemented; company-scoped | `app/platform_workflow_api.py:106` |
| GET | `/api/v1/runs/{run_id}/factor-links` | Implemented; company-scoped | `app/platform_workflow_api.py:59` |
| POST | `/api/v1/runs/{run_id}/factor-links` | Implemented; company-scoped | `app/platform_workflow_api.py:71` |
| POST | `/api/v1/runs/{run_id}/factor-links/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:65` |
| POST | `/api/v1/runs/{run_id}/factor-preparation` | Implemented; company-scoped | `app/platform_workflow_api.py:77` |
| GET | `/api/v1/runs/{run_id}/factor-profiles` | Implemented; company-scoped | `app/platform_workflow_api.py:83` |
| GET | `/api/v1/runs/{run_id}/factors` | Implemented; company-scoped | `app/platform_workflow_api.py:100` |
| GET | `/api/v1/runs/{run_id}/files/{kind}` | Implemented; company-scoped | `app/platform_sales_api.py:351` |
| POST | `/api/v1/runs/{run_id}/order-comparison` | Implemented; company-scoped | `app/platform_workflow_api.py:151` |
| POST | `/api/v1/runs/{run_id}/order-comparison/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:145` |
| POST | `/api/v1/runs/{run_id}/order-reuse` | Implemented; company-scoped | `app/platform_workflow_api.py:139` |
| GET | `/api/v1/runs/{run_id}/order-reuse/choices` | Implemented; company-scoped | `app/platform_workflow_api.py:122` |
| POST | `/api/v1/runs/{run_id}/order-reuse/preview` | Implemented; company-scoped | `app/platform_workflow_api.py:133` |
| GET | `/api/v1/runs/{run_id}/order-snapshots` | Implemented; company-scoped | `app/platform_workspace_api.py:230` |
| POST | `/api/v1/runs/{run_id}/order-snapshots` | Implemented; company-scoped | `app/platform_workspace_api.py:256` |
| POST | `/api/v1/runs/{run_id}/order-snapshots/preview` | Implemented; company-scoped | `app/platform_workspace_api.py:251` |
| GET | `/api/v1/runs/{run_id}/orders/starter` | Implemented; company-scoped | `app/platform_workspace_api.py:180` |
| GET | `/api/v1/runs/{run_id}/orders/template/{role}` | Implemented; company-scoped | `app/platform_workspace_api.py:191` |
| POST | `/api/v1/scenario-jobs` | Implemented; company-scoped | `app/platform_workflow_api.py:112` |
| PUT | `/api/v1/settings/site` | Implemented; company-scoped | `app/platform_workspace_api.py:75` |
| GET | `/api/v1/sources` | Implemented; company-scoped | `app/platform_sales_api.py:151` |
| POST | `/api/v1/sources` | Implemented; company-scoped | `app/platform_sales_api.py:131` |
| GET | `/api/v1/sources/{source_id}` | Implemented; company-scoped | `app/platform_sales_api.py:142` |
| POST | `/api/v1/sources/{source_id}/preview` | Implemented; company-scoped | `app/platform_workspace_api.py:123` |
| POST | `/api/v1/sources/{source_id}/sheet` | Implemented; company-scoped | `app/platform_workspace_api.py:129` |
| GET | `/api/v1/units` | Implemented; company-scoped | `app/platform_workspace_api.py:79` |
| POST | `/api/v1/units` | Implemented; company-scoped | `app/platform_workspace_api.py:83` |
| GET | `/api/v1/views` | Implemented; company-scoped | `app/platform_workspace_api.py:283` |
| POST | `/api/v1/views` | Implemented; company-scoped | `app/platform_workspace_api.py:294` |
| DELETE | `/api/v1/views/{view_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:310` |
| GET | `/api/v1/views/{view_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:299` |
| PUT | `/api/v1/views/{view_id}` | Implemented; company-scoped | `app/platform_workspace_api.py:305` |
| GET | `/api/v1/workspace` | Implemented; company-scoped | `app/platform_workspace_api.py:69` |
| POST | `/api/v1/{kind}/{resource_id}/archive` | Implemented; company-scoped | `app/platform_lifecycle_api.py:79` |
| GET | `/api/v1/{kind}/{resource_id}/metadata` | Implemented; company-scoped | `app/platform_lifecycle_api.py:63` |
| PATCH | `/api/v1/{kind}/{resource_id}/metadata` | Implemented; company-scoped | `app/platform_lifecycle_api.py:67` |
| POST | `/api/v1/{kind}/{resource_id}/restore` | Implemented; company-scoped | `app/platform_lifecycle_api.py:83` |
| GET | `/api/v1/{kind}/{resource_id}/revisions` | Implemented; company-scoped | `app/platform_lifecycle_api.py:87` |
| GET | `/api/weather` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1274` |
| POST | `/api/weather/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1279` |
| GET | `/api/weather/{snapshot_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1289` |
| GET | `/api/workspace` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:635` |

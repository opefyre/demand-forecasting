# Public API coverage

Generated from source decorators by `scripts/audit_public_api.py`; no application stores are opened.

21 implemented v1 operations. The rest of the useful business API is not delivered yet.

New company authentication deliberately blocks unscoped legacy business routes. Existing local mode remains unchanged.

The Better Auth identity service supplies library-managed login, Google callback, verification, recovery and factor endpoints behind `/api/login/*`. These are not business CRUD.

Future v1 resources: sales history/sources/datasets, orders/snapshots, factors/live feeds/assumptions, grouped forecasts/jobs/results/exports, releases, actual-vs-forecast checks, personal chats/views, company settings/units, connections/ingestion runs and schedules. Immutable source evidence uses archive/revision rather than destructive overwrite.

| Method | Route | Delivery | Source |
|---|---|---|---|
| GET | `/api/actual-results/{evaluation_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:940` |
| GET | `/api/actual-results/{evaluation_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:948` |
| POST | `/api/actuals/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:889` |
| POST | `/api/actuals/sources/{source_id}/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:897` |
| GET | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:935` |
| POST | `/api/actuals/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:926` |
| POST | `/api/actuals/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:916` |
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
| POST | `/api/assistant/mapping` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:967` |
| POST | `/api/assistant/query` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:958` |
| GET | `/api/auth/callback` | Account bridge; existing OIDC routes also retained | `app/security.py:259` |
| GET | `/api/auth/login` | Account bridge; existing OIDC routes also retained | `app/security.py:251` |
| POST | `/api/auth/logout` | Account bridge; existing OIDC routes also retained | `app/security.py:283` |
| GET | `/api/auth/providers` | Account bridge; existing OIDC routes also retained | `app/security.py:247` |
| GET | `/api/auth/session` | Account bridge; existing OIDC routes also retained | `app/security.py:229` |
| GET | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:134` |
| POST | `/api/customers` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:138` |
| POST | `/api/customers/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:146` |
| PUT | `/api/customers/{customer_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/customers.py:142` |
| GET | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:88` |
| PUT | `/api/customers/{customer_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_profiles.py:93` |
| GET | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:995` |
| POST | `/api/datasets` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1278` |
| POST | `/api/datasets/validate` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1266` |
| GET | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1479` |
| POST | `/api/datasets/{dataset_id}/forecast-factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1497` |
| POST | `/api/datasets/{dataset_id}/forecast-factors/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1488` |
| GET | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1691` |
| POST | `/api/datasets/{dataset_id}/forecast-orders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1743` |
| POST | `/api/datasets/{dataset_id}/forecast-orders/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1734` |
| GET | `/api/datasets/{dataset_id}/forecast-orders/template/{role}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1711` |
| POST | `/api/datasets/{dataset_id}/forecast-settings` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1305` |
| POST | `/api/decisions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:634` |
| GET | `/api/export/{run_id}/{kind}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:554` |
| POST | `/api/factor-imports` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1207` |
| POST | `/api/factor-imports/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1197` |
| POST | `/api/factor-imports/table` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1188` |
| GET | `/api/factor-imports/{snapshot_id}/available` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1217` |
| GET | `/api/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1179` |
| POST | `/api/factors/{factor_id}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1255` |
| GET | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:320` |
| POST | `/api/forecast-updates` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:323` |
| GET | `/api/forecast-updates/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:326` |
| GET | `/api/forecast-updates/{key}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:332` |
| POST | `/api/forecast-updates/{key}/steps` | Pending company-scoped v1 migration; blocked in new auth mode | `app/monthly_refresh.py:329` |
| POST | `/api/fva/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:884` |
| GET | `/api/health` | Health check; not a business API | `app/main.py:306` |
| GET | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:801` |
| POST | `/api/integrations` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:859` |
| GET | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:199` |
| POST | `/api/integrations/factor-folders/{snapshot_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:204` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/accept` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:222` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:210` |
| POST | `/api/integrations/factor-folders/{snapshot_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/factor_folders.py:217` |
| GET | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:806` |
| POST | `/api/integrations/folders` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:811` |
| GET | `/api/integrations/folders/candidates/{identifier}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:837` |
| POST | `/api/integrations/folders/candidates/{identifier}/forecast` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:849` |
| POST | `/api/integrations/folders/{identifier}/auto-draft` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:843` |
| POST | `/api/integrations/folders/{identifier}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:821` |
| POST | `/api/integrations/folders/{identifier}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:827` |
| GET | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:137` |
| POST | `/api/integrations/order-folders/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:150` |
| POST | `/api/integrations/order-folders/{run_id}/enabled` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:156` |
| POST | `/api/integrations/order-folders/{run_id}/reuse` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:145` |
| POST | `/api/integrations/order-folders/{run_id}/review` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_folders.py:163` |
| POST | `/api/integrations/{connector_id}/sync` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:867` |
| GET | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1045` |
| POST | `/api/inventory` | Out of sales/demand scope; do not publish | `app/main.py:1093` |
| POST | `/api/inventory/sources` | Out of sales/demand scope; do not publish | `app/main.py:999` |
| POST | `/api/inventory/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1007` |
| POST | `/api/inventory/sources/{source_id}/values` | Out of sales/demand scope; do not publish | `app/main.py:1027` |
| POST | `/api/inventory/validate` | Out of sales/demand scope; do not publish | `app/main.py:1018` |
| GET | `/api/inventory/{snapshot_id}` | Out of sales/demand scope; do not publish | `app/main.py:1102` |
| GET | `/api/inventory/{snapshot_id}/projection` | Out of sales/demand scope; do not publish | `app/main.py:1110` |
| GET | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1126` |
| POST | `/api/inventory/{snapshot_id}/receipts` | Out of sales/demand scope; do not publish | `app/main.py:1171` |
| POST | `/api/inventory/{snapshot_id}/receipts/validate` | Out of sales/demand scope; do not publish | `app/main.py:1161` |
| GET | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1565` |
| POST | `/api/jobs` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1571` |
| GET | `/api/jobs/{job_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1606` |
| POST | `/api/jobs/{job_id}/cancel` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1615` |
| POST | `/api/jobs/{job_id}/retry` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1623` |
| GET | `/api/live-sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:471` |
| PUT | `/api/live-sources/servix/credential` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:475` |
| PUT | `/api/live-sources/{key}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:498` |
| PUT | `/api/live-sources/{key}/permission` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:505` |
| POST | `/api/live-sources/{key}/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/live_sources.py:512` |
| GET | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:243` |
| POST | `/api/login/{path:path}` | Better Auth proxy; identity-service allowlist | `app/security.py:243` |
| GET | `/api/monitoring` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:878` |
| POST | `/api/operations/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:336` |
| GET | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:88` |
| PUT | `/api/order-books/{dataset_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/order_books.py:93` |
| GET | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:607` |
| POST | `/api/plans` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:646` |
| POST | `/api/plans/{plan_id}/comments` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:776` |
| GET | `/api/plans/{plan_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:725` |
| POST | `/api/plans/{plan_id}/overrides` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:753` |
| POST | `/api/plans/{plan_id}/overrides/{override_id}/revert` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:786` |
| GET | `/api/plans/{plan_id}/quantities` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:702` |
| PATCH | `/api/plans/{plan_id}/status` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:736` |
| GET | `/api/plans/{plan_id}/supply` | Out of sales/demand scope; do not publish | `app/main.py:694` |
| POST | `/api/plans/{plan_id}/versions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:712` |
| POST | `/api/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:327` |
| GET | `/api/production/schema` | Out of sales/demand scope; do not publish | `app/main.py:1055` |
| GET | `/api/production/sources/{source_id}` | Out of sales/demand scope; do not publish | `app/main.py:1074` |
| POST | `/api/production/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1063` |
| POST | `/api/receipts/sources` | Out of sales/demand scope; do not publish | `app/main.py:1134` |
| POST | `/api/receipts/sources/{source_id}/preview` | Out of sales/demand scope; do not publish | `app/main.py:1142` |
| GET | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:194` |
| POST | `/api/recurring-forecasts` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:196` |
| POST | `/api/recurring-forecasts/{key}/check` | Pending company-scoped v1 migration; blocked in new auth mode | `app/recurring_forecasts.py:198` |
| POST | `/api/run` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:345` |
| GET | `/api/run-list` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1636` |
| POST | `/api/run-saved` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1331` |
| GET | `/api/runs/latest` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:584` |
| GET | `/api/runs/{run_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1440` |
| GET | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1444` |
| POST | `/api/runs/{run_id}/assumptions` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1524` |
| POST | `/api/runs/{run_id}/factor-batch` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1554` |
| POST | `/api/runs/{run_id}/factor-batch/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1547` |
| POST | `/api/runs/{run_id}/factor-comparison` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1461` |
| GET | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1470` |
| POST | `/api/runs/{run_id}/factor-links` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1515` |
| POST | `/api/runs/{run_id}/factor-links/preview` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1506` |
| POST | `/api/runs/{run_id}/factor-preparation` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1532` |
| GET | `/api/runs/{run_id}/factor-profiles` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1541` |
| GET | `/api/runs/{run_id}/factors` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1452` |
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
| GET | `/api/sample/{name}` | Local demo helper; do not publish | `app/main.py:1645` |
| PUT | `/api/site` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:133` |
| POST | `/api/sources` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:972` |
| GET | `/api/sources/{source_id}` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:980` |
| POST | `/api/sources/{source_id}/sheet` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:986` |
| GET | `/api/today` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:612` |
| GET | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1050` |
| POST | `/api/units` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1085` |
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
| POST | `/api/v1/invitations` | Implemented; company-scoped | `app/platform_api.py:145` |
| DELETE | `/api/v1/invitations/{invitation_id}` | Implemented; company-scoped | `app/platform_api.py:149` |
| GET | `/api/v1/me` | Implemented; company-scoped | `app/platform_api.py:49` |
| GET | `/api/v1/members` | Implemented; company-scoped | `app/platform_api.py:141` |
| DELETE | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:162` |
| PATCH | `/api/v1/members/{member_id}` | Implemented; company-scoped | `app/platform_api.py:153` |
| POST | `/api/v1/members/{member_id}/revoke-sessions` | Implemented; company-scoped | `app/platform_api.py:166` |
| GET | `/api/weather` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1231` |
| POST | `/api/weather/refresh` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1236` |
| GET | `/api/weather/{snapshot_id}/export` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:1246` |
| GET | `/api/workspace` | Pending company-scoped v1 migration; blocked in new auth mode | `app/main.py:592` |

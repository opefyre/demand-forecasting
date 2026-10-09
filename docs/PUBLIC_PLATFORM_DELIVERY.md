# Public platform delivery

Approved scope: sales/demand forecasting only. Reuse maintained open-source
packages; retain licences and attribution. No SAML or messaging commands in v1.

## Milestones

- [x] Review and publish a secret-scanned checkpoint of existing app code.
      Baseline verification: 679 backend tests and 238 interface tests passed.
- [ ] Better Auth service: email/password, Google, invitation-only organizations,
      four roles, admin two-factor authentication, session revocation.
  - [x] Password sign-in, verification, invitations and reset/recovery wiring.
  - [x] Four roles, administrator session-specific 2FA and recovery codes.
  - [x] Suspension, role changes, removal and company-session revocation.
  - [ ] Google OAuth and production mail verified with deployment credentials.
- [ ] Company-scoped persistence, files, jobs, schedules and assistant context.
  - [x] Explicit workspace factory and isolated customer/product directory.
  - [x] Sales history/files, order books/reviews, factors, grouped forecasts,
        durable jobs, results/exports and independent release approvals.
  - [x] Personal AI context, views, actual-vs-forecast checks, settings and core
        frontend migration; company/user-separated browser drafts.
  - [ ] Advanced factor/scenario assistant actions and recurring monthly updates
        with company-scoped scheduling; no shared-data fallback.
- [ ] Public `/api/v1` and route-by-route permission/coverage inventory.
  - [x] Initial 21 v1 operations and source-derived full route inventory.
  - [x] Core screen operations and matching frontend migration: 105 v1 operations.
  - [ ] Remaining resource lifecycle, advanced automation and ingestion routes.
- [x] Scoped personal and company API keys; revocation, rotation and expiry.
- [ ] Useful CRUD for customers/products, inputs/orders, forecast lifecycle,
      views/conversations, settings, connections and schedules.
- [ ] SFTP pull, Odoo 18/19, Google Sheets and generic HTTP ingestion.
- [ ] Slack, Teams Workflows, Telegram and eligible WhatsApp notifications.
- [ ] Unified English/Persian management UI using the existing design framework.
  - [x] People, API access and sign-in components; no new page-specific styles.
  - [ ] Connections, schedules and notification management.
- [ ] Cross-company, role, key, ingestion, migration and end-to-end acceptance.
- [ ] Publish tested commits to the existing GitHub repository.

## Agreed access

Admin manages users/settings/connections and forecasting. Planner manages inputs
and drafts. Approver reviews/releases without editing inputs or calculating.
Viewer sees approved reports and read-only AI only. Own chats/views are personal.
Users issue keys within their current rights; admins issue restricted company keys.

## Safety and delivery

Keep current local evaluation usable while the new authenticated platform is built.
Do not enable authenticated multi-company mode until isolation is tested end to end.
Preserve existing immutable evidence and quantities. New snapshots are revisions,
not silent replacements. Credentials/client files/private outputs are never pushed.
Provider adapters are not called live-verified without a real ingestion/account test.

Commit each verified milestone on `codex/public-platform`. Never force-push.

## Access milestone — 9 October 2026

Implemented, **not activated in the live demo**. New company mode fails closed for
legacy unscoped business APIs rather than accessing shared client data. Activating
it now would block those workflows; the company-scoped engine migration comes next.

Verification: full Python suite 695 checks (694 passed, one opt-in integration
skipped); frontend 243 passed; 21 identity checks including real
PostgreSQL/Node/Python acceptance passed.
Additional route-inventory tests and authentication recovery tests are tracked
with this milestone. Test accounts/data are isolated and disposable; no real
credentials, client data, Google or mail accounts were changed.

Browser fixture: four roles, role-change dialog, invitation, restricted company-key
choices, one-time key display, Persian translation and 390px layout checked.
Fixed an empty-state bug that hid populated People/API-key tables.

Details: [setup and limitations](AUTH_PLATFORM_SETUP.md),
[route-by-route coverage](PUBLIC_API_COVERAGE.md).

## Company forecasting API milestone — 9 October 2026

Delivered backend pipeline: separate sales sources/datasets, customer/order books,
immutable reviewed orders/factors, atomic named multi-method forecasts, company
Huey jobs/recovery, filtered demand/model exports and independent approvals.
Public coverage is now **56 operations**; useful remaining routes are still open.
No new mathematical engine, paid AI call or client-data replacement was used.

Two disposable companies were tested with four customers, two SKUs and 36 months
of history. Checks include orders above/below forecasts, missing orders, factor
values in model outputs, Gregorian/Persian periods, all demand export formats,
viewer restrictions, independent approval, simultaneous retries and rollback.
The current demo is not switched to company mode: AI/personal context, remaining
screens, settings and connection APIs must first move to company-scoped services.

See [scope, workflow and remaining work](COMPANY_FORECAST_DELIVERY.md).

Verification: full backend suite **710 checks: 709 passed, one optional identity
integration skipped**; all **243 interface tests passed**. The focused sales,
identity middleware and legacy spreadsheet compatibility run passed 29 checks.
Secret scan: no new findings; staged pre-commit secret check passed. Existing local
demo health confirmed; it was not restarted, reconfigured or populated with test data.

## Next delivery chunks

Core context/screens milestone: [delivery and limits](COMPANY_CONTEXT_DELIVERY.md).
Full backend 725 checks: 724 passed, one optional integration skipped. All 249
frontend tests and production build passed. Two-company synthetic browser journey
checked orders, grouped model results, exports, chats, settings and viewer access.

1. Finish company-scoped advanced assistant factor/scenario actions, monthly
   updates and recurring schedules. Core assistant/personal views, actual results,
   settings, external-source management and first-use-to-export screens have moved
   to company stores; see [context delivery](COMPANY_CONTEXT_DELIVERY.md).
2. Public CRUD completion and ingestion: maintained SFTP/Google libraries,
   version-aware Odoo, safe HTTP; preview/validation, mapping and repeat-safe sync.
3. Notifications and schedules: Slack/Teams/Telegram/eligible WhatsApp with
   admin-only connection setup, delivery history and explicit outbound consent.
4. Deployment acceptance: Google/mail credentials, real provider setup,
   backup/restore, role-based browser walkthrough and published API documentation.

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
- [x] Company-scoped persistence, files, jobs, schedules and assistant context.
  - [x] Explicit workspace factory and isolated customer/product directory.
  - [x] Sales history/files, order books/reviews, factors, grouped forecasts,
        durable jobs, results/exports and independent release approvals.
  - [x] Personal AI context, views, actual-vs-forecast checks, settings and core
        frontend migration; company/user-separated browser drafts.
  - [x] Advanced factor/scenario assistant actions and recurring monthly updates
        with company-scoped scheduling; no shared-data fallback.
- [ ] Public `/api/v1` and route-by-route permission/coverage inventory.
  - [x] Initial 21 v1 operations and source-derived full route inventory.
  - [x] Core screen operations and matching frontend migration: 105 v1 operations.
  - [x] Advanced scenarios, monthly updates and recurring drafts: 131 v1 operations.
  - [x] Read-only input connection lifecycle/captures/review: 140 v1 operations.
  - [x] Connected customers/orders, provider adapters and scheduled captures: 145 v1 operations.
  - [x] Resource naming, archive/restore and recorded revisions: 150 v1 operations.
  - [x] Administrator notification destinations and delivery history: 161 v1 operations.
  - [ ] Deployment acceptance and published deployment API documentation.
- [x] Scoped personal and company API keys; revocation, rotation and expiry.
- [ ] Useful CRUD for customers/products, inputs/orders, forecast lifecycle,
      views/conversations, settings, connections and schedules.
  - [x] Remaining input/forecast naming, archive/restore and revision navigation.
- [x] SFTP pull, Odoo 18/19, Google Sheets and generic HTTP ingestion implementation.
  - [x] HTTPS complete exports and pinned-host-key SFTP, company-separated history/future captures.
  - [x] Reviewed mapping, immutable receipts/revisions and repeat-safe fetch/accept.
  - [x] Connected customer/order review, Odoo, Sheets and permission-checked recurring input pulls.
  - [ ] Live client-account verification and deployment activation; adapters are synthetic-tested only.
- [x] Slack, Teams Workflows, Telegram and eligible WhatsApp notification implementation.
  - [ ] Real account/template eligibility and provider delivery verification.
- [ ] Unified English/Persian management UI using the existing design framework.
  - [x] People, API access and sign-in components; no new page-specific styles.
  - [x] Company-scoped recurring forecast management, shared components and translations.
  - [x] Business connections and notification management.
    - [x] Business input connections share the existing collection/dialog framework and Persian catalogue.
- [ ] Cross-company, role, key, ingestion, migration and end-to-end acceptance.
  - [x] Company-state restore safeguards and read-only deployment configuration checks.
  - [x] Separate deployment templates, restricted services and account/credential runbook.
  - [x] Separate Cloudflare domain hold and private R2 buckets; isolated Google/Resend identities created.
  - [ ] Cloudflare durable state/auth/vault/job migration and idle-sleeping engine deployment.
    - [x] Private native D1 access operations and concurrent last-admin protection deployed.
    - [x] Company-bound encrypted R2 checkpoints and native durable job/revision ledger deployed.
    - [x] Offline Linux engine deployed with bounded deadlines and five-minute idle policy.
    - [ ] Existing company CRUD/screens, recurring/live workflows and measured remote idle/wake acceptance.
  - [x] Create and privately store a Resend sending-only key restricted to the forecast domain.
  - [x] Securely store replacement Google secret and verify the exposed secret is disabled.
  - [ ] Wire production credentials; verify Google sign-in and real mail delivery.
  - [x] Four-role API checks against the actual identity permission catalogue.
  - [ ] Deployment-host role/browser journey, real accounts and encrypted off-device recovery.
- [ ] Publish tested commits to the existing GitHub repository.

## Agreed access

Admin manages users/settings/connections and forecasting. Planner manages inputs
and drafts. Approver reviews/releases without editing inputs or calculating.
Viewer sees approved reports and read-only AI only. Own chats/views are personal.
Users issue keys within their current rights; admins issue restricted company keys.

Selected deployment: Cloudflare Workers Paid and Containers, domain
`forecast.vrolen.com`. [Actual resources, credential actions and launch gates](CLOUDFLARE_DEPLOYMENT.md).
The domain is held closed; the app is not publicly launched.
Private runtime delivery, test evidence and remaining cloud migration:
[CLOUD_RUNTIME_DELIVERY.md](CLOUD_RUNTIME_DELIVERY.md).

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

Advanced workflows milestone: [delivery and limits](COMPANY_WORKFLOWS_DELIVERY.md).
Company-scoped scenarios, monthly updates and recurring drafts are implemented.
Full backend: 735 checks, 734 passed, one optional integration skipped. Frontend:
249 passed. Production build and identity-service checks passed. No paid AI call.

1. Deployment acceptance: Google/mail credentials, real provider setup,
   backup/restore, role-based browser walkthrough and published API documentation.
   Local recovery/configuration safeguards are implemented; remaining host/account
   checks are tracked in [deployment acceptance](DEPLOYMENT_ACCEPTANCE.md).

Input-connections milestone: [delivery, setup and limits](COMPANY_CONNECTIONS_DELIVERY.md).
HTTPS/SFTP fetch/review/save and connection CRUD are implemented; real client
accounts and unattended ingestion are not verified or enabled. Existing local
evaluation stays unchanged. Company-mode activation remains a separate gate.

Verification: backend 760 checks (759 passed, one optional identity integration
skipped), all 250 interface checks passed, production build passed. Browser
acceptance covered fetch/review/save, Persian mobile setup and a second-company
planner. Synthetic encrypted SFTP tests also reject changed host keys/files.

Connected-inputs milestone: [workflow, setup and limits](COMPANY_INGESTION_DELIVERY.md).
Customer/order captures now feed the owned directory/order book after explicit
review. Sheets uses a read-only service account; Odoo 18/19 uses version-specific
customer/order APIs. Hourly, six-hourly and daily fetches recheck live administrator
access. New data still waits for review; no unattended overwrite or publication.
Real provider accounts and company-mode activation remain acceptance gates.

Verification: backend **780 checks (779 passed, one optional integration skipped)**,
all **254 interface checks passed**, production build passed. Browser acceptance
covered customer/order review, preservation, daily schedule configuration,
Persian narrow-screen setup and second-company restricted controls. No paid AI call.

Resource-lifecycle milestone: [delivery and evidence rules](COMPANY_LIFECYCLE_DELIVERY.md).
Company-scoped input/source/forecast naming, reversible archive and recorded
revision navigation are implemented. Multi-method forecasts share one lifecycle;
monthly results link to their recorded baselines. Evidence and approvals remain
unchanged. The shared UI includes Persian and narrow-screen support.
Company mode is still not activated in the original local demo.

Verification: backend 794 checks (793 passed, one optional integration skipped),
then 39 focused checks after the final retry-job safeguard; all 260 interface
checks and the production build passed. Browser acceptance covered reversible
archive, explicit revisions, Persian/mobile controls and separate company names.

Notifications milestone: [workflow, security and provider limits](COMPANY_NOTIFICATIONS_DELIVERY.md).
Administrator-controlled destinations, explicit consent, five business events,
company-specific outbox/history, safe manual retries and archive/restore are
implemented using Apprise and existing framework/transport/scheduling components.
API keys and non-administrator roles cannot access messaging controls/history.
Real provider accounts and company-mode activation remain deployment gates.

Verification: full backend suite 821 checks (820 passed, one optional integration
skipped), followed by 54 focused checks after final recovery/permission safeguards;
all 264 frontend checks and the production build passed. Synthetic browser checks
covered explicit send consent, linked retry history, archive/restore staying
paused, company isolation, restricted navigation and Persian mobile dialogs.

## Deployment safeguards — 10 October 2026

Company restore now pauses imports, recurring forecasts and live factors, interrupts
active jobs/fetches and expires old assistant actions while preserving business
records and completed receipts. Notification recovery remains paused and safe.
Runtime sanitization never rewrites uploaded files merely because their filename
resembles a database. Identity PostgreSQL and secret vaults are explicitly outside
the state archive and need separate recovery before activation.

Read-only deployment checks reuse identity configuration validation. Actual four-role
permissions are exercised against the company API. No new UI or dependency, paid
AI request, real message or live-data replacement was introduced.

Verification: backend 824 checks (823 passed, one optional integration skipped),
17 final recovery/role checks passed, 264 interface checks and production build
passed. Identity type checks and 10 tests passed; optional PostgreSQL acceptance
was not configured. Offline secret scan passed; existing demo health confirmed.

Next: isolated deployment origin/database, actual Google/mail/provider accounts,
four-role browser acceptance and encrypted off-device recovery. See
[deployment acceptance](DEPLOYMENT_ACCEPTANCE.md). Company mode is not activated
in the existing local demo.

## Deployment preparation — 10 October 2026

Prepared a separate single-host Linux reference installation using Caddy/systemd:
loopback company API on 8020, private identity on 8011, one worker, restricted
runtime write paths, read-only startup checks and manual-only owner bootstrap.
Blank protected-settings templates and the exact domain/account/credential
inventory are in [deployment setup](DEPLOYMENT_SETUP.md). No new package, provider
call, host installation, migration, copied secret or local-demo change.

Linux connector/notification/live-source vault portability remains unresolved;
macOS Keychain is not a deployable Linux vault. AI is disabled in the template:
OpenAI country eligibility for the Iranian client must be resolved rather than
assuming an overseas host bypasses it. Neither gate is marked completed.

Verification: 8 deployment-template contract tests passed; identity type check
and 10 identity tests passed (one optional PostgreSQL check skipped). Native Linux
systemd/Caddy validation and real hosting/account acceptance remain to be run on
the selected host. See [acceptance checklist](DEPLOYMENT_ACCEPTANCE.md).

Next: obtain the chosen hostname, host and first-owner details; select/recovery-
test the secure Linux vault, configure dedicated PostgreSQL/mail/Google in private
staging, then verify four-role journeys, selected providers and encrypted recovery.
Original port-8010 demo remains separate; no production activation in this chunk.

# Private cloud workflows — 10 October 2026

Implemented on the dedicated forecast services, not a public launch. The public
edge remains closed. Local demo records and other cloud services are unchanged.
No real provider request, OpenAI call, mail or notification was made in this run.

## Delivered

- The shared contract has 169 explicit company operations, covering the existing
  business API, plus 14 native identity/access-management operations.
- Cloud assistant chat, personal history, parallel short titles, import-mapping
  advice and reviewed action execution reuse the existing OpenAI SDK/agent tools.
  Models are selected separately for query, title, review and decision tasks.
  Personal conversations never enter shared company projections.
- Advanced factor comparisons, scenario jobs, cancellation/retry and monthly
  updates reuse the existing company workflows and forecasting libraries.
- Existing read-only HTTPS, Google Sheets, Odoo 18/19 and pinned-host-key SFTP
  adapters now have private cloud transport. Customers, orders and history enter
  immutable capture/review flows; scheduled pulls never silently accept imports.
- Existing external sources can refresh through their original parsers, receipts
  and cooldown rules: Servix currency, Hormuz shipping/disruption, World Bank Iran
  inflation/industry and commodity history, NY Fed supply-chain pressure and the
  permission-gated IMF monthly Iran CPI source. Availability and source frequency
  do not become magically real-time or guarantee useful model accuracy.
- Native durable alarms run opted-in input pulls, source refreshes, monthly draft
  preparation and event-driven notifications. They check the owner's current
  administrator rights. Recorded monthly cycles do not recalculate after sleep;
  completed drafts remain unapproved until reviewed. No idle polling/container cron.
- Existing admin-only notification destinations, tests, retries and delivery
  history are connected, using Apprise. Slack, Teams Workflows, Telegram and
  eligible WhatsApp retain their existing provider/consent requirements.
- Members, invitations, key create/rename/revoke/rotate, session revocation,
  access options and audit routes use native Better Auth/D1, not business snapshots.

## Private transport and storage

The numerical container remains offline. Only its private Worker can relay an
attempt-scoped request. Every relay checks live identity, scopes, cancellation,
deadline and the current company revision. Exact provider routes and read-only
connector operations are allowlisted; arbitrary proxies, redirects and provider
writes are denied. HTTP hosts are checked for public DNS addresses; SFTP TCP uses
the resolved public IPv4 address and existing SSH host-key verification.

Credentials in queued request bodies are AES-GCM encrypted **before** R2 writes,
bound to company and body hash. Original company-bound encrypted vaults remain
in checkpoints. The dedicated encryption key is held privately by storage and
engine Workers, never in images or Git. Failed network attempts can persist
cooldown/delivery evidence without automatically replaying outside requests.

AI requests have durable daily/per-user/per-attempt limits and `store: false`.
The real provider key would be injected by the Worker, not the offline container.
**AI is still disabled in cloud configuration**: provider country eligibility
for the Iranian client and a private live test remain unresolved. No local key
was copied to production to bypass this gate.

## Verification and limits

Checks exercise cold checkpoint restores, four connected customers, encrypted
requests/credentials, repeat-safe receipts, saved personal chat titles, source
failure cooldowns, scheduled imports and monthly mathematical drafts. Providers
and identity replies in the Python relay tests are explicit fakes. Native workerd
tests use actual disposable SQLite/R2 with fake engine/identity responses.
Neither proves a live client integration or forecast accuracy on client data.

Final checks: 210 backend tests pass; 32 cloud adapter/controller tests pass;
native storage and identity suites each pass two checks. All 268 interface checks
and the interface build pass; identity type/schema checks pass. Shared identity
tests pass 19 checks with three optional skips. The route test also checks every
native business route in reverse, including expanded template/lifecycle paths;
identity routes have their separate native management tests.
All ten cold-workflow checks also pass in offline Linux with the small engine
limits, in 396.5 seconds under local x86 emulation. That is the entire multi-step
suite, not measured Cloudflare cold-start latency or a per-forecast timing.
The dedicated cloud engine is deployed with zero live instances; the public edge
still returns HTTP 503 and the separate local demo health returns HTTP 200.

Repeat: `python -m unittest tests.test_cloud_workflows tests.test_cloud_api`
and `node --test deploy/cloudflare/*.test.mjs`. Native storage/identity checks
use the existing `auth-service` scripts. The Linux workflow test runs offline,
non-root, with 1 GiB RAM and 0.25 CPU. Existing deprecation/database-resource
warnings remain. Deployment versions and final counts are recorded separately.

Current bounded size/record limits and scoped orphan/request retention work in
CLOUD_API_DELIVERY.md remain. SFTP supports public IPv4, not private LAN endpoints.
Cloud screens still need the authenticated private gateway; no new UI clutter,
settings page, banner or styling framework was introduced in this backend slice.

## Next substantial task (superseded by owner acceptance)

The following was this slice's handoff. The owner-only interface, real Google,
MFA/email, remote forecast/export and measured corrected sleep/wake are now
verified in [owner acceptance](CLOUD_OWNER_ACCEPTANCE.md). Current next tasks are
cold Automatic performance/progress, recovery/restore and explicitly approved
live-provider acceptance. Public access and AI remain separately gated.

Connect the owner-only authenticated cloud interface to these services, bootstrap
the owner through the restricted setup path, and verify Google sign-in, fresh
admin MFA, Resend mail and two-company browser permissions. Then run one bounded
synthetic remote forecast and observe actual cold start, completion, sleep/wake
and resource use. Keep all other people denied. Live provider tests require
dedicated read-only test accounts/configurations; AI remains gated separately.
Public access requires a separate explicit decision, not this implementation.

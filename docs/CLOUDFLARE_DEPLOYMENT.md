# Cloudflare deployment

Status: 10 October 2026. Infrastructure preparation is partly complete.
**The forecasting app is not deployed or ready for public use.**
The local demo remains independent at `http://127.0.0.1:8010`.

## Confirmed scope

- Account: `b53df72f41f5135daf312100e73ff6a1` (Opefyre).
- Domain: `forecast.vrolen.com`, under existing `vrolen.com`.
- Existing Workers Paid plan; no subscription or paid add-on enabled.
- Google project: `vrolen`, number `945632758521`.
- Owner/test contact: `opefyre@gmail.com`.
- No other Worker, bucket, database, OAuth client, domain or mail key is to be modified.
- No copying local client data, demo outputs or existing AI/connector secrets to production.

## Created and checked

| Resource | State |
| --- | --- |
| Worker `demandlab-forecast-edge` | New isolated domain hold. Every route returns HTTP 503; no backend, assets, credentials, cron or storage bindings. |
| `forecast.vrolen.com` | Worker custom domain created; HTTPS and closed app/login/API routes checked. No wildcard route. |
| R2 `demandlab-forecast-files` | New empty Standard bucket, Western Europe location hint; public r2.dev access disabled. |
| R2 `demandlab-forecast-backups` | New empty Standard bucket, Western Europe location hint; public r2.dev access disabled. |
| Google client `Vrolen Forecast` | Separate Web client created with only the forecast origin and callback. Existing `Vrolen` client preserved. Not connected to app; secret replacement required below. |
| Resend `forecast.vrolen.com` | Separate domain added in Ireland without an upgrade. DNS and domain verified; enforced TLS enabled for this domain only. Receiving disabled. |

The edge configuration is [wrangler.jsonc](../deploy/cloudflare/wrangler.jsonc).
It disables workers.dev, preview URLs and observability payloads, limits CPU to
10 milliseconds, and cannot wake any container. This is an access hold, not a
successful application launch. It does not expose or tunnel the local demo.

The existing Vrolen website, `app.vrolen.com`, `demo.vrolen.com`, root MX/SPF,
Google client, Finkavo domain/keys and seven pre-existing R2 buckets were not edited.
Wrangler's OAuth token cannot read/write DNS records directly; email records were
added through the authenticated Cloudflare UI, not by obtaining a broad new token.

## Google login

Client ID: `945632758521-baj6dsc8irl5qmcknbi0tgt4ui0skjl0.apps.googleusercontent.com`.

- Origin: `https://forecast.vrolen.com`.
- Callback: `https://forecast.vrolen.com/api/login/callback/google`.
- Google consent remains in Testing, so sign-in is restricted to the project's test users.
- Existing branding, audience and other OAuth clients were not changed.

**Secret safety incident:** a browser output exposed the newly generated client
secret. It has never been installed in Cloudflare or used by the app. Treat it as
compromised; replace it before deployment. The download was moved out of Downloads
into the ignored `secrets/` folder with mode 0600, and is quarantined as
`forecast-google-oauth.DO-NOT-USE.json`. Do not copy it into production.

User action on the new **Vrolen Forecast** client only:

1. Click **Add secret**; save its credential securely as
   `secrets/forecast-google-oauth.json` (never paste the secret into chat).
2. Disable the old secret on this new client. Do not change the existing Vrolen client.
3. Tell Codex when complete. Only non-secret metadata will be checked.

The replacement page is left open. Do not publish the shared Google consent app
or broaden its scopes merely to make this new client work. Check the existing
test-user list read-only before making any audience change.

## Resend

Domain ID: `de761bde-67af-4e4b-8d89-91a31cc13fc9`.
Sender planned: `Vrolen Forecast <notifications@forecast.vrolen.com>`.

The current [official free plan](https://resend.com/pricing) includes three sending
domains and a 100-email daily limit. Finkavo does not consume all three domain
slots: Resend accepted the second domain without an upgrade. Usage limits are
shared with Finkavo; do not enable transactional overages or a domains add-on.

Only the records shown by Resend for this domain were added:

- TXT `resend._domainkey.forecast.vrolen.com`: generated DKIM public key.
- DNS-only CNAME `rsend.forecast.vrolen.com` → `rsend-euw1.forge.rmta.net`.
- DNS-only CNAME `send.forecast.vrolen.com` → `send.forge.rmta.net`.

No root MX/SPF/DMARC change, inbound mail activation or broad Cloudflare integration grant.
Delivery requires TLS: a receiving server that lacks encryption will fail rather
than receive password-reset/invitation mail unencrypted. Open/click tracking was not enabled.
These are Resend's current generated records, not guessed legacy SPF/MX templates.

On 2026-10-10, after explicit action-time approval, the **forecast-production** key
was created with **Sending access** restricted to **forecast.vrolen.com**. Its
one-time value was saved directly to ignored `secrets/forecast-resend-api.txt`
with mode 0600, without displaying it in chat or tool output. The copied value
was cleared from the clipboard. Final key-detail metadata confirms the domain
and permission; existing Finkavo keys were not changed. The new key has not yet
been installed in Cloudflare or used to send mail.

After domain verification and key storage: wire it using the existing maintained
mailer/provider solution, send one setup test to the owner, and verify actual
verification/reset mail and delivery failures. DNS verification alone is not a
mail-delivery test. Credentials must use Cloudflare secrets, never public Worker vars.

## Sleep and cost policy — not activated yet

The next runtime must use Cloudflare's maintained container APIs, not a custom
process-hosting platform. Initial target: one named engine instance, no warm pool,
no replicas; profile only the smallest instance that passes memory/forecast tests.
Do not claim the 256 MiB instance is sufficient for this numerical engine.

- Target inactivity timeout: five minutes after useful work completes.
- An accepted forecast/import remains durable outside the container; running
  work renews its bounded lease/heartbeat. Never kill an active forecast just
  because the user closed the browser or HTTP response returned.
- A job has a deadline; only active work extends the lease. No forever heartbeat.
- Login, static assets, dashboards of saved results and unrelated traffic must
  not wake the mathematical engine. Start it only for authorized work.
- Schedules use durable alarms/queues outside the container; no always-on cron
  process inside the container. No one-minute health ping defeating sleep.
- Job retries are bounded and repeat-safe; a restart must not double-send mail
  or apply orders twice. Finished jobs must allow sleep.
- Idle/wake behavior and actual resource use must be measured before launch.

The existing $5 plan includes some container usage, not unlimited containers.
See [current container pricing](https://developers.cloudflare.com/containers/platform/pricing/).
R2 free allowances are account-wide, shared with other apps; see
[R2 pricing](https://developers.cloudflare.com/r2/pricing/). No hard spending cap
has been selected, and this Worker CPU limit is not an account-wide bill cap.
No container has been deployed or started in this milestone.

## Required engineering before the app can go live

1. **Durable app state:** current company records, uploads, outputs, SQLite job
   queue and scheduler use the local filesystem. Cloudflare container disk is
   [ephemeral](https://developers.cloudflare.com/containers/faq/). Move durable
   records/jobs to D1/Durable Objects/Queues as appropriate and files to private
   R2; keep company/role checks, immutable revisions and order calculations intact.
   R2 FUSE is not a safe live SQLite WAL replacement. An upload on shutdown alone
   does not protect against crashes. No unused D1 database has been created.
2. **Identity portability:** Better Auth is maintained, but this implementation
   uses PostgreSQL and PostgreSQL-specific policy/migration SQL. Cloudflare D1
   is not a drop-in PostgreSQL server. Adapt the supported auth adapter and custom
   policy storage, then re-run real role, MFA, invitation, key and company-isolation
   tests. Do not deploy an ephemeral PostgreSQL container.
3. **Portable integration vault:** macOS Keychain does not exist in Linux
   containers. Use maintained encryption/secret storage and recovery, preserving
   company-separated access. R2 credentials and raw connector secrets are never
   public or plaintext rows. Optional live integrations remain disabled until verified.
4. **Container image/build:** no Docker-compatible engine is installed on this
   Mac. Use an approved official/open-source build engine or isolated GitHub
   build flow once runtime code is ready. Do not install a paid hosting service.
5. **Durable scheduling and sleep:** implement the bounded job lifecycle above;
   test idle, long-running forecasts, abrupt stop, restart, concurrent jobs and
   export totals against the local engine. Do not start sleep on current local state.
6. **Acceptance:** real Google sign-in and mail, owner bootstrap, two companies,
   four roles, forecast/export, wanted live factors, encrypted backup/restore and
   cost observation. Only then replace the domain hold with the actual app.

AI remains off for this deployment. Existing local keys were not copied; the
Iran-related provider eligibility gate in [deployment setup](DEPLOYMENT_SETUP.md)
still applies. Creating infrastructure does not resolve that gate.

## Verification evidence

- Three edge tests passed: route closure, honest unavailable API response, and
  domain/cost/isolation configuration. Wrangler dry-run passed.
- Domain-only hold deployed; HTTPS GET on `/`, `/api/v1/customers` and
  `/api/login/callback/google` returned the expected no-store 503.
- Both new R2 public development URLs checked disabled.
- Resend domain verified and enforced-TLS setting confirmed; real mail delivery untested.
- New Google credential origin/callback/project checked without printing its value.
- Local demo health remained OK; its existing process and configuration preserved.
- This is not evidence that containers, D1, real sign-in or mail delivery work yet.

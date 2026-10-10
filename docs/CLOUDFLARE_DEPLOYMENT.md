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
| Worker `demandlab-forecast-identity` | Private identity foundation deployed. No routes, workers.dev or preview URL. HTTP always returns 404; only private readiness RPC exists. |
| D1 `demandlab-forecast-identity` | New WEUR database, `f0f8d4b4-ff3d-4bcc-90ac-c08ff97b64e7`. Library-generated schema applied; zero users, companies and sessions. |
| `forecast.vrolen.com` | Worker custom domain created; HTTPS and closed app/login/API routes checked. No wildcard route. |
| R2 `demandlab-forecast-files` | New empty Standard bucket, Western Europe location hint; public r2.dev access disabled. |
| R2 `demandlab-forecast-backups` | New empty Standard bucket, Western Europe location hint; public r2.dev access disabled. |
| Google client `Vrolen Forecast` | Separate Web client with only the forecast origin/callback. Replacement installed as a private identity Worker secret; exposed predecessor disabled. Login remains inaccessible and real sign-in untested. |
| Resend `forecast.vrolen.com` | Separate verified Ireland domain, TLS required and receiving disabled. Restricted key installed in the private identity Worker; real mail delivery untested. |

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
compromised; it was replaced and disabled before deployment. The download was moved out of Downloads
into the ignored `secrets/` folder with mode 0600, and is quarantined as
`forecast-google-oauth.DO-NOT-USE.json`. Do not copy it into production.

On 2026-10-10 the owner added a replacement secret. Its Google JSON download was
moved to ignored `secrets/forecast-google-oauth.json` with mode 0600; the Downloads
copy is gone. Client identity and replacement match were verified without
printing the secret. The replacement is now installed in the private identity Worker
only. It has not been used for real sign-in; the public callback remains closed.

The owner disabled the older exposed secret on 2026-10-10. The Google client
page confirms the older secret is **Disabled** and the replacement is **Enabled**.
The disabled credential remains quarantined locally and must never be deployed.
No further credential-creation action is required from the owner at this checkpoint.

Do not publish the shared Google consent app
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
and permission; existing Finkavo keys were not changed. The new key is now a
Cloudflare secret on the private identity Worker only; no real mail was sent.

The maintained Resend SDK is wired with owner-only recipients while private,
fixed sender, hashed request idempotency and safe errors. Next, send one setup
test to the owner and verify actual
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
   does not protect against crashes. The new identity D1 database does not yet
   contain business records or durable forecasting jobs.
2. **Identity portability:** Better Auth is maintained, but this implementation
   uses PostgreSQL and PostgreSQL-specific policy/migration SQL. Cloudflare D1
   is not a drop-in PostgreSQL server. Shared auth configuration, the maintained
   native D1 adapter and company/role/session/MFA/key resolution are implemented
   and tested. Remaining: concurrent administrator operations, last-admin protection,
   invitation management, recurring grants and their private bridge. Registration is
   deliberately denied even for the owner; there is no production bootstrap route.
   Do not deploy an ephemeral PostgreSQL container.
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
- D1 schema migration applied to the new identity database only. Read-only remote
  count confirmed zero users, companies and sessions; no client/demo data uploaded.
- Shared identity suite: 18 passed, two optional tests skipped. The separately
  built native-Worker suite passed both checks, including closed HTTP routes and
  private readiness RPC against generated native D1 schema. One of those checks
  overlaps the unit suite. Schema drift/type checks passed.
- 41 focused Python deployment/security/access checks passed. Existing FastAPI
  deprecation/resource warnings remain; no full production acceptance is claimed.
- Cloudflare API confirms workers.dev and preview URLs disabled on both new
  Workers. Identity deployment has no targets; active version after secret setup:
  `4bcbb273-c57d-4a37-ad29-db3aa208af20`.
- Credential names confirmed without values. Dedicated production auth secret is
  generated once in ignored `secrets/forecast-auth-secret.txt` (0600), not reused
  from local auth. Installer accepts only the approved closed Worker/config.
- No public app/auth/API route is activated. This is not evidence that the
  container, real Google sign-in, mail delivery or full business migration work yet.

## Repeatable private identity checks

From `auth-service/`: `npm run check`, `npm test`,
`npm run schema:cloudflare:check` and `npm run test:cloudflare-worker`.
The last builds with pinned Wrangler and uses disposable Miniflare data and
synthetic credentials; its test-only caller is never deployed.

`node --import tsx scripts/install-cloudflare-secrets.ts` validates the private
credential files without displaying/uploading their values. `--install` uploads
them through stdin only to `demandlab-forecast-identity`. Do not manually copy
secrets into configuration, arguments, logs or Git. The quarantined Google file
is never loaded. Git contains code/schema only, not credentials or databases.

Next substantial build: complete serialized D1 administrator policy/bridge,
then durable company records, encrypted connector storage and job scheduling
outside the sleeping container. The public hold stays in place until a separate
explicit access decision; deployment completion must not automatically open it.

# Cloudflare deployment

Status: 10 October 2026. The owner-only cloud interface is deployed. Real Google
sign-in, owner MFA, Resend delivery, remote calculation and CSV export are verified.
Sleep/wake acceptance is in progress; this is **not a public or production launch**.
The local demo remains independent at `http://127.0.0.1:8010`.

Latest private API slice: 169 explicit company operations plus 14 native
identity/management operations, including assistant workflows, live connectors,
durable schedules, reports, exports and personal resources, are implemented.
Shared asynchronous screen/download adapters are connected through the
owner-only authenticated private UI gateway. See [scope and gates](CLOUD_WORKFLOWS_DELIVERY.md)
and [live owner acceptance](CLOUD_OWNER_ACCEPTANCE.md).

Current API-bridge deployment versions: identity
`04ea7aa7-943b-4b18-9e4a-46b58ead19e5`, storage
`5b71f9db-98d6-4bf5-b670-50a0be979ae9`, engine
`0fcf85be-8aa3-46c8-bf6e-06fc36314f97`; image
`sha256:bb84d6cc0a7d2ee07edaaff2390daa1c9fc844beb715f009a6341990d176d45f`.
Earlier versions below record the preceding backbone checkpoint. The dedicated
build VM is stopped after testing and its temporary registry login cleared after
the upload. The sign-in screen is reachable, but company routes require the
verified owner and fresh MFA. One owner mail test was delivered. No AI request
or client-source connection was made during this acceptance slice.

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
| Worker `demandlab-forecast-edge` | Owner-only compiled UI and private bindings. Company data requires verified owner and fresh MFA. No signup, outsider or bearer-key access. |
| Worker `demandlab-forecast-identity` | Private D1 permissions service and serialized administrator coordinator deployed. No routes, workers.dev or preview URL. HTTP always returns 404; private RPC only. |
| Worker `demandlab-forecast-storage` | Private native SQLite job/revision ledger and company-bound R2 checkpoint/artifact service deployed; private RPC only. |
| Worker `demandlab-forecast-engine` | Offline, non-root Linux engine with five-minute inactivity policy; private Worker relays only permission-checked, attempt-bound provider requests. No public listener or generic proxy. |
| D1 `demandlab-forecast-identity` | Dedicated WEUR database, `f0f8d4b4-ff3d-4bcc-90ac-c08ff97b64e7`. Library-generated schema; one verified owner, one company and one MFA session. |
| `forecast.vrolen.com` | Worker custom domain created; HTTPS and closed app/login/API routes checked. No wildcard route. |
| R2 `demandlab-forecast-files` | Dedicated Standard bucket with fictional owner-acceptance inputs/results; public r2.dev access disabled. |
| R2 `demandlab-forecast-backups` | Dedicated Standard bucket with immutable owner-acceptance checkpoints; public r2.dev access disabled. |
| Google client `Vrolen Forecast` | Separate Web client with only the forecast origin/callback. Replacement installed privately; exposed predecessor disabled. Real owner sign-in verified. |
| Resend `forecast.vrolen.com` | Separate verified Ireland domain, TLS required and receiving disabled. Restricted key installed privately; owner recovery email delivered. |

The edge configuration is [wrangler.jsonc](../deploy/cloudflare/wrangler.jsonc).
It disables workers.dev, preview URLs and observability payloads, limits CPU to
50 milliseconds. Only authenticated, MFA-verified company operations can wake
the dedicated engine; reading runtime status cannot start it. It does not expose
or tunnel the local demo. No public company access is enabled.

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
only. Real owner Google sign-in is now verified through the restricted gateway.
Outsider access and public registration remain blocked.

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

## Sleep and cost policy — deployed, remote behavior unmeasured

The runtime uses Cloudflare's official native container APIs, not a custom
process-hosting platform. Fixed singleton engine routing, no warm pool or replicas;
initial size is 0.25 CPU, 1 GiB RAM and 4 GB scratch disk. The bounded Linux pilot
passes; larger workloads and actual Cloudflare resource use still need profiling.
Do not claim the 256 MiB instance is sufficient for this numerical engine.

- Configured inactivity timeout: five minutes after useful work completes.
- An accepted forecast/import remains durable outside the container; running
  work has a persisted bounded lease. Never kill an active forecast just
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
The dedicated container application is deployed and ready, with **zero live
instances** at the remote read-only check. No cloud calculation has started yet.
The image upload itself does not establish measured sleep, wake latency or cost.
Native Durable Object scheduling is Cloudflare's beta policy; it does not accept
`max_instances`. Only one fixed engine ID is routed by this private application.

## Required engineering before the app can go live

1. **Cloud workflows/private UI gateway:** primary company resources, approved
   reports/exports and screen/download adapters now have private cloud bridges.
   Networked assistant, advanced/recurring actions and remaining connection/admin
   routes plus the authenticated private UI gateway still need completion;
   see CLOUD_REPORTS_DELIVERY.md. Cloudflare container disk is
   [ephemeral](https://developers.cloudflare.com/containers/faq/) and used as
   scratch only. Native SQLite jobs/revisions and immutable R2 company checkpoints
   now keep accepted work outside it, preserving existing calculations and orders.
   R2 FUSE is not a safe live SQLite WAL replacement. An upload on shutdown alone
   does not protect against crashes. Current private checkpoint staging is not
   the complete cloud UI flow. No local client data was
   uploaded. See [runtime delivery](CLOUD_RUNTIME_DELIVERY.md).
2. **Identity portability:** Better Auth is maintained, but this implementation
   uses PostgreSQL and PostgreSQL-specific policy/migration SQL. Cloudflare D1
   is not a drop-in PostgreSQL server. Shared auth configuration, the maintained
   native D1 adapter and company/role/session/MFA/key resolution are implemented
   and tested, including concurrent administrator operations, last-admin protection,
   invitations, keys, audit and background grants in private RPC. Registration is
   deliberately denied even for the owner; there is no production bootstrap route.
   Do not deploy an ephemeral PostgreSQL container.
3. **Live integrations:** AES-GCM encrypted company-bound credentials now work in
   Linux checkpoints, with an engine-only Cloudflare secret. Real credentials were
   not copied. Live factor fetching, recurring connector pulls and notification
   delivery need their permission-checked cloud execution outside the offline
   mathematical container; providers remain disabled until separately verified.
4. **Image/build:** open-source Colima/Docker built the isolated amd64 image.
   A dedicated build profile and private Docker config avoid changing the user's
   default Docker context or startup services. Base digest and tested Python
   versions are pinned. The image excludes all local data, credentials and tests.
5. **Durable scheduling and measured sleep:** native job alarms, cancellation and
   deadline fencing are implemented. Local native restart/busy/stop/failure and
   offline Linux order/export checks pass. Recurring business schedules and actual
   remote cold-start, idle shutdown, abrupt stop and billing observation remain.
6. **Acceptance:** real Google sign-in and mail, owner bootstrap, two companies,
   four roles, forecast/export, wanted live factors, encrypted backup/restore and
   cost observation. Only then replace the domain hold with the actual app.

AI remains off for this deployment. Existing local keys were not copied; the
Iran-related provider eligibility gate in [deployment setup](DEPLOYMENT_SETUP.md)
still applies. Creating infrastructure does not resolve that gate.

## Earlier backbone verification evidence

The following is the historical closed-domain checkpoint, not the current owner
interface state. Current live identity/mail/calculation/export evidence and
remaining gates are recorded in [owner acceptance](CLOUD_OWNER_ACCEPTANCE.md).

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
- Shared identity suite: 19 passed, three optional tests skipped. The separately
  built native-Worker suite passed both checks, including closed HTTP routes and
  private operations against generated native D1 schema, including competing admin
  changes. Schema drift/type checks passed. Dedicated native storage suite passed
  two checks; engine lifecycle/configuration passed ten; focused company/deployment
  Python suite passed 39. Three checkpoint/calculation checks also passed in the
  offline Linux image with four customers, partial orders and two existing methods.
- 41 focused Python deployment/security/access checks passed. Existing FastAPI
  deprecation/resource warnings remain; no full production acceptance is claimed.
- Cloudflare API confirms workers.dev and preview URLs disabled on all four
  dedicated Workers; no backend public targets. Resource bindings name only the
  new forecast identity database, private buckets and private services. Engine
  encryption secret presence confirmed without its value.
- Deployment versions: identity `901cddca-0c20-40c4-a5fb-51bdb19c205a`, storage
  `e87515ef-f86f-41b4-bb6c-4202fc0acca9`, engine
  `2e5a7c8e-e810-4a86-9d4e-99ea3fa95765`. Image digest:
  `sha256:1b9707fbca9f82a078889f72b156130a72d47519f3c5a4d30983f8237d16a3c0`.
- Credential names confirmed without values. Dedicated production auth secret is
  generated once in ignored `secrets/forecast-auth-secret.txt` (0600), not reused
  from local auth. Installer accepts only the approved closed Worker/config.
- No public app/auth/API route is activated. This is not evidence that the
  measured cloud idle/wake, real Google sign-in, mail delivery or full cloud UI/API
  business migration work yet. Cloud container application is ready with zero live
  instances; this milestone did not wake it or incur forecast execution.

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

Current next task: finish measured owner sleep/wake acceptance, then improve cold
automatic calculation performance and verify recovery/restore. Existing cloud
business bridges are implemented. Other people remain denied until a separate
explicit access decision; deployment completion must not automatically open it.

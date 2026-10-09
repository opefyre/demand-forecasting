# Deployment setup

Prepared 10 October 2026. Templates are ready for a separate staging installation;
no public deployment, account, DNS record or local-demo setting has been changed.
The existing demo stays at `http://127.0.0.1:8010`.

## What I need from you

| Item | Exact information/access needed |
| --- | --- |
| Domain | Choose the full hostname. `forecast.vrolen.com` is a suggestion, not a reservation. Give scoped DNS access or apply the A/AAAA records yourself. No registrar password needed. |
| Server | Existing server or hosting account, chosen region, server IP, OS and SSH username. Use SSH public-key access; do not send a root password. Linux reference setup below uses one dedicated Ubuntu/Debian host. |
| Company owner | Owner email, display name, company name and short company identifier. Choose a temporary 12+ character password securely; the owner verifies email and enrolls two-factor authentication. |
| Email | SMTP host, port, username, password/app credential and verified sender address. For example `forecast@vrolen.com` only if that domain is selected and verified. Provider supplies SPF/DKIM records; existing SMTP can be reused. |
| Google sign-in | Google Cloud project and a **Web application** OAuth client ID/secret. Exact authorized redirect: `https://CHOSEN-HOST/api/login/callback/google`. Add the chosen origin; configure consent/audience and an invited test account. |
| Database | Dedicated PostgreSQL database name, app username, password, hostname and port, or permission to create these on the selected host. Remote transport must verify TLS certificates. Do not provide a provider master password. |
| Backups | Separate off-device storage account/destination, restricted credentials, retention choice and a safe place for the encryption/recovery key. We must test a restore, not just upload archives. |

A new hosting, database or mail subscription is **not automatically required**:
existing suitable services can be reused. Hosting is not promised to be free.
For initial staging, 4 vCPU, 8 GB RAM and 60 GB disk is a starting estimate, not a
capacity guarantee; actual forecast load and data retention determine sizing.

Provide non-secret choices here. Put credentials in the agreed private secrets
folder or enter them directly into the provider/server; never paste keys into
chat, issues, Git or screenshots. Keep local credentials where they are. Production
configuration stays in `/etc/demandlab/secrets` on the deployment host, outside Git.
Separate random 32+ character auth and bridge secrets will be generated there;
you do not need another account for them.

## Two launch gates

1. **Linux integration vault:** current connector, live-source and notification
   credentials use macOS Keychain. These cannot be moved to Linux by copying
   files. A maintained secure vault must be selected, implemented and recovery-
   tested before secret-backed connections are enabled. The protected startup
   settings file below is not a replacement for that vault. The reference host
   templates do not pretend this is solved.
2. **AI eligibility:** [OpenAI's supported-country list](https://help.openai.com/en/articles/5347006-openai-api-supported-countries-and-territories)
   does not include Iran. An overseas server alone is not evidence of permission
   to offer this service to the Iranian client. AI stays off until eligibility
   is resolved or an eligible local/open-source provider is selected. No key is
   requested or reused in this preparation. A later eligible setup needs an
   explicit production-key choice, supported model IDs for each job and spending
   limits; current local model configuration is not proof of API availability.

## Optional connections — only those you want to use

| Connection | Needed after the host/vault is ready |
| --- | --- |
| Servix | Confirm whether the existing account/key may be used for deployment and its quota/licence. Do not create another account now. |
| Google Sheets | A separate service-account JSON credential, Sheets API enabled, spreadsheet ID and worksheet name; share only that spreadsheet as Viewer. This is not the Google sign-in credential. |
| Odoo 18 | HTTPS URL, database, company ID, dedicated read-only login and API key. |
| Odoo 19 | HTTPS URL, database, company ID and dedicated read-only API key. API access depends on the client's Odoo plan. |
| SFTP | Host, port, read-only username/password, exact server host key and absolute export-file path. Current connector supports password authentication, not private-key authentication. |
| HTTPS export | Complete export URL and optional read-only bearer credential. No password/token in the URL. No ERP write access needed. |
| Slack | Channel incoming webhook. |
| Teams | Teams Workflows webhook, not a retired Office 365 connector. |
| Telegram | Bot token and destination numeric chat ID. |
| WhatsApp | Eligible Business Cloud account, phone-number ID, restricted access token, approved template/language and recipient. Availability and fees must be checked; not promised free or available for Iran. |

Keyless public factor sources do not require user accounts. Their reachability,
freshness and suitability must still be checked from the actual server. Only
reviewed, dated data is allowed into forecasts; unavailable sources are not
silently replaced with invented values. Optional connections can stay disabled.

## Reference layout

Use existing open-source **Caddy**, **systemd**, **PostgreSQL**, Better Auth and the
app's existing libraries. No new cloud framework or bespoke deployment manager.

```text
Public HTTPS :443
  Caddy → private app 127.0.0.1:8020
             → private identity 127.0.0.1:8011 → PostgreSQL
             → local company files and forecast worker

/opt/demandlab                 fresh, pinned application checkout
/etc/demandlab/secrets         protected startup/bootstrap configuration
off-device encrypted storage  company state + identity + vault recovery
```

One API process and one worker on one host. Do not add API workers, share the
workspace between hosts or scale horizontally without revisiting schedulers,
SQLite storage and locking. Do not use the demo `run.py` launcher in deployment:
the service files own the worker separately. Only ports 80/443 are public;
8010/8011/8020 and PostgreSQL must not be internet-accessible. SSH is restricted
to the operator's access path. Do not publish the local demo using a tunnel.

## Host installation procedure

This is a reference runbook, **not an installer to run on this Mac**. Choose the
host first. Keep Caddy public traffic disabled until the acceptance checklist is
complete; use a private staging hostname/network for real service tests.

1. Install supported Python 3.13, Node 22+ at `/usr/bin/node`, PostgreSQL and Caddy
   on the dedicated host. Follow [Caddy's official installation](https://caddyserver.com/docs/install).
   Patch the OS and set firewall rules. Configure verified remote-database TLS if
   applicable; do not downgrade certificate verification to make a connection work.
2. Create a dedicated non-login `demandlab` system user. Clone a verified release
   to `/opt/demandlab` without copying local `data`, `runs`, `.env`, secrets or
   Keychain entries. Install Python requirements into `.venv`; run `npm ci` and
   the frontend build, and `npm ci` in `auth-service` **including dev dependencies**
   because its current runtime uses `tsx`. Run dependency checks. Freeze the
   resolved Python package list with the release evidence for reproducible recovery.
3. Own the checkout and installed dependencies as root, readable but not writable
   by the app user. Create `data`, `runs` and `.forecast-work` owned by `demandlab`
   with mode 0700; pre-create `.workspace.lock` owned by it with mode 0600.
   Only these paths are writable under the service sandbox. Never deploy over a
   running workspace. External CA files must be readable at their configured paths.
4. Create `/etc/demandlab/secrets` root-owned, mode 0700. Copy the blank
   [settings template](../deploy/deployment.env.example) to `deployment.env`,
   root-owned, mode 0600, and fill it privately. This file uses systemd environment
   syntax: quote values containing spaces or special characters appropriately;
   no shell expansion. Do not create a checkout `secrets/.env.local` that could
   override these settings. The service manager reads the protected file; runtime
   configuration is passed to the dedicated processes. A deployment secret manager
   can provision this file; it is not an encrypted vault. Limit host/journal access.
5. Copy the `deploy/linux/demandlab-*.service` and `demandlab.target` files to the
   host's systemd unit directory. Run `systemd-analyze verify` there, reload units
   and start **only** `demandlab-check.service`. It performs read-only configuration
   checks, not credential/service verification. Fix errors without printing secrets.
6. Create an empty, isolated identity database with an app-owned schema. Keep
   API/identity/worker stopped. Fill protected `bootstrap.env` using the separate
   [owner template](../deploy/bootstrap.env.example); start the manual-only
   `demandlab-bootstrap.service`. It migrates and creates the first owner/company,
   and refuses a second bootstrap. Remove the short-lived bootstrap credential
   file afterward; do not store it in long-running service configuration.
7. Start `demandlab.target` in private staging. After any settings change, stop
   and start the **whole target**, so the completed oneshot configuration check is
   rerun and all processes get the same settings. Do not just restart one worker.
   Runtime processes restart independently after failures; an unavailable identity
   service must deny protected requests, not grant access. Monitor all service
   states and worker health, not merely whether the target says active.
8. Replace the hostname in the [Caddy template](../deploy/linux/Caddyfile.example).
   Validate it with `caddy validate` on the host. Caddy proxies only the app;
   never serve the checkout directory or expose the identity service directly.
   Configure DNS and HTTPS according to [Caddy's HTTPS requirements](https://caddyserver.com/docs/quick-starts/https).
   Its admin endpoint stays local. Do not enable access logging of invite/reset URLs.
9. Complete [deployment acceptance](DEPLOYMENT_ACCEPTANCE.md): real mail, Google,
   MFA, four roles, two companies, keys/docs, an actual forecast/export, wanted
   providers and encrypted off-device recovery. Resolve the vault and AI gates
   above. Keep connection schedules and notification consent off until verified.
10. Only then enable public traffic and boot startup. Record release SHA, dependency
    versions and restore evidence. Keep the local demo independent.

## Maintenance and recovery

Stop `demandlab.target` before app/schema changes or offline backups. Caddy should
show maintenance, not route to a half-restored installation. Use the existing
workspace backup tool plus PostgreSQL `pg_dump`/`pg_restore`; encrypt archives and
recover vault secrets separately. Never put database passwords in command arguments.
See [recovery guidance](WORKSPACE_RECOVERY.md) and [identity recovery](DEPLOYMENT_ACCEPTANCE.md).

Deploy a new pinned release while stopped. Back up identity before migrations;
rolling code back does not undo schema changes. Test restores in new isolated
directories/databases. Never restore old sessions or keys into public traffic.

## Prepared versus verified

- Prepared: blank settings, offline owner setup, restricted service units, HTTPS
  proxy, account/credential inventory and host runbook. Contract tests check these
  against the current app ports, runtime paths and configuration rules.
- Not verified here: Linux service execution, Caddy certificate issuance, actual
  server capacity, PostgreSQL/mail/Google credentials, Linux vault, Iranian-client
  AI eligibility or live integrations. Those need the chosen host and accounts.
- No packages installed, migrations run, AI requests made or original demo data
  changed by this preparation.

Next: choose hostname/host/owner/mail/Google setup; prepare the secure Linux vault
and isolated staging, then run the host/account acceptance checks before launch.

# Authentication and public API foundation

Status: tested foundation, not yet a complete authenticated forecasting deployment.
Company sales/forecast/jobs, assistant scenarios, monthly updates, recurring
forecasts, connected inputs and notifications now use separate stores.
Keep the demo in local mode pending deployment acceptance.
Do not expose local evaluation mode to the internet.

## What is available

- Better Auth email/password, verified email, password reset, invitations,
  Google configuration, sessions, 2FA and single-use recovery codes.
- Admin, Planner, Approver and Viewer. Organization membership is checked on every
  protected request. Administrators must verify a factor in the current session;
  enrolling once does not authenticate all later Google/password sessions.
- Settings → People: invite, change role, suspend/restore, remove, sign out.
- Settings → API access: personal keys within current rights; restricted company
  keys for admins. Hashes remain in PostgreSQL, raw key shown once. Default expiry
  90 days, maximum 365 days; 60 requests/minute/key. Rotate/revoke immediately.
- `/api/v1` provides identity/access management, customers/products, sales inputs,
  reviewed orders/factors, grouped jobs/results/exports, approvals, personal
  chats/views, actual-results comparisons, settings and external factor connections.
  See COMPANY_FORECAST_DELIVERY.md for the workflow and limitations; remaining
  business API coverage is listed in PUBLIC_API_COVERAGE.md.

These screens are available in `better_auth` mode only. They are intentionally not
shown as nonfunctional management controls in the unauthenticated local demo.

## Services and secrets

Python app is the only public entry point. It forwards `/api/login/*` to the
private identity service at `127.0.0.1:8011`. The private `/internal/*` endpoints
require a separate shared bridge secret and must not be exposed by a proxy.
An isolated PostgreSQL database stores identity. Sales files, customers/orders,
factors, jobs/results and approvals use explicit company-separated storage.
There is no default-company fallback.

Use `auth-service/.env.example` as the configuration-field reference. Actual
values belong in the ignored `secrets/.env.local` or a deployment secret manager,
never this document, source control, command arguments or screenshots. Use
different random 32+ character auth and bridge secrets. Set secret-file access
to owner-only. Never put passwords or keys in browser storage.

Required fields:

- `DEMANDLAB_PUBLIC_ORIGIN`: exact HTTPS origin; loopback HTTP allowed locally.
- `DEMANDLAB_AUTH_DATABASE_URL`: isolated PostgreSQL database.
- `BETTER_AUTH_SECRET`, `DEMANDLAB_AUTH_BRIDGE_SECRET`.
- `DEMANDLAB_AUTH_SERVICE_URL=http://127.0.0.1:8011` for Python.
- Production: `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, optionally credentials.
- Optional Google: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` together.

Google callback: `https://APP-HOST/api/login/callback/google`. Account linking is
disabled. New accounts need a pending company invitation, including Google
accounts. Verified email and invitation acceptance precede company access.
Google support is wired, but real OAuth/consent and SMTP delivery are not verified.

For local testing only, `DEMANDLAB_AUTH_DEV_MAIL=true` writes messages to ignored
`secrets/auth-mail` (owner-only permissions), without sending email. The service
refuses this mode on public origins. Reset/invitation links are sensitive.

## Initial owner and migrations

Install locked packages with `npm ci` in `auth-service`. Run `npm run migrate`
against the dedicated auth database. It uses Better Auth's migrations plus
company status/key-binding/audit/session-factor tables.

The offline `npm run bootstrap` command initializes an empty installation. Supply
`DEMANDLAB_BOOTSTRAP_EMAIL`, `DEMANDLAB_BOOTSTRAP_PASSWORD`,
`DEMANDLAB_BOOTSTRAP_NAME`, `DEMANDLAB_BOOTSTRAP_COMPANY` and
`DEMANDLAB_BOOTSTRAP_SLUG` through the process environment or protected secret
manager. Do not type a password into shell arguments/history. Remove bootstrap
values after use. No HTTP route can enable this exception. Existing installations
are rejected. Owner must verify email and set up an authenticator normally.

`npm start` listens on loopback only. Do **not** set the Python application's
`DEMANDLAB_AUTH_MODE=better_auth` on the existing demo yet. Useful business routes
have migrated; unscoped legacy routes remain blocked deliberately. Activation
requires deployment acceptance, not just changing this setting.

## Public callers

Use `Authorization: Bearer …` for supported business operations. Keys are bound
to one company; a header cannot switch them to a different one. Personal keys
lose permissions immediately when the owner's role changes; suspended/removed
owners lose access. Keys cannot mint other keys or manage users.

Browser writes require matching origin plus `X-DemandLab-CSRF` from
`/api/auth/session`. Access/key administration requires an interactive session.
OpenAPI: `/api/v1/openapi.json`; interactive docs: `/api/v1/docs` when signed in.
Membership determines company selection; request bodies cannot select a company.

## Verification

`npm run check` and `npm test` in auth-service test configuration/policies.
Set `DEMANDLAB_AUTH_TEST_POSTGRES` to a test PostgreSQL administrative connection
to include real acceptance tests. They create/drop only a uniquely named test
database, never clear an existing app database. The test includes real Better
Auth HTTP sign-in, factor challenges, invitations, key lifecycle, two companies
and the Python application's actual bridge/proxy middleware.

`frontend/access-fixture.html` is a development-only browser fixture, not included
in the production bundle. Its four people and keys are memory-only and synthetic;
clicking it never changes actual access. Frontend tests also check shared layouts,
safe errors, viewer restrictions and Persian labels. Full company-scoped sales,
jobs and core AI context are additionally covered by company-store tests and the
disposable browser fixture in COMPANY_CONTEXT_DELIVERY.md. Advanced monthly
automation is implemented. Google/mail and real provider/deployment acceptance
remain open.

## Read-only deployment check

Run `npm run preflight` from `auth-service`. For a separate local company test,
use `npm run preflight -- --local`. It reuses the service configuration checks
without opening a database, sending email or contacting providers. It prints no
credentials. Invalid configuration returns a nonzero exit status; successful
configuration is explicitly **not** a verified deployment.

The shared secret file must be a regular, owner-owned, owner-only file on
macOS/Linux; symlinks are refused. PostgreSQL URLs, SMTP ports and paired mail/
Google credentials are checked. The supplied identity service must remain at
`http://127.0.0.1:8011`, behind the Python entry point.

See [deployment acceptance](DEPLOYMENT_ACCEPTANCE.md) for the remaining real-account
checks and separate identity-database recovery.

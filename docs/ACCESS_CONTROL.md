# Company access and plan approval

New platform work: see [Better Auth setup and current limits](AUTH_PLATFORM_SETUP.md)
and [delivery checklist](PUBLIC_PLATFORM_DELIVERY.md). The material below describes
the retained single-workspace OIDC mode, not the new company-scoped platform.

Status: implemented foundation, 21 September 2026. The running localhost preview
remains **local evaluation**, not an authenticated company deployment.

## What is implemented

Authlib 1.8 provides OpenID Connect sign-in with discovery, signed identity-token
validation, state, nonce and PKCE. There is no custom password database. A signed,
Secure, HttpOnly, SameSite=Lax cookie refers to a revocable server-side session in
`data/identity.sqlite3`. Sessions expire after one hour; logout revokes the session.
Unsafe authenticated requests require a matching CSRF token and same-site origin.

The operator assigns exact provider subject identifiers to roles. Membership is
reread on requests, so removing a member or reducing their role takes effect on
the next request. Invalid configuration fails closed rather than enabling local
access. One installation is one shared company workspace, **not tenant isolation**.

| Role | Access |
| --- | --- |
| Viewer | Read workspace and exports; query the existing helper |
| Planner | Import, calculate, draft, adjust, submit and comment |
| Reviewer | Read, comment, return and independently approve/publish plans |
| Admin | Configure inputs/access-sensitive application settings and plan workflows; cannot approve their own plan |

Plan creators, changes, reversals, comments and state transitions capture the
verified issuer/subject and display name when signed in. Typed names cannot replace
the signed-in actor. Approval rejects a creator or adjustment author, including
reversed edits. Legacy plans without a verified creator require a new signed-in
revision. Publishing requires a verified approval. Existing evidence gates remain.
Plan exports distinguish company sign-in from self-declared activity.

Local mode still permits labelled synthetic approval exercises. It now blocks
approval/publication of real or unclassified plans. Existing saved records are
not retroactively relabelled or authenticated.

## Operator configuration (not enabled by this implementation)

Configure an existing company or self-hosted OIDC provider. Register a confidential
client with the exact callback `https://YOUR-APP-HOST/api/auth/callback`. Supply
these environment values through the deployment's secret/configuration manager;
do not commit secrets or send them through chat:

- `DEMANDLAB_AUTH_MODE=oidc`
- `DEMANDLAB_PUBLIC_ORIGIN`: the app's exact HTTPS origin, without a path.
- `DEMANDLAB_OIDC_ISSUER`: the provider's exact issuer, preserving any trailing slash.
- `DEMANDLAB_OIDC_CLIENT_ID` and `DEMANDLAB_OIDC_CLIENT_SECRET`.
- `DEMANDLAB_SESSION_SECRET`: a cryptographically random secret of at least 32 characters.
- `DEMANDLAB_MEMBERS_FILE`: absolute path to an operator-controlled JSON file
  mapping exact subject identifiers to `viewer`, `planner`, `reviewer` or `admin`.

The API must see the configured HTTPS origin. A reverse proxy must preserve the
host, terminate TLS correctly and accept forwarded headers only from trusted
proxies. Keep the application listener private. Provider deployment, secret-file
permissions, HTTPS/proxy configuration and real accounts require deployment
acceptance; none were configured against the client here.

## Verification and limits

- Eleven focused tests exercise Authlib's actual cryptographic login flow against
  an isolated mock HTTP provider: state, nonce, issuer, audience, expiry, signing
  key, PKCE, cookie tampering, revocation, roles, CSRF and independent approval.
  These are not a real-provider integration test and send no client data externally.
- Full backend suite: 185 checks passed before the final nonce-flag hardening;
  the 11 security checks passed again after that change. Frontend build passed.
- Restarted local preview opens Today with its saved selections. Read-only sample
  checks still reconcile all 72 plan/export rows, revision differences and supply
  quantities. The published parent record's hash remains unchanged.
- Browser smoke check confirms the Settings local-mode warning, published-plan
  review controls and plan-to-Supply navigation retaining that published plan.
  No browser console errors were reported in this check.
- Company sign-in UI, actual provider compatibility, multi-user load, MFA/recovery,
  full role-specific browser acceptance and tenant isolation remain unverified/open.
- Session expiry returns to sign-in; universal unsaved-form recovery is not done.
- Identity binding currently covers plan governance, not every older import/job/
  scenario record. Session retention/cleanup and whole-app recovery remain open.

References: [Authlib Starlette integration](https://docs.authlib.org/en/stable/oauth2/client/web/starlette.html)
and [Starlette session middleware](https://www.starlette.io/middleware/#sessionmiddleware).

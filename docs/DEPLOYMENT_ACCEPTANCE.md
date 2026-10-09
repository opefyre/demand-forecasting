# Deployment acceptance

10 October 2026. Local safeguards are implemented; the app is not yet verified
on a public company deployment. Do not reconfigure the existing port-8010 demo.

## Completed locally

- Read-only `npm run preflight` in `auth-service`, sharing runtime configuration
  validation. HTTPS origin, private bridge, database URL, mail port/credential
  pairs and private secret-file checks; no database/provider calls or secret output.
- Two-company backup/restore: jobs interrupt, input/forecast/source schedules
  pause, old assistant actions expire and notification recovery remains safe.
  Customers, sales/order snapshots, saved results, action receipts, accepted input
  evidence and observation dates remain unchanged. Original stores are untouched.
- Four-role API acceptance uses the actual TypeScript permission catalogue,
  not an independently invented role list. Admin/Planner can update customers and
  start forecasts; Approver can read drafts but cannot calculate; Viewer cannot
  read draft inputs. Non-admins cannot administer notifications. Company B cannot
  read company A's inputs, even as Admin.
- Existing tests separately cover independent approvals, approved-only viewer
  exports, scope reduction, keys, CSRF, company isolation and revoked schedules.
- No new UI, styles, packages, paid AI calls or real provider messages in this chunk.

## Required before activation

- [ ] Choose the public HTTPS origin and deployment host; keep the identity service
      private. Expose only the Python entry point. Local evaluation must not be public.
- [ ] Provision an isolated identity PostgreSQL database, run migrations and
      bootstrap an initial owner. Use verified database transport/access controls.
- [ ] Verify real mail: invitation, email verification and password recovery.
- [ ] Configure Google OAuth's exact callback and test an invited account,
      sign-out/revocation and admin session-specific two-factor authentication.
- [ ] Walk all four roles in the actual deployment browser, including denied
      direct links, session expiry, exports and two-company switching.
- [ ] Verify real HTTPS/SFTP/Sheets/Odoo accounts and notification destinations
      selected for deployment; do not enable unused integrations.
- [ ] Publish the authenticated `/api/v1/docs` and `/api/v1/openapi.json` at that
      origin; verify a least-privilege caller and revoked/expired keys.
- [ ] Complete encrypted off-device recovery of company state, identity and secrets,
      matching the same application release; validate capacity and retention.

The existing local preflight correctly reports missing company-deployment settings.
This is not a failure of the demo. `configuration_ok` does not verify credentials,
provider eligibility, mail delivery, database migrations, backups or HTTPS hosting.

## Recover identity separately

Use PostgreSQL's existing `pg_dump`/`pg_restore` tools, not a custom database
exporter. Store credentials in a private PostgreSQL service/password file or
the deployment secret manager, never command arguments or Git.

1. Put the installation in maintenance; stop public API, identity, workers and
   schedulers. Preserve a matching application release and consistent company/
   identity backups. The workspace lease only coordinates app state, not PostgreSQL.
2. Back up company files using `scripts/workspace_backup.py`; back up the dedicated
   identity database separately in PostgreSQL custom format. Both contain private
   business/personal data; encrypt and protect them before off-device storage.
3. Restore company state to a **new** staging directory and identity to a **new,
   isolated, empty** PostgreSQL database. Never restore over a running database.
   Verify checksums, row counts, company IDs, schema and restore-report.json.
4. Before exposing the recovered installation, invalidate all restored identity
   sessions, verification/reset links and API keys in the isolated restored database.
   The app's key checks require an unrevoked `demandlab_key_bindings` row. PostgreSQL
   session deletion also clears the linked MFA/company-session evidence.
5. Re-establish owner access through verified sign-in and fresh two-factor challenge.
   Review old pending invitations/member roles and credentials. Issue new keys.
   Do not change member/role records silently to compensate for a mismatched backup.
6. Restore vault credentials through an appropriate deployment secret manager.
   Current company connector/notification credentials use macOS Keychain and do
   not travel in the ZIP. A different host/root must explicitly re-establish them;
   Linux secret-vault portability remains an acceptance gate, not a plaintext fallback.
7. Run preflight, actual identity/role checks and a disposable forecast/export.
   Review and explicitly re-enable wanted schedules and notification consent.
   Switch traffic only after acceptance; do not run two installations on the same state.

No identity database, real credential, real destination or existing client workspace
was restored, revoked, migrated or changed during these local tests.

## Verification

- Full backend regression: 824 checks, 823 passed, one optional real-identity
  integration skipped. Final targeted recovery/role checks: 17 passed.
- Frontend: 264 passed; production build passed with existing chunk-size warnings.
- Identity service: type check passed; 10 tests passed, one opt-in PostgreSQL
  integration skipped. The test database was not configured for this run.
- Dependency consistency and staged offline secret scan passed.
- Existing port-8010 demo health passed; no restart or data/configuration changes.

## Next chunk

Prepare an isolated deployment with the chosen domain, PostgreSQL, mail and Google
accounts. Verify those services and the four-role browser journey, then validate
the actual input providers and off-device restore. Activation stays gated until
those checks pass; do not call the app production-ready from synthetic tests alone.

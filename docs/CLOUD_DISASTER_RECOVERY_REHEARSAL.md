# Private cloud recovery rehearsal — 10 October 2026

## Scope

The owner completed the reset email, password entry, email/password sign-in and
authenticator verification privately. The newly opened Chrome tab was checked,
not the older reset-link tab. It shows Admin access and the saved forecast
“Tehran · Automatic allocation check”, with total demand of 3,982.84 tonnes.
No passwords, reset links, authenticator secrets or recovery codes were read.

The cloud restoration uses a separate database and durable ledger. It does not
replace the live identity database, switch the domain, execute forecasts, fetch
providers or deliver messages. There is no public rehearsal URL.

## Recovery safeguards

- Verify every restored reference belongs to the selected company.
- Compare the committed company archive in the files and independent backup
  buckets by SHA-256; preserve the committed revision and historical job receipts.
- Restore identity into a new D1 database with sessions, verification tokens,
  cached provider tokens and pending invitations invalidated, and API keys disabled.
- Verify the preserved encrypted MFA secret with Better Auth's own decryption.
  Do not generate an authenticator code or expose the plaintext.
- Verify the company vault key using a random encrypted test challenge, and prove
  that decryption with a different company binding fails. This is a key-recovery
  check, not a live connector credential or provider-login test.
- Restore queued/running jobs as interrupted; pause every restored schedule and
  delete alarms. Never replay old work automatically.
- Compare the live source head again to establish that it was not advanced or
  replaced by the rehearsal.
- Complete only once; repeat triggers return without restoring again.

The identity backup predates today's password reset. Restoring that backup does
not prove that the new password exists in the restored copy. A real cutover must
require fresh sign-in/recovery and operator review before enabling any schedules.

## Isolated resources and evidence

- Worker: `demandlab-forecast-recovery-rehearsal`.
- D1: `demandlab-forecast-recovery-20261010`,
  `81830101-c461-4c9c-81d8-20bb187c3da3`.
- Rehearsal ID: `dr-20261010`.
- Private backup objects: company-bound `recovery/dr-20261010/` ledger,
  encrypted synthetic probe and result receipt.
- Local evidence stays in the private Git-ignored
  `secrets/recovery-20261010-yFxW29WE/` directory. Never publish SQL exports,
  restored databases, ledger payloads or credentials.

The disabled checked-in configuration explicitly has an empty trigger list, no
public routes and no engine, provider or mail service binding. The operator
temporarily approved a one-minute trigger on this Worker only; after completion,
remove that trigger and both temporary decryption secrets.

## Verification

43 cloud controller/gateway/recovery tests pass. The compiled native-runtime
recovery test also passes, including restored running/queued jobs, a due schedule,
MFA decryption, wrong-company denial and repeat-run safety. Identity type checks
pass. The authentication suite passes 27 checks with four optional tests skipped;
the skipped native recovery and storage checks pass when run separately. No UI
components or design styles were added or changed.

## Remote result: partial, not accepted

The new cloud D1 database contains one user, one company, one member and one MFA
record, with zero sessions, reset tokens or active API keys. A read-only count
query confirms no database changes during verification.

The approved temporary trigger was created at 16:04:42 UTC. Deployment
`f38ff016-21ad-496e-9ffe-a0d41f8a3690` reports both `fetch` and `scheduled`
handlers, the correct private bindings and enabled rehearsal variable. At
16:35:09 UTC, neither the ledger snapshot nor completion receipt existed in R2.
The dashboard reported no invocations/events; its event-history page warns that
new Workers may take 30 minutes to appear. This does not establish a root cause
or certify the forecast-ledger restore. No successful cloud ledger restore,
remote vault decryption or remote MFA decryption is claimed.

Cleanup is verified: the rehearsal is disabled, the Cloudflare API returns an
empty trigger list and the official secret-list command returns `[]`. Both
temporary `AUTH_RECOVERY_KEY` and `VAULT_RECOVERY_KEY` bindings were removed. Keep the
private database and encrypted probe as isolated evidence, with no executing
schedule or public URL. The original company vault/authentication keys remain
unchanged in their normal private locations.

Disabled rehearsal deployment: `5f76d659-619a-432a-a96c-8f794544bbb3`, followed
by the two secret-removal deployments. The app's private storage Worker is
`7e7cb0dc-ce57-40eb-bb1d-5688efb205e2`; it adds only the operator's read-only
snapshot and a size bound that correctly counts Persian text bytes. Its schema,
resource bindings and public-access policy are unchanged. Domain, identity,
engine, email, other Cloudflare services and local-demo data are unchanged.
The diagnostic log listener is stopped. Local health remains 200 and anonymous
cloud customer access remains 401.

## Remaining acceptance boundaries

This is a cloud restore rehearsal, not a production cutover. Before client access:
agree backup retention and recovery targets; rehearse authorized promotion and
schedule re-enablement; complete role-based workflow tests and client source
reconciliation. Do not enable AI, add users or expose access as part of recovery.

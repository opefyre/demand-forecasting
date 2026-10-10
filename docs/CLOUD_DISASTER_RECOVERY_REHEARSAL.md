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

The disabled checked-in configuration has an empty trigger list, no public routes
and no engine, provider or mail binding. The earlier trigger did not produce a
receipt. The completed rehearsal instead used an authenticated, private service
binding through Wrangler's official local operator interface. No operator Worker
or public endpoint was created. Both temporary decryption secrets are removed.

## Verification

46 cloud controller/gateway/recovery checks pass. Each compiled native identity,
storage and recovery suite passes two checks. The identity suite tests all four
roles against the 169-route permission inventory. Identity type checks pass;
the authentication suite passes 27 checks with four optional checks skipped.
The native identity/storage/recovery checks pass separately; PostgreSQL is not
the deployed Cloudflare database. Python backup/restore passes 13 checks.
Shared-design corrections and retention evidence are recorded in
[CLOUD_RETENTION_ROLE_ACCEPTANCE.md](CLOUD_RETENTION_ROLE_ACCEPTANCE.md).

## Remote result: verified

The new cloud D1 database contains one user, one company, one member and one MFA
record, with zero sessions, reset tokens or active API keys. A read-only count
query confirms no database changes during verification.

The earlier temporary trigger had no completion receipt. Its failure cause is
not established. A direct private operator invocation completed at
`2026-10-10T16:47:09.374Z`, restoring the actual cloud archive and ledger into the
isolated resources above. Receipt: `verified: true`, 20 revisions, 41 job records,
36 completed jobs and 120 company-bound references. Remote MFA-secret and company
vault-key decryption passed, including wrong-company denial. Zero sessions or
provider tokens restored; zero engine/provider calls; live ledger unchanged.

Committed revision: `fbcb713929b045c58825f9503285a6fa`.
Archive SHA-256: `6c3f5d99a77c471bd766b88f31c9dc8c1450cb3fa5fa416c75d5c0f3b4e922ad`.
Ledger SHA-256: `652c46ff56c8ebcc746cd9633581469d80c90dec9caa8deb827a1ab6d2fb694a`.

The same verified archive was restored into a private offline review. Three saved
forecasts (`4bc668601e37`, `a9df1110b127`, `19ade25fd9d6`) each preserve 108 rows,
3,982.844528790624 tonnes total demand, 2,099.364 confirmed outstanding tonnes
and 1,837.768528790624 calculated remaining tonnes. Exact saved calculation
objects, customer/order inputs and six exports per forecast match the original.
CSV/JSON compare byte-for-byte; XLSX compares every workbook member except the
non-business creation timestamp. Eighteen exports verified without recalculation.
These are fictional Tehran acceptance inputs, not proof of client accuracy.

Cleanup is verified: the rehearsal is disabled, the Cloudflare API returns an
empty trigger list and the official secret-list command returns `[]`. Both
temporary `AUTH_RECOVERY_KEY` and `VAULT_RECOVERY_KEY` bindings were removed. Keep the
private database and encrypted probe as isolated evidence, with no executing
schedule or public URL. The original company vault/authentication keys remain
unchanged in their normal private locations.

Final disabled rehearsal deployment: `f39367b1-3562-4053-a8a9-43ca12075050`.
An operator call now returns `verified: false, phase: disabled`; secret list is
`[]`. Storage deployment `1f955e8d-ead4-4f39-8193-c8f2893a3363` adds private
latest/history ledger replication. Its schema, resources and access remain
unchanged. No live identity, engine or mail changes. Other Cloudflare services and
local demo data are unchanged. Local health is 200; anonymous customer access 401.

## Remaining acceptance boundaries

This is a cloud restore rehearsal, not a production cutover or provider-wide
disaster test. Retention and automated role checks are complete. Before client
access: agree recovery-time/data-loss targets, explicitly approve promotion and
schedule re-enablement, complete the full bilingual cloud sales journey and
client-source reconciliation. Do not enable AI, add users or open access through
recovery work.

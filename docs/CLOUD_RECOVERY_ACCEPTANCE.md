# Private speed and recovery checks — 10 October 2026

## Scope

Only the dedicated forecast engine/controller, storage response handler and forecast
interface were deployed. Other Vrolen/Finkavo services, cloud identity/access settings and the local
8010 demo data were not changed. The numerical image and mathematical methods are
unchanged. Access remains owner-only with fresh MFA; cloud AI remains disabled.

## Automatic performance

The prior smallest allocation throttled numerical work to 0.25 CPU. The controller
now gives the singleton one CPU with the required 3 GiB RAM, 4 GB scratch disk, a bounded
12-minute work lease and five-minute idle shutdown. A deployed controller cannot
resize a warm container. Before the next job it replaces an idle old allocation;
it does not interrupt active work. Warm instances of the new allocation are reused.

Cloudflare bills CPU by actual use, while memory/disk are provisioned usage:
[official pricing](https://developers.cloudflare.com/containers/platform/pricing/).
This increases the CPU ceiling, not a new subscription or an unlimited-free claim.
Memory is tripled while the work is bounded and still sleeps after five minutes;
faster completion can offset this, but actual memory cost depends on run duration.
The real account bill
must be checked separately. There is no account-wide hard spending cap.

The same fictional Tehran history/order inputs completed in approximately 338
seconds in the first live retest, versus roughly nine minutes in the preceding
acceptance. Its result remains 3,982.84 tonnes. This first retest may have reused
the old warm allocation; it is not proof of the new allocation's cold timing.
The supported new-allocation repeat reached its completed, durably saved result
within 74 seconds of clicking “Run selected methods” (the first completion
observation, not a millisecond-exact timer). It retained the same 3,982.84-tonne
total, 2,099.36 confirmed outstanding and 1,837.77 expected-not-ordered quantities.
This includes the request/queue/calculation/save path, not just an isolated model
fit. These synthetic data timings are not a latency guarantee for larger workloads.
After the completed run and dashboard read, the owner-only runtime check confirmed
`running: false`, `busy: false` and a 300,000 ms idle timeout. The new allocation
therefore shuts down automatically as configured; observing runtime does not wake it.

The first attempted custom one-CPU/one-GiB allocation failed Cloudflare startup
validation; the saved input/output head was not replaced. Cloudflare custom sizes
require at least one CPU and three GiB memory per CPU, per its
[limits](https://developers.cloudflare.com/containers/platform/limits/). The final
allocation meets those requirements. Failed engine jobs now return a safe service
failure instead of incorrectly presenting a saved-data/version conflict.

Offline profiling uses `scripts/benchmark_automatic.py`: fixed synthetic history,
804 rows, 18 series and six future months. The native macOS profiled run took
18.605 seconds. It includes an optional seventeenth LightGBM model absent from the
production Linux image. It is not a cloud-speed benchmark. An emulated amd64 Linux
quarter-CPU test was stopped after 13 minutes; emulation is not production evidence.
No fitting, held-out testing or order-consumption rule was removed to improve speed.

The shared forecast wizard now says “Calculating…” during the cloud operation,
using the existing translated status and global structure. No page, style, banner,
fake percentage or estimated completion time was added.

The repeated wizard exposed a transport race: a delayed read response could
rewind the browser's optimistic-write revision after a successful write. Saves
failed closed with a version conflict rather than overwriting data. Read responses
now cannot rewind that authority; parallel bootstrap reads also do not overwrite
an already-established head. A regression test holds an old read until after a
write and checks that the following write uses the newer revision. Writes are
still never replayed automatically after a lost response or a conflict.

## Account recovery

`auth-service/test/recovery.test.ts` uses maintained Better Auth and disposable
native D1, synthetic credentials and captured mail. It verifies:

- Outside email addresses, other origins and external return addresses are denied.
- A valid reset link works once; expired links and weak passwords fail.
- Password reset revokes old sessions and session MFA proofs.
- Company membership and MFA enrollment survive reset. The new password still
  requires MFA; a recovery code works once and cannot be reused.

These are real library/policy tests, not a live change to the owner's password.
The earlier real recovery email was delivered; actual owner password entry and
recovery-code use remain a user-controlled browser drill. Never send codes here.

## Real backup restoration

Downloaded one exact company revision from the private backups bucket and its
checkpoint counterpart from the private files bucket. Both are 196,012 bytes with
SHA-256 `7a488cf2d9f21df33183aa191ced519d135764f3dbc1ab84162e093cfd584fea`.
Revision `9b57fb285d9c442a979bef902f3d4eae` contains the original accepted run
`19ade25fd9d6` and order snapshot `78fcdfbc0a98e3df628b3cc344484c2a`.

`scripts/cloud_restore_review.py` requires the exact company and independently
supplied archive checksum, verifies bounds/manifest/file hashes/SQLite integrity,
and restores only into a new directory. All 23 files verified. Restored active jobs
stop; imports, source refresh, recurring drafts and notifications pause. Completed
results and business inputs are retained. Ordinary engine wake uses its existing
separate restore path and does not apply disaster-recovery sanitization.

Using the restored stores and existing demand calculation/export code reproduces
the earlier live CSV byte-for-byte: 108 rows, 79 order lines, five mapped customer
names and total 3,982.84 tonnes. The customer master table itself is empty in this
backup; these five customer identities are in the accepted history/order mapping,
not five restored customer-master records. Export SHA-256:
`c48d83c56d2765fece604f8c11c988308f327bfdf4583386322361fc7d159fdd`.
The live ledger/head and original workspace were never replaced.

A fresh export of only the dedicated identity D1 database was restored into
in-memory SQLite by `auth-service/scripts/verify-identity-restore.ts`. Integrity and
foreign keys pass: one user, one company, one member, one enrolled MFA record.
Sanitization of the review copy removes sessions/reset verifications, disables API
keys/pending invitations and clears cached OAuth access/refresh/ID tokens. Ownership
and encrypted MFA data survive; no replayable session/provider token remains.
No production identity rows or credentials were changed. Matching Worker secrets
are still needed for a real cutover and encrypted credential recovery.

Cloudflare's D1 export CLI printed a one-hour signed download URL. It was not
repeated or saved to Git; the export remains in a private directory/file. Do not
paste export-command output into documentation, tickets or messages.
The backup and restored review copy are retained under the private, Git-ignored
`secrets/recovery-20261010-yFxW29WE/` directory. The identity export contains
sensitive authentication state; never publish it or include it in a support log.

## Boundaries and next steps

This is an isolated restore drill, not a live disaster cutover. A complete cloud
cutover also needs the durable storage ledger, matching Worker secrets and explicit
operator reconciliation before re-enabling schedules or delivery. Restoration must
never silently rerun an old forecast, connector fetch, assistant action or message.
Next: user-controlled live account-recovery completion, then a dedicated company
restore/cutover rehearsal with the ledger and encrypted credentials. Do not open
access to another user or enable Iran-client AI/providers as part of either task.

## Verification and deployment receipts

- 272 interface checks; build and identity type checks pass.
- 40 cloud controller/gateway checks; two compiled native storage checks pass.
- 26 shared authentication checks pass; three optional checks remain skipped.
- 24 targeted cloud/recovery/API backend checks pass; the final 17 recovery/compute
  checks pass again after tightening the compressed-size precheck.
- Secret scan and staged whitespace checks pass; no backups, credentials or actual
  identity rows are in Git. Build warnings about library directives, runtime fonts
  and bundle size are existing limitations, not silent test failures.
- Engine controller: `ef662b66-51cb-4141-b782-0395c060a55b`, same mathematical image.
- Private interface: `4cf38663-a21e-4fb5-b5b1-7d5815ce9c63`.
- Identity version is unchanged. Storage response version:
  `63278575-9355-4fd0-9f81-6f348a3ff1cd`. Its schema, resource bindings and access
  policy are unchanged.
- Local 8010 health is 200; anonymous cloud customer access remains 401.

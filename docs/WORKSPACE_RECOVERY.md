# Local state backup and recovery

7 October hardening: recovery also pauses order/factor folder schedules, live
external-source refresh and recurring monthly forecasts; history auto-drafts are
disabled. Interrupted external refresh becomes failed without changing observation
dates. Business snapshots, cycle history, permissions and quotas remain intact.
See RELEASE_PILOT.md for current isolated volume/Persian restore evidence.

Implemented and exercised on macOS, 21 September 2026. This is an offline local
state recovery tool, not a distributed/zero-downtime backup service or a claim of
production readiness. It uses Python standard-library SQLite backup, ZIP,
checksums and POSIX process locks; no new dependency was introduced.

## Scope and safeguards

The ZIP includes regular files under `data/` and `runs/`: uploaded source bytes,
saved datasets, stock/receipt versions, units, actual comparisons, decisions,
plans, factor/weather caches, integration configuration, completed run results
and exports. SQLite databases are copied through the SQLite backup API and
integrity-checked; journal sidecars are not independently copied. Every included
file has a SHA-256 and size in the manifest.

Application code, installed dependencies, environment secrets, external export
folders and unfinished `.forecast-work` directories are not included. Preserve
the exact application release/source separately. The manifest records the original
root and requirements hash, not a reproducible environment or a code attestation.
Absolute external paths must be reviewed on another machine. The bundled sample
files remain part of the separately preserved application checkout.

Stop **all** API processes and workers before backup. Main app and job modules
hold shared process leases before initializing stores; backup holds an exclusive
lease for its complete operation. App starts and backups fail explicitly if they
conflict. POSIX `flock` is supported on macOS/Linux. This cooperative lock cannot
protect against old code, external database writers or manual filesystem edits;
do not run those during maintenance. Windows/network filesystem behavior is not
certified. Upgrade/restart old processes before relying on the lease safeguard.

Archives are published without overwriting another file and have private 0600
permissions. They contain confidential client data and are **not encrypted**.
Keep on encrypted, access-controlled storage; arrange a separate off-device copy
and retention policy. No backup was uploaded externally. Checksums detect damage,
not a maliciously replaced archive and manifest; use trusted backups only.

## Commands

From the project, after stopping the app/worker:

```sh
.venv/bin/python scripts/workspace_backup.py backup /secure/existing-folder/new-backup.zip
.venv/bin/python scripts/workspace_backup.py restore /secure/existing-folder/new-backup.zip /secure/existing-folder/new-restore
```

Restore accepts only a **new** directory, never overwrites the running workspace,
rejects unsafe/duplicate/unlisted paths and links, limits declared size/file count,
and verifies hashes and SQLite integrity before removing `RESTORE_INCOMPLETE`.
A failed restore remains marked and cannot start the app; inspect it and retry
into a different new directory. The command does not recursively erase failures.

After verification, restored runtime state is deliberately made inactive:

- Sign-in sessions are invalidated, if present.
- The restored transient Huey queue is discarded; completed run files remain.
- Queued/running/publishing job records become interrupted, for explicit retry;
  completed job history is unchanged and worker leases are cleared.
- Integration and export-folder schedules are disabled, retaining settings and
  history. Review paths, source permissions and credentials before enabling.

`restore-report.json` records the source archive hash, verified file count and
these changes. Business quantities, review history and plan statuses are not
rewritten. Copy the matching app release around the restored state, reconfigure
secrets/member files outside the archive, review source paths and test locally
before replacing an operational installation. Do not start two installations
against the same state. No automatic in-place cutover is supplied.

## Verification evidence

Seven recovery tests cover process exclusion, immutable destinations, committed
WAL data, corruption, traversal, symlinks, runtime sanitization, source preservation
and failed-restore startup refusal. Full suite: **216 passing tests**. A subsequent
targeted rerun of the seven recovery tests passes after adding lease cleanup at
process exit. Existing unrelated dependency/resource warnings remain.

Actual local drill:

- Archive `.recovery/state-20260921.zip`, SHA-256
  `8fe0fd9c9c4126ee398866ecdbc03fc7cb810994bc5768c764e77d10d92167a4`.
- 244 files, 22,225,257 uncompressed bytes verified into
  `.recovery/drill-20260921`; originals not replaced.
- All 40 saved-input files and 188 run files match original bytes. All rows in
  six business SQLite databases (10 tables) match the originals: decisions,
  inventory including receipts, plans, actuals, units and retained plan backup.
- Restored folder schedules disabled; queue removed only from the restored copy.
  No live identity database existed; session invalidation is covered by tests.
- Restarted app health 200 and worker available. A live backup attempt correctly
  refused without creating its destination archive.

This verifies a local data restore, not startup of a relocated deployment, an
off-device disaster drill, power-loss guarantees, migrations across releases,
retention automation, encryption/key management or multi-host recovery. Those
remain deployment acceptance gates.

23 September follow-on: an isolated regression round-trip also preserves the
customer directory, reviewed sales snapshots, user-owned saved views and AI journal
using their actual store schemas. These already fall within the existing data-folder
backup boundary; no new custom backup mechanism was introduced. This is a local
temporary-workspace test, not an off-device drill or a live backup of the client data.

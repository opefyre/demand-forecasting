# Local plan persistence

Saved plans now use `data/plans.sqlite3`, through Python's standard SQLite library.
This is a local reliability improvement, not a claim of complete production database,
multi-tenant security or disaster-recovery readiness.

## Guarantees and boundaries

- Each edit reads and writes inside `BEGIN IMMEDIATE`. SQLite serializes writers
  across application instances/processes; concurrent comments and revision branches
  do not overwrite one another. Readers see committed snapshots.
- Errors roll the entire edit back. Unchanged plans are not rewritten. The store
  does not permit record removal through an update. Revision request IDs are unique.
- The first access migrates the legacy JSON in one transaction. It validates records,
  records the source SHA-256/count/time, and sets schema version 1. The JSON file is
  retained unchanged, never used as a silent fallback and never automatically reimported.
- Invalid JSON, duplicate IDs, invalid records, non-finite values, corrupt databases
  and unsupported schema versions fail visibly instead of producing an empty registry.
- Database connections are short-lived, with full synchronization and a 30-second
  busy timeout. This is single-host SQLite on a local filesystem, not shared network
  storage, a distributed database or a load-tested multi-user deployment.
- Transactions protect storage integrity. They do not establish authenticated actors,
  independent approval rights or optimistic conflict prompts for two planners editing
  the same quantity. Those remain separate requirements.

## Migration operation

Stop all old app/worker processes before first access with the new version: old code
still writes JSON and cannot coordinate with the database. Retain the JSON and the
database snapshot. Do not run an old version against the retained JSON after migration;
that would ignore subsequent database edits.

On 21 September 2026, all seven existing records were compared as complete objects
before/after migration. They matched exactly. Legacy file SHA-256:
`32ea368de298df1be4b6d4e3842f4adc5e74c9be201978519a4cdbf32bafc15a`.
The original remains at `data/plans.json`; initial database snapshot is
`data/plans-post-migration-20260921.sqlite3`.

## Backup and recovery

From the project directory:

```sh
.venv/bin/python scripts/backup_plans.py /absolute/existing/folder/plans-unique-name.sqlite3
```

Uses SQLite's online backup API and checks database integrity. An existing destination
is never overwritten. Keep backups on separately managed protected storage. No automated
schedule, retention or off-device copying is configured.

To recover, stop the app and worker, preserve the current database, validate the selected
backup, and restore it as `data/plans.sqlite3`. A restored backup contains the schema and
migration marker, so retained JSON will not be reimported. Restart and reconcile plans
against source runs. This is an operator action, not an implemented end-user restore UI.
Plan-only snapshots do not contain run results, uploaded source files, other registries,
or settings; those must also be protected for a complete application recovery.

## Evidence

Nine tests cover exact migration/reopening, malformed source rollback and retry,
transaction failure, 32 comments from four separate processes, simultaneous migration
and creation, cross-instance revision idempotency/version numbering, isolated backup
restoration, corrupt/unsupported database rejection and no-deletion protection.
Full backend suite: 166 passing tests.

The restarted app passed `scripts/verify_plan_review.py`: 72 rows of published sample
plan `e2379cd021` and 72 rows of revision `51f34a7686` still match their exports.
Published plan record hash is unchanged; previous quantity 125, revised quantity 135,
and +10 revision difference remain intact. Synthetic evidence only.

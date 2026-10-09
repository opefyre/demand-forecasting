# Reviewed refresh to draft — 27 September 2026

Data → Connections → Export folders now offers **Create draft forecast** for a
reviewed/saved candidate. This single action checks the folder again, validates the
retained dataset and dispatches the existing background forecast job. It does not
publish a plan or copy current orders. Review orders separately for the new run.

Reuses FolderInputs, DatasetStore, Huey/SQLite jobs and the existing job activity bar.
No new dependencies, paid service or external connector. Admin-only under the
existing integration permissions; no permission expansion.

Safety:
- Unreviewed input cannot dispatch.
- New file contents create a candidate requiring review rather than using an old
  version silently. Failed refreshes do not dispatch.
- Job is pinned to the accepted dataset, not a mutable folder path.
- Stable candidate request ID prevents duplicate jobs from repeat clicks/retries.
- Stopped jobs use the existing explicit Retry action; completed inputs reuse the
  completed job. Prior forecasts and input versions remain unchanged.
- Only sales history and optional future-factor files are eligible. Production-file
  selection was removed from this connection form; old records remain preserved.

Verification: 19 targeted folder/job tests; 382 full backend tests; 55 frontend
tests; production build. Existing database resource/dependency warnings remain.
Route tests use an isolated durable job ledger: unreviewed/changed/failed refresh
blocking and repeat-request reuse pass. Background worker execution is covered by
the existing job suite, not a newly created live client run. The new connection
button has not yet been browser-tested against a configured live folder.

Follow-up: optional scheduled drafts are implemented using the existing APScheduler
and job queue. In Connections, enable **Create drafts after input review** on a
scheduled folder. Default is off, including existing connections. Changed files
still require review/save; a later check submits the accepted version with the same
deduplication key used by the manual action. Refresh history retains dispatch
outcomes and job IDs. Pause prevents future checks/dispatches, not jobs already
running. No automatic publication or copied/renewed orders. App must be running.

Verification: 384 backend tests, 55 frontend tests and build pass. Tests cover
opt-in, persistence, pause, changed/invalid files, dispatch failure and reuse of
the manual job. Existing dependency/resource and bundle-size warnings remain.
Live browser acceptance of this control remains pending; no real schedule enabled.

Next build: reviewed order-source refresh with stable order-line IDs, cancellation
and fulfillment updates, then combine those orders with the draft without counting
the same demand twice. Client order-source credentials/schema remain prerequisites
for a real integration; start with the existing import path and synthetic evidence.

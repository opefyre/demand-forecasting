# Local export-folder ingestion

Implemented 21 September 2026. This is actual local file ingestion, not the older
connection-availability diagnostic. It does not implement ERP/database/HTTP ingestion.

## User workflow

1. Import one representative complete export in Data and review its mappings,
   units, calendar, factors and optional production tables. Save that dataset.
2. In **Data → Connections**, an administrator chooses **Connect folder**. Select
   that reviewed mapping, an approved absolute folder and exact filenames. History
   is required; future-factor/production files are optional where the mapping
   already contains them. Explicitly confirm file access; label synthetic files.
3. Choose manual checks or 15-minute/hourly/six-hourly/daily checks. Automatic checks
   run only while the application is running. Schedules are restored at startup;
   this does not replay every interval missed while the application was stopped.
4. **Check now** or a scheduled check reads complete exports. New valid contents
   become an immutable-source snapshot ready for review. Invalid files create a
   failed history entry; earlier valid inputs remain accessible. Unchanged contents
   do not create another candidate. No forecast, accepted dataset or plan is
   automatically overwritten or approved.
5. **Review inputs** opens the existing guided review. Confirm settings, warnings,
   future assumptions and any stock dates. Save creates a new dataset linked to
   the original template, with refresh time, exact filenames and byte hashes.
   Then run a forecast as usual. Reviewed connections offer **View saved data**.

Use **complete replacement exports**, not increment-only files. Do not append an
export to history blindly: the application cannot infer corrections or duplicates.
Unspecified roles retain the template's saved inputs; these retained roles are
recorded in provenance. New production dates or future-factor gaps require review.

## Operator boundaries

- `DEMANDLAB_IMPORT_ROOTS` is a JSON array of explicitly approved absolute folder
  roots. By default only this repository's `sample_data` directory is approved.
  Do not approve a whole home directory, secrets directory or filesystem root.
- Only exact CSV, TSV, JSON, XLSX or XLS filenames are supported: no wildcards,
  subfolder traversal or linked files. Each input is limited to 50 MB and must be
  a regular file unchanged during reading and at least two seconds old.
- Publish exports atomically after writing finishes. Multi-file exports are not
  a database transaction; the ERP/exporter must supply a consistent bundle.
- Company mode restricts connection creation, checks and pause/resume to admins.
  Planners can review and save staged inputs. Local mode is still evaluation only.
- SQLite serializes checks and retains configurations, outcomes and source
  references. APScheduler is the existing scheduling library; no new scheduler
  was invented. Each connection permits one scheduled instance and coalesces
  missed executions. Distributed scheduler leadership is not implemented.
- JSON dataset publication and SQLite acknowledgment remain separate writes, but
  acceptance now uses a deterministic save request and a SQLite transaction.
  A process stopping between them recovers the same published version on retry;
  concurrent acceptance is serialized. Staging cleanup, retention, whole-app
  restore, power-loss/storage-failure testing and automatic forecasts remain open.
- The newest ten check entries appear in the UI; earlier entries remain in the
  database. An older valid candidate stays available if newer files fail.

## Evidence

- Nine focused tests: changes/unchanged hashes, invalid exports, consent/root/
  filename restrictions, missing/symlink/actively-written files, concurrent checks,
  restart persistence, review provenance, real scheduler execution, pause,
  concurrent acceptance and recovery after a simulated pre-acknowledgment stop.
- Final full suite: 196 Python tests pass; ten JavaScript import/chart checks and
  the production frontend build pass.
- Security tests cover planner denial of folder administration/check endpoints.
- Browser workflow used synthetic mapping `64208d8e50394c148c0036c9e3f8abf2`,
  connection `8d7ae21e25074cbfbbd58a6f03cc1944`, candidate
  `12c0d1ad4c6f4cd68297b1dfdd985f9d` and reviewed dataset
  `17b267a293be41a0b5366e719b4c0f37`. Seven rows and FX selection were retained;
  the original six-row dataset stayed unchanged. A repeated check returned
  `unchanged`. The earlier synthetic save was linked to its reviewed marker
  after the final acknowledgment UI fix; quantities/source IDs were not changed.
- Form input accessible names were added during browser inspection. The connection
  status view was visually inspected at the current 715px viewport; full keyboard,
  mobile/laptop matrix and real ERP export acceptance are still open.
- After the final restart, **View saved data** opened the seven-row reviewed
  dataset with its FX selection and short-history warnings. No browser errors
  were reported. No schedule was enabled for the live synthetic fixture; actual
  scheduled execution was exercised in an isolated test.
- Saved-data follow-up: browser opens “Saved data” with Done/Forecast actions,
  not another save request. Running from it created job
  `cb7eedeeb5ec471d82c69e520458e0e4` and successful run `5d78ab8284a4`, while
  retaining exactly one `Synthetic scheduled export` dataset. The result shows
  “More history needed,” 70 units for August 2025 and selection-only evidence.
  This seven-month fixture tests the workflow, not real-world forecast accuracy.

Library reference: [APScheduler 3.x guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html).

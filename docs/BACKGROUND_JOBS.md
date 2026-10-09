# Background forecasting — local deployment

Starting a forecast, method rerun or scenario queues a calculation. The status
panel stays visible while the rest of the app remains usable. Reloading reads the
saved job instead of starting another run. Choose **Open result** when ready;
results never unexpectedly replace the forecast currently being reviewed.

**Cancel** prevents queued work from starting. Running jobs stop at the next fitting
checkpoint; one current library fit may need to finish first. The app says
“Stopping” until cancellation is recorded. Partial results never enter the forecast
list. Once atomic saving starts, the result completes rather than being partially
rolled back. Job completion does not approve or publish a business plan.

Failed/interrupted jobs retain their inputs. **Retry** creates a linked attempt,
not a rewritten history record.

## Reused infrastructure

[Huey](https://huey.readthedocs.io/en/latest/) 3.4 owns persistent SQLite task
delivery. SQLAlchemy/SQLite store the application job ledger and worker health.
Existing forecasting libraries perform the calculations. Execution context adds
cancellation checks and private output staging, not replacement forecast methods.

[Huey's documented shutdown behavior](https://huey.readthedocs.io/en/latest/consumer.html)
does not guarantee redelivery of interrupted in-flight tasks. The application
therefore records leases and identifies interrupted work explicitly; a queue alone
is not treated as a guarantee of recovery.

## Operation

`python run.py` starts the API and a separate local Huey worker. The local process
supervisor restarts a stopped worker. Direct Uvicorn startup requires a separate
`python -m app.worker` process using the same workspace/environment.

Calculations run serially by default to avoid exhausting a laptop. Atomic claims
prevent duplicate messages or workers from executing the same job twice. This is
not yet a distributed, authenticated, tenant-aware deployment.

- `data/jobs.sqlite3`: requests, states, cancellation, ownership and result references.
- `data/queue.sqlite3`: Huey's queue.
- `.forecast-work/<job>/<attempt>/`: unpublished outputs, excluded from source control
  and inaccessible through forecast list/export routes.
- `runs/<run>/`: complete results, published using an atomic directory rename.

Heartbeats update every five seconds. After 120 seconds without a job heartbeat,
unfinished work becomes **Interrupted**, or **Cancelled** if a stop was requested.
A stale attempt cannot publish afterward. Queued jobs are redispatched on startup;
duplicate delivery is harmless. If a crash occurs just after saving a result,
recovery verifies embedded job/attempt identifiers before marking it ready.

API callers must reuse their `request_id` after an ambiguous submission response;
the same identifier with different inputs is rejected. The browser does this too.

Use SQLite's backup mechanism, or stop both processes before copying their state.
A live copy of the main database alone may omit WAL transactions. Automated
backup/restore, staging-file retention, authenticated visibility, deployment
migrations and broader concurrent-user/load testing remain open work.

## Evidence

Seven isolated regression tests cover idempotency, persisted queue state,
two-worker claim races, queued/running cancellation, failed-job isolation,
lost-lease rejection, recovery after result save but before ledger commit, and API
submission/cancellation/retry/health.

Live canceled job `be88538c8ee04cdb9b66fc852b61a156` produced no result. Retry
`c11aa6c4a390424883686177d7783e4c` survived browser reload and produced run
`619dfd528e3d`. Synthetic separate-confirmation WAPE remained 5.6587%. This is not
client accuracy evidence.

Live worker interruption: `e9e5b49381e54d2aa6e1ac29cec96d63` was confirmed running
when its worker received SIGTERM. The supervisor restarted the worker; after the
120-second lease expired the UI showed **Interrupted — retry when ready**, with no
published run. This was checked on the 390px layout. An earlier interruption probe
finished before the stop arrived and correctly remained Ready; it is not counted
as interrupted-work evidence.

Retry `35cb2fe436264184a3cc9e2484dd4c13` then completed normally as forecast
`b2e0a2e9e080`. The interrupted attempt remains unchanged in the ledger.

## Restart correction, 21 September

The routing sample exposed orphaned consumers left by previous app shutdowns.
They could claim new jobs using old in-memory application code. Confirmed workers
from this project were stopped; no source files or saved forecasts were deleted.
`run.py` now supplies its PID to the owned worker. The worker checks that it still
has that parent and terminates if the app disappears, including shutdowns that
bypass Python cleanup. Standalone workers remain supported without that option.

Live verification: app PID 82468 and its worker 82469 were the only active pair.
After terminating the idle app, both PIDs disappeared without separately stopping
the worker. The app was then restored with one owned consumer. A regression test
covers owned-parent loss and standalone mode. This does not replace distributed
deployment or long-duration recovery testing.

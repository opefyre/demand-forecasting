# Private cloud runtime — 10 October 2026

This milestone is the permissions/storage/compute backbone, **not a cloud UI launch**.
The public domain still returns 503. No owner bootstrap, public login/API, client
data transfer, live connector request or OpenAI call was performed. The local demo
is independent and unchanged.

## Permissions

The maintained Better Auth native D1 adapter and shared four-role catalogue are
reused. Private operations cover identity, policy, personal/company keys,
rotation/revocation, invitations, membership changes, audit and background grants.
Administrator operations are serialized in a native Durable Object; identity is
checked inside that lock, including session-specific fresh MFA. Last-admin
protection is tested under competing requests. Company keys cannot exceed their
role or act as access administrators. Queued work rechecks live membership,
session/key expiry and revocation before starting. Saved grants contain IDs, not
cookies or raw keys. Registration remains denied, including for the owner.

## Durable company state

Native Durable Object SQLite owns the job and revision ledger. Existing verified
backup code and SQLite's online backup API create company-only checkpoints,
including live WAL data. Private R2 files and backup buckets hold immutable
checkpoints; both writes must finish before the ledger acknowledges a revision.
Only the exact company prefix is restored. Size limits, checksums, SQLite integrity,
path/symlink checks and restrictive permissions are enforced.

Connector/source/notification credentials use the maintained cryptography AES-GCM
implementation, bound to company, purpose and identifier. Only ciphertext is
checkpointed. The dedicated encryption key stays in an ignored private local
file and private engine/storage Worker secrets; storage now seals queued credential
bodies before R2 writes. It is injected at container startup, never baked into
the image. Existing macOS Keychain behavior remains unchanged for the local app.

Requests are repeat-safe per company. Accepted jobs survive runtime recreation;
canceled or expired attempts cannot publish outputs. Checkpoint head and job
success commit together. Interrupted calculations fail with a review/retry state,
not automatic expensive replay. Saved artifacts are served directly from R2 with
role checks and do not wake the engine. Drafts are not exposed to Viewer keys.

## Sleeping engine

Official native Cloudflare container APIs are reused. Fixed singleton routing,
no warm pool, no public URL, no inbound host mapping and no internet from the
container. Initial bounded profile: 0.25 CPU, 1 GiB RAM, 4 GB scratch disk. A
five-minute inactivity timeout is set on startup/reattachment; a twelve-minute
deadline alarm stops stuck work. Completed jobs remove their deadline alarm and
scratch outputs. No health ping or scheduler runs inside the container.

The image contains code and pinned, tested Linux dependencies, not credentials,
client spreadsheets, demo records, tests or local databases. Non-root Python
reuses the existing models, reviewed saved configuration and order/demand engine.
No substitute Worker math or AI calculation is introduced.

Native Durable Object scheduling is currently Cloudflare's beta policy. It does
not accept a configured `max_instances`; the application routes only to one fixed
engine ID. This is **not an account-wide spending cap**. The selected small profile
passes the bounded synthetic pilot, not every possible production workload.

## Verification

- Shared identity tests: 19 passed, three optional checks skipped; the two native
  suites below are run separately rather than claimed from those skips.
- Built native identity Worker: two checks passed with actual D1/DO runtime,
  company isolation, keys, MFA, revocation and competing admin changes.
- Native storage runtime: two checks passed with actual SQLite/R2, queued and
  completed state across restart, cancellation fencing, authorization changes,
  request deduplication and reads without an engine call. Its calculation provider
  is an explicit test fake, not a claimed cloud mathematical acceptance.
- Engine lifecycle/configuration: ten Node checks passed, including no cold-read
  start, five-minute policy, bounded alarm, busy protection, startup/calculation/
  backup/truncated-stream failure and closed resource configuration.
- Python company/deployment regression: 39 checks passed. Existing deprecation
  and database-resource warnings remain.
- Same three cloud checkpoint/calculation tests passed in Linux, non-root,
  offline, 1 GiB/0.25 CPU Docker container. Four customers, 36 months, partial
  fulfilled orders and two existing methods; both results survived fresh scratch
  restores. Calculated demand/order totals reconciled. This is synthetic evidence,
  not client-accuracy evidence or a measured Cloudflare idle/wake result.
- Identity type/schema checks passed. Local demo health remains OK.

Repeat checks from `auth-service`: `npm run check`, `npm test`,
`npm run schema:cloudflare:check`, `npm run test:cloudflare-worker`,
`npm run test:cloud-storage`, `npm run test:cloud-engine`.
Native tests use disposable local resources, not production accounts or buckets.
Python: `.venv/bin/python -m unittest tests.test_cloud_compute`.

## Deployment and acceptance

Deployment IDs and remote privacy checks are recorded in
[Cloudflare deployment](CLOUDFLARE_DEPLOYMENT.md). Merely uploading an engine image
does not verify real cold-start latency, actual sleep or billing. Those require a
bounded private remote exercise and observation, never continuous health polling.

## Next substantial build

The private networked workflows and durable schedules are now implemented; see
[cloud workflows](CLOUD_WORKFLOWS_DELIVERY.md). The following wider migration
paragraph records the earlier backbone milestone. Owner-only gateway and actual
remote/browser/provider acceptance are still open.

The next core API slice is now implemented: see
[private company API bridge](CLOUD_API_DELIVERY.md) for its exact supported routes,
checks and limits. The original paragraph below describes the wider still-open
screen/assistant/release/recurring migration, not a claim that the core bridge is
missing or that the whole cloud app is finished.

Bridge the existing company APIs/screens to this durable runtime: customers,
orders, import/review, factors, conversations, grouped forecasts, releases and
saved-result views. Current `stageWorkspace` is a private administrator-only
checkpoint operation, **not the complete user input CRUD or cloud import wizard**.
Port recurring imports/monthly drafts, live factor fetching and notification
delivery to permission-checked work outside the offline mathematical container.
Then run owner-only Google/MFA/mail and two-company browser acceptance plus a
remote forecast/stop/wake/cost exercise. Public access stays closed until an
explicit separate decision. AI eligibility and real provider acceptance remain
separate gates; do not copy existing local keys automatically.

# Private company API bridge — 10 October 2026

This records the original core bridge. The subsequent [approved reports/resource
and screen-adapter slice](CLOUD_REPORTS_DELIVERY.md) supersedes its route counts
and corresponding remaining-work items. This is not the cloud UI launch. The public domain and every
backend HTTP listener remain closed. No real company data, identity account,
provider credential, mail or AI request is created by these checks.

The updated dedicated identity, engine and storage services are deployed. Versions:
identity `c7e61139-1fea-41d0-afc1-a0853bdcd697`, engine
`fe9f65e3-1464-447b-a9fd-37a073123957`, storage
`b962cedf-f8cd-47c0-9c78-10ad32c1e061`. Engine image:
`sha256:fa802040310c6809b9ee6aca2e31a7af87c150750556910e73187fda4ce06d32`.
The public hold was not redeployed. No other services or resources were changed.

## Implemented

The shared [route contract](../app/cloud_api_contract.json) connects 20 company
commands and 19 saved-data reads. It is checked against the existing FastAPI
OpenAPI paths; no second customer/order/forecast implementation is introduced.
Maintained FastAPI, Pydantic, httpx ASGI transport and the existing company stores,
review code and mathematical engine are reused. ASGI startup hooks never run in
the offline engine, so local schedulers and identity services do not start.

- Customer creation, editing, product replacement, archiving and bulk review/import.
- Multipart source upload, sheet preview/selection, dataset mapping/review,
  immutable input creation and forecast settings.
- Versioned order books, order preview/proof and saved order snapshots.
- Factor imports/review and reviewed dataset-factor inputs. This does not fetch
  live providers from the offline engine.
- One forecast group containing all selected methods, using the existing
  partial-order consumption and model code.
- Saved lists/details for customers, sources, datasets, orders, factors, model
  choices, forecast groups, runs and customer/SKU/month demand.

## Request and persistence rules

`ForecastStorage.companyApi(credentials, Request, requestId, expectedRevision)`
is private service-binding RPC, **not a public HTTP route**. GET returns a saved
JSON view directly from R2, with the committed company revision. Supported query
filters are explicit: list pagination/archive inclusion, method frequency/profile,
and demand customer/SKU/month. Unknown query fields fail instead of being ignored.

Writes return HTTP 202 with a durable operation ID, not a premature API success.
The future UI gateway must poll `companyApiResult(credentials, id)` outside the
container. Pending work remains 202; completed work returns the existing API's
actual status/body and its exact revision. A multi-model forecast still returns
one group, not separate unrelated forecast names. The raw response is available
only to the same actor with their current required scopes.

Upload bytes are bounded and stream-hashed using Cloudflare's maintained
[DigestStream](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/),
not buffered twice or logged. IDs, hashes and required scopes are saved, not raw
API keys/cookies. Identical retry IDs/bytes reuse one receipt; changed bytes fail.
Live identity, membership, expiry, revocation and scope intersection are checked
again before execution. A stale revision or overlapping company write is rejected.
The separate company revision guard complements the existing order-book version.

The scratch engine restores only that company, invokes the existing API and
returns a company-only checkpoint plus saved read views. Both R2 checkpoint
copies and output objects must exist before the ledger atomically publishes the
new revision and success. Validation failures preserve their safe 4xx response
but **never promote scratch changes**. Cancellation/deadline fences still apply.
Neither results polling nor saved reads wakes the container. Direct artifact
access cannot bypass the API response/view permissions.

## Deliberate limits / remaining work

- The existing local UI has not been switched to this asynchronous private RPC
  protocol. No public API, owner bootstrap, login callback or preview is opened.
- Conversations, assistant actions, releases/Viewer-only approved reports,
  personalized views, settings/units, lifecycle revision actions and filtered
  binary exports still need their cloud bridge. Draft reads are never substituted
  for approved Viewer reports; unsupported routes explicitly fail closed.
- Source-file operations currently conservatively require all input-category
  scopes because file roles can differ. Native per-file role filtering for narrow
  keys remains; the original API also validates the actual file role.
- Read views are snapshots of a committed revision, not live provider refreshes.
  Existing expiry/review guards still run before orders/forecasts are accepted.
- Request bodies are limited to 51 MiB including multipart overhead (existing
  file API remains 50 MiB); checkpoints to 64 MiB compressed/256 MiB expanded;
  read views to 12 MiB and each primary collection to 5,000 records. Exceeding a
  limit fails without silently dropping rows. This is a bounded initial deployment,
  not a claim of unlimited scale. Projection generation currently rebuilds the
  company's supported read views per successful command.
- Immutable request-body retention/orphan cleanup needs a scoped policy before
  production. No broad bucket deletion/expiration is installed by this milestone.
- Recurring imports, live factors, notification delivery and networked assistant
  work must execute outside the offline numerical container.
- Real remote wake/sleep, actual cost, Google/mail and owner-only browser journeys
  remain acceptance gates. Uploading an image is not measured remote acceptance.

## Verification

57 focused Python company/workflow/deployment tests passed, including four new
cloud API checks. Those exercise four customers across fresh scratch restores,
edit/archive and invalid/unauthorized writes; actual multipart upload, mapping,
versioned order book and reviewed snapshot; and two real methods under one
forecast with four customers and partial fulfilled orders. Current demand remains
49 tonnes, with no duplicated confirmed-order contribution.

Native storage checks use actual disposable workerd SQLite/R2 and explicit fake
identity/compute services. They cover first empty-company writes, replay/conflict,
same-actor response protection, company/Viewer denial, persisted reads across
restart without a compute call, invalid writes preserving the revision, and no
projection exposure through forecast artifact routes. Native D1 identity checks
also cover queued non-forecast scope grants and malformed/empty scope denial.
Twelve engine lifecycle checks pass, including durable API success and 4xx
responses without checkpoint promotion. Shared auth: 19 passed/three optional
skips; native identity/storage suites run separately, two checks each. Type/schema
checks pass. The unchanged local demo's `/api/health` reports OK.

The same seven cloud API/checkpoint tests also passed in the Linux amd64 image,
non-root user 10001, no network or private mounts, 1 GiB RAM and 0.25 CPU. The
complete local suite took 428 seconds. This is a synthetic bounded-workload test,
not a measurement of Cloudflare cold start, idle shutdown or production accuracy.

Repeat: `.venv/bin/python -m unittest tests.test_cloud_api tests.test_cloud_compute`;
from `auth-service`, `npm run check`, `npm test`, `npm run test:cloudflare-worker`,
`npm run test:cloud-storage`, `npm run test:cloud-engine` and
`npm run schema:cloudflare:check`. Local native tests require loopback access.

## Next substantial chunk

Finish approved-report/export and remaining resource bridges, then connect the
existing screens to asynchronous operations without adding UI clutter. Afterward
port assistant/live-source/recurring work and perform the owner-only cloud journey
and measured wake/sleep test. Keep the local demo independent and public access
closed throughout.

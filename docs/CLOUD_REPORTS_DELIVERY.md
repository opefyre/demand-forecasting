# Private reports and resource bridge — 10 October 2026

Follow-up: the networked/recurring orchestration described as remaining below is
now implemented in [cloud workflows](CLOUD_WORKFLOWS_DELIVERY.md). This file records
the earlier reports milestone; current deployment IDs are in CLOUDFLARE_DEPLOYMENT.md.

This extends the existing company API; it is not a public application launch.
The local demo stays independent. No other cloud services, real company data,
identity accounts, provider connections, AI requests or mail are changed.

Deployed private versions: identity `f7ec875f-fb1f-45e4-86d6-de56fbd2e308`,
storage `fc20db3f-5240-4698-aa46-09371cdac76b`, engine
`2619d520-6ed9-47c4-91e8-ee9723c4e224`. Engine image:
`sha256:e9bbb6ca643ab8111806a1a61f1c58683174f497b9bfa326004113c2c03b4f9c`.
The public edge was not redeployed. Temporary registry credentials were removed;
the two disposable test containers were removed and the dedicated build VM stopped.

## Delivered scope

The shared route contract now covers **108 operations: 47 commands and 61 reads**.
All are checked against the existing FastAPI OpenAPI routes. Existing maintained
FastAPI, httpx, Pydantic, SQLite, export libraries and company stores are reused.

- Release preview, submission, independent approval, approved-report lists/details.
- Approved-only Viewer report projections generated through the original report
  access gates, never by handing over draft data and hiding it in the browser.
- CSV, Excel and JSON planning exports; customer/SKU/month filters on existing
  draft/snapshot exports; model packages, import templates and actual-result CSV.
- Input/forecast naming, archive/restore and revision navigation.
- Company site settings, unit versions, customer factor profiles, order review
  after calculation and actual-result review/evaluation resources.
- Personal saved-view CRUD and saved-chat list/detail/history, rename, archive,
  restore/trash/pin operations and text export through the original journal.
  These records never enter shared company projections. Company integration keys
  cannot read personal conversations or views. New AI execution is not included.

## Persistence and access

All commands still use the private durable operation bridge, current identity,
scope intersection, company/revision fencing and immutable company checkpoints.
Queued actions now use the **live role**, not the role saved when they were queued.
Completed receipts require the same actor, unchanged role and current scopes.
Read receipts are rejected if the company revision has since changed.

Exports invoke the original export code in offline scratch space with the actual
caller. They recheck report approval, latest reviewed orders, expiry, receiving
policy, exact source hashes and filters. The private result returns the actual
binary bytes, filename and content type, not a JSON/base64 download wrapper.
An export creates **no business revision or checkpoint backup**. A changed company
revision or different report-check day blocks reuse of an old download receipt.

Same-day report reads use R2 and do not wake computation. After a day changes in
the company's timezone, a report read performs a bounded read-only refresh through
the original API. Its saved projection can replace the old read view without
changing the business revision. Ordinary empty collections remain empty; an empty
company workspace is resolved through the same existing workspace API, not fake
frontend defaults. Personal reads and export preparation are explicit queued work;
they can wake the sleeping engine. No idle/background polling was added.

## Screen connection

The existing screens now have one shared opt-in cloud transport. A future
authenticated private gateway must advertise `transport: 'cloud'` alongside the
existing `mode: 'better_auth'` and validated user/company identity.

The transport obtains the company revision, sends one stable outer request ID,
polls the saved operation and returns the original API status/body to the screen.
A completed business HTTP 202 is not mistaken for another queued cloud job.
Lost writes are **never automatically replayed**; company/user/role changes stop
in-flight polling. Existing download links use the same transport and retain
attachment bytes/filenames. Local and conventional company-server modes are unchanged.
No new page, modal, style, setting or status banner was added.

`screen-gateway.mjs` is a private adapter, not an HTTP listener. It handles revision
and operation polling, bounds browser bodies whose Content-Length is absent, and
requires origin plus upstream session/CSRF validation for signed-in changes.
Caller-supplied company/role headers never select a company. It is deliberately
**not bound to the public edge**, which remains closed. No cloud browser sign-in
journey has been verified by these component/transport tests.

## Verification and remaining gates

66 focused backend checks, all 268 interface checks/build, 20 cloud controller/
transport/gateway checks and type/schema checks pass. Shared auth: 19 passed and
three optional skips; native identity and storage suites separately pass two
checks each. The local demo health is OK and the public domain still returns 503.
Five Linux checks pass offline, non-root, 1 GiB RAM and 0.25 CPU: three report/
contract/settings tests in 245 seconds and two latest-contract/chat privacy tests
in 84 seconds. These are local emulated runtime checks, not remote cost evidence.
Synthetic checks use four customers, 36 months of history, partial fulfilled
orders, real existing model calculations, independent approval, three approved
export formats and cold checkpoint restores. Native disposable workerd tests
exercise actual SQLite/R2 but explicitly fake identity/compute responses; they
are not real cloud calculations or client forecast-accuracy evidence.

Repeat backend: `.venv/bin/python -m unittest tests.test_cloud_api
tests.test_cloud_compute tests.test_platform_sales tests.test_company_context
tests.test_resource_lifecycle tests.test_demand_releases`. Interface:
`node --test frontend/src/*.test.mjs`; cloud adapters:
`node --test deploy/cloudflare/company-api.test.mjs
deploy/cloudflare/engine-lifecycle.test.mjs`. Native checks use the existing
auth-service `test:cloud-storage` and `test:cloudflare-worker` scripts.

Remaining cloud work is not marked complete: networked assistant execution,
advanced scenario/monthly actions, live-source/ERP fetches, recurring schedules,
notification delivery and remaining connection/admin routes need their cloud
orchestration. The offline engine must not be given Internet access to bypass
that work. Some source routes deliberately require all category scopes until
native per-file filtering is finished. Existing bounded size/record limits and
scoped orphan/body retention work in CLOUD_API_DELIVERY.md still apply.

Next: wire an owner-only authenticated UI gateway and verify Google/mail, browser
roles and actual remote wake/sleep. No public access is opened automatically.

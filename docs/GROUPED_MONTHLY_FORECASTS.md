# One monthly forecast workflow — 10 October 2026

New monthly updates and newly configured schedules now reuse New forecast:
sales history → factors → customers/orders → selected methods → grouped results.
They no longer calculate a provisional baseline before reviewing current orders.

## Delivered

- One editable name and one forecast group for all selected methods. The existing
  dashboard, method comparison, revision navigation and demand exports are reused.
- Included factors show their names/providers; recorded future assumptions remain
  available in a disclosure. No extra provider fetch or invented future values.
- Shared method controls, Page/Panel/Stack/Grid/Actions and fixed scrollable Modal.
  No CSS, inline appearance or new design tokens were added.
- Draft and history-import storage are isolated by company, user and update ID.
  Reload restores completed methods; retry chains resolve to the latest attempt.
- Exact current order-review validation, stale-tab detection, immutable input
  checks, supported-model validation and original-result preservation remain in force.
- Default names use site-local dates and revision suffixes rather than accumulating
  repeated dates. Older local results without a durable group receipt retain their
  original run reference and can start a new reviewed group.
- Unchanged wizard settings skip a redundant cloud write/checkpoint.

## Schedules and compatibility

Newly configured schedules prepare reviewed sales plus the selected methods.
The user then checks current factors/orders and starts the calculation. They do
**not** silently calculate against last month's orders or auto-approve exports.

Existing saved updates/schedules remain readable and keep their previous behavior.
The API defaults to that legacy contract; callers opt into `workflow: "grouped"`.
Editing/confirming schedule settings explicitly adopts the new workflow. An
existing legacy cycle is not overwritten during a same-month workflow change.

## Executed verification

- 59 focused backend tests passed; 36 passed again after naming changes. The final
  local-legacy compatibility/retry slice passed 14 tests.
- 304 interface tests, 53 Cloudflare service tests and production build passed.
- Offline Linux checks use 0.25 CPU, 1 GiB RAM, no network and fictional data.
  Four customers, two products, corrected history, partial/no orders and two
  factor-aware methods exercise cold checkpoints and exact request retries.
  All six checks passed in the exact final uploaded image (126.694 seconds).
- Browser: two methods completed under one name; reloading restored the result.
  Administrator schedule save/check opened the same wizard without starting jobs.
- Desktop 1512×736: 24px panel padding, 18px headings, 40px action buttons,
  44px inputs, 960×680 fixed schedule dialog with internal scrolling.
- Mobile 390×844, English and Farsi: 358×680 dialog, single-column fields,
  44px inputs, internal scrolling, no document overflow; RTL verified.
  Screenshot: `screenshots/grouped-monthly-schedule-fa-mobile.png` (ignored locally).
- Private cloud: “Tehran · Monthly multi-method review” completed with reviewed
  saved orders, retained GSCPI/Brent factors and explicit future assumptions.
  Ridge and Elastic Net results were 4,070.6 and 4,030.2 tonnes respectively.
  The original forecast remains a separate revision; no provider refresh occurred.
  Order review was noticeably slow during deployment; end-to-end cloud latency
  was not measured, so this is functional acceptance, not a performance claim.
  Screenshot: `screenshots/cloud-grouped-monthly-result.png` (ignored locally).
  View forecast then Compare methods opened both monthly curves and the shared
  comparison table under that same name. Screenshot:
  `screenshots/cloud-grouped-monthly-comparison.png` (ignored locally).

## Deployment

- Edge: `fe21e437-a698-46ae-93aa-94024d2a8cc0`.
- Engine: `66b31740-3787-4a83-88b5-379630b8f1f7`.
- Image: `sha256:40ecb853943ea3015b10b2fc519fac9e4651fdb9d760a698521734984a830dcb`.
- Owner-only access, MFA and five-minute idle shutdown remain unchanged.
  Local `/demand` responds with 200. No other Cloudflare services were modified.
  Temporary registry login was removed and the dedicated build VM stopped.
  The disposable UI fixture was stopped; the independent local demo stays running.

These are workflow/quantity checks, not proof of real-client forecasting accuracy.
No AI calls, new source subscriptions, invitations or permission changes occurred.
The existing large frontend bundle and test deprecation/resource warnings remain.

## Next substantial task

Bring the assistant's older order-reuse proposals, order-comparison and revision
screens onto these same shared components and reviewed grouped workflow. Verify
the entire bilingual mobile journey through result comparison, approval and export.
Include distinguishable comparison colours and measured cloud review latency in
that acceptance pass; this delivery does not close those remaining UX concerns.
AI-provider eligibility, client data/source permissions, accuracy testing and an
authorized multi-person pilot remain separate release gates.

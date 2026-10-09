# Input and forecast lifecycle

Implemented in company mode. The existing local demo remains in its current mode.

## Delivered

- One shared menu for input datasets and forecasts: rename, archive/restore,
  versions, and (for grouped forecasts) create revision in the existing wizard.
- Uploaded source names/status are managed from input version details.
- Archived items are hidden from default lists and new-forecast input choices;
  an explicit Show archived control makes them recoverable.
- Each selected method belongs to one forecast name and archive state.
- Input revisions show their recorded parents and branches, with dates and
  direct opening. Unrelated inputs are not presented as revisions.
- Forecast revisions use an explicit parent forecast identifier. Monthly/scenario
  results also navigate back through their recorded baseline, including a grouped
  baseline. Existing independent runs are not retroactively linked by guesswork.
- Saved-order choices distinguish forecast name, method and review date.
- Shared Radix menus/dialogs, existing global layout/styles and English/Persian
  translations. No inline styles, new page stylesheet or design tokens were added.

## Evidence and access

Names and archive state live in a separate, company-owned SQLite metadata store.
Source bytes, dataset JSON, model results, quantities, request fingerprints and
approval/export evidence are not rewritten. Direct reads/approved exports remain
available after archiving; archive is not deletion or approval revocation.

Edits require the appropriate input/customer/order/factor/forecast write scope.
Optimistic versions reject stale edits; concurrent edits have one winner. Viewers
can read metadata only for approved reports, not draft revision names or IDs.
Grouped result IDs resolve to the same forecast metadata record.

Archived inputs cannot start a new forecast. The worker checks again before
calculating, including scheduled jobs and archived grouped forecasts. Active
queued/running forecast groups cannot be archived until they finish.

## Public API

For `sources`, `datasets`, `forecasts` and `runs`:

- `GET /api/v1/{kind}/{id}/metadata`
- `PATCH /api/v1/{kind}/{id}/metadata` — name and expected metadata version
- `POST /api/v1/{kind}/{id}/archive` — expected metadata version
- `POST /api/v1/{kind}/{id}/restore` — expected metadata version
- `GET /api/v1/{kind}/{id}/revisions`

Source uploads are immutable captures; their revision route returns the capture,
not an invented replacement chain. Dataset revisions record changed source IDs.
List endpoints accept `include_archived=true`. Forecast creation optionally takes
`parent_forecast_id`; it must belong to the current company and be finished.

## Verification

Synthetic fixtures only; no paid AI calls or real provider accounts were used.
Browser checks exercised input rename/archive/restore, a forecast revision using
saved orders and a real mathematical model, opening its original result, forecast
archive/restore, Persian controls and a 390px dialog without page overflow.
Focused backend checks cover separation, permissions, stale/concurrent edits,
immutable evidence, worker rejection, grouped aliases and approved-viewer access.

Full backend: 794 checks, 793 passed and one optional integration skipped.
After the final retry-job safeguard, all 39 focused lifecycle/sales/job/API checks
passed. All 260 interface checks and the production build passed. A second
company retained its original names and results during the browser walkthrough.

## Next

Admin-managed outbound notifications, explicit consent and delivery history.
Then deployment credentials, real provider-account verification, backup/restore
and role-based acceptance before activating company mode.

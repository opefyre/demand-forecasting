# Iran monthly inflation and regional shipping — 3 October 2026

## Delivered

The existing httpx/pandas/FactorStore, scheduler, factor scenarios and Recharts
are reused. No new modelling framework, paid subscription or client-data transfer.

- **Hormuz ship traffic is connected**, with six-hour automatic checks, pause,
  retained versions, safe failure/cooldown and stale-source warnings.
- **Official IMF monthly Iran CPI connector is implemented but disabled** until
  the administrator records permission covering automated commercial reuse.
  Permission is an administrator declaration, not a grant issued by this app.
- Both adapters can feed the existing reviewed what-if workflow using a selected
  factor-aware model, explicit lag/scope and future assumptions. Missing history
  blocks saving; neither adapter overwrites forecasts or booked orders.
- Data → Factors prioritizes Iran FX/monthly CPI and relevant monthly/regional
  sources. Annual inflation/industry move into a collapsed background section.
  Source details have bounded interactive charts; missing dates stay gaps.

## Source selection and research evidence

| Source | Finding on 3 October | Decision |
| --- | --- | --- |
| [Official IMF CPI](https://data.imf.org/Datasets/CPI) | Current SDMX 2.1 flow `IMF.STA:CPI(5.0.0)`; exact monthly Iran all-items index key `IRN.CPI._T.IX.M`. A bounded 2026 research sample returned seven observations, January–July, latest index 676.9, base 2021=100. | Prefer this official feed over a stale mirror. Adapter requests only this series, 2010 through the last completed month; full historical production capture is NOT yet verified. |
| [IMF API guidance](https://data.imf.org/en/Resource-Pages/IMF-API), [terms](https://www.imf.org/en/About/copyright-and-terms.) | Research metadata and bounded data sample responded without an account/key. Current terms ask for permission for potential commercial reuse and restrict bulk downloading/LLM training. | No repeated commercial fetch until permission recorded. A free account is not a substitute for permission. No proxy, mirror fallback or bypass. |
| [DBnomics IMF CPI mirror](https://db.nomics.world/IMF/CPI/M.IR.PCPI_IX) | Live endpoint worked, but series ended May 2025; dataset update August 2025. | Do not present this as current Iran inflation. |
| [CBI inflation](https://www.cbi.ir/Inflation/Inflation_FA.aspx) | Current monthly-ending inflation rates are readable; these are not monthly CPI index levels. Automated commercial reuse could not be established; legal page timed out. | Keep local candidate, not an unverified scraper. |
| [SCI](https://amar.org.ir/) | Read attempt returned 502; current API/access/reuse not established. | A failed request is not evidence that SCI is permanently unavailable. No connected claim. |
| [IMF PortWatch](https://portwatch.imf.org/), official ArcGIS item `3da2b9ca97684916b75c4013f95d18ab` | Official chokepoint data exist, including longer Hormuz history. The item links IMF terms. | Better long-history candidate after commercial permission; not silently enabled. |
| [hormuz.now API and licence](https://hormuz.now/data), [method](https://hormuz.now/methodology) | Provider-owned crossing counts explicitly allow commercial use under CC BY 4.0. Endpoint bundles IMF columns under separate rights. Own history starts April 2026; legacy/mixed tracking is reconstructed and AIS misses ships. | Connect only provider-owned counts. Discard IMF values, calibrated averages, baselines and political-status labels. Not equivalent to official PortWatch or customs cargo data. |

These are engineering suitability findings, not legal advice or an accuracy claim.
The source contract rejects changed CPI base/scale/measure/country/schema instead
of silently converting them. Version 5.0.0 is pinned; a major provider version
change requires reviewed adapter maintenance.

## Real connected shipping capture

The app fetched 167 provider rows. The current partial UTC day was excluded:
**166 complete days, 20 April–2 October 2026**, with five complete Gregorian
months (May–September). April and October are incomplete. Most historical days
are reconstructed; September includes 29 reconstructed/mixed days. The live
capture is not a stable-method multi-year series.

Monthly feature = mean own-provider crossings across every complete UTC day in
the month. All calendar days are required. Missing days are not zero demand or
filled; no partial monthly totals are compared with complete months. This is a
regional shipping proxy, not tonnes, confirmed cargo, Tehran plant availability,
war probability or customer demand. Relevant route exposure must be reviewed.

Only selected provider-owned fields are retained. Their immutable projection has
a SHA-256; the full upstream response hash is separately recorded, but its bundled
IMF fields are discarded, not stored or exported. Re-parsing the retained projection
validates numerical values, counting definition, dates, units and tracking flags.
Stored monthly summaries cannot override recomputed inputs.

## Forecast-use rules

- First local capture time is not the historical publication date.
- Both feeds remain context by default; explicit reviewed sensitivity use is
  required. Unsupported historical accuracy/ranges are withheld.
- IMF index levels are not month-on-month or year-on-year inflation rates, and
  inflation percentages are not percentage changes in physical sales.
- Completed Gregorian source months are lagged; Persian sales months use the
  existing last-complete-Gregorian-month policy, not renamed/split averages.
- Current source values captured after a forecast cutoff cannot become future
  observations retrospectively. Future unknowns require named assumptions.
- Five shipping months cannot cover the existing 36-month demo. Preview reports
  missing history; saving such a linked scenario is blocked rather than filled.
- Confirmed customer/SKU/month orders retain their existing consumption rules.

## Permission handoff

Data → Factors → Iran monthly price index → Review access links current terms
and the IMF copyright contact. Obtain permission covering systematic automated
retrieval, commercial forecasting/derivatives and intended output sharing. Record
the permission email/agreement reference, then explicitly Connect. Recording alone
does not enable refresh. Withdraw permission pauses and blocks new requests.
No permission, account acceptance or message was submitted on the user's behalf.

## Verification

- 12 new backend tests: exact source identity, scale/base/units, finite values,
  duplicate/future dates, count reconciliation, partial/missing days, changed
  definitions/licence, stale update, integrity, permission persistence/revocation,
  no unauthorized provider call, and reviewed CPI linking on synthetic sales.
- 501 backend tests, 77 frontend tests and production build pass. Existing large
  bundle/font-path and legacy library warnings remain.
- Real shipping connection checked in the UI; 1280px and 390px details/access
  modals fit the viewport. Mobile chart 320px; modal 360px; page 390px, no horizontal
  overflow. Annual background is collapsed; duplicate access/details action removed.
- Existing synthetic run `df87c7ec00ae` independently rechecked: ten Persian
  months, two customer/SKU combinations, unchanged original orders and six
  reconciled CSV/Excel/JSON exports. No OpenAI call was made this checkpoint.

## Next substantial build

Assistant-led first order-file import and factor-scenario workflow: inspect the
user's request, guide the existing mapping/review services, propose a bounded
scenario, confirm calculation, reconcile partial orders and open the filtered
customer/SKU/month dashboard/export. Reuse existing services; do not introduce
a second import wizard or task-type picker. Include failure/ambiguity recovery.

Still open: IMF commercial permission/live full-history capture, permitted longer
regional trade history, scheduled weather, client evidence/accuracy and whole-route
operational acceptance. This checkpoint is not whole-product completion.

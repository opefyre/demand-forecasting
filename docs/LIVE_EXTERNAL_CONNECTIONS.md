# Live external connections — 3 October 2026

## Latest — reviewed live-factor scenarios delivered

- Forecast → Scenarios → Add forecast factors now offers the 15 live monthly
  commodity series and Iranian USD/rial reference quotes. Uses existing sklearn
  methods and the existing saved-input/job/order/export workflows, not a new engine.
- New live sources require explicit what-if acknowledgment and a single selected
  factor-aware method. Downloaded/revised past observations are NOT historical
  accuracy evidence. Automatic best-model selection, accuracy scores and empirical
  ranges are withheld from this mode before any result/export is written.
- Exact retained-file hashes/units/observations checked. Source snapshots stay
  immutable. Missing history, missing future assumptions and invalid price values
  block calculation. Future observed values must have been captured before the
  forecast starts at Tehran midnight, including UTC offset.
- FX monthly mean uses each observed Tehran day's last quote, giving each day one
  vote. Complete Gregorian months require at least 80% observed calendar days — an
  explicit app guardrail, not a provider guarantee. No gap filling. Current real
  capture produces 22 admitted months; September 2025 and April 2026 fail coverage.
  Factory settlement/open-market basis remains unverified.
- Persian plans retain true planning boundaries. Source Gregorian monthly averages
  use the last complete source month at the planning lag cutoff, not fabricated
  Persian averages. Review inputs, comparison charts and order-comparison tables
  now consistently display Persian planning labels.
- Original sales, orders and baseline forecasts stay unchanged. Scoped scenarios
  retain unselected series. Demand CSV/Excel/JSON exports explicitly identify
  `what_if_unvalidated` forecasts; no double-counting of confirmed orders.
- Synthetic local demo `d5fc4a311a66` compares live aluminum history plus an explicit
  $2,500/tonne future assumption against Persian baseline `422d36f6e1d2`. Two
  customers, ten months; separate order draft `38c9f2dec8d36179c70121f9107c0ad3`.
  Methods differ (weighted recent average vs Ridge); the change is NOT attributed
  solely to aluminum and is NOT evidence of client accuracy.
- 478 backend tests, 69 frontend tests and production build pass. Tests include
  source tampering, FX day weighting/coverage, absent history, acknowledgment,
  model restrictions, Tehran capture cutoff, Persian alignment, suppressed scores
  and ranges in actual workbook/CSV outputs, scoped preservation, and mixed orders.
  Desktop/390px centered modal and comparison checks completed. No paid AI call or
  client-data transmission. Existing build-size/deprecation/resource warnings remain.

Remaining major work: permission-cleared monthly Iranian CPI and regional
shipping/trade feeds; factory FX basis confirmation and additional reliable history;
publication-time or prospective factor-benefit validation and real-client accuracy
acceptance. Annual inflation remains background only.

User authorized live connections and account-page handoff. This supersedes earlier
notes deferring integrations. Sales/demand remains the sole product scope.

## Working and verified on this computer

- World Bank monthly commodity prices: direct automated download from the official
  commodity-markets page. Fifteen energy, metal and agricultural price series,
  with exact source units. Latest observed month September 2026; Brent/aluminum
  each contain 801 observations. Reference prices, not Iranian factory input prices.
- New York Fed GSCPI: latest observed month August 2026, 348 observations. Existing
  explicitly reviewed vintage-link workflow remains available for scenarios.
- World Bank Iran annual inflation: completed-year API range fixed and fetched.
  This is national annual background context, NOT a monthly/live Iranian CPI feed.
- Automatic daily public supply/commodity checks and weekly annual-indicator
  checks enabled. Only while the local server runs; schedules resume on restart.

## Account handoff / limitations

- Servix free-account signup opened in Chrome. User creates/verifies their account.
  In the local app: Data → Factors → Iran exchange rate → Connect. Paste the API
  key there, not in chat. Verify/save validates the USD_RLS catalog with Servix
  before using macOS Keychain via the existing open-source `keyring` package.
- Follow-up completed: user created the account and supplied
  `secrets/servix-api.txt`. Catalog verification succeeded, actual macOS Keychain
  write/read succeeded, and authenticated history fetched 666 quote observations
  from 3 October 2024 through 3 October 2026. Automatic refresh is enabled. This
  does not establish complete day coverage or the correct factory settlement basis.
- API key travels only in the server-to-Servix X-API-Key header; never URL query,
  SQLite, project files, browser storage, response body or AI. Local credential
  request parsing does not echo invalid input. Admin-only source mutations behind
  existing role/origin controls. Non-local plaintext HTTP key setup blocked.
- FX uses rials per USD, not toman. Retains individual timestamped reference
  quotes; no manufactured daily/monthly values or assumed full history coverage.
  Initial bootstrap bounded to 24 months and 31-day requests. Incremental fetches
  overlap previous quote watermark by seven days, capped at 24 months. Durable
  40-request/day app limit leaves headroom within the advertised free 50/day plan;
  other uses of the same account can exhaust it sooner. 429 stops fetching.
- Iran industry-growth endpoint still fails in live checks. Error/cooldown visible;
  no fabricated substitute. Remains scheduled; the last good capture is retained.
- SCI/CBI monthly CPI, verified Iranian business FX basis, regional shipping/trade
  and weather scheduling are NOT completed connections. Do not call them live.

## Forecast safety and user journey

Data → Factors starts with live connections; details/observations are centered
modals. Weather-by-location and old factor-file workflows remain secondary and
collapsed. Existing saved data and forecasts are preserved.

Refreshes retain raw responses, hashes, units, dates and separate saved versions.
Public capture dates are not original historical publication dates. Commodity and
FX observations enter only the explicitly reviewed what-if workflow described
above; annual macro observations remain context-only. They do NOT silently enter
old historical accuracy claims or forecasts. Supply-pressure scenario linking retains its existing
explicit conservative vintage-month timing policy; exact release dates unverified.

Background fetches report checking/completion/failure without locking navigation.
Pause/resume and duplicate-click guards; safe provider error messages, bounded
downloads/decompression, fixed HTTPS hosts, no redirects or environment proxies
for these feeds, cooldowns, daily limits, and interrupted-refresh recovery.
Source observation age and fetch age are separate; a successful HTTP response is
not proof of up-to-date data. No paid call or client-data transmission occurred.

## Verification

New connector/parser/security tests cover units, missing/duplicate months,
publication-time exclusion, raw captures, allowed download host, oversized data,
redirect refusal, credential redaction/storage failure, quotas across restarts,
429 stopping, bootstrap/incremental ranges, pause/resume and background recovery.
Full backend suite and frontend tests/build pass; details recorded in checklist.
Desktop and 390px source-list/key-modal checks performed. All 471 backend tests,
68 frontend tests and the production build pass. Subsequent authenticated Iranian
FX capture verified separately from the mocks.

Private project files now live in the ignored `secrets/` directory (mode 700),
with files mode 600. Existing `.env.local` moved to `secrets/.env.local`; `run.py`
loads that file before starting the server and worker. Existing OpenAI configuration
still reports ready, without an API call. The Servix text file remains there;
runtime access uses the verified Keychain copy. No existing secret was rotated.

## Next substantial build

Complete permission-cleared monthly Iran CPI and regional shipping/trade feeds,
then verify forecast benefit using genuine publication-time history or new actuals.
Keep the reviewed what-if mode separate from validated accuracy; never advertise
historical accuracy using information unavailable at the test date.

Provider references: [World Bank commodities](https://www.worldbank.org/en/research/commodity-markets),
[World Bank API](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures),
[Servix free plan](https://servix.cc/free-api), [Servix terms](https://servix.cc/terms),
[Servix methodology](https://servix.cc/methodology), [Servix endpoints](https://servix.cc/docs/endpoints),
[Keyring](https://keyring.readthedocs.io/en/latest/).

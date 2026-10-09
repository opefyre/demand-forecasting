# Iran and global factor sources

Latest, 3 October: licensed provider-owned Hormuz daily crossings are live;
official IMF monthly Iran CPI connector is implemented behind a commercial-use
permission gate. Bounded official research sample reaches July 2026; the mirror
ends May 2025 and is not substituted. Five complete shipping months contain mostly
reconstructed tracking and cannot cover the 36-month demo. See REGIONAL_LIVE_FACTORS.md
for primary sources, exact limits, tests and current acceptance. Older connection
status notes below are historical.

Latest implementation, 3 October: live World Bank commodities, GSCPI and annual
Iran inflation are connected; Servix Iranian USD/rial history is authenticated
and auto-refreshing. Monthly commodity/FX what-if scenarios now work with reviewed
timing, coverage and future assumptions. No unsupported historical accuracy claim.
Annual inflation stays background-only. See LIVE_EXTERNAL_CONNECTIONS.md; the older
benchmark below is retained as source research, not the current connection status.

3 October update: official CBI inflation and FX pages remain readable. SCI access
could not be verified; Bonbast still directs business use to its API. No approved
free commercial Iranian CPI/FX feed or verified release archive established.
Iran-ready file imports now handle Persian calendar/digits, actual period bounds,
Tehran release timing, rial/toman/quote-quantity normalization and inflation meaning.
See IRAN_FACTOR_INPUTS.md. This does not constitute a live provider connection.

Checked 24 September 2026. Sales/demand forecasting only. Public visibility is not
permission for automated collection, commercial use or AI. This is an engineering
assessment, not legal advice. No paid subscription or provider contact was initiated.

## Source benchmark

| Source / parameter | Coverage / access finding | Decision |
| --- | --- | --- |
| [CBI inflation](https://www.cbi.ir/Inflation/Inflation_FA.aspx) | Iran, monthly-ending and annual rates; Persian calendar. Public page verified; API/reuse not established. | Priority local candidate. Obtain dated releases with permission. Distinguish rolling annual inflation from monthly price change and CPI index levels. |
| [Statistical Centre of Iran](https://www.amar.org.ir/) | Candidate CPI/PPI/regional statistics; website inaccessible to this research tool. Exact current series/API/licence unverified. | Research/import candidate, not connected. Tool access failure does not establish permanent unavailability. |
| [CBI exchange rates](https://www.cbi.ir/exrates/rates_fa.aspx) | Public Iranian currency table; some quotes per 100/1,000 currency units. Stable API/automated reuse not verified. | Client must choose the appropriate market and rate; do not substitute for actual settlement rates. |
| [Bonbast FAQ](https://www.bonbast.com/faq), [terms](https://www.bonbast.com/disclaimer) | Tehran free-market quotes in toman. Commercial use directed to subscribed API; redistribution restricted. | Not a free production connector. Approved contract and explicit buy/sell, rial/toman choices needed. |
| [TGJU terms](https://www.tgju.org/terms) | Iranian FX/gold; copying/use of prices and data restricted. No verified free commercial API. | Do not use a third-party scraper merely because its code is open source. Permission needed. |
| [AlanChand API](https://alanchand.com/media/api) | Iranian FX JSON; paid plans and three-day trial advertised. | Trial is not an ongoing free tier. Optional licensed adapter, not default. |
| [Iran Open Data terms](https://iranopendata.org/en/terms/), [copyright](https://iranopendata.org/en/copyright/) | Iranian historical datasets. Terms restrict Iran-located users and commercial extraction/AI uses. | Exclude from this client's automated pipeline unless eligibility and permissions are resolved. Name does not imply an open licence. |
| [Iran Chamber research centre](https://rc.iccima.ir/) | Candidate monthly Shamakh/PMI. Official endpoint inaccessible here; archive/API/reuse unverified. | Research candidate only; no connected-feed claim. |
| [Tavanir statistics](https://amar.tavanir.org.ir/) | Candidate electricity context; endpoint inaccessible here, no verified free site-outage API. | Prefer client's dated disruption/lost-sale logs. National generation is not actual Tehran plant availability. |
| [World Bank indicators](https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation) | Iran national annual inflation/industry, existing unkeyed connector. | Already implemented as context, not a live monthly feed. Do not present interpolated annual values as observed monthly data. |
| [NASA POWER](https://power.larc.nasa.gov/docs/tutorials/service-data-request/api/) | Free global gridded weather API; Tehran coordinates supported; archives can be revised. | Existing connector. Grid estimates are not factory sensors. Customer location may matter more than factory location. |
| [NY Fed GSCPI](https://www.newyorkfed.org/research/policy/gscpi), [terms](https://www.newyorkfed.org/privacy/termsofuse) | Global monthly supply pressure, not Iran-specific. Public CSV with vintage columns; business/automated use permitted subject to conditions. | New context connector implemented. Attribution retained; no endorsement or automatic sales multiplier. |
| [World Bank Pink Sheet](https://www.worldbank.org/en/research/commodity-markets) | Global monthly commodity/energy prices; public historical downloads. Selected series and third-party rights need review. | Next candidate where relevant to customers/products; not connected in this slice. |
| [GDELT](https://www.gdeltproject.org/data.html) | Public global news-event data/downloads; hosted query compute can cost extra. | Research candidate only. News volume is not verified conflict probability or lost sales. Review coverage/bias, deduplicate and test. |
| [Open-Meteo pricing](https://open-meteo.com/en/pricing) | Free hosted tier is non-commercial; commercial service paid. Self-hosting has separate obligations/costs. | Do not label it a free commercial SaaS feed. Existing NASA adapter avoids duplication. |

## Forecasting rules

- Customer orders and history remain primary. Factor changes must not erase booked orders or count them twice.
- Seasonality comes from repeated history plus calendar effects. Nowruz, holidays, working days, customer shutdowns, promotions and price changes need dates and scope, not a universal multiplier.
- Forecast tonnes separately from money: inflation/FX changing prices does not automatically change physical demand by the same percentage.
- Keep global, Iran-national, provincial, customer and Tehran-site coverage distinct.
- Preserve Jalali/Gregorian boundaries. A Jalali month is not a Gregorian month with another label. Keep original units, period, conversion and publication date.
- FX needs currency pair, market, buy/sell, quote quantity and rial/toman. Use client settlement history where it is the relevant exposure.
- War/disruptions are uncertain: separate observed history from approved future scenarios. No invented future observations or promise to predict conflict.
- Compare with/without a factor on the same historical forecast dates. More factors can reduce accuracy; keep the simpler result when appropriate.
- Recheck provider terms and regional eligibility before deployment; no proxy/access-control workarounds.

## New connector contract and evidence

`global_supply_pressure` reads the fixed CSV used by the NY Fed chart, reusing
httpx, pandas, standard CSV and FactorStore. No new dependency or forecasting model.
No client information is sent. Streaming is limited to 2 MB and redirects rejected.
Schema, dates, vintage order, finite values, future values, duplicates and missing
months are checked. Each successful fetch retains the exact response, SHA-256 and
a separate snapshot. Errors preserve prior versions.

The complete vintage matrix is retained; only the latest column is displayed.
Vintage labels establish a month, not a verified historical publication day.
`available_at` therefore remains actual local capture time; this source is
`context_only` by default. A separately approved public-vintage link now derives
conservative month-end availability without altering this snapshot. See
PUBLIC_FACTOR_COMPARISON.md. These assumed cutoffs are not verified release dates.

The source normally publishes monthly around the fourth business day. Freshness
uses a transparent grace rule: warn when latest observation is more than two
calendar months behind today. API reads recompute this; fetching old data is not
the same as making it fresh.

Live check: 348 months, September 1997–August 2026; September 2026 vintage, 57 vintage
columns. Latest value 1.06 standard deviations. No observations passed an August
2026 cutoff when captured in September. Synthetic parser tests cover failure,
revision selection, provenance and freshness; they are not accuracy benchmarks.

Verification: 327 backend tests and 43 frontend tests pass; production build passes
(existing bundle-size/font-path warnings remain). Browser acceptance fetched and
saved the real series through Data → External context, displayed monthly coverage
and `2026-08 / 1.06` correctly, and showed no horizontal page overflow at 390 px.
Default viewport restored. Local demo restarted at http://127.0.0.1:8010/.
Existing forecasts and orders were not recalculated or modified by this slice.

## Next task

The reviewed conservative-month-end comparison is implemented; see
PUBLIC_FACTOR_COMPARISON.md for limits and evidence. Next: connect saved order
reviews to these scenarios, then permission-cleared Iranian inputs. Client inputs
still needed: relevant FX market and dated monthly CPI/FX history.
# Implementation update — 3 October

Live public supply pressure, 15 World Bank commodity series and Iran annual
inflation fetched. Automatic-refresh controls added. Servix signup/private key
setup and authenticated history are verified (666 quotes; two-year span).
Industry API failing. Monthly Iranian
CPI and regional shipping are still pending. These statements supersede older
connection-status notes below; see LIVE_EXTERNAL_CONNECTIONS.md for evidence and
forecast-use gates. Research candidates are not working integrations.

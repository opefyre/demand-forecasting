# Iran factor inputs — 3 October 2026

## Delivered

Data → External context → Import factor retains the three-step flow. File/columns
now includes Gregorian/Persian calendar and publication timezone. Source details
reveals FX or inflation controls only when that data kind is selected.

- Persian/Arabic digits, decimal and thousands marks are accepted. Gregorian dates
  use YYYY-MM-DD; Persian text dates accept YYYY-MM-DD or YYYY/MM/DD. No guessing.
- Persian dates use the existing MIT-licensed PersianTools dependency. Excel date
  cells require Gregorian mode; Persian dates must be text. Leap days are validated.
- Persian monthly/annual periods retain their true Gregorian start/end boundaries.
  Monthly observations must end on the last Persian day; annual ones end in Esfand.
  Gaps follow the selected calendar, rather than a misleading Gregorian month count.
- Publication dates become eligible at the end of the declared UTC or Tehran day.
  IANA historical timezone rules are used. Dates are uploader-declared, not verified
  releases; a revised value replaces the old value only after its own availability.
- Original dates and values remain inspectable beside normalized values. Retained
  files, exact source hashes, definitions and immutable versions are preserved.

## Exchange rates and inflation

An FX import requires foreign currency, market, buy/sell/mid/settlement basis,
source rial/toman and quote quantity. Market and quote basis are never inferred.
The rate direction is local currency paid for foreign currency, not its inverse.
Saved values are **IRR per one foreign currency unit**:

    normalized rate = source value × (10 for toman, 1 for rial) ÷ quote quantity

Example: 9,500,000 toman per 100 USD → 950,000 IRR per USD. These are synthetic
test values, not current market quotes. Daily data can be retained as context;
daily-to-monthly aggregation and automatic quote inversion are not delivered.

Inflation must be identified as CPI index (with base year), change from previous
month, change from same month last year, or annual-average inflation. Values are
not automatically compounded, deflated, rebased or used as a tonnes multiplier.
Different market, basis, CPI base, calendar or release timezone requires a separate
factor. Existing updates preserve the reviewed definition and previous snapshots.

## Forecast linking

Monthly Persian inputs require explicit approval of **last complete Persian month**
alignment. For a target Gregorian sales month and its selected lag, take the lagged
Gregorian month end, then find the exact last Persian month completed by that date.
Use only that month's release available before the target cutoff; never substitute
an older nonmissing month. Missing history blocks saving. Unknown future values
require reviewed assumptions, just as for Gregorian factors.

This is an explicit lagged feature, not a Gregorian monthly CPI/FX estimate. Sales
remain Gregorian-month forecasts. Alignment evidence includes lag cutoff, actual
observation end, original Persian period and original value. Normalization metadata
travels with model input definitions and Excel source/alignment sheets. Existing
baseline matching, held-out accuracy checks and order-aware comparisons are reused.
Factor input test horizons still freeze the last training value; future scenario
assumptions are not known historical observations. Booked orders remain unchanged.

## Refresh and source limits

Imported-factor freshness is recomputed on read from the observation end, not the
download date. Review guidance: daily >7 days, monthly >62 days, annual >550 days.
These are disclosed app thresholds, not guaranteed provider publication deadlines.
Update file retains the contract and previous version. Scheduled factor-file/API
refresh is still pending; existing sales/order scheduling does not refresh factors.

Source check 3 October:

- [CBI inflation](https://www.cbi.ir/Inflation/Inflation_FA.aspx) is publicly readable;
  monthly-ending and annual figures must not be interpreted as monthly CPI growth.
  Free commercial API/reuse permission and historical release archive not verified.
- [CBI FX](https://www.cbi.ir/exrates/rates_fa.aspx) is readable; permission, stable
  API and the correct client market are not verified.
- [SCI](https://www.amar.org.ir/) could not be read through the research tool. This
  is a verification limit, not proof that the source is unavailable.
- [Bonbast FAQ](https://www.bonbast.com/faq) confirms toman quotes and directs
  businesses to its API. No subscription, scraping or contact initiated.
- [PersianTools](https://github.com/majiidd/persiantools) provides the existing
  open-source date/digit conversion; no custom calendar algorithm or new package.

The client FX market is an outstanding explicit question. Live Iranian CPI/FX is
not connected. Existing World Bank/NASA/GSCPI adapters remain separate; annual
Iran context is not silently transformed into a monthly feed. No paid AI call or
client data sent externally by this implementation.

## Verification and next major task

401 backend tests, 58 frontend tests and build pass. Tests cover known calendar
boundaries/leap days, Tehran availability cutoffs, revisions/gaps, independently
checked FX math, definition changes, freshness, review/idempotency and API behavior.
Real-engine Persian factor → forecast → matched accuracy → Excel alignment export
is exercised, preserving the baseline. The browser sample shows 950,000 IRR/USD,
original Persian values, one revision and a missing month. Desktop/390px review and
source controls checked; page width 390px without page-level horizontal overflow.
The sample was previewed, not saved as a live factor or forecast. Existing demo
unchanged. Fixture: sample_data/iran_fx_normalization_demo.csv.

Follow-up delivered 3 October: local **factor refresh → validation → reviewed new
version → forecast draft**, reusing existing tools. See FACTOR_FOLDER_REFRESH.md
for implementation, verification and boundaries. Live provider APIs remain pending.
Client history/order export acceptance and live-provider eligibility remain needed
before operational accuracy or production readiness can be claimed.

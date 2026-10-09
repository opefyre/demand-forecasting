# Historical weather connection

Implemented and verified 21 September 2026. This adds an actual NASA POWER
download, not a simulated connection-status card. It remains historical context,
not an automatic forecast input or a future-weather service.

## Workflow

Data → External context → Weather history → Choose location & dates.

Enter a descriptive location name, decimal latitude/longitude and historical
dates. Explicitly confirm sending the coordinates and dates to NASA POWER.
Location names, source files, sales records and client identifiers remain local.
Changing a form value clears permission. There is no inferred Tehran city-centre
or plant coordinate. All previous successful snapshots remain selectable.

The connector uses the existing open-source HTTPX library against NASA's fixed
daily endpoint. No account, key or new paid dependency is required. Requests use
temperature (`T2M`) and precipitation (`PRECTOTCORR`), community AG and UTC days.
There are no arbitrary URLs or user credentials in this adapter. HTTP redirects
are not followed. Connection establishment is retried twice; HTTP failures are
shown without replacing earlier snapshots. A 24-hour exact-request cache avoids
unnecessary repeat calls. New ranges or later refreshes create immutable versions.
The lock/cache scope is this local process, not a distributed deployment.

## Data contract and checks

Grain: one requested calendar day in UTC, with temperature in °C and daily
precipitation in mm/day. NASA's grid estimates are not on-site sensor readings;
UTC is not the Asia/Tehran civil-day boundary.

- Validate explicit permission, location name, finite coordinates, historical
  date ordering, 1981 lower bound and approximately ten-year request-size limit.
- Check returned coordinates, time standard, parameter units and response shape.
  Unknown units fail rather than being guessed or silently converted.
- Detect duplicate JSON keys/dates and out-of-range observation dates; cap streamed
  response size at 4 MB. Reject invalid/non-finite readings and negative rain.
- NASA's −999 sentinel and absent days become null, not zero. Coverage exposes
  available/missing days and latest reading separately from the download time.
- Only complete calendar months receive monthly values. Temperature is a mean;
  precipitation is summed across complete daily intervals. Incomplete months
  remain unknown separately for each variable, including leap-year checks.
- Preserve original response bytes, SHA-256, source header/version, request,
  capture time, normalized daily values and source/attribution links. Export and
  cache reuse verify that the original response still matches its hash.
- Daily CSV includes units in column names, coordinates, UTC time standard,
  availability time, snapshot ID, source hash and context-only status.

High-confidence risk findings addressed by these guards: daily/calendar grain
confusion, sentinel-as-observation errors, biased partial-month summaries and
revised-history leakage. Historical observations receive **first local capture**
availability timestamps, not invented original release dates. The existing
point-in-time gate excludes them from historical cutoffs before that capture.
They are deliberately not auto-joined into model training or validation.

## Public example verification

Snapshot `7c1c62d3f56d4e34adb5836638ecd407` was fetched through the browser:

- Location: the public NASA documentation example at 0°, 0°; **not the client**.
- Range: 1–31 January 2025; 31 temperature and 31 rainfall readings; no gaps.
- Independent mean temperature: 27.38064516129032 °C; rainfall total: 105.33 mm.
- All daily export rows reconcile to the preserved original response. Hash matches.
- Repeat browser request returns the same snapshot with explicit cache-reuse text.
- Browser checks cover empty state, form/permission, native date entry, successful
  fetch, monthly values, update/re-confirmation and 390px containment. Desktop
  checked at 1280×850; mobile at 390×844. This is not whole-product acceptance.
- Nine new test cases bring the Python suite to 126 passing tests; four existing
  chart-data tests remain separate. Tests cover request privacy, invalid inputs,
  schema/time/unit/location guards, missing readings, complete/leap months,
  caching/version retention, failure preservation, raw integrity, size/duplicate
  rejection, API validation and CSV export. Frontend build passes with existing
  bundle/dependency warnings.

Read-only reproduction: `scripts/verify_weather_sample.py` reads the saved source
and compares its arithmetic and the running app's CSV. No client data is uploaded.

## Source decisions and remaining work

NASA documents the [daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/),
[data origin, grid resolution and latency](https://power.larc.nasa.gov/docs/faqs/data/),
and [UTC versus local solar time](https://power.larc.nasa.gov/docs/faqs/other/).
The daily endpoint supplies historical grid data, with possible recent delays and
later revisions, not forecasts. Attribution and use guidance are linked to
[NASA Earthdata](https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy).
Free access is not an operational SLA; reachability and usage suitability from
the client's own Iran network still require deployment checks.

Open: confirmed factory coordinates; future-weather provider/assumptions;
governed joining to item/site histories and true release vintages; automatic
synchronisation and freshness policy; forecast-value validation; country/region
FX and disruption feeds; authenticated consent/roles, distributed locking,
storage/retention limits and production-scale tests. This connector does not
reduce the remaining approved product scope or establish forecast accuracy.

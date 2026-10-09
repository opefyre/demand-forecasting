# Reviewed factor-file refresh

3 October 2026. Sales/demand forecasting only.

## What is implemented

In **Data → External context**, the connection icon beside an imported factor
opens a centered dialog. An administrator selects one file in an approved local
folder and either manual checks or a 15-minute/hourly/6-hour/daily interval.
The existing folder reader, file parsers, SQLite storage, APScheduler,
factor imports and forecast jobs are reused. No new package or paid service.

The export must contain the complete factor history, including retained revisions,
with the reviewed columns, calendar, publication timezone, units, market and
measure. A changed file is checked using the saved mapping; the user does not
repeat mapping. Unchanged accepted bytes do not create another factor version.

**Refresh & review** opens the existing review screen directly, without fake
upload/mapping steps. It reports new, changed and removed releases. Changed
values appear first, with previously saved and proposed values; removed releases
can be inspected. The preview is capped at 30 rows, but validation checks all rows.
Row errors, changed headings, files still being written, linked files and
unapproved paths block review/acceptance. Gaps stay empty, not zero.

**Save factor** explicitly approves an immutable new version. It rechecks the
file, connection and parent version, rejects stale approvals and safely retries
interrupted saves without duplication. Original files, factor versions, orders,
forecast results and published reviews remain unchanged.

With an active baseline forecast, **Prepare forecast draft** opens the existing
factor comparison dialog with the new version selected. The user reviews lag,
future assumptions, optional customer/product scope and method. Only approval
queues the calculation. Existing matched historical accuracy and exported factor
alignment/source evidence remain authoritative. Adding a factor may worsen error.

Scheduled checks only stage inputs. They never approve a factor, start a forecast,
alter customer orders or publish a plan. Connections survive server restarts and
can be paused/resumed; schedules remain subject to the server being running.

## Verification

- 11 focused tests: full refresh/review/save/retry, unchanged-file deduplication,
  invalid rows, mapping changes, source/configuration changes, file changes during
  acceptance, interrupted publication recovery, safe paths, pause/resume and
  restored schedules/API routes.
- Real forecasting engine test: accepted factor → reviewed linked dataset →
  calculated comparison → Excel alignment; original baseline preserved.
- Full regression and build recorded in IMPLEMENTATION_CHECKLIST.md.
- Browser acceptance uses `factor_refresh_demo.csv`, explicitly synthetic index
  values, not real Iranian inflation/FX. The original demo is kept intact.
  Desktop and 390px refresh/review/save/draft verified; schedule left off.
  Result `0ea4a37ff8ef` completed against baseline `0cfe066d816f` and exported
  39 alignment rows. Historical error was 7.21% baseline vs 7.94% with the factor;
  the UI correctly reports that the baseline performed better. This synthetic
  factor is workflow evidence, not an accuracy improvement claim.

## Boundaries and next substantial task

This is a local export connection, not an authenticated Iranian provider API.
Publication dates remain uploader-declared. Daily FX is not silently averaged
into monthly values. No live Iranian CPI/FX source or production schedule is enabled.

Next: a client-connected monthly forecasting cycle—one actual ERP/export contract
for sales, customers and open orders, confirmed FX market and dated factor history,
source-total reconciliation, scheduled draft preparation and reviewed SKU/customer/
month handoff. Client credentials/samples and receiving-system semantics are needed
for live acceptance, not more synthetic model claims.

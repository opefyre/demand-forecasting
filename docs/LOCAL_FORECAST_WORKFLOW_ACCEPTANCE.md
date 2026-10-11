# Local forecast workflow — 11 October

## Scope

Local code only. No cloud configuration/deployment, live provider refresh, AI
provider calls or changes to saved client/demo records. Browser checks use a
disposable, company-separated fixture on loopback port 8013. Real company stores,
order reconciliation and mathematical forecasting are used; identity and external
factor feeds are test fixtures. Dummy results are not evidence of client accuracy.

## Fixed

- Back navigation no longer silently discards selected factors or future assumptions.
  Reopening restores editable choices, never an old factor review approval/token.
- Forecast horizon, planning calendar and holiday settings survive modal reopening.
  Applying settings preserves factor choices for the derived history version.
- Applied order edits/import choices survive Back and modal reopening, bound to the
  input context and order-book version. A changed book loads current orders and
  requires review. Active row edits block navigation/dismissal until applied/cancelled.
- The factor chooser includes compatible saved factors, not just two provider types.
  Unavailable restored selections cannot crash the screen or bypass review; they
  can be removed. Failed factor reads offer the shared reload action.
- Non-monthly history is blocked early with accurate instructions. The previous
  claim that it could proceed without factors was wrong: combined orders currently
  require monthly planning. Daily/weekly combined planning is not implemented.
- Shared global panels, fields, actions, errors and fixed dialog are retained.
  No new CSS, inline styles, page-specific visual rules or infrastructure changes.

## Verification

Browser: six-month Gregorian forecast, four customers and two products in the input
directory, existing confirmed orders (20 tonnes open, 2 fulfilled), one selected
external factor with lag and explicit future assumptions, two factor-aware methods
under one forecast name. Methods complete, both appear in a shared comparison,
customer/product filters update the values, and the downloaded Persian comparison
CSV retains full precision matching the displayed rounded numbers.

The factor selection/85-unit assumption survives Back, with Continue blocked until
a fresh review. Horizon 6 survives closing/reopening. An order quantity changed
from 16 to 25 survives Back and closing/reopening without premature approval.
Persian controls/quantities were inspected; at 390px page width is exactly 390px and
the fixed modal's own body scrolls (576px viewport, 1135px content).

New API/engine regression imports history and a published-date synthetic Iranian
inflation factor, inherits the existing order book into derived factor inputs,
calculates Ridge and Elastic Net in one group, verifies factor values/provenance,
all customer/month rows, no-order customers' positive demand, fulfilled/open/expected
arithmetic and identical filtered CSV/JSON planning quantities with SKU `001` intact.
Existing revision tests cover corrected sales, both planning calendars, independent
approval, exports and company/role isolation.

Test results: 344 frontend checks; 16 workflow/platform/revision backend checks;
39 sales-consumption/factor-link/live-alignment backend checks; frontend build.
All pass. Live refresh/auth/cloud deployment are not tested in this slice.

## Remaining code work

### Exception-path follow-up

- Fixed a silent warning bypass: new forecasts now stop on input warnings before
  saving the order book or reviewed snapshot. Users can edit the same modal or
  explicitly continue. The normal, warning-free path adds no extra screen.
- New customer/product pairs without history or full monthly commitments are
  identified before calculation. Known orders remain available; missing additional
  demand stays unknown, never zero. Complete reviewed commitments can supply the
  missing monthly totals; no customer forecast is invented.
- Duplicate customer/product additions are rejected before changing the directory.
- If saving the reviewed snapshot fails after saving the order book, the editor
  keeps the new book version so a retry does not conflict with its own save.
- Review uses existing shared disclosures/tables/actions, with authored Farsi
  translations. No CSS or inline style changes.

Verification: 346 frontend checks; 26 order/workflow/consumption backend checks;
16 public-platform/full-workflow checks; 16 factor-link checks; production build.
Synthetic seven-month history and 36-month intermittent sales exercise real model
calculations. Cancelled and unconfirmed orders do not inflate confirmed demand;
partial fulfilment/cancellation preserves the outstanding balance. Existing factor
checks reject missing/unpublished observations and missing future assumptions.
Browser checks cover new-customer warnings, incomplete order coverage, explicit
continuation, model selection, calculation, result navigation, unknown totals and
disabled final export. English/Farsi warning screens retain the shared design.

### Inline monthly commitments

- New forecasts and order updates now share one inline commitment editor. Add,
  edit or remove a full monthly total for any customer/product, including new
  customers without history. No commitment file is required.
- Month choices use the actual forecast periods, including Persian boundaries.
  Quantities keep full precision; owner, reason, expiry and duplicate checks are
  required before applying. Manual edits clear obsolete commitment import evidence.
- Applied commitments survive Back. Pending edits block continuation and dialog
  dismissal in both the new forecast and shared order-update dialog.
- Preview rejects expired commitments and totals below confirmed orders plus
  deliveries before model fitting. A monthly total replaces the estimate; it is
  never added on top of orders.
- Existing global disclosure, grid, fields, table, actions and fixed modal are
  reused. No new styles or inline styles. Authored controls/errors are translated.

Verification: 351 frontend checks, 30 order/full-workflow/sales-consumption backend
checks, production build. All pass. A real company/API/engine regression covers
three Persian periods, a new Tehran customer, partial cancellation/fulfilment,
15.123456 monthly demand, 7 open orders, 2 already fulfilled and 13.123456 exported
future demand. Browser checks cover blank validation, applied input persistence,
calculation/results, Farsi editing and a 390px mobile viewport. Input precision is
retained; the commitment form is outside the horizontally scrolling table.

### Assistant-to-wizard handoff

- Fixed a stale navigation race: when the user changes/leaves chat during workspace
  refresh, its old action cannot reopen a forecast. Failed refresh never navigates.
- Executable handoff tests verify exact source, method and customer arguments and
  cancellation before/during refresh. The existing shared wizard remains the only
  destination; no UI elements, styles or parallel wizard were added.
- A real company-store/API regression verifies a four-month assistant draft inherits
  the current order book, includes the customer directory and warns about a new
  customer without history. Inputs remain unreviewed; no job is dispatched. Repeating
  the action reuses its draft. Revoked forecasting access and other-company access
  are rejected. Existing suites cover advanced factor/monthly/order proposals.

Verification: 355 frontend checks; 38 full-workflow, assistant, company-context and
company-workflow backend checks; production build. All pass. AI replies are mocked;
no provider calls or credential changes. This is automated handoff verification,
not a new browser acceptance of every chat scenario.

Next: broader English/Farsi navigation/error audit across the complete manual and
assistant journeys, including mobile, unavailable inputs and interrupted requests.

### Bilingual load recovery — local browser check

- Customer/order initial loading failures now expose the shared Reload saved data
  action. Reload retries reads only, keeps the wizard open and never approves or
  writes inputs. Unmounted reads still cannot update another step.
- Factor future/history review values and included-factor quantities use the same
  locale formatter. Dates/month identifiers have explicit bidirectional isolation;
  stored numbers and forecast calculations are unchanged.
- The global Steps component now localizes step numbers, not just labels. No new
  CSS, inline styles, page-specific layouts or UI elements were introduced beyond
  the existing shared error recovery action.

Verification: 358 frontend tests, 15 order/full-forecast-workflow backend tests and
production build pass. The disposable browser fixture injects one failed order read
in English, then another in Farsi. Both recover through Reload; the checkbox remains
unchecked. Back, modal closing/reopening, review, method selection, calculation and
saved-result navigation were exercised. Farsi mobile viewport is 390px, page width
390px, fixed dialog width 358px. The recovered three-month/four-customer forecast
completes with 20 open orders, 2 fulfilled, 113 expected and 135 total demand.
The latest build's Persian step digits were checked in the browser. Factor formatting
is covered by render tests, not a new connected-factor browser calculation here.

Remaining: interrupted/polling/export errors and advanced assistant proposals need
the same full browser pass. This is not whole-app UI or accuracy acceptance. All test
records are temporary; existing client/demo records and cloud services are unchanged.
Do not claim the full assistant/mobile exception matrix or whole-app acceptance
from these narrower checks.

Daily/weekly combined order planning remains unsupported and is now explicit.
Real-client forecast accuracy still requires actual history and future actuals;
dummy data cannot certify it. Whole-app acceptance is not claimed.

### Independent progress and export recovery — 11 October

- Job reads settle independently: a failed read no longer hides other methods'
  completed results. Terminal jobs are not repeatedly fetched. Failed reads pause
  automatic polling; the shared Reload action retries saved reads only. Write
  failures remain separate and are never cleared by unrelated polling.
- Result summaries preserve available method totals, expose read failures and can
  be reloaded without recalculation. Customer filters participate in refresh;
  missing demand remains unknown, not zero or a raw sales prediction.
- Known API exports are handled in local/company mode as well as the existing
  cloud transport. Failures keep the workspace open. The shared DownloadLink
  puts draft/approved export errors inside the dialog, not behind its overlay.
  It prevents repeat clicks, preserves filenames/bytes, honours error/cooldown
  information and discards replies after unmount or company/session changes.
  Recovery instructions and download status are translated. No CSS, authored
  inline styles or page-specific appearance rules were added.

Verification: 371 frontend tests, nine backend job tests and production build pass.
Tests cover partial status/summary failures, interrupted/cancelled terminal states,
read-only recovery, missing customer estimates, export route selection, 429,
connection/unreadable responses, attachment bytes and company-change cancellation.
Backend tests cover interrupted claims, duplicate publishing prevention, retry
chains and incomplete-file cleanup. Existing build chunk-size and backend resource
warnings remain; they were not addressed in this change.

Disposable browser checks: one English export 503 remains inside its dialog;
retry clears the error without leaving Forecast. A real two-method calculation
(Last period and Recent average) completes with 135 tonnes per method. After
loading the latest build, the Farsi export 503 uses the translated inline recovery
instruction and its retry clears the error. Screenshot:
`/private/tmp/demandlab-export-recovery-fa.png` (temporary local evidence).
The browser download-event waiter timed out; receipt of a saved browser file is
not claimed. Binary delivery is covered by executable transport/download tests.
The intended result-read fault did not trigger because the fixture originally
matched 32-character run IDs instead of the engine's 12-character IDs; the fixture
was corrected, but the partial-read browser test still needs rerunning.

Next: complete the advanced assistant proposal/review journeys and the interrupted
job/partial-summary browser matrix, then the broader English/Farsi design audit.
No live AI/provider calls, infrastructure/deployment edits or changes to existing
client/demo data. Full app acceptance and real-client accuracy remain pending.

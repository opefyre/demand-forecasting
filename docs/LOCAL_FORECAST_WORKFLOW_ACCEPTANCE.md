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

Next: exercise the full exception matrix through the assistant and shared wizard:
short/intermittent sales, new customers/products without history, cancelled/partial
or incomplete orders, stale factors and missing future assumptions. Resolve any
remaining blockers with the same global components, then review bilingual error
wording and keyboard/mobile behavior for those exception paths.

Daily/weekly combined order planning remains unsupported and is now explicit.
Real-client forecast accuracy still requires actual history and future actuals;
dummy data cannot certify it. Whole-app acceptance is not claimed.

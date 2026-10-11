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

Next: finish assistant-to-wizard exception handoffs and the broader bilingual
navigation/error audit. Add an inline first-forecast commitment entry for customers
with no history (the engine/API already support reviewed complete commitments, but
the new wizard currently only exposes their import in existing-forecast updates).
Do not claim the full assistant/mobile exception matrix or whole-app acceptance
from these narrower checks.

Daily/weekly combined order planning remains unsupported and is now explicit.
Real-client forecast accuracy still requires actual history and future actuals;
dummy data cannot certify it. Whole-app acceptance is not claimed.

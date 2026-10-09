# Visible sales import acceptance

24 September 2026. Bounded browser acceptance, not a whole-product UX approval.

## Improvements

- Customer and product matching are visible in the main column-matching step,
  rather than hidden under an optional category section. File preview includes both.
- Replaced the ambiguous Item label with Forecast group and a tooltip explaining
  customer–product grouping. Product category remains optional.
- Historical-file upload uses a real focusable button; Enter opens the picker.
  The previous hidden input could be targeted without opening it reliably.
- Uploaded sample files can be explicitly marked as samples, not company actuals.
  Changing that choice clears the prior validation/approval state.
- Removed a stale instruction referring to a nonexistent Demand navigation page.
- Export options fit on small screens: Yes — exclude orders / No — include orders.
  The adjacent description retains the distinction between expected demand, open
  orders and fulfilled quantities. No calculation or export policy changed.

Existing React, Radix controls, file parsing and forecast engine reused. No new
packages, external transmissions or paid OpenAI requests.

## Browser evidence

- Uploaded existing synthetic `paper_printing_history_36m.csv` through the file picker.
- Checked laptop column mapping, unfinished-import restoration after reload, and
  keyboard replacement upload. Customer/product suggestions persisted.
- Tested 390 × 844 viewport: no page overflow; invalid horizon 0 gives a correction
  message; changing it to 3 allows review. Sample classification is visible in review.
- Saved and calculated `UI acceptance · synthetic sales`, run `0cfe066d816f`:
  504 historical rows, 14 customer/product series, September–November 2026 forecast.
- Opened the calculation, retained customers matched from history, uploaded
  `ui_acceptance_orders.csv` with three synthetic order lines and reviewed source
  dates, complete order coverage and quantity/status meanings.
- Saved snapshot `b0629851fcc3290b8c5c0e004d09fa11`; verified 42 result rows.
  Lumen's 200 ordered − 20 delivered − 10 cancelled gives 170 open, 190 total,
  and zero additional expectation in September. PrintWorks keeps forecast remainder
  above its 25 ordered; cancelled lines add no confirmed demand; other customers
  keep their model estimates.
- Verified both export choices and resulting URL mode in the centered mobile dialog.
  All six API export combinations (Excel/CSV/JSON × combined/residual) reconcile:
  195 open, 20 fulfilled, total demand 3,647.4146943162245 tonnes; combined planning
  quantity is total minus the fulfilled 20. Exports are still drafts.
- Reload restores the saved result; final laptop screenshot inspected, no captured
  browser console errors. Temporary viewport override reset; demo left open.
- Frontend build and 45 JavaScript tests pass; whitespace check clean. Backend was
  not modified this turn; last full backend regression remains 369 tests.

## Remaining acceptance and next task

The new browser journey did not yet exercise external-factor upload/link screens,
replacement customer-file mapping, every order correction path or all dashboard
filters. Backend tests cover the combined factor journey, but that is not browser
acceptance. Original client/demo data was not overwritten.

Next: walk through dated factor import → publication/lag review → separate scenario
→ order-aware comparison. Audit the order form's optional commitments section and
long mapping forms for progressive disclosure, without hiding essential checks.
Continue with correction/retry cases and customer-file replacement after that.
Do not call the full product production-ready on the strength of this sample.

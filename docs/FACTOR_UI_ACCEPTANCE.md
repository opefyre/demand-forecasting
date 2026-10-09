# Factor workflow and optional order-input acceptance

24 September 2026. Sales/demand only; synthetic browser fixtures, not client
accuracy acceptance or a new live Iranian feed.

## Delivered

- Factor import is now three focused steps: file/columns, source details, review.
  Back navigation retains inputs but clears approval before another save.
- Exact, unambiguous headings suggest the three column matches. Missing, duplicated
  or stale mapped columns cannot advance. Ambiguous headings are left for the user.
- Replaced the native file control's misleading “No file chosen” after upload with
  a normal Choose/Replace button and the retained uploaded filename.
- Publication-date guidance distinguishes the release date from the download date.
  Review keeps location, unit, sample/real classification, gaps and revisions visible;
  detailed values are expandable instead of another always-open table.
- Changing the selected factor clears the previous future assumption and approval.
  This prevents carrying a number across factors with different units/meanings.
- Empty customer-confirmed monthly commitments are behind an optional disclosure.
  Existing commitments open the section and show the loaded count. The regular
  customer/order workflow and validation rules are unchanged.
- Worksheet changes retain the previous usable preview if reading the new sheet
  fails, instead of removing the controls needed to recover.

Existing React/Radix controls, pandas import and forecasting packages reused.
No new dependency, connector, paid API request or client-data transmission.

## Checked in the browser

- Uploaded `factor_observations_demo.csv`, reviewed suggested mapping, supplied
  synthetic Iran source details and saved `UI acceptance · synthetic index`.
- At 390 × 844, review displayed four periods, one revision and the missing April
  2025 period. Save remained disabled before approval. Back → Review required
  fresh approval. Gap was not filled or disguised as zero.
- In the baseline `0cfe066d816f` scenario screen, this incomplete factor produced
  32 missing/unpublished periods and disabled Calculate comparison.
- Switched factors after typing 110; verified the fixed UI cleared that number.
- Selected the existing complete `Synthetic monthly context · linking demo`,
  explicitly entered 140 for unknown future values, and reviewed the 2-month lag.
  September used the published 129.086; October/November used the entered assumption.
  Historical matching displayed observation and publication dates before the target.
- Calculated a separate linked scenario and compared the same customer orders.
  Historical error was **worse: 7.21% → 7.89%**. This is no evidence of an improvement;
  the baseline remains the selected sales forecast, not silently replaced.
- Saved comparison draft `0f9138aeb705b42732a5352e59393f12` from baseline order snapshot
  `b0629851fcc3290b8c5c0e004d09fa11`. Read-only verification checked 42 rows, unchanged
  order/source hash, 195 open tonnes, 20 delivered tonnes, JSON exports in both modes,
  combined Excel and residual CSV. Scenario total: 3,660.7622312952526 tonnes.
- Optional commitments were hidden when empty and remained accessible by expanding.
- Mobile page width stayed at 390 px; temporary viewport override reset. Final
  laptop factor-entry screen inspected. Original forecast left selected.

## Verification

48 frontend tests pass (three new mapping cases), production frontend build passes,
and whitespace checks pass. Existing bundle-size warning remains. Backend logic
was not changed; latest complete backend regression remains 369 tests.

Recheck saved comparison without changes:
`scripts/verify_order_comparison.py --verify 0f9138aeb705b42732a5352e59393f12`.

## Next bounded task

Finish customer-file replacement and order correction/retry browser acceptance:
duplicate references, mismatched customer/product codes, partial fulfillment,
cancellations and re-upload after an error. Improve messages and recovery paths
where demonstrated. Preserve stored versions and keep advanced inputs optional.

Still not verified here: live Iranian CPI/FX history and source permissions,
independent release-date archives, per-month factor assumption curves, complete
cross-browser accessibility, production deployment and client accuracy acceptance.

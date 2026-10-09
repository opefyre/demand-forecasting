# Order correction checkpoint — 26 September 2026

Scope: customer/order upload recovery only. No new models, providers, paid AI calls,
or changes to existing saved forecasts.

Implemented:
- File controls reset after selection so the same filename can be selected again.
- Use saved customers/orders (or Clear upload for an empty starting list) discards
  an unsaved upload and its error; it does not delete uploaded evidence or snapshots.
- Missing required mappings and changed-but-unread headings block Continue.
- Changing input meanings, uploads, mappings or order-file mode clears review approval.

Verification:
- 50 JavaScript tests pass; frontend production build passes (existing chunk-size warning).
- 16 targeted Python tests pass: order revisions plus sales-import journey.
- Added regression coverage: rejected duplicate/reassigned references followed by a
  corrected save and retry; original snapshot remains unchanged. Customer replacement
  preserves text SKU `001` and the original snapshot.
- Browser: uploaded synthetic orders; changed heading row; Continue blocked with
  a specific instruction. Use saved orders restored the no-upload state.
- Browser: confirming review enabled Preview demand; changing the review note
  disabled it again. Exited without saving.

Limits and next task:
- Same-filename reselection is implemented but not separately browser-verified.
- Full small-screen correction/error-layout acceptance remains open.
- Selected demo's review expiry is 24 September, so demand totals/exports are now
  correctly blocked. Do not silently extend it or claim the demo is export-ready.
- Next: make expired-order recovery obvious and verify a separately reviewed
  synthetic update through customer/SKU/month views and planning exports.

## Follow-up completed — 26 September

- Stale/unknown order reviews now show a specific next step and review deadline;
  the existing Update orders action becomes Review orders (no extra banner/button).
- Added a server-status-based guidance test: 51 JavaScript tests and build pass.
- `scripts/verify_order_review.py` created synthetic review
  `7ff53e12a0360e04ec0d495056d368ea`, valid through 3 October. It leaves source
  `b0629851fcc3290b8c5c0e004d09fa11` unchanged; repeated save is not duplicated.
- All 42 rows reconcile; combined and remaining-demand exports pass in JSON and CSV.
- Browser checked old-version guidance, selected new review, and verified Lumen's
  monthly table: September baseline 73.96, open orders 170, fulfilled 20, remainder 0,
  total 190. October/November retain forecasts without orders. Restored all-customer chart.
- Demo totals: open orders 195, expected 3432.41, total including fulfilled 3647.41 tonnes.
- No new forecast model, live external feed or paid AI call. This is synthetic evidence,
  not client-data acceptance. Excel export was not retested in this follow-up.
- Next: small-screen correction workflow and clearer actionable import errors;
  same-filename browser reselection remains to verify.

## Small-screen follow-up — 26 September

- Browser verified same-filename reselection: after changing the heading row to 2,
  selecting the same CSV again restored row 1 and enabled Continue.
- Found and fixed empty-heading previews replacing valid mappings. Empty previews
  now show a specific correction instruction and retain the previous mapping.
- Browser verified row 200 produces that error, blocks Continue and preserves all
  selected columns; reading row 1 again clears the error and enables Continue.
- Upload/mapping and review forms checked at 390px and 320px. Document width matches
  viewport width. Long upload names can wrap; file icons retain their size.
- Added spacing between the review heading and first fields after visual inspection.
- 52 JavaScript tests pass; production build passes with the existing chunk warning.
- Exited without saving and restored default viewport and the selected renewed demo.
- Next: validate full customer-list replacement and duplicate/mismatched order errors
  in the browser, not only backend tests. Broad mobile/dashboard acceptance remains open.

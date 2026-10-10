# Reviewed history, forecast revision and planning export — 10 October 2026

## Delivered

- Company/cloud history replacement now uses the existing full-history comparison.
  Preview shows added, changed and removed customer/product periods. Saving a
  replacement requires acknowledgement, recomputes the receipt, saves it with the
  new input version and leaves the original files, orders and results unchanged.
  Same-source settings changes do not invent a replacement review.
- New forecast and monthly updates now share one `Steps` component. Monthly
  stages, source status, comparisons and exports use shared panels, grids, actions,
  definitions, disclosures and collection/search controls. Removed the entire
  203-line monthly appearance sheet and competing old progress rules.
- Monthly updates stay under Forecast rather than taking over Home. Closing an
  update returns to its forecast dashboard. Existing updates are resumed rather
  than duplicated, and explicit refresh is locked while in progress.
- Demand review/export uses the same fixed, internally scrolling dialog as New
  forecast. Shared tabs, forms, checkbox and action layout replace its dedicated
  styling. Receiving-system policy still determines whether orders are included;
  draft downloads remain separate from independently approved releases.
- Updated authored Persian labels, quantities and units; identifiers and API
  values remain unchanged. Persian horizon labels retain ASCII numeric values so
  selecting a month count cannot submit an invalid number.

No new package, model, provider call, public access or approval bypass was added.
Cloud remains owner-only; independent approval tests use isolated fictional
companies, not new live accounts. The local demo remains independent.

## Executed verification

- 293 interface tests pass; production build passes. Existing bundle-size and
  third-party directive warnings remain; this work does not claim to fix those.
- 34 host tests pass across input corrections, public company sales and cloud API.
- 13 tests pass in the exact Linux engine image: input-correction tests plus the
  combined cold-start journey, networking disabled, 0.25 CPU / 1 GiB limit.
- Combined real-engine journey: four customers / two SKUs / 36 original months;
  remove an old month and correct the latest Aftab quantity 20→26; review/save a
  new history version; re-review partial confirmed orders; run Last observed and
  Recent average under one revised group; preserve parent revision navigation;
  reject export while pending and reject self-approval; approve as an independent
  reviewer; read CSV/Excel/JSON as a report-only user. Every customer/SKU/month
  quantity agrees to nine decimal places and leading-zero SKUs survive all forms.
  A wrong-company principal is denied. Restoring the final checkpoint preserves
  original source bytes and the complete original forecast exactly.
- Actual local browser: monthly settings stay at `/demand`; saved history advances
  to settings; English export preview retains fixed 960×680 dimensions and scrolls
  1,234px of content inside a 519px body. Inputs remain 44px / 16px. Only observed
  inline style was the library's pointer-events measurement, not authored styles.
- Persian monthly settings at 390×844: RTL, page/content widths both 390px,
  single-column forms, shared 20px panel padding, 16px radius and 18px headings.
  Source/order business names are not machine-translated. Browser preview did not
  submit a live planning approval or create a new forecasting calculation.

## Remaining acceptance

This is not a full-product readiness claim. Next substantial chunk: complete the
remote monthly-update journey with corrected history, retained live-factor
assumptions and current orders; test interruption/reload, changed input versions
and stale approvals, and finish the advanced factor/revision mobile walkthrough.
Continue migrating any legacy appearances encountered to the shared framework.

Actual provider capture receipts, additional provider permissions/credentials,
AI-provider eligibility, real-client accuracy and an explicitly authorised
multi-person pilot remain separate gates. Do not open access automatically.

## Deployment

Private edge: `e5932d40-c778-48b0-826f-e9c9fb1251ce`.
Verified Linux image: `sha256:db5d50212ef091381a4ec96dd4a247439d52b83fd836440f4f50f18858d300e0`.
Private engine: `f205ff64-b3b3-4852-beec-58e08d1a9403`; the deployed image matches
the verified digest above. Five-minute idle, route-less engine, owner-only edge
and disabled cloud AI settings are unchanged. Identity/storage/domain services
and credentials were not changed.

After deployment, the private browser restored the existing live-market group at
4,070.56 tonnes. The English approval/export form uses shared controls with no
visible explanatory banner; no new live calculation or approval was submitted.
Screenshot: `docs/screenshots/cloud-reviewed-export.png` (local evidence,
git-ignored). The Persian export stage also renders translated labels.

Local `/api/health` returns 200; anonymous cloud customer access still returns
401. Temporary registry login was removed and the dedicated build VM stopped.

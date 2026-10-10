# Monthly cloud recovery — 10 October 2026

This slice fixes recovery and design defects in the existing monthly draft update.
It does not change forecasting formulas, open access or enable cloud AI.

## Fixed

- Reload on Forecast restores the company/user-scoped update instead of clearing it.
  Other pages and read-only users do not automatically open a writing workflow.
- Checking saved status no longer resets unsaved method/horizon choices. A stopped
  calculation returns to its recorded settings and needs a fresh confirmation.
- Completed, failed, cancelled and interrupted jobs stop polling. The former
  completed-job loop unnecessarily woke the engine and conflicted with review writes.
- Already-included factors are identified as included, not described as a
  history-only baseline. Keeping them does not fetch or fabricate new observations.
- Loading, status actions and factor choices use the shared page/panel/action
  structure. The order-reuse dialog now has fixed dimensions, internal scrolling,
  shared summaries/table/checkbox/actions and Persian quantities/units.
- Repeated order-source labels get a short saved-review identifier; unique labels
  stay short. Saved IDs and exact order-review validation remain unchanged.

No new appearance sheet, inline appearance or page-specific sizing was introduced.
Shared Vrolen colours, motion, controls and reduced-motion rules remain in use.
The assistant's older saved-order proposal is not migrated by this slice.

## Executed checks

299 interface tests and the production build pass. Thirty focused backend tests
pass together; one additional stopped-job cold-recovery test passes separately.
Known host core-count warnings and intentionally rejected factor jobs are not
test failures. The pre-existing build-size warning remains.

The actual cloud ASGI/checkpoint bridge, with four fictional customers and two
products, verifies complete-history correction, retained factor history/future
sources, strict future coverage, a factor-aware calculation, cold reloads,
stale-tab rejection, renewed orders and CSV/Excel/JSON quantities per customer,
product and month. Deliveries are excluded. Newer or expired orders invalidate
the prior export approval. Another user cannot read the owner's update. Original
source bytes and results survive restoration unchanged.

A separate restored cancelled job requires renewed confirmation, keeps its
recorded horizon/method and rejects an unconfirmed retry. An exact completed
request retry returns the same job, not another calculation. No provider calls
or access changes are part of these tests.

## Private cloud acceptance

Published edge/assets version `146d25e5-4689-4830-9b33-4461034f3310`.
The engine image, sign-in service, storage, secrets and unrelated services were
not changed. Owner-only access, MFA and five-minute engine sleep remain enabled;
the local demo remains available.

In Chrome, a separate six-month Ridge update from the fictional Tehran case
completed, retained its included supply/oil factors and reused the saved order
book after explicit coverage review: five customers, 79 order lines. Reuse kept
the original 10 October as-of date and 9 November expiry. Reload restored both
the orders step and the completed update. The Persian ready page displayed RTL
navigation and translated controls. No corrected-history upload was tested in
this browser run; correction is covered by the cold-checkpoint test above.

The downloaded JSON contains 108 unique customer/product/month rows, five
customers, four products and six months. Every exported quantity equals open
orders plus remaining demand, and equals total less delivered quantity. The
planning total is 4,024.849998069947 tonnes, excluding 45.712 delivered tonnes.
Draft and unvalidated what-if markers are preserved. The download-event listener
timed out, but the resulting file was independently found and validated against
the new run/order snapshot. No repeated export request was necessary.

Screenshot: `screenshots/cloud-monthly-update.png` (local, ignored by Git).
The cloud viewport override did not apply: this run does **not** establish
390-pixel/mobile acceptance. That remains open with the legacy-screen migrations.

## Next substantial build

Bring monthly updates and recurring drafts onto the same grouped-forecast
contract as New forecast: one named revision, multiple methods, one reviewed
customer/order input version before calculation, and shared comparison/export
navigation. Keep previous quantities and source/factor receipts immutable.
Then complete the remaining order-comparison/assistant proposal and revision
screen migration through shared components, including Persian/mobile recovery.

Real-client accuracy, raw provider capture-receipt inspection, additional source
permissions, AI-provider eligibility and an authorised multi-person pilot remain
separate acceptance gates. This document is not a full-product readiness claim.

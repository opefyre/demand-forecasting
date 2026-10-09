# Customer/product monthly factor batches — 7 October 2026

## Delivered

One reviewed monthly forecast can now contain different factor sources, methods,
timing and future assumptions for different customer/product groups. The existing
forecast engine calculates each group separately. Selected results are combined;
products left out retain their exact baseline. No new mathematical model or package
was introduced. Up to 20 distinct groups are supported.

Forecast → Calculation details → Scenarios → Add forecast factors, and the Factors
step of Update forecast, open the same centered review dialog. Choose a customer/
product, review its sources and assumptions, add it to the batch, and repeat when
needed. Saved profiles are optional. Reusable defaults remain in Customers → Factors.
Small screens use compact group cards with visible edit/remove controls. Help
explains the workflow. There is no additional navigation section.

Browser drafts retain only reviewed input-version identifiers. Reloading restores
the groups, not an approval. Review the batch again before calculating. Changing a
group clears approval. Calculation runs through the existing background queue.
The monthly update continues to Orders, changes review and exports afterwards.

## Safeguards

- Groups must originate from the same original baseline, with explicit disjoint
  customer/product scope. Duplicates, overlaps and mixed real/sample data are blocked.
- Baseline contents, derived settings, source bytes, profile revisions, source
  coverage and assumptions are checked again before and after calculation.
  Older comparisons without these bindings require a fresh review.
- Every result must match its group, engine, unit, series and forecast periods.
  Invalid, non-finite or negative values, duplicate/missing rows and differences
  between chart/table quantities are blocked.
- The queued job publishes the combined result only when all groups complete.
  Failure/cancellation does not replace the original forecast or orders.
- Orders are not copied or changed by factor calculations. They are explicitly
  reviewed for the new result. Each customer's orders consume only its own SKU/month.
- Group evidence is retained; the combined result does not inherit the baseline's
  global accuracy score or claim a calibrated portfolio range. Per-series evidence
  and bounds may remain where the underlying calculation supports them. Recently
  downloaded historical factors remain reviewed what-if evidence.
- Forecast packages include exact source alignment, customer/product scope and
  limitations. Existing demand exports continue to support CSV, Excel and JSON.

## Verification

578 backend checks pass, including real-model batch calculations, unchanged products,
partial orders, all six demand exports, stale/tampered inputs and monthly handoff.
105 interface checks and the production build pass. Existing library warnings about
database cleanup/deprecations and the bundle-size advisory remain; not zero-warning.

A separate synthetic browser demo exercises reviewed factor groups, restored drafts,
the actual calculation queue and a reviewed saved-order reuse. Its generated history
has four customer/product series over 48 months and six forecast months. Two groups
use different artificial factors; two products retain their baseline. Dated factor
values and future assumptions are labelled synthetic, not actual Iran observations.
Browser calculation `f301c7c1142a` derives from baseline `d729c16c0f56`.
Reviewed reused order snapshot `d04934f2b3d1ec97a82da44d72289463` has 370 tonnes
still open and 20 fulfilled. The exports contain 24 customer/product/month rows:
3,680.719663548081 tonnes expected but not yet ordered and 4,050.719663548081
tonnes still to serve including open orders. The dashboard total including fulfilled
is 4,070.719663548081 tonnes; fulfilled quantities are not exported as future demand.
Evidence and all six exports are saved in outputs/factor-batch-demo-evidence.json.
This is a workflow/arithmetic test, not independent evidence of client accuracy.

Desktop, 390px and 320px batch review were checked. Mobile table/action clipping
was fixed with responsive group cards and wrapping footer actions. Reload restored
both groups but required fresh approval. Stale/permission-blocked live suggestions
remained disabled; the explicitly artificial fixtures were selected for this test.
The actual background job reached Ready; monthly output and export-mode dialog were
verified. Wrong generic “percentage adjustment” and “more history” messages on batch
results were removed; absent combined bounds no longer offer a misleading checkbox.
Final browser console inspection found no errors. Screenshots: outputs/factor-batch-
desktop.png, factor-batch-mobile.png, factor-batch-smallest.png,
factor-batch-monthly-output.png and factor-batch-demo.png.

The validation skill guided exact-scope checks, independently recomputed export totals
and the prohibition on carrying unsupported combined accuracy claims. No provider
refresh, OpenAI call, new key or external account change was needed.

## Still open / next major build

Next: assistant-led multi-customer monthly batches, using the same review, calculation,
order and export services. Plain-language requests should resolve exact customer/SKU
scope, ask about ambiguity, prepare multiple groups, require confirmation, show job
progress and open the demand result. No hidden assumptions or automatic publication.

Whole-product acceptance still needs permitted complete live history and successful
stale-feed refresh, broader live assistant acceptance, sufficient actual client history
and measured accuracy, receiving-system checks and deployment/operational acceptance.
This delivery does not mark the entire product complete.

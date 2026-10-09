# Input corrections and repeat-upload review

7 October 2026. Sales/demand only.

Confirmed: saved inputs, mapping proposals, immutable originals, task-specific
OpenAI models and the existing Agents SDK/import flow already exist.
Not established: a model can safely infer missing sales, the client quantities
are unconstrained demand, or a formatting correction improves accuracy.

This delivery:

- [x] Bounded, evidence-backed formatting proposals with before/after cells.
- [x] Approval creates a new input version; no original/order/forecast mutation.
- [x] Repeat history review compares periods, customer–SKU coverage and quantities.
- [x] Existing assistant and import screens reused; no second wizard.
- [x] Regression checks, local sample and laptop/mobile verification.

Arbitrary quantity/date corrections and fuzzy customer merging remain outside
this safe formatting step. Uncertain business meanings require a human decision.

## Delivered behavior

Ask the assistant to check formatting or prepare an updated-history upload.
Its tools only inspect and propose. Cell review requires a checkbox and explicit
save; the backend repeats validation and checks input hashes. Full-history upload
uses the existing file/column/settings/review flow. It replaces history in the
new version, never appends partial rows automatically. The before/after review
shows removed periods as “Not present”, not zero sales. Retained future inputs
are labelled and their existing coverage checks remain active.

Corrections are bounded overlays for mapped identifiers, dates and quantities:
trim outer spaces, Unicode composition, and Persian/Arabic digit normalization
for dates/measures only. Product/customer identifiers retain their digits and
leading zeroes. No missing quantities, fuzzy name matches or date meanings are
inferred. Up to 100 cells per input version; larger changes require a fresh file.
Overlays bind to the original history hash and are cleared for replacement files.
Derived linked-factor history contains corrections once, never replays old indexes.

## Verification and boundaries

- 522 backend tests / 89 interface tests passed; production build passed.
- Twelve new backend checks include actual SDK tools, strict human confirmation,
  unchanged totals/source bytes, changed/corrupt evidence, exact customer/product
  names, Persian dates/digits, repeat-upload receipts and a real local forecast.
- Five additional interface checks cover before/after review, saved/expired
  corrections, removed months, repeat-upload handoff and clearing old overlays.
- Synthetic local sample `188e966a95b7`: six reviewed customer-space corrections,
  210 tonnes preserved, product code `0001` retained, original unchanged.
- Browser tested actual upload → mapping → settings → comparison with 210 → 300
  tonnes; one period added, one changed, one removed. Save remained blocked until
  review; the replacement version was **not saved** in the browser check.
- 1280px / 390px: no page-width overflow; tables scroll within their container.
  Proof: `outputs/repeat-upload-review.jpg` and its mobile companion.
- The replacement draft survived a page reload and required validation again;
  earlier approval was not carried forward.
- No OpenAI calls in this delivery. Real SDK tool execution and server services
  were tested; live model choice/wording for the new tools was not re-tested.
- Existing dependency/resource/bundle-size warnings remain.

## Next major chunk

A guided monthly forecast refresh: review updated history, refresh relevant live
factors, calculate the new forecast, review the current order book, then compare
and export by customer/product/month. Reuse existing services and keep separate
approvals for input changes, calculations and orders. Missing history, ambiguous
customer matches, stale sources and unknown order coverage must stop the workflow.
This is not a new production/inventory module. Client accuracy validation,
external-source permissions and deployment acceptance are still open.

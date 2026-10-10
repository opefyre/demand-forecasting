# Shared order review and comparison — 10 October 2026

## Delivered

- Assistant forecast, factor, order-reuse, scenario, input-mapping and correction
  proposals use the existing global Panel/Stack/Actions/Disclosure framework.
  Order reuse and order comparison share their receipts with the manual dialogs.
- Approvals uses the shared collection/table structure. Revision menus already
  use the shared fixed dialog and were verified, not rebuilt.
- Removed competing proposal/comparison/review appearance rules. No page-specific
  CSS or authored inline styles were added. Existing Vrolen accent retained.
- Counts, quantities, units and authored labels follow English/Farsi. Original
  customer names, identifiers and imported cells remain unchanged. Unknown
  quantities remain unknown, never silently zero.
- Method curves use centralized colours and line-pattern tokens. Appearance is
  assigned by the saved group's method index; hiding a method cannot recolour
  the others. All 24 supported slots have distinct colour/pattern pairs.
  Dots remain visible for isolated observations; missing values remain gaps.
- Order-comparison requests cannot overwrite a newly selected forecast context;
  duplicate clicks are blocked. Reviewed tokens and original-result preservation
  remain unchanged.
- Browser acceptance caught a missing request ID in company planning previews.
  Preview and submission now share one request ID; changed inputs reset it.
  This fixes the rejected Review quantities action without relaxing API validation.

## Executed verification

- 312 interface tests, 48 focused backend tests, 53 Cloudflare service tests and
  production build passed. Existing bundle-size/deprecation/resource warnings remain.
- Disposable loopback company fixture: four customers, two products, 36 history
  months, partial/full/no orders, two methods; actual stores/API/math, mocked
  identity/providers/AI. No live provider refresh or OpenAI call.
- English desktop comparison: green solid and blue dashed curves, 2px widths.
  Hiding the first method left the other colour/pattern unchanged.
- Farsi 390×844: fixed dialog 358×680, RTL, internal scrolling and document width
  390px. Aftab: 6 open + 54 expected = 60 tonnes; Pars: no orders but 15 expected.
- Complete local company handoff: draft CSV download; planning preview; planner
  submission; independent administrator approval; approved CSV via fixture API.
  Same-person approval was unavailable. Approved output preserved 12 rows, four
  customers, two products, three months, receiver policy and approval/source hashes.
  Remaining-forecast quantities total 113 tonnes (27/43/43); orders were not added
  twice. Full outlook is 135 tonnes including 2 already fulfilled.
- Shared Approvals refreshed to Approved on closing review. Farsi revision menu
  opened the current saved version successfully. The fixture was stopped after
  verification; the independent local demo remains running.
- Screenshot: `screenshots/shared-review-fa-mobile.png` (ignored local evidence).

## Deployment

Only `demandlab-forecast-edge` was updated, version
`6f277501-7536-4563-9bfd-d28aa3c8f031`. Identity, storage, engine image and other
services were not redeployed. Owner-only access, MFA and idle engine sleep remain
unchanged. Unauthenticated company API returns 401; local `/demand` returns 200.
The signed-in owner reopened the saved cloud method comparison after deployment:
same six monthly quantities, green solid / blue dashed 2px curves and all saved
filters. Screenshot: `screenshots/cloud-shared-method-comparison.png`.
Cloud cold-read completion was observed but not timed; no performance claim.

## Boundaries and next task

This is shared presentation plus a planning-request fix, not a new forecasting
algorithm or a claim of full app acceptance. Proposal markup is regression-tested;
every possible AI-generated proposal was not exercised in a live browser.

The older standalone Update orders path still uses its legacy file-first flow.
Advanced factor batch/scenario calculations also retain their previous workflow,
including applying orders after calculation in legacy paths. They need consolidation
with the reviewed grouped wizard. Existing saved schedules are not silently changed.

Next substantial slice: consolidate those remaining legacy order/factor actions,
measure cloud review/calculation latency, and verify numerical equivalence and
safe retries. Then run a full bilingual client-style acceptance pass. Real-client
accuracy, source/AI-provider eligibility and a permitted multi-person cloud pilot
remain separate release gates.

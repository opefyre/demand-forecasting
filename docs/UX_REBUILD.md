# Workflow rebuild — September 16

## Scope precedence — 22 September 2026

This file preserves historical UI verification. Current product requirements and
new acceptance work are in PRODUCT_REDESIGN.md and IMPLEMENTATION_CHECKLIST.md.
The product is now sales/demand forecasting only: current orders plus estimated
remaining demand, per customer/SKU/period. Older Supply, inventory, material and
capacity navigation requirements below are superseded, not remaining deliverables.
The sales-only multi-view dashboard and agentic assistant are requirements, not
features implemented by this documentation update. Existing app/demo are unchanged.

## 21 September follow-up (current implementation)

The earlier checklist below is historical, not acceptance of the entire approved
product scope. Current verification: 216 backend checks, 16 JavaScript checks and
the current production build. These are not whole-product acceptance.

- Shared field accessibility: native captions now target their controls, help text
  is attached through `aria-describedby`, and Radix select triggers receive the
  same bindings. Existing precise accessible names are preserved; nested fields
  own their labels. Six new React server-render checks cover identifiers, grouping,
  nested suffix markup, custom select bindings and existing names/descriptions.
- Browser keyboard check on saved input `Synthetic scheduled export`: clicking
  “How far ahead?” focuses Forecast horizon and attaches its guidance; Tab reaches
  method help then the selector; Enter opens, Down moves to Repeating seasonal
  demand, and Escape restores the unchanged Choose the best fit value and focus.
- Board line review dialog: opens on Review owner, Shift+Tab wraps inside the
  dialog to Save review, Escape closes and returns focus to Manage review: Board
  line. No data saved. Import layout checked at 1280×850; centered review dialog
  checked at 390×844. Browser error log empty. Disabled controls are skipped by
  initial-focus selection. Full role-specific browser checks and actual screen
  reader/RTL acceptance remain open; this bounded check does not establish them.

- Today now provides a source-backed daily queue with exact plan/supply navigation.
  Five viewport widths inspected; selector overflow corrected; filter, focus and
  supply action verified. See `TODAY_WORKFLOW.md` for scope, evidence and gaps.
- Owned reviews add centered owner/date/action forms, status/overdue filters and
  retained history. Laptop/small-screen visual checks and a synthetic review cycle
  passed; calculated risks remain separate from task completion. Full keyboard
  coverage and company assignment acceptance remain open.

- Plan-storage follow-up: all seven existing records migrated unchanged; browser reload
  still shows the published sample, 72 values and the 125-tonne adjustment. Both sample
  versions and exports reconcile after restart (`PLAN_STORAGE.md`). No UI redesign
  or new responsive-acceptance claim is implied by this backend-only change.

- Forecast inspected at 1440×900, 1280×800, 1024×768, 768×1024 and 390×844.
  Larger type is retained; oversized axis values and last-date clipping corrected.
  The uncertainty-band animation was disabled so it cannot detach during resize.
- Limited evidence is visible on the outlook, not hidden only in Accuracy. The
  first forecast quantity is labelled by its actual date, not misleadingly “next month”.
- External-context source/history views checked at 1280 and 390 widths.
- Synthetic saved-input rerun `5d1b2ebe361d` reproduced 5.6587% separate confirmation
  WAPE and now records source hashes. No client accuracy conclusion follows.
- Synthetic plan `af2fb75272` changes the first COA-ART-135 · Domestic period from
  116.4914 to 128.14 tonnes. Browser verified selection of approved-plan supply,
  its combined export link, and hardwood pulp changing from 475.1 to 481.9 tonnes.
  Desktop and 390px supply layouts checked; wide tables retain horizontal scrolling.
- Plan exports/supply share one quantity resolver; draft supply and changed source
  files fail clearly. API tests inspect exported workbook quantities, not just HTTP success.
- This does not complete every dialog/import/keyboard/RTL regression or the
  deployment roadmap. Remaining acceptance stays open in IMPLEMENTATION_CHECKLIST.md.

The earlier declaration of production readiness was not supported. The app had browser-only inputs, reset-prone mappings, connection tests presented as integrations, and product-relationship records presented as modelling. Automated unit tests did not establish a usable workflow.

## Acceptance checklist

- [x] Four everyday destinations: Forecast, Data, Plans, Supply. Keep labels visible on laptops.
- [x] Forecast methods and accuracy are contextual tabs; short actions use centered accessible dialogs.
- [x] Import progresses through files, columns, settings, review. Show actual file values.
- [x] Replacing files invalidates dependent validation; uploading future factors preserves history mapping.
- [x] Saved source bytes, sheet selection and mappings survive browser/server restart.
- [x] Validate dates, quantities, item identifiers and future factors before an expensive forecast.
- [x] Rerun methods and scenarios using saved inputs after refresh.
- [x] Hide fabricated source status, ornamental metrics, unsupported relationship/AI claims and repeated action buttons.
- [x] Contextual keyboard/touch help, accessible selects, focus management and consistent field dimensions.
- [x] Plan selection loads its exact run; published plans have no edit affordance.
- [x] Verify user flows at desktop/laptop/mobile sizes and exercise a full saved-input forecast.

## Still not production capabilities

Legacy connectors perform availability checks; the separate World Bank context integration ingests snapshots. Product relationships/promotions are records, not estimated causal models. Historical monitoring now requires matching evaluation evidence; live drift and automatic retraining remain unimplemented. Local plan storage is not multi-user authentication or role enforcement. These are not deployment settings and must not be claimed complete.

## Verification evidence

21 September import-save reliability:
- Same save request recovers the same immutable dataset; changed inputs with that
  request are rejected. Fully written files are atomically published without
  clobbering another writer. Separate-process retry tests verify one exact record.
- Folder acceptance serializes reviewers and recovers a process stop after dataset
  publication but before acknowledgment. This is not whole-app power-loss or
  distributed-storage certification.
- Opening unchanged saved data no longer creates an unfinished edit; its review
  shows Saved data, Done and Forecast. Changing classification counts as an edit.
- Save-and-forecast keeps the import open if job submission fails, retaining its
  save request and explaining that the inputs were saved. Browser failure injection
  for this network-error branch remains open; request persistence is unit-tested.
- Browser saved-input forecast `5d78ab8284a4` completed and opened with the correct
  short-history warning. No duplicate input dataset was created (`FOLDER_INPUTS.md`).
- 196 Python tests, ten JavaScript checks and the production build pass.

21 September repeat-import repair:
- Replacement history retains matching date/quantity/item/metadata/factor names.
  Missing columns are cleared for review, never substituted with guessed columns.
  Replacing future factors leaves history mapping intact. Production replacement
  still requires its independent mapping/date review.
- Existing dataset edits now have isolated persistent drafts, restored after
  reload. Restored inputs require fresh validation/acknowledgment. Errors restoring
  saved files are visible. Saving captures parent dataset and changed source roles,
  without changing previous datasets or forecast snapshots.
- Four new JavaScript checks plus the four existing chart-data checks pass; seven
  saved-workflow Python checks pass (including a new source-replacement lineage/
  immutability test). Production frontend build passes. Full suite not rerun for
  this bounded change; earlier full-suite evidence remains 185 checks.
- Browser: seed `64208d8e50394c148c0036c9e3f8abf2`, edit name/horizon, reload,
  reopen, validate with the same FX selection, acknowledge warning and save.
  Child `6cdb572096af43628d2493259bd0f97c` retains exact source IDs/factors,
  records its parent and has horizon 2; original remains horizon 1. Both are
  explicitly synthetic and no client file was modified.
- Actual file-picker replacement could not be completed through the current
  in-app browser controls (picker event timed out; native-app fallback unavailable).
  Mapping behavior is unit-tested, but this does not claim full browser acceptance
  of replacement uploads, automated ingestion or every recovery path.

21 September linked-version increment:
- Approved/published plans offer Create new version: short centered name/owner/
  reason form, same forecast, effective adjustments only, new draft status.
  Original comments/approvals are not copied as approvals of the new draft.
- New versions have parent/root identifiers and unique family version numbers.
  A frozen parent-adjustment snapshot powers Previous plan and From previous
  quantities, including export. Changed-only filtering uses that comparison.
  Retry identifiers prevent duplicate creation; conflicting reuse is rejected.
- Six new tests cover immutability, latest active adjustments, concurrent retry,
  branch numbering, validation, API behavior and previous-plan/export arithmetic.
- Browser-created draft `51f34a7686` branches from published `e2379cd021` and
  changes September COA-ART-135 from the previous 125 to 135 (+10), preserving
  the statistical 118.6565277319. Parent canonical-record SHA256 remains
  `b72ea8f06e59524a67aeb2b1ea2fab8f01378cac586c9ee3e28cdf06bca83f85`.
  `scripts/verify_plan_review.py` checks all 72 exported draft rows and lineage.
- Draft reload, changed-only previous-plan comparison and previous-version link
  verified in the browser. Centered creation form checked at 1280 and 390 px;
  final mobile form keeps all controls visible. Cancel creates no second draft.
- This is same-forecast revision, not an automatic roll into a new horizon.
  Identity/roles, multi-process plan persistence and client approval remain open.

21 September plan-review increment:
- Save opens the exact draft; selection survives reload. Review quantities use
  the export/supply resolver, with search, changed-only filter and 50-row pages.
- Edits begin at the current plan quantity. Current adjustments can be reversed
  with a reason; history remains. Return-to-draft/review actions are available.
- Forecast comparison now requires an explicit plan choice or Forecast only;
  View supply carries that exact plan. Publishing is labelled local-only, with
  no implied ERP transmission or authenticated identity/role enforcement.
- Browser sample plan `e2379cd021` from synthetic run `431fed798551`: draft →
  130-tonne adjustment → review → reversal → draft → 125-tonne adjustment →
  review → approval → publication → exact forecast comparison → supply.
  Baseline COA-ART-135 September remains 118.6565277319; plan is 125.
- `scripts/verify_plan_review.py` reconciles all 72 review/export rows, exported
  material rows, source hash and independent September PULP-HW requirement
  473.6500601117 (saved 473.650). Original client files were not changed.
- Two API checks cover review/export/reversal equality and invalid plan/override
  rejection. Missing review-control padding was corrected during laptop testing.
  Whole-app keyboard/RTL and client acceptance remain open.
- Final plan-review screenshots checked at 1280 and 390 px. DOM layout checks
  found no page-width overflow at 1440/1280/1024/768/390; this is scoped to this
  page, not whole-app acceptance. Pagination reaches the final 22 of 72 rows;
  Next disables on page 2. Browser error log was empty; viewport override reset.

21 September actual-results increment:
- Guided sample import, mappings, explicit unit/closure/reviewer, coverage review,
  immutable save, browser/server restart recovery, period breakdown and source
  download verified through the app. September excluded from prospective evidence
  when the forecast was issued after September began; sample labels remain visible.
- Visually inspected at 1280×850 and 390×844. Small-screen summaries stack, controls
  remain usable, and wide result tables scroll inside their surface. The comparison
  is restored after reload; absent evidence is not displayed as zero.
- 80 automated tests pass, including paired approval timing, timezone boundaries,
  duplicate/invalid actuals, partial coverage, zero denominators, row export,
  save-request retry and exact historical-comparison evidence.

21 September inventory increment:
- Completed stock upload → mapping → review → save → Supply projection in the
  browser with explicitly labelled synthetic data. Snapshot survived restart.
- Client MPS FG sheet suggested C/L/K/G/H/D correctly; Persian units and `032`
  pallet identifier remain visible. Empty stock date blocks validation and scrolls
  the error into view. Client draft is retained without saving invented stock.
- Fixed native date-input event retention found during live interaction.
- Visually checked 1280×800 and 390×844 stock screens and mobile client mapping.
  Mobile stock heading/search stack vertically; wide tables scroll internally.
  Document-width checks at 390/768/1024/1280/1440 show no page overflow. These are
  scoped inventory checks, not certification of every remaining product workflow.
- Current suite: 64 passing tests; production frontend build succeeds. Existing
  dependency deprecation and bundle-size warnings remain, without build failure.

- Browser: 1366×900, 1024×768 and 390×844. Checked the four-step sample import, responsive library/actions, accessible select, tap-to-open help, modal initial focus and Escape focus return, method rerun after reload, scenario totals, and published-plan read-only controls.
- Saved baseline `0a92b9d6b63c`: 720 rows, 12 items, 12-month forecast; 5.23% WAPE on 432 historical test points.
- AutoETS rerun `7409b082a757`: source files reused after refresh; 5.34% WAPE.
- Scenario `40c86922164b`: exactly 10% above its originating baseline, with unchanged history and no refit.
- Automated: 27 tests pass, including API uploads/selected-sheet persistence, invalid-input rejection, monthly alignment, future ambiguity, order netting and scenario immutability.
- These checks establish the listed local workflow only. The remaining roadmap in `IMPLEMENTATION_CHECKLIST.md` is open.

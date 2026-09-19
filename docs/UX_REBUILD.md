# Workflow rebuild — September 16

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

Current connectors perform availability checks; they do not synchronise usable datasets. Product relationships/promotions are records, not estimated causal models. Model monitoring compares runs without enforcing comparable populations. Local plan storage is not multi-user authentication or role enforcement. These are not deployment settings and must not be claimed complete.

## Verification evidence

- Browser: 1366×900, 1024×768 and 390×844. Checked the four-step sample import, responsive library/actions, accessible select, tap-to-open help, modal initial focus and Escape focus return, method rerun after reload, scenario totals, and published-plan read-only controls.
- Saved baseline `0a92b9d6b63c`: 720 rows, 12 items, 12-month forecast; 5.23% WAPE on 432 historical test points.
- AutoETS rerun `7409b082a757`: source files reused after refresh; 5.34% WAPE.
- Scenario `40c86922164b`: exactly 10% above its originating baseline, with unchanged history and no refit.
- Automated: 27 tests pass, including API uploads/selected-sheet persistence, invalid-input rejection, monthly alignment, future ambiguity, order netting and scenario immutability.
- These checks establish the listed local workflow only. The remaining roadmap in `IMPLEMENTATION_CHECKLIST.md` is open.

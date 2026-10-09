# Today: daily review entry point

Implemented 21 September 2026 inside the existing React/Radix/Phosphor app.
The default landing route is now `#today`; existing links to Forecast still work.
No additional dashboard framework, package, external feed or client-data upload was added.

## Scope and evidence

The selected saved forecast and explicit statistical/approved-plan quantity selector
control the page. Reviews and activity are restricted to that run, site and real/sample
classification. Sample context is visibly labelled. Approved supply uses the same
source-verified resolver as plan supply and export; failure never falls back to baseline.

Four summaries: independently checked historical error, distinct materials below their
supplied stock targets, distinct over-capacity lines, and the last actual period.
Unavailable checks are not zero. Historical error is not a future-accuracy promise;
material shortfalls are not service probabilities. No excess-stock risk or service
score is invented where the required evidence/policy is unavailable.

The decision queue includes:

- Plans awaiting review, opening their quantity-review page.
- One material/line decision at its earliest affected period, with number of affected
  periods, quantity and unit. Review opens the correct supply tab, item and period.
- Suspicious demand changes/zero-sales patterns, opening the exact forecast item.
  Suspected lost sales are explicitly not confirmed lost sales.
- Missing supply evidence or a missing separate accuracy check, leading to the
  relevant input or accuracy page.
- Monthly history ending before the latest completed calendar month. This uses the
  configured site time zone, not the computer's date or a guessed factory reporting SLA.
- A save-plan action when the selected run has no matching plans; empty workspaces
  receive one import action.

The list initially shows five decisions. Type filtering, filtered counts, Show more,
manual refresh and keyboard focus from Review decisions are implemented. Recent activity
links back to the exact plan. These actions navigate real pages; no sidebar page uses a modal.

## Verification

Eight new backend tests; full suite 174 passing tests. They cover empty state, distinct
risk counts/earliest-period routing, unavailable evidence, site/run/sample isolation,
monthly freshness, diagnostic wording, rejected draft/mismatched quantity basis, and
plan-resolver failure without fallback. Production frontend build passes with existing
bundle-size/font-resolution/Radix warnings.

Live synthetic run `431fed798551`, published plan `e2379cd021`:
10 decisions, six affected materials, three constrained lines and one demand-pattern
check. Historical error is 4.575412857238763% on saved independent test evidence.
`scripts/verify_today.py` reconciles every material/capacity decision, period, count
and displayed gap against the selected plan's supply rows.

Browser: material filtering, Show more (all six materials), All reset, keyboard
filter interaction, Review decisions focus and the Hardwood pulp action were exercised.
The material action kept published plan `e2379cd021`, September 2026 and Hardwood pulp;
the supply view showed 473.7 tonne required (display rounding), consistent with the
independent prior plan-output check. No sample or client records were altered.

The Today layout was inspected at 390, 768, 1024, 1280 and 1440 px. A 390px selector
overflow was found and corrected; document width equals viewport width at all five
sizes. Review links for every individual diagnostic, all missing/error screens in
the browser, and a full assistive-technology audit remain unverified.

## Owned review workflow — 21 September follow-up

Planners/admins can assign a named owner, due date, status and action/decision to
an existing queue item. A short centered Radix dialog records the change; it is
not a sidebar destination. Read-only users can inspect records but cannot save.
Owner names express intended responsibility, not accepted assignments or access
grants. Company sign-in identifies the person recording a change; local actions
are honestly attributed to Local session.

SQLite records are scoped to exact site, forecast, plan and source classification.
They include version, source-evidence fingerprint and append-only action history.
Each event retains its evidence snapshot. Stale evidence/versions return a conflict;
request replay does not duplicate changes. No record is created by simply viewing
the queue. Changed evidence returns a previously reviewed issue to active review,
preserving its previous decision, owner and due date.

To review, In progress, Overdue, Reviewed and All statuses intersect the existing
type filter. Overdue uses the site's calendar date; due today is not overdue. Marking
a review complete changes its workflow status only: supply quantities, forecast
evidence and risk totals do not change. Reviewed items remain accessible, and a
new recorded action can reopen one. Forecast options now include creation time to
distinguish runs sharing a name and history end date.

Verification: seven new review-store tests cover persistence, scope isolation,
review/reopen history, source changes including sub-display-rounding changes,
date/field guards, request replay and concurrent-update conflicts. Security tests
verify viewer/reviewer write denial. Full suite: 203 Python tests; production build
passes. Broader multi-user deployment and identity-directory assignment are not
claimed by these tests.

Browser: run `431fed798551`, **statistical forecast** basis (no approved plan),
decision `materials:PULP-HW`. Assigned Sample materials planner with due date
20 September, recorded In progress, filtered Overdue (one row), then recorded
Reviewed. The active queue decreased from ten to nine, Reviewed showed one,
and All statuses restored ten. Both notes remain in history. The displayed
51.9-tonne gap and totals of six material risks/three capacity risks stayed unchanged.
These are synthetic review records, not a real procurement assignment.

Centered form and queue inspected at 1280×850 and 390×844. Controls fit and the
viewport override was reset. Final reload retained the review and the clearer
forecast label; browser error log was empty. Pointer-based filters/history passed;
the attempted End/Enter status-selection shortcut did not change the selection,
so complete keyboard/assistive-technology acceptance remains open.

## Remaining approved work

This completes a bounded daily review entry point, not every operational decision.
Assignment acknowledgements, cross-plan/company queues, service and
excess-risk measures, weekly/daily freshness policies, actuals-driven plan-change
alerts, overdue-order escalation and real-site acceptance remain open. Broader identity,
integrations and forecasting requirements in PRODUCT_REDESIGN.md are unchanged.

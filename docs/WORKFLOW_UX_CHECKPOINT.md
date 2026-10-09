# Forecast-first navigation — 23 September 2026

## Latest focused correction

Follow-on review work: Monthly grid (customer × SKU × month), selectable quantity,
coverage filter/table and saved views are implemented. Saved views are private to
the signed-in subject (shared local identity in local-demo mode), persisted on the
server, and pin the order snapshot. They are presentation preferences, not new
approved forecasts. No-order status applies only to a fresh reviewed order source;
missing history and stale feeds remain separately flagged.

The sample Export customer view reconciles to 1,655.4 tonnes. Filtering to its
no-order periods gives 1,367.06 tonnes in both summary and monthly grid. Saving
and reopening “Demo · Export monthly” after reload restored customer, grid and
order version. CSV uses the same selected rows; absent filtered cells are “Not in
selection”, present unknown quantities stay “Unknown”.

Assistant job results retain their requested customer and show all matching SKUs.
New model-only results do not automatically inherit a previously reviewed order
book. Broader agent tools and live acceptance are still pending.

Supersedes the initial layout notes below: Customers is now a primary page and
Help is secondary navigation. Home's repeated instructional cards moved into
Help. Assistant is a plain composer using the active forecast and remembered or
latest order snapshot, with automatic model-role routing. No setup card, mode
picker, or forecast/order picker is shown. Readiness errors appear only after a
send attempt; real data sharing still requires explicit consent.

Customers are saved independently in `data/customers.sqlite3`. CSV/XLSX imports
preview before adding; duplicates reject the complete batch, never overwrite.
Active customer/product links can be included explicitly in real-data order
review via “Use customer directory”. Saved forecasts are immutable and no-order
customers remain eligible. This directory does not fabricate history for new
customers or silently add unrelated products to their demand.

Forecast controls are compact. Bar/trend/table views, grouping, quantity sorting,
filters/reset and filtered review CSV share the selected population and unit.
Planning exports are still full order-version exports with explicit scope.
Unknown quantities stay unknown, not zero. Trends use chronological months.

Verification: 250 backend tests and 24 frontend tests passed; production build
passed. Browser checks covered sample totals, customer filter/reset, sorted table,
trend chart, assistant empty state, and centered customer/product dialog.
Responsive checks at 390px and normal laptop width caught and corrected a legacy
toolbar stacking rule and product-row field margins. Help navigation/accordions
were also checked. Test customer writes used isolated temporary databases; no
dummy customer records were added to the user's workspace.
No live AI request or production-readiness claim. Remaining broader work includes
multi-turn assistant memory, customer edit/upload tools for the assistant,
customer-specific result navigation, connector expansion and client acceptance.

## Initial pass (historical)

Problem reported: opening the app offered records and controls without a clear
starting action. This checkpoint changes navigation and presentation, not the
forecasting mathematics. It does not establish market leadership or production
acceptance.

## Interaction model

- Home is the root route (`/` and `#today`). One primary action: add history,
  continue a meaningful unfinished import, open saved input ready for calculation,
  or create a new forecast. Existing forecasts are separate continuation rows.
- A compact four-step explanation establishes sequence: sales history → model
  calculation → customer orders → demand review/export. The step cards are not
  fake progress indicators or duplicate buttons.
- Sample exploration is a secondary action. Sample datasets do not count as real
  company progress. Empty/corrupt draft storage is not an unfinished import.
- Primary sidebar: Home, Forecast, Data, Assistant. Saved reviews and Settings are
  secondary. Every sidebar destination is a page, not a drawer or modal.
- Forecast (`#demand`) is the customer-order-aware demand view. Model diagnostics
  remain at `#forecast`, reached via “How was this calculated?”. Completed ordinary
  calculation jobs open the demand view with the next-step prompt for orders.
- Results show either chart or table, not both at once. Customer/product/month
  filters remain visible. Single-value unit and order-version selectors are hidden.
- Export is a centered action dialog. It asks whether the receiver already has
  orders, then offers Excel/CSV/JSON. Full-snapshot scope and draft status remain
  explicit; quantities and export policies are unchanged.
- Data excludes samples by default, with an explicit checkbox to reveal them.
  Saved reviews similarly separates sample/unclassified older records. No data,
  saved plans or forecasts were deleted. Unknown legacy provenance is not relabelled
  as real company data.

## Design references and interpretation

Reviewed the [Linear start guide](https://linear.app/docs/start-guide) and
[Notion sidebar guidance](https://www.notion.com/help/navigate-with-the-sidebar).
These informed a familiar persistent sidebar, explicit starting workflow and
secondary actions. The specific information hierarchy is an implementation choice
for sales forecasting, not a claim that all SaaS products use an identical design.
Existing Radix controls and Phosphor icons were reused; no new design framework.

## Acceptance evidence

- 21 JavaScript checks pass, including empty workspace, sample-only workspace,
  meaningful draft detection, saved-input stage and baseline/scenario separation.
- Production frontend build passes. Existing large-bundle warning remains.
- Browser: root Home → new forecast opens the upload/mapping/settings/review flow;
  Home → sample → chart/table and centered export dialog; Data sample toggle and
  Saved reviews destination checked against actual local records.
- Home and centered export dialog visually checked at 1280 px and 390 px; temporary
  viewport override reset. App left on Home with the local server running.
- Local calculations and saved sample values unchanged; no backend changes in
  this checkpoint. Previous 245-Python-test checkpoint is not counted as a new run.

Remaining acceptance: client usability sessions, full file-to-final-demand journey
with client order exports, live AI evaluation and the broader implementation
checklist. This update fixes the starting point and primary review hierarchy;
it is not a claim that every legacy advanced screen has been redesigned.

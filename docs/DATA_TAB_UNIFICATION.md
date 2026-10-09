# Data tab structure repair — 9 October

The previous repair standardized the outer page, not the tab interiors. This follow-up replaces those competing interiors.

## Completed

- All five tabs use one `Collection`: controls on the left, actions on the right, then a shared content surface.
- Your files, Customers, Orders, Factors and Connections use the existing shared table component. No separate record-card layouts.
- Common search/picker dimensions, typography, padding, gaps, backgrounds and row actions. Appearance is owned by `ui-framework.css`; values come from `tokens.css`. No authored inline styles.
- Orders use Add/Edit dialogs; coverage remains an expandable section. Cancel leaves the row unchanged. Saving still uses the existing version-checked order API.
- Customer forms, connection setup, weather forms and factor-file layouts reuse shared form/grid/action components. Removed redundant nested surfaces and old tab-specific CSS, including the separate live-source stylesheet.
- Existing provider permissions, refresh cooldowns, warnings, order/customer identities and saved forecast data remain intact.
- Fixed empty-state messages hiding loaded records. Added regression coverage using the real table empty-state contract.
- Fixed long dataset names enlarging the mobile layout. Tables retain readable columns and scroll within their content area.

## Verification

- **235 frontend tests passed**, including nine Data structure/form/empty-state/CSS ownership checks.
- Production build passed. Existing large-bundle advisory remains.
- Three backend frontend-route tests passed. The full backend suite was not rerun for this UI-only change; the earlier 673-test result belongs to the previous audit.
- Browser: all five tabs in English at desktop 1280 × 720, and in English/Persian at mobile 390 × 844. No horizontal page overflow in the final mobile checks.
- Desktop: all five toolbars share x=264, y=244, width=984 and height=44; content surfaces share x=264, y=312, width=984, padding=24. Table headings share 14px text and 12px/20px padding. Surface height varies with records, not a separate layout.
- Mobile: all five content surfaces share width=358, padding=20 and 14px body text. Wide tables scroll internally.
- Browser journeys: source search/empty state/details; Customer and Connection dialogs; Orders add/apply/edit/cancel/remove. The order test remained unsaved and was discarded. No new credentials, provider refreshes, AI calls or company-data writes were made by these checks.
- Language and viewport restored to English/default desktop.

## Screenshots

- [Your files](screenshots/data-unified-your-files.png)
- [Customers](screenshots/data-unified-customers.png)
- [Orders](screenshots/data-unified-orders.png)
- [Factors](screenshots/data-unified-factors.png)
- [Connections](screenshots/data-unified-connections.png)
- [Persian mobile](screenshots/data-unified-persian-mobile.png)

This closes the Data-tab structure discrepancy. It is not a claim that every other application workflow or forecasting model has been re-audited in this change.

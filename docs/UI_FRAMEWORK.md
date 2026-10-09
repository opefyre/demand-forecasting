# Shared interface framework

## Settings correction — 7 October 2026

The previous Settings acceptance was incorrect. Replacing CSS values with variables
did not eliminate separate layouts or conflicting component rules. Product units,
workspace, AI and scheduling used different markup and spacing conventions.

Settings now uses the same global components from `frontend/src/ui-layout.jsx`:
Panel, Stack, Grid, Actions, FieldGroup, DefinitionList and Disclosure. Appearance
is owned by `ui-framework.css`, imported once through `design-system.css`.
Pages provide content and actions; these components do not accept page-specific
appearance classes. No inline styles were added.

Removed obsolete unit, language, workspace and recurring-settings appearance rules.
Both the unit-definition form and schedule dialog use the shared form components.
Saved definitions, schedules, API contracts and calculations were not changed.

## Global contracts

- Section heading: 18px / 600 weight; every panel header has a 40px minimum height.
- Body and labels: 14px; labels have a shared 24px minimum height.
- Inputs and dropdowns: 44px height, 16px type, 8px/12px padding, 8px radius.
- Buttons: the existing global Button component; 40px height, 14px type, 8px/16px padding.
- Panel padding: 24px desktop, 20px compact; radius 16px.
- Main component spacing: 24px; form grids 16px; action gaps 8px.
- Table headings/body: shared 14px type; long reference text wraps in a generic note cell.
- All values are semantic tokens in `tokens.css`, not values declared by a page.
- Width follows one shared content column. Height follows content, not a fixed card height.
- Two/three-column form grids become one column on narrow screens.

## Verification

169 frontend tests pass and production build passes. New tests check actual rendered
Settings markup, require shared component ownership and reject dedicated Settings
appearance rules. These strengthen the earlier value-only token checks.

Browser checks: all five sections in English and Persian at 1280px and 390px.
Measured desktop panels were uniformly 804px wide with 24px padding; mobile panels
were 358px with 20px padding. Every checked input/dropdown was 44px high. Buttons,
heading/body type, radius and layout gaps matched the shared contracts. No page
overflow. Unit creation was opened and cancelled; the schedule dialog was opened
and closed without saving. No business data or credentials were changed.

Evidence: `docs/screenshots/settings-framework-measurements.json` and
`settings-framework-{workspace,units,ai,schedules,access}-persian.png`.
The saved-unit table was also checked; it fits the desktop panel without clipping.

## Boundary

This verifies all Settings sections and their forms, not a completed migration of
every other screen. Other active screens still have legacy page-specific layout
rules; tokenized values alone must not be described as a unified framework.
Future migrations must consume these shared components rather than add overrides.

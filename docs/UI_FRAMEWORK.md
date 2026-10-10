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

## Advanced factor migration — 10 October

Factor linking, grouped factor comparisons, preparation recommendations and
customer/product exposure profiles now consume the same shared forms, panels,
actions and disclosures. Fifty-two obsolete appearance rules were removed; fixed
dialogs and the global table-scroll behavior replace competing layouts.
See [factor workflow checkpoint](FACTOR_WORKFLOW_DESIGN.md) for measured mobile
profile checks, calculation/export evidence and the remaining browser boundaries.

## Shared picker repair — 10 October

The live-source list exposed a global sizing defect: root-level aliases referenced
Radix measurements that exist only on the open menu. The computed height was
unbounded, clipping the first options above the viewport. The shared picker now
resolves runtime measurements on its own content node, with a tokenized 340px
ceiling and internal scrolling. Menu, option and scroll-button appearance have
one owner in `ui-framework.css`; 42 competing legacy CSS lines were removed.
No page overrides or authored inline styles were introduced.

Browser verification at 1512×736: the long factor menu stayed between approximately
150px and 483px, with computed maximum height 340px. GSCPI and Brent were selected
by their visible names and the corresponding factor forms appeared. New regression
checks reject root-level Radix-select aliases and duplicate picker ownership.

Factor review now shows Checking… and clears prior approval before a new request.
Change factors is locked during pending wizard operations. Shared brand colours,
control dimensions, spacing, motion and reduced-motion behavior are retained.

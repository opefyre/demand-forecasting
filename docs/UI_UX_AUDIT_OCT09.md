# Whole-app UX repair

**Data follow-up:** the original check below covered outer page structure but did not eliminate differing tab interiors. Those are now replaced with shared collection/table/form components; see [DATA_TAB_UNIFICATION.md](DATA_TAB_UNIFICATION.md) for the separate changes and current verification.

## Actions

- [x] Shared page structure: header/actions, navigation/controls, content. Main pages use `Page`, `PageControls` and `PageTabs`; the global framework owns their appearance.
- [x] Remove redundant opening subtitles, repeated headings and developer copy, including the demand opening statement and generic file/server notices. Keep actionable data-quality and safety warnings.
- [x] Home: edge-to-edge second sidebar; toggle in its header; no repeated chat icons.
- [x] Home: Import sales, Customers & orders, View forecasts, with real destinations.
- [x] Conversations: accessible three-dot menu, rename, pin/unpin, archive/restore, recoverable deletion, private workspace link and text export. Search and folder filters included.
- [x] Review all main destinations, all five Data tabs, all five Settings sections, and the forecast setup sequence. Desktop English and narrow/mobile Persian checks; not every possible viewport/data combination.
- [x] Functional and automated checks: navigation, dialogs, saved chats, permissions, forecast filters/exports and input workflows.

## Repairs found during the audit

| Problem | Action |
| --- | --- |
| Data and Forecast had separate heading/spacing patterns | Both use the same structural framework; title/action row, controls, then content. Settings, Help, Approvals, input review and calculation details use the same contract. |
| Settings had its own navigation structure | Shared horizontal page tabs and shared Panel/form primitives. Product units uses input/forecast language rather than stock language. |
| Chat history appeared as a padded widget | Removed outside padding, gap and rounding. History sits directly beside the main sidebar, beneath the common top bar. |
| Repeated chat icons and pencil buttons | Title-only rows; three-dot menu appears on hover/focus and remains visible on narrow screens. |
| Home lacked direct tasks | Three compact actions alongside prompt suggestions, only on an empty chat. |
| Chat menu dialog lost keyboard focus | Shared menu-to-dialog handoff restores menu focus before opening the next surface. Rename and share inputs receive focus. |
| Fast navigation could lose a click during browser snapshots | Immediate state commits with shared CSS transitions; native page snapshots disabled for app operations. Regression checks cover rapid/out-of-order transitions. |
| Wizard retained the prior step's scroll offset | Shared layout resets internal scroll on step changes. Fixed modal dimensions remain independent of content height. |
| Missing comparison values looked like a broken chart | Unknown values are labelled; no empty chart when every estimate is missing; Check coverage opens the coverage view. No missing values are converted to zero. |
| Selecting a single month hid the line-chart value | A point is drawn when only one period is selected, in comparison and baseline trend charts. |
| Help described an old disconnected workflow | Updated to Data → unified Forecast modal → compare/filter/export. |
| Archived chats could appear actionable | Archived/Trash chats are read-only until restored; the server also rejects resuming their actions. |

## Verification

- Backend: **673 tests passed**, full discovery suite. Covers forecasting/order combinations, imports, factors, reviews, jobs, access controls and saved workflows; provider calls are mocked.
- Frontend: **226 tests passed**, full suite. Includes authored stylesheet/token scanning, no authored inline styles, single ownership of shared page/panel contracts, translation coverage, navigation motion, chat structure, dialog handoff and missing-comparison handling.
- Production frontend build passed. Build still reports a large-bundle advisory; no loading-time benchmark was performed.
- Browser: English desktop 1280×720; Persian phone 390×844 and narrow laptop 1024×768. Temporary viewport overrides reset after testing.
- Data and Forecast title rows both measured at **x=264, y=104** with the expanded desktop sidebar. No document-level horizontal overflow on inspected narrow/mobile pages; wide tables scroll inside their own containers.

### Browser journeys

| Area | Checks |
| --- | --- |
| Home | Welcome/composer, three quick-action destinations, expanded/collapsed navigation, history visibility, mobile history, Persian direction. |
| Chats | Synthetic conversation: rename, pin, archive, restore, Trash, restore, search, reopen, share-link copy and text download. Original name restored; no permanent deletion. |
| Data | Files, Customers, Orders, Factors and Connections; customer form opened/cancelled; order row added/removed without saving; folder form inspected/cancelled. No live refresh or new integration setup. |
| Forecast | Existing synthetic result, chart/table/coverage views, month filter, view CSV download, multiple-method comparison and missing-data states. Check coverage opens the correct view. Filtering Demo customer 001 showed both methods with numeric estimates (39.96 and 45.09 tonnes); selecting November left one table row; deselecting Last period removed that column/line; comparison CSV contained only the selected method/month. No new company forecast or approval created. |
| Wizard | Sales selection, factors/calendar/horizon, customer/order review, method choices; fixed desktop/mobile size and internal scroll. Run not submitted in the live workspace; calculation paths exercised by backend tests. |
| Settings | Workspace, Product units, AI settings, Schedules, Access. English desktop/Persian mobile; no settings or credentials saved. |
| Help / Approvals | Shared structure, translated guidance, empty review state; approval permissions exercised in automated tests, not a company release. |

## Evidence and boundaries

- Screenshots: `screenshots/oct09-home.png`, `screenshots/oct09-data.png`, `screenshots/oct09-forecast.png`, `screenshots/oct09-method-comparison.png`, `screenshots/oct09-home-persian-laptop.png`.
- Shared styles are authored through the central token registry and imported through the design-system entry point. Third-party chart/dialog libraries may generate runtime styles; no application-authored inline styles were introduced.
- Share is a **private owner-workspace link**, not public publishing and not a grant of access to other accounts. Text download supports sharing outside the app. Trash is recoverable; no permanent purge is exposed.
- Saved client names, imported names, chat messages and workspace names are not automatically translated or renamed. Synthetic provenance is retained internally; it is not presented as real client accuracy.
- Stale order reviews, stale Servix observations, and missing IMF permission remain genuine data/integration conditions, not decorative banners. They were not bypassed or silently treated as fresh.
- Browser checks are agent-run user journeys, **not real client user testing**. Tests do not establish production readiness, client forecast accuracy, or exhaustive coverage of every input/viewport/provider combination.
- Existing client data, original forecasts and model calculations were preserved. No paid OpenAI call was made for this audit.

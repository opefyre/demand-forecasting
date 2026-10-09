# Workflow refinement — 9 October 2026

- [x] Remove development labels and redundant interface copy. Keep source classification in metadata, not decorative badges.
- [x] Consolidate sales history, customers, orders, factors and connections in Data. Legacy Customers addresses open that tab.
- [x] Add manual conversation renaming and asynchronous short AI titles. A manual name cannot be overwritten by the title task.
- [x] Fixed forecast dialog with internal scrolling; skip native workspace snapshots while dialogs are open. Do not open the global calculation overlay or queue toast over this wizard.
- [x] Edit forecast horizon and calendar inline without reopening the import process. Changed settings create a new source version; original data stays unchanged.
- [x] Use the customer directory and saved orders automatically; simplify review. Customer files are optional, not required. Orders share the source lineage and use conflict-checked saves.
- [x] One named forecast containing multiple method results and filtered comparisons. Separate internal model receipts remain for evidence, but the Forecast picker shows one grouped item.
- [x] Test workflow, permissions, calculations, responsiveness and English/Persian.

## Verification

- 215 frontend tests; 52 backend tests; production build passed.
- Backend acceptance uses isolated synthetic data and real forecasting libraries. Tested mixed orders/no orders, unknown history, immutable evidence, persisted orders, versions, group consistency, permissions and chat ownership.
- Browser: completed a 10-month, two-method forecast named **October demand comparison** using existing synthetic history. One forecast appears in the picker; customer filtering and selecting one or both methods change the chart and table. Exported CSV matches the filtered figures (39.961333… and 45.088 tonnes per month for Demo customer 001).
- Dialog checked at 1280×720 and 390×844: fixed dimensions across steps, internal scroll, no horizontal document overflow. Customer review loads existing directory/orders and no customer upload is needed.
- Manual rename saved in the browser: **Synthetic forecast review**. English/Persian labels and RTL checked; a missing Save orders translation found during verification was repaired.
- AI title generation is tested with mocked provider responses, failures and parallel completion. Default title role is `gpt-4.1-nano`, configurable by `DEMANDLAB_AI_TITLE_MODEL`; uses the existing server-only credentials, sharing consent and call limits. No paid OpenAI request or external data-source refresh was made in this batch. Live title quality/access is not claimed as verified.
- Proof: `screenshots/workflow-method-comparison.png`. Local server restarted with the current backend and compiled interface.

## Boundaries

Synthetic fixtures do not establish client accuracy. Unknown customer history/order coverage still prevents a falsely complete total. Existing record names and original forecasts are preserved; unrelated runs are not merged merely because their names match. Forecast-engine tuning remains the separately agreed next phase.

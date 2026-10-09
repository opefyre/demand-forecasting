# Demo guide — 21 September 2026

Scope note, 22 September: the product requirements now focus exclusively on
sales/demand forecasting, combining current customer sales orders with calculated
remaining demand. The current demo has NOT yet been rebuilt for that scope.
Its delivery examples below concern incoming supply, not customer sales orders;
do not present them as the new order-aware forecasting functionality. Supply and
inventory steps are legacy capabilities, no longer target product features.

Open http://127.0.0.1:8010/#forecast on this computer. The local app is running.
If it has stopped, run `.venv/bin/python run.py` from the project directory.
This is a working local demonstration, not production acceptance.

## Five-minute walkthrough

1. **Forecast:** select **Synthetic range verification - 6 months**. This saved
   sample covers September 2026–February 2027. Show the connected history/forecast
   chart, change the product, and toggle the planning range. No new training run
   is needed for the presentation.
2. **Methods / Accuracy:** show the method comparison and separate later-period
   test. The displayed 4.6% error belongs to synthetic sample data; it is not a
   promise about the client's forecast accuracy. The range is an estimate, not
   guaranteed coverage.
3. **Plans:** open **Synthetic workflow verification** (published), then
   **Synthetic revised plan** (draft). Show the revision and quantity comparison.
   Keep the published sample unchanged.
4. **Supply → Inventory:** use the forecast baseline and **Sample stock · August
   2026**. For **PKG-KRAFT-120**, September has 50 tonnes opening stock and 183.7
   tonnes demand. With **No future receipts**, closing stock is −133.7 tonnes.
   Select **Demo · imported deliveries**: a confirmed 200-tonne purchase changes
   closing stock to 66.3 tonnes. Expand the full receipt schedule: one included
   purchase and one excluded, unconfirmed production completion. A positive
   month-end balance does not promise that no shortage occurs earlier.
5. **Today / Data:** show the review queue with owners and dates, then the saved
   inputs and repeat-file connection. Reviews track decisions; they do not
   silently change forecast quantities. Export the forecast if useful.

## Optional delivery-file demonstration

Use `sample_data/receipts_demo.csv` through Supply → Inventory → Add deliveries →
Import a delivery file. The saved version above already exists, so repeating this
step is optional.

Map Order → reference, Product → product, Outstanding → quantity, UOM → unit,
Usable → usable date, Type → delivery type, State → confirmation status.
Map Purchase → purchase delivery; Production → production completion;
Open → confirmed; Waiting → not confirmed. Review both rows and confirm they
are not already in opening stock. One saved schedule replaces another; it does
not add to an older schedule.

## What to say clearly

- Sample data is labelled. The two original client workbooks were not modified.
- The client sales workbook contains only January–July 2026 actuals. More actual
  history is needed to validate annual seasonality and client accuracy reliably.
- Tehran is configured, but city selection does not automatically supply reliable
  exchange rates, war impacts or future weather. Available external context and
  explicit assumptions must not be presented as proven causal forecast drivers.
- Real ERP ingestion, full operational replenishment, company sign-in deployment
  and broader acceptance remain unfinished. See `NEXT_WEEK_HANDOFF.md`.

## Verified at this checkpoint

222 Python tests and 16 JavaScript tests pass; the frontend build passes.
Delivery upload, mapping, review, save and stock reconciliation were exercised in
the browser, including affected laptop and phone layouts. This is bounded demo
verification, not a claim that every screen or production workflow is certified.

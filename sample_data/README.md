# Sample inputs

## Iran manufacturing sample

Use these files for the primary end-to-end sample:

1. `iran_manufacturing_history_60m.csv` — 60 months of synthetic Qazvin manufacturing history.
2. `iran_manufacturing_scenario_12m.csv` — 12 months of explicit operating and external assumptions.
3. `iran_scenario_event_notes.csv` — human-readable scenario documentation; it is not a model input.
4. `iran_operations_master.xlsx` — BOM, material master, open POs, capacity calendar, relationships and promotions.
5. `iran_actuals_followup_3m.csv` — three synthetic closed periods for forecast-value-add testing.

The sample covers 12 product/customer demand streams, inventory and safety stock, production capacity, BOM consumption, purchase orders, MOQ, supplier lead times, quality holds, product relationships, promotions, USD/IRR, inflation, industrial production, pulp prices, weather, energy curtailment, logistics, Iranian working days, and events. Every value is synthetic and intended only for validation and demonstration.

Regenerate it with:

```bash
.venv/bin/python scripts/generate_iran_sample_data.py
```

## Earlier paper and printing sample

Use these two files as inputs if you want to import the demo manually:

1. `paper_printing_history_36m.csv`
2. `paper_printing_scenario_6m.csv`

`scenario_event_notes.csv` only explains the synthetic incidents used in the demo.

The historical file contains 14 customer–SKU demand streams across 8 SKUs, 6 categories and 11 customers. The future file contains the next six monthly scenario assumptions for those same demand streams. It is retained as a smaller compatibility fixture.

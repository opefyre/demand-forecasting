# Synthetic factor-testing cases

Generated fixtures, not client history or real Iranian economic observations.
Quantities are plausible illustrative tonnes, not market-calibrated estimates.

Run `.venv/bin/python scripts/generate_factor_test_samples.py` to reproduce seed
7301. The manifest records each case and the meaning of the fields.

Six cases cover useful signals, irrelevant inputs, mixed customer behaviour,
changed relationships, sparse demand and short history. Each has three customers,
four customer/product series and preserved product codes `0001`–`0003`. Five cases
have 84 monthly observations per series; short history has 24. There are 1,776
historical sales rows across the cases and six months of future assumptions each.

`*-history.csv` is input. `*-assumptions.csv` explicitly holds factors at their
last recorded value. `*-withheld-actuals.csv` is separate test material: it must
not be mapped as future assumptions or used to select the forecast method.
The final historical test window is also reserved after model selection.

The full saved demo uses `mixed_customers` with existing StatsForecast and sklearn
models. Tests additionally run all six cases with seeds 7301 and 8107 using a
smaller existing-model catalog. Neither test proves actual client accuracy or
that exchange rates cause demand changes. No live source or OpenAI call is needed.

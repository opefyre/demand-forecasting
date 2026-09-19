from pathlib import Path
import sys
import shutil
import tempfile
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from app.data import prepare_history, build_future_covariates
from app.forecast_engine import run_forecast

history_raw = pd.read_csv(BASE / "sample_data" / "paper_printing_history_36m.csv")
future_raw = pd.read_csv(BASE / "sample_data" / "paper_printing_scenario_6m.csv")

drivers = [
    c for c in history_raw.columns
    if c not in {"date", "series_id", "sku", "category", "customer", "demand_tonnes", "revenue_eur"}
]
history, _ = prepare_history(
    history_raw,
    date_col="date",
    target_col="demand_tonnes",
    item_col="series_id",
    driver_cols=drivers,
    frequency="monthly",
)
future, _ = build_future_covariates(
    history,
    future_raw,
    future_date_col="date",
    future_item_col="series_id",
    known_driver_cols=drivers,
    frequency="monthly",
    horizon=6,
)

tmp = Path(tempfile.mkdtemp(prefix="demand-signal-smoke-"))
try:
    result = run_forecast(
        history=history,
        future_covariates=future,
        known_driver_cols=drivers,
        horizon=6,
        frequency="monthly",
        profile="fast",
        runs_dir=tmp,
    )
    assert result["forecast_rows"], "No forecast rows produced"
    assert result["leaderboard"], "No model leaderboard produced"
    assert result["metrics"]["validation_horizon"] == 6, "Backtest horizon does not match the forecast horizon"
    assert "bias_pct" in result["metrics"], "Bias metric missing"
    assert "interval_coverage_pct" in result["metrics"], "Interval coverage metric missing"
    assert result["series_diagnostics"], "Per-series diagnostics missing"
    assert all(row["p10"] <= row["p50"] <= row["p90"] for row in result["forecast_rows"]), "Invalid forecast interval"
    assert (tmp / result["run_id"] / "forecast_package.xlsx").exists(), "Excel export missing"
    print(f"  Smoke test: OK ({len(result['forecast_rows'])} forecast rows; best model: {result['best_model']})")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

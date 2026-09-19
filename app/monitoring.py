from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def build_monitoring(runs_dir: Path, current: dict | None = None) -> dict:
    paths = sorted(runs_dir.glob("*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    runs = []
    for path in paths[:12]:
        try:
            runs.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    if current and (not runs or runs[0].get("run_id") != current.get("run_id")):
        runs.insert(0, current)
    latest = runs[0] if runs else {}
    previous = runs[1] if len(runs) > 1 else {}
    current_metrics, previous_metrics = latest.get("metrics", {}), previous.get("metrics", {})
    wape_now, wape_before = current_metrics.get("wape_pct"), previous_metrics.get("wape_pct")
    model_drift = None if wape_now is None or wape_before is None else float(wape_now) - float(wape_before)

    leaderboard = latest.get("leaderboard", [])
    champion = leaderboard[0] if leaderboard else None
    challenger = leaderboard[1] if len(leaderboard) > 1 else None
    history = []
    for run in runs:
        metrics = run.get("metrics", {})
        history.append({
            "run_id": run.get("run_id"),
            "data_end": run.get("summary", {}).get("end"),
            "wape_pct": metrics.get("wape_pct"),
            "bias_pct": metrics.get("bias_pct"),
            "coverage_pct": metrics.get("interval_coverage_pct"),
            "best_model": run.get("best_model"),
            "evidence": metrics.get("evidence_level"),
        })

    quality_now = latest.get("summary", {}).get("data_quality_score")
    quality_before = previous.get("summary", {}).get("data_quality_score")
    data_drift = None if quality_now is None or quality_before is None else float(quality_now) - float(quality_before)
    reasons = []
    if model_drift is not None and model_drift > 3:
        reasons.append(f"Validation WAPE worsened by {model_drift:.1f} points.")
    if data_drift is not None and data_drift < -5:
        reasons.append(f"Data quality fell by {abs(data_drift):.1f} points.")
    if abs(float(current_metrics.get("bias_pct") or 0)) > 10:
        reasons.append("Absolute validation bias is above 10%.")
    retrain = bool(reasons) or not previous
    return {
        "champion": champion,
        "challenger": challenger,
        "history": history,
        "model_drift_wape_points": model_drift,
        "data_quality_drift_points": data_drift,
        "retrain": {"recommended": retrain, "reasons": reasons or (["Initial production baseline should be established."] if not previous else ["No retraining threshold was crossed."])},
        "policy": {"cadence": "monthly", "wape_trigger_points": 3, "bias_trigger_pct": 10, "data_quality_trigger_points": -5},
    }


def forecast_value_add(run: dict, plans: list[dict], actuals: pd.DataFrame) -> dict:
    required = {"item_id", "timestamp", "actual"}
    actuals = actuals.copy()
    actuals.columns = [str(c).strip().lower() for c in actuals.columns]
    missing = required - set(actuals.columns)
    if missing:
        raise ValueError(f"Actuals file needs: {', '.join(sorted(required))}")
    actuals["timestamp"] = pd.to_datetime(actuals["timestamp"]).dt.strftime("%Y-%m-%d")
    actuals["actual"] = pd.to_numeric(actuals["actual"], errors="coerce")
    forecast = pd.DataFrame(run.get("forecast_rows", []))
    if forecast.empty:
        raise ValueError("Run does not contain forecast rows.")
    forecast["timestamp"] = pd.to_datetime(forecast["timestamp"]).dt.strftime("%Y-%m-%d")
    merged = actuals.merge(forecast[["item_id", "timestamp", "baseline_mean"]], on=["item_id", "timestamp"], how="inner")
    if merged.empty:
        raise ValueError("No actual rows overlap the forecast periods and item identifiers.")
    plan = next((p for p in plans if p.get("run_id") == run.get("run_id") and p.get("status") in {"approved", "published"}), None)
    overrides = {(o["item_id"], o["period"]): o["value"] for o in (plan or {}).get("overrides", []) if not o.get("reverted_at")}
    merged["approved"] = [overrides.get((str(row.item_id), str(row.timestamp)), row.baseline_mean) for row in merged.itertuples()]
    denom = max(float(np.abs(merged["actual"]).sum()), 1e-9)
    baseline_error = float(np.abs(merged["actual"] - merged["baseline_mean"]).sum() / denom * 100)
    approved_error = float(np.abs(merged["actual"] - merged["approved"]).sum() / denom * 100)
    rows = []
    for item, group in merged.groupby("item_id"):
        item_denom = max(float(np.abs(group["actual"]).sum()), 1e-9)
        base = float(np.abs(group["actual"] - group["baseline_mean"]).sum() / item_denom * 100)
        approved = float(np.abs(group["actual"] - group["approved"]).sum() / item_denom * 100)
        rows.append({"item_id": item, "baseline_wape_pct": base, "approved_wape_pct": approved, "fva_points": base - approved, "observations": int(len(group))})
    return {"baseline_wape_pct": baseline_error, "approved_wape_pct": approved_error, "fva_points": baseline_error - approved_error, "observations": int(len(merged)), "plan_id": (plan or {}).get("id"), "items": rows}

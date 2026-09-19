from __future__ import annotations

import json
import math
import os
import time
import uuid
import warnings
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

if not os.environ.get("LOKY_MAX_CPU_COUNT"):
    os.environ["LOKY_MAX_CPU_COUNT"] = str(os.cpu_count() or 1)
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.forecasting.theta import ThetaModel

try:
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except Exception:
    LGBMRegressor = None
    LIGHTGBM_AVAILABLE = False


CALENDAR_PREFIX = "calendar_"


def _calendar_cols(row: pd.Series | dict) -> list[str]:
    keys = row.index if isinstance(row, pd.Series) else row.keys()
    return [str(c) for c in keys if str(c).startswith(CALENDAR_PREFIX)]


@dataclass
class ModelSpec:
    name: str
    kind: str
    estimator: object | None = None


def _json_safe(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if np.isnan(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _seasonal_lag(frequency: str) -> int:
    return {"monthly": 12, "weekly": 52, "daily": 7}[frequency]


def _lag_set(frequency: str, n_points: int) -> list[int]:
    candidates = [1, 2, 3]
    if n_points >= 8:
        candidates.extend([4, 6])
    seasonal = _seasonal_lag(frequency)
    if n_points >= seasonal + 6:
        candidates.append(seasonal)
    if n_points >= seasonal * 2 + 4:
        candidates.append(seasonal * 2)
    return sorted(set(x for x in candidates if x < n_points))


def _model_specs(profile: str, seed: int = 42) -> list[ModelSpec]:
    specs = [
        ModelSpec("Seasonal naive", "naive"),
        ModelSpec("AutoETS", "ets"),
        ModelSpec("AutoARIMA", "arima"),
        ModelSpec("Theta", "theta"),
        ModelSpec("Croston", "croston"),
        ModelSpec("TSB intermittent", "tsb"),
        ModelSpec("Ridge + drivers", "ml", Ridge(alpha=2.0)),
        ModelSpec(
            "Histogram gradient boosting",
            "ml",
            HistGradientBoostingRegressor(
                max_iter=120 if profile == "fast" else 155,
                learning_rate=0.05,
                l2_regularization=1.0,
                max_leaf_nodes=15,
                random_state=seed,
            ),
        ),
    ]
    if LIGHTGBM_AVAILABLE:
        specs.append(
            ModelSpec(
                "LightGBM + drivers",
                "ml",
                LGBMRegressor(
                    n_estimators=150 if profile == "fast" else 185,
                    learning_rate=0.035,
                    num_leaves=15,
                    max_depth=5,
                    min_child_samples=10,
                    subsample=0.9,
                    colsample_bytree=0.9,
                    reg_lambda=1.0,
                    random_state=seed,
                    n_jobs=-1,
                    verbosity=-1,
                ),
            )
        )
    if profile == "deep":
        specs.extend(
            [
                ModelSpec(
                    "Random forest",
                    "ml",
                    RandomForestRegressor(
                        n_estimators=70,
                        min_samples_leaf=2,
                        max_features=0.8,
                        random_state=seed,
                        n_jobs=1,
                    ),
                ),
                ModelSpec(
                    "Extra trees",
                    "ml",
                    ExtraTreesRegressor(
                        n_estimators=85,
                        min_samples_leaf=2,
                        max_features=0.9,
                        random_state=seed,
                        n_jobs=1,
                    ),
                ),
            ]
        )
    return specs


def _make_pipeline(estimator, X: pd.DataFrame) -> Pipeline:
    numeric = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
    categorical = [c for c in X.columns if c not in numeric]
    transformers = []
    if numeric:
        num_steps = [("imputer", SimpleImputer(strategy="median"))]
        if isinstance(estimator, Ridge):
            num_steps.append(("scale", StandardScaler()))
        transformers.append(("num", Pipeline(num_steps), numeric))
    if categorical:
        transformers.append(
            (
                "cat",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical,
            )
        )
    pre = ColumnTransformer(transformers=transformers, remainder="drop", sparse_threshold=0)
    return Pipeline([("prep", pre), ("model", clone(estimator))])


def _feature_row(
    *,
    target_history: list[float],
    driver_row: pd.Series | dict,
    time_idx: int,
    lags: list[int],
    known_driver_cols: list[str],
    item_id: str,
    forecast_step: int = 1,
) -> dict:
    row: dict[str, object] = {
        "time_idx": float(time_idx),
        "forecast_step": float(max(1, forecast_step)),
        "item_id": str(item_id),
    }
    for lag in lags:
        row[f"lag_{lag}"] = float(target_history[-lag]) if len(target_history) >= lag else np.nan
    for window in [2, 3, 6, 12]:
        vals = target_history[-window:] if target_history else []
        row[f"rolling_mean_{window}"] = float(np.mean(vals)) if vals else np.nan
        row[f"rolling_median_{window}"] = float(np.median(vals)) if vals else np.nan
        row[f"nonzero_rate_{window}"] = float(np.mean(np.asarray(vals) > 1e-9)) if vals else 0.0
    for span in [3, 6, 12]:
        vals = np.asarray(target_history[-max(span * 3, span):], dtype=float)
        if len(vals):
            alpha = 2.0 / (span + 1.0)
            ewm = float(vals[0])
            for value in vals[1:]:
                ewm = alpha * float(value) + (1.0 - alpha) * ewm
            row[f"ewm_{span}"] = ewm
        else:
            row[f"ewm_{span}"] = np.nan
    vals3 = target_history[-3:] if target_history else []
    vals6 = target_history[-6:] if target_history else []
    row["rolling_std_3"] = float(np.std(vals3, ddof=0)) if len(vals3) >= 2 else 0.0
    row["rolling_std_6"] = float(np.std(vals6, ddof=0)) if len(vals6) >= 2 else 0.0
    if len(target_history) >= 4:
        recent = float(np.mean(target_history[-2:]))
        prior = float(np.mean(target_history[-4:-2]))
        row["recent_momentum"] = (recent / prior - 1.0) if abs(prior) > 1e-9 else 0.0
    else:
        row["recent_momentum"] = 0.0
    zero_run = 0
    for value in reversed(target_history):
        if float(value) > 1e-9:
            break
        zero_run += 1
    row["zero_run_length"] = float(zero_run)
    if len(target_history) >= 12:
        recent_mean = float(np.mean(target_history[-3:]))
        annual_mean = float(np.mean(target_history[-12:]))
        row["seasonal_level_ratio"] = recent_mean / annual_mean if abs(annual_mean) > 1e-9 else 1.0
    else:
        row["seasonal_level_ratio"] = 1.0
    for col in list(dict.fromkeys(known_driver_cols + _calendar_cols(driver_row))):
        if col in driver_row:
            val = driver_row[col]
            row[col] = val.item() if hasattr(val, "item") else val
    return row


def _supervised_frame(grp: pd.DataFrame, known_driver_cols: list[str], lags: list[int]) -> tuple[pd.DataFrame, pd.Series]:
    grp = grp.sort_values("timestamp").reset_index(drop=True)
    targets = grp["target"].astype(float).tolist()
    item_id = str(grp.iloc[0]["item_id"]) if len(grp) else "Unknown"
    rows: list[dict] = []
    ys: list[float] = []
    warmup = max(max(lags, default=1), 3)
    for i in range(warmup, len(grp)):
        rows.append(
            _feature_row(
                target_history=targets[:i],
                driver_row=grp.iloc[i],
                time_idx=i,
                lags=lags,
                known_driver_cols=known_driver_cols,
                item_id=item_id,
            )
        )
        ys.append(targets[i])
    return pd.DataFrame(rows), pd.Series(ys, dtype=float)


def _global_supervised_frame(history: pd.DataFrame, known_driver_cols: list[str], lags: list[int]) -> tuple[pd.DataFrame, pd.Series]:
    frames = []
    targets = []
    for _, grp in history.groupby("item_id", sort=False):
        X, y = _supervised_frame(grp, known_driver_cols, lags)
        if len(X):
            frames.append(X)
            targets.append(y)
    if not frames:
        return pd.DataFrame(), pd.Series(dtype=float)
    return pd.concat(frames, ignore_index=True), pd.concat(targets, ignore_index=True)


def _direct_supervised_frame(
    grp: pd.DataFrame,
    known_driver_cols: list[str],
    lags: list[int],
    max_horizon: int,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build a direct multi-horizon training frame.

    Each row predicts a specific future step from observed history only. This avoids
    feeding a model's own predictions back into later steps, a common source of
    long-horizon flattening in recursive forecasts.
    """
    grp = grp.sort_values("timestamp").reset_index(drop=True)
    targets = grp["target"].astype(float).tolist()
    item_id = str(grp.iloc[0]["item_id"]) if len(grp) else "Unknown"
    rows: list[dict] = []
    ys: list[float] = []
    warmup = max(max(lags, default=1), 3)
    for origin in range(warmup, len(grp)):
        horizon_here = min(max_horizon, len(grp) - origin)
        for step in range(1, horizon_here + 1):
            target_idx = origin + step - 1
            rows.append(
                _feature_row(
                    target_history=targets[:origin],
                    driver_row=grp.iloc[target_idx],
                    time_idx=target_idx,
                    lags=lags,
                    known_driver_cols=known_driver_cols,
                    item_id=item_id,
                    forecast_step=step,
                )
            )
            ys.append(targets[target_idx])
    return pd.DataFrame(rows), pd.Series(ys, dtype=float)


def _global_direct_supervised_frame(
    history: pd.DataFrame,
    known_driver_cols: list[str],
    lags: list[int],
    max_horizon: int,
) -> tuple[pd.DataFrame, pd.Series]:
    frames: list[pd.DataFrame] = []
    targets: list[pd.Series] = []
    for _, grp in history.groupby("item_id", sort=False):
        X, y = _direct_supervised_frame(grp, known_driver_cols, lags, max_horizon)
        if len(X):
            frames.append(X)
            targets.append(y)
    if not frames:
        return pd.DataFrame(), pd.Series(dtype=float)
    return pd.concat(frames, ignore_index=True), pd.concat(targets, ignore_index=True)


def _naive_forecast(target_history: list[float], steps: int, seasonal_lag: int) -> list[float]:
    hist = [float(x) for x in target_history]
    out: list[float] = []
    for _ in range(steps):
        if len(hist) >= seasonal_lag:
            val = hist[-seasonal_lag]
        elif len(hist) >= 3:
            val = float(np.mean(hist[-3:]))
        elif hist:
            val = hist[-1]
        else:
            val = 0.0
        val = max(0.0, float(val))
        out.append(val)
        hist.append(val)
    return out


def _ets_forecast(target_history: list[float], steps: int, seasonal_lag: int) -> list[float]:
    y = np.asarray(target_history, dtype=float)
    if len(y) < 5:
        return _naive_forecast(target_history, steps, seasonal_lag)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            if len(y) >= seasonal_lag * 2:
                fit = ExponentialSmoothing(
                    y,
                    trend="add",
                    damped_trend=True,
                    seasonal="add",
                    seasonal_periods=seasonal_lag,
                    initialization_method="estimated",
                ).fit(optimized=True, use_brute=False)
            else:
                fit = ExponentialSmoothing(
                    y,
                    trend="add",
                    damped_trend=True,
                    initialization_method="estimated",
                ).fit(optimized=True, use_brute=False)
            return [max(0.0, float(v)) for v in fit.forecast(steps)]
        except Exception:
            return _naive_forecast(target_history, steps, seasonal_lag)


def _arima_forecast(target_history: list[float], steps: int, seasonal_lag: int) -> list[float]:
    y = np.asarray(target_history, dtype=float)
    if len(y) < 8:
        return _naive_forecast(target_history, steps, seasonal_lag)
    # Small, deterministic information-criterion search. It is intentionally bounded
    # so portfolio runs remain practical while avoiding a misleading fixed ARIMA.
    orders = [(0, 1, 1), (1, 1, 0), (1, 1, 1), (2, 1, 0), (0, 1, 2), (1, 0, 1)]
    best_fit = None
    best_aic = math.inf
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for order in orders:
            try:
                fit = ARIMA(y, order=order, trend=None).fit()
                if np.isfinite(fit.aic) and fit.aic < best_aic:
                    best_fit, best_aic = fit, float(fit.aic)
            except Exception:
                continue
    if best_fit is None:
        return _naive_forecast(target_history, steps, seasonal_lag)
    try:
        return [max(0.0, float(v)) for v in best_fit.forecast(steps)]
    except Exception:
        return _naive_forecast(target_history, steps, seasonal_lag)


def _theta_forecast(target_history: list[float], steps: int, seasonal_lag: int) -> list[float]:
    y = np.asarray(target_history, dtype=float)
    if len(y) < 8:
        return _naive_forecast(target_history, steps, seasonal_lag)
    period = seasonal_lag if len(y) >= seasonal_lag * 2 else 1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            fit = ThetaModel(y, period=period, deseasonalize=period > 1).fit()
            return [max(0.0, float(v)) for v in fit.forecast(steps)]
        except Exception:
            return _naive_forecast(target_history, steps, seasonal_lag)


def _croston_forecast(target_history: list[float], steps: int, alpha: float = 0.12) -> list[float]:
    y = np.asarray(target_history, dtype=float)
    nz = np.flatnonzero(y > 1e-9)
    if len(nz) == 0:
        return [0.0] * steps
    first = int(nz[0])
    z = float(y[first])
    p = float(first + 1)
    interval = 1.0
    for t in range(first + 1, len(y)):
        if y[t] > 1e-9:
            z = alpha * float(y[t]) + (1 - alpha) * z
            p = alpha * interval + (1 - alpha) * p
            interval = 1.0
        else:
            interval += 1.0
    f = max(0.0, z / max(p, 1e-9))
    return [f] * steps


def _tsb_forecast(target_history: list[float], steps: int, alpha: float = 0.18, beta: float = 0.12) -> list[float]:
    y = np.asarray(target_history, dtype=float)
    nz = np.flatnonzero(y > 1e-9)
    if len(nz) == 0:
        return [0.0] * steps
    z = float(y[nz[0]])
    p = min(1.0, max(0.01, len(nz) / max(len(y), 1)))
    for value in y:
        occurrence = 1.0 if value > 1e-9 else 0.0
        p = beta * occurrence + (1 - beta) * p
        if occurrence:
            z = alpha * float(value) + (1 - alpha) * z
    f = max(0.0, p * z)
    return [f] * steps


def _stat_forecast(spec: ModelSpec, target_history: list[float], steps: int, seasonal_lag: int) -> list[float]:
    if spec.kind == "naive":
        return _naive_forecast(target_history, steps, seasonal_lag)
    if spec.kind == "ets":
        return _ets_forecast(target_history, steps, seasonal_lag)
    if spec.kind == "arima":
        return _arima_forecast(target_history, steps, seasonal_lag)
    if spec.kind == "theta":
        return _theta_forecast(target_history, steps, seasonal_lag)
    if spec.kind == "croston":
        return _croston_forecast(target_history, steps)
    if spec.kind == "tsb":
        return _tsb_forecast(target_history, steps)
    raise ValueError(f"Unknown statistical model: {spec.kind}")


def _recursive_predict(
    model: Pipeline,
    *,
    target_history: list[float],
    future_rows: pd.DataFrame,
    lags: list[int],
    known_driver_cols: list[str],
    start_time_idx: int,
    item_id: str,
) -> list[float]:
    hist = [float(x) for x in target_history]
    preds: list[float] = []
    for step, (_, driver_row) in enumerate(future_rows.iterrows()):
        x = pd.DataFrame(
            [
                _feature_row(
                    target_history=hist,
                    driver_row=driver_row,
                    time_idx=start_time_idx + step,
                    lags=lags,
                    known_driver_cols=known_driver_cols,
                    item_id=item_id,
                )
            ]
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="X does not have valid feature names.*")
            pred = max(0.0, float(model.predict(x)[0]))
        preds.append(pred)
        hist.append(pred)
    return preds


def _direct_predict(
    model: Pipeline,
    *,
    target_history: list[float],
    future_rows: pd.DataFrame,
    lags: list[int],
    known_driver_cols: list[str],
    start_time_idx: int,
    item_id: str,
) -> list[float]:
    """Predict every future step from the same observed origin."""
    features = []
    for step, (_, driver_row) in enumerate(future_rows.iterrows(), start=1):
        features.append(
            _feature_row(
                target_history=target_history,
                driver_row=driver_row,
                time_idx=start_time_idx + step - 1,
                lags=lags,
                known_driver_cols=known_driver_cols,
                item_id=item_id,
                forecast_step=step,
            )
        )
    if not features:
        return []
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="X does not have valid feature names.*")
        values = model.predict(pd.DataFrame(features))
    return [max(0.0, float(value)) for value in values]


def _wape(actual: np.ndarray, pred: np.ndarray) -> float:
    denom = float(np.abs(actual).sum())
    if denom <= 1e-9:
        return float(np.mean(np.abs(actual - pred))) if len(actual) else math.inf
    return float(np.abs(actual - pred).sum() / denom)


def _smape(actual: np.ndarray, pred: np.ndarray) -> float:
    denom = np.abs(actual) + np.abs(pred)
    valid = denom > 1e-9
    return float(np.mean(2.0 * np.abs(actual[valid] - pred[valid]) / denom[valid])) if valid.any() else 0.0


def _bias(actual: np.ndarray, pred: np.ndarray) -> float:
    denom = float(np.abs(actual).sum())
    return float((pred - actual).sum() / denom) if denom > 1e-9 else 0.0


def _metric_bundle(actual: np.ndarray, pred: np.ndarray) -> dict[str, float | None]:
    if not len(actual):
        return {"wape_pct": None, "mae": None, "rmse": None, "smape_pct": None, "bias_pct": None}
    errors = actual - pred
    return {
        "wape_pct": _wape(actual, pred) * 100.0,
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "smape_pct": _smape(actual, pred) * 100.0,
        "bias_pct": _bias(actual, pred) * 100.0,
    }


def _series_profile(values: np.ndarray, seasonal_lag: int) -> dict:
    nonzero = np.flatnonzero(values > 1e-9)
    if len(nonzero) >= 2:
        adi = float(np.mean(np.diff(nonzero)))
        nz = values[nonzero]
        cv2 = float((np.std(nz) / max(np.mean(nz), 1e-9)) ** 2)
    elif len(nonzero) == 1:
        adi, cv2 = float(len(values)), 0.0
    else:
        adi, cv2 = float(len(values)), 0.0
    if adi < 1.32 and cv2 < 0.49:
        demand_class = "smooth"
    elif adi < 1.32:
        demand_class = "erratic"
    elif cv2 < 0.49:
        demand_class = "intermittent"
    else:
        demand_class = "lumpy"

    seasonality_strength = 0.0
    if len(values) >= seasonal_lag * 2 and np.std(values) > 1e-9:
        seasonality_strength = float(np.clip(np.corrcoef(values[seasonal_lag:], values[:-seasonal_lag])[0, 1], -1, 1))
        if not np.isfinite(seasonality_strength):
            seasonality_strength = 0.0
    isolated_zero_count = 0
    if len(values) >= 3:
        isolated_zero_count = int(sum(
            values[index] <= 1e-9 and values[index - 1] > 1e-9 and values[index + 1] > 1e-9
            for index in range(1, len(values) - 1)
        ))
    window = max(3, min(seasonal_lag, len(values) // 3))
    earlier = values[-2 * window:-window] if len(values) >= 2 * window else values[:window]
    recent = values[-window:] if len(values) >= window else values
    earlier_mean = float(np.mean(earlier)) if len(earlier) else 0.0
    recent_mean = float(np.mean(recent)) if len(recent) else 0.0
    pooled = float(np.std(np.concatenate([earlier, recent]))) if len(earlier) and len(recent) else 0.0
    structural_break_score = abs(recent_mean - earlier_mean) / max(pooled, 1e-9)
    relative_shift = abs(recent_mean - earlier_mean) / max(abs(earlier_mean), 1e-9)
    structural_break = bool(structural_break_score >= 0.8 and relative_shift >= 0.15)
    if len(values) < max(12, seasonal_lag):
        lifecycle = "new"
    elif recent_mean > earlier_mean * 1.15:
        lifecycle = "growth"
    elif recent_mean < earlier_mean * 0.85:
        lifecycle = "decline"
    else:
        lifecycle = "mature"
    return {
        "demand_class": demand_class,
        "average_demand_interval": adi,
        "squared_coefficient_variation": cv2,
        "zero_share": float(np.mean(values <= 1e-9)) if len(values) else 0.0,
        "seasonality_strength": max(0.0, seasonality_strength),
        "history_points": int(len(values)),
        "lifecycle": lifecycle,
        "structural_break_suspected": structural_break,
        "structural_break_score": structural_break_score,
        "stockout_or_lost_sales_suspected": isolated_zero_count > 0,
        "isolated_zero_periods": isolated_zero_count,
    }



def _weights_from_wapes(wapes: dict[str, float]) -> dict[str, float]:
    finite = {k: v for k, v in wapes.items() if np.isfinite(v)}
    if not finite:
        return {"Seasonal naive": 1.0}
    best = min(finite.values())
    # Avoid diluting a strong ensemble with models that failed badly on held-out data.
    eligible = {
        k: v for k, v in finite.items()
        if v <= max(best * 1.75, best + 0.12)
    }
    eligible = dict(sorted(eligible.items(), key=lambda pair: pair[1])[:6]) or {min(finite, key=finite.get): best}
    raw = {
        k: math.exp(-4.0 * max(0.0, v - best)) / max(v, 0.025)
        for k, v in eligible.items()
    }
    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}


METHOD_GROUPS = {
    "seasonal": {"Seasonal naive", "AutoETS", "Theta", "AutoARIMA"},
    "trend": {"AutoETS", "Theta", "AutoARIMA"},
    "intermittent": {"Croston", "TSB intermittent", "Seasonal naive"},
    "driver": {
        "Ridge + drivers",
        "Histogram gradient boosting",
        "LightGBM + drivers",
        "Random forest",
        "Extra trees",
    },
}


def _select_method_weights(wapes: dict[str, float], method: str) -> dict[str, float]:
    method = (method or "recommended").strip()
    if method == "recommended":
        return _weights_from_wapes(wapes)
    if method in METHOD_GROUPS:
        allowed = METHOD_GROUPS[method]
    elif method.startswith("model:"):
        allowed = {method.split(":", 1)[1]}
    else:
        allowed = {method}
    eligible = {name: score for name, score in wapes.items() if name in allowed and np.isfinite(score)}
    if not eligible:
        available = ", ".join(sorted(wapes))
        raise ValueError(f"Selected forecasting method is unavailable. Available methods: {available}")
    if len(eligible) == 1 or method.startswith("model:"):
        return {min(eligible, key=eligible.get): 1.0}
    return _weights_from_wapes(eligible)

def _rolling_folds(
    history: pd.DataFrame,
    frequency: str,
    profile: str,
    horizon: int,
) -> tuple[list[tuple[pd.Timestamp, list[pd.Timestamp]]], int]:
    dates = [pd.Timestamp(x) for x in sorted(pd.to_datetime(history["timestamp"]).unique())]
    if len(dates) < 6:
        split = max(3, len(dates) - 1)
        return [(dates[split], dates[split:])], len(dates[split:])
    max_folds = 3 if profile == "deep" else 2
    seasonal = _seasonal_lag(frequency)
    min_train = max(8, seasonal + 4 if len(dates) >= seasonal + 8 else 6)
    available = max(1, len(dates) - min_train)
    fold_h = min(max(1, int(horizon)), available)
    fold_count = min(max_folds, max(1, available // fold_h))
    first_origin = len(dates) - fold_count * fold_h
    origins = [first_origin + i * fold_h for i in range(fold_count)]
    origins = [o for o in origins if o >= min_train and dates[o:o + fold_h]]
    if not origins:
        origin = max(3, len(dates) - fold_h)
        origins = [origin]
    return [(dates[o], dates[o:o + fold_h]) for o in origins], fold_h


def _fit_backtest(
    history: pd.DataFrame,
    known_driver_cols: list[str],
    horizon: int,
    frequency: str,
    profile: str,
    method_selection: str,
):
    specs = _model_specs(profile)
    records: dict[str, dict[tuple[str, str], tuple[float, float]]] = {spec.name: {} for spec in specs}
    actual_by_key: dict[tuple[str, str], float] = {}
    fit_times: dict[str, float] = {spec.name: 0.0 for spec in specs}
    seasonal = _seasonal_lag(frequency)
    folds, validation_horizon = _rolling_folds(history, frequency, profile, horizon)
    residuals_by_item_step: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))

    for val_start, val_dates in folds:
        train_history = history[pd.to_datetime(history["timestamp"]) < val_start].copy()
        val_history = history[pd.to_datetime(history["timestamp"]).isin(val_dates)].copy()
        if train_history.empty or val_history.empty:
            continue
        min_train = int(train_history.groupby("item_id").size().min())
        lags = _lag_set(frequency, min_train)
        X_all, y_all = _global_direct_supervised_frame(
            train_history,
            known_driver_cols,
            lags,
            max_horizon=max(1, len(val_dates)),
        )

        fitted_ml: dict[str, Pipeline] = {}
        for spec in specs:
            if spec.kind != "ml" or len(X_all) < 12:
                continue
            started = time.perf_counter()
            try:
                pipe = _make_pipeline(spec.estimator, X_all)
                pipe.fit(X_all, y_all)
                fitted_ml[spec.name] = pipe
            except Exception:
                pass
            fit_times[spec.name] += time.perf_counter() - started

        for item_id, val_grp in val_history.groupby("item_id", sort=False):
            item_id = str(item_id)
            val_grp = val_grp.sort_values("timestamp").reset_index(drop=True)
            train_grp = train_history[train_history["item_id"].astype(str) == item_id].sort_values("timestamp").reset_index(drop=True)
            if train_grp.empty:
                continue
            target_hist = train_grp["target"].astype(float).tolist()
            y_actual = val_grp["target"].astype(float).to_numpy()
            for idx, row in val_grp.iterrows():
                key = (item_id, pd.Timestamp(row["timestamp"]).strftime("%Y-%m-%d"))
                actual_by_key[key] = float(y_actual[idx])
            for spec in specs:
                started = time.perf_counter()
                try:
                    if spec.kind == "ml" and spec.name in fitted_ml:
                        preds = _direct_predict(
                            fitted_ml[spec.name],
                            target_history=target_hist,
                            future_rows=val_grp,
                            lags=lags,
                            known_driver_cols=known_driver_cols,
                            start_time_idx=len(train_grp),
                            item_id=item_id,
                        )
                    elif spec.kind == "ml":
                        preds = _naive_forecast(target_hist, len(val_grp), seasonal)
                    else:
                        preds = _stat_forecast(spec, target_hist, len(val_grp), seasonal)
                except Exception:
                    preds = _naive_forecast(target_hist, len(val_grp), seasonal)
                fit_times[spec.name] += time.perf_counter() - started
                for idx, pred in enumerate(preds):
                    row = val_grp.iloc[idx]
                    key = (item_id, pd.Timestamp(row["timestamp"]).strftime("%Y-%m-%d"))
                    records[spec.name][key] = (float(y_actual[idx]), float(pred))

    model_wapes: dict[str, float] = {}
    model_metrics: dict[str, dict] = {}
    step_by_key: dict[tuple[str, str], int] = {}
    for item_id in sorted({key[0] for key in actual_by_key}):
        item_keys = sorted((key for key in actual_by_key if key[0] == item_id), key=lambda key: key[1])
        for index, key in enumerate(item_keys):
            step_by_key[key] = index % max(validation_horizon, 1)
    for spec in specs:
        pairs = list(records[spec.name].values())
        actual = np.array([p[0] for p in pairs], dtype=float)
        pred = np.array([p[1] for p in pairs], dtype=float)
        model_wapes[spec.name] = _wape(actual, pred) if len(actual) else math.inf
        model_metrics[spec.name] = _metric_bundle(actual, pred)
        horizon_rows = []
        for step in range(max(validation_horizon, 1)):
            step_pairs = [pair for key, pair in records[spec.name].items() if step_by_key.get(key) == step]
            if not step_pairs:
                continue
            step_actual = np.asarray([pair[0] for pair in step_pairs], dtype=float)
            step_pred = np.asarray([pair[1] for pair in step_pairs], dtype=float)
            horizon_rows.append({"step": step + 1, **_metric_bundle(step_actual, step_pred), "validation_points": len(step_pairs)})
        model_metrics[spec.name]["horizon_metrics"] = horizon_rows
        step_wapes = [row["wape_pct"] for row in horizon_rows if row.get("wape_pct") is not None]
        model_metrics[spec.name]["stability_pct"] = float(np.std(step_wapes)) if step_wapes else None

    recommended_weights = _weights_from_wapes(model_wapes)
    weights = _select_method_weights(model_wapes, method_selection)

    # Each series gets its own model mix. This is important for mixed catalogs:
    # intermittent-demand models can help sparse items without dragging down stable series.
    series_weights: dict[str, dict[str, float]] = {}
    ensemble_gate_count = 0
    item_ids = sorted({key[0] for key in actual_by_key})
    for item_id in item_ids:
        item_wapes: dict[str, float] = {}
        for spec in specs:
            pairs = [pair for key, pair in records[spec.name].items() if key[0] == item_id]
            if pairs:
                actual = np.array([p[0] for p in pairs], dtype=float)
                pred = np.array([p[1] for p in pairs], dtype=float)
                item_wapes[spec.name] = _wape(actual, pred)
            else:
                item_wapes[spec.name] = math.inf
        selected_weights = _select_method_weights(item_wapes, method_selection)
        if method_selection == "recommended" and len(selected_weights) > 1:
            keys = [key for key in actual_by_key if key[0] == item_id]
            ensemble_actual = []
            ensemble_predicted = []
            for key in keys:
                weighted = [
                    (weight, records.get(name, {}).get(key, (0.0, np.nan))[1])
                    for name, weight in selected_weights.items()
                    if key in records.get(name, {})
                ]
                if weighted:
                    mass = sum(weight for weight, _ in weighted) or 1.0
                    ensemble_actual.append(actual_by_key[key])
                    ensemble_predicted.append(sum(weight * prediction for weight, prediction in weighted) / mass)
            best_name = min(item_wapes, key=item_wapes.get)
            if ensemble_actual and _wape(np.asarray(ensemble_actual), np.asarray(ensemble_predicted)) >= item_wapes[best_name]:
                selected_weights = {best_name: 1.0}
                ensemble_gate_count += 1
        series_weights[item_id] = selected_weights

    ensemble_residuals: list[float] = []
    ensemble_actual: list[float] = []
    ensemble_pred: list[float] = []
    ensemble_by_step: dict[int, dict[str, list[float]]] = defaultdict(lambda: {"actual": [], "predicted": []})
    portfolio_residual_by_date: dict[str, float] = defaultdict(float)
    portfolio_step_by_date: dict[str, int] = {}
    for key, actual in actual_by_key.items():
        item_id = key[0]
        active_weights = series_weights.get(item_id, weights)
        weighted = []
        for name, weight in active_weights.items():
            pair = records.get(name, {}).get(key)
            if pair is not None:
                weighted.append((weight, pair[1]))
        if not weighted:
            continue
        mass = sum(w for w, _ in weighted) or 1.0
        pred = sum(w * p for w, p in weighted) / mass
        ensemble_actual.append(actual)
        ensemble_pred.append(pred)
        residual = actual - pred
        ensemble_residuals.append(residual)
        ordered_dates = sorted(k[1] for k in actual_by_key if k[0] == item_id)
        step = ordered_dates.index(key[1]) % max(validation_horizon, 1)
        residuals_by_item_step[item_id][step].append(residual)
        ensemble_by_step[step]["actual"].append(actual)
        ensemble_by_step[step]["predicted"].append(pred)
        portfolio_residual_by_date[key[1]] += residual
        portfolio_step_by_date[key[1]] = step

    actual_arr = np.array(ensemble_actual, dtype=float)
    pred_arr = np.array(ensemble_pred, dtype=float)
    metrics = {
        **_metric_bundle(actual_arr, pred_arr),
        "rolling_folds": len(folds),
        "requested_horizon": int(horizon),
        "validation_horizon": int(validation_horizon),
        "validation_points": len(actual_arr),
        "lightgbm_available": LIGHTGBM_AVAILABLE,
        "ensemble_gate_series": ensemble_gate_count,
    }
    metrics["horizon_metrics"] = [
        {
            "step": step + 1,
            **_metric_bundle(
                np.asarray(values["actual"], dtype=float),
                np.asarray(values["predicted"], dtype=float),
            ),
            "validation_points": len(values["actual"]),
        }
        for step, values in sorted(ensemble_by_step.items())
        if values["actual"]
    ]
    history_periods = int(pd.to_datetime(history["timestamp"]).nunique())
    fold_count = int(len(folds))
    requested_horizon_covered = int(validation_horizon) >= int(horizon)
    if fold_count >= 3 and requested_horizon_covered:
        evidence_level = "strong"
        evidence_reason = "Three rolling validation windows cover the requested horizon."
    elif fold_count >= 2 and requested_horizon_covered:
        evidence_level = "moderate"
        evidence_reason = "Two rolling validation windows cover the requested horizon."
    else:
        evidence_level = "limited"
        evidence_reason = (
            f"Only {fold_count} rolling validation window(s) were available for a {horizon}-period horizon. "
            "Review the plan manually or provide more history before publication."
        )
    metrics.update({
        "history_periods": history_periods,
        "evidence_level": evidence_level,
        "evidence_reason": evidence_reason,
        "automatic_publish_allowed": evidence_level != "limited",
    })
    if len(ensemble_residuals):
        interval_spread = float(np.quantile(np.abs(ensemble_residuals), 0.80))
        metrics["interval_coverage_pct"] = float(np.mean(np.abs(ensemble_residuals) <= interval_spread) * 100.0)
        metrics["interval_target_pct"] = 80.0
    else:
        metrics["interval_coverage_pct"] = None
        metrics["interval_target_pct"] = 80.0
    leaderboard = [
        {
            "model": name,
            **model_metrics[name],
            "score": -model_wapes[name] if np.isfinite(model_wapes[name]) else None,
            "fit_time": fit_times.get(name, 0.0),
            "weight": weights.get(name, 0.0),
            "recommended_weight": recommended_weights.get(name, 0.0),
        }
        for name in sorted(model_wapes, key=lambda n: model_wapes[n])
    ]
    series_diagnostics: dict[str, dict] = {}
    for item_id, grp in history.groupby("item_id", sort=False):
        values = grp.sort_values("timestamp")["target"].astype(float).to_numpy()
        item_pairs = []
        for key, actual in actual_by_key.items():
            if key[0] != str(item_id):
                continue
            active = series_weights.get(str(item_id), weights)
            weighted = [(w, records[name][key][1]) for name, w in active.items() if key in records.get(name, {})]
            if weighted:
                mass = sum(w for w, _ in weighted) or 1.0
                item_pairs.append((actual, sum(w * p for w, p in weighted) / mass))
        item_actual = np.array([p[0] for p in item_pairs], dtype=float)
        item_pred = np.array([p[1] for p in item_pairs], dtype=float)
        profile_row = _series_profile(values, seasonal)
        profile_row.update(_metric_bundle(item_actual, item_pred))
        profile_row["best_model"] = max(series_weights.get(str(item_id), weights), key=series_weights.get(str(item_id), weights).get)
        wape = profile_row.get("wape_pct")
        bias = profile_row.get("bias_pct")
        short_penalty = 12.0 if len(values) < seasonal * 2 else 0.0
        profile_row["quality_score"] = round(
            max(0.0, 100.0 - min(70.0, float(wape or 0.0) * 2.0) - min(15.0, abs(float(bias or 0.0)) * 0.5) - short_penalty),
            1,
        )
        series_diagnostics[str(item_id)] = profile_row

    calibration = {
        item: {str(step): vals for step, vals in steps.items()}
        for item, steps in residuals_by_item_step.items()
    }
    portfolio_steps: dict[int, list[float]] = defaultdict(list)
    for date, residual in portfolio_residual_by_date.items():
        portfolio_steps[portfolio_step_by_date[date]].append(residual)
    calibration["__portfolio__"] = {str(step): values for step, values in portfolio_steps.items()}
    return (
        specs,
        weights,
        recommended_weights,
        series_weights,
        metrics,
        leaderboard,
        np.array(ensemble_residuals, dtype=float),
        calibration,
        series_diagnostics,
    )


def _fit_full_models_and_predict(
    history: pd.DataFrame,
    future_covariates: pd.DataFrame,
    known_driver_cols: list[str],
    frequency: str,
    specs: list[ModelSpec],
):
    seasonal = _seasonal_lag(frequency)
    min_points = int(history.groupby("item_id").size().min())
    lags = _lag_set(frequency, min_points)
    max_horizon = max(1, int(future_covariates.groupby("item_id").size().max()))
    X_all, y_all = _global_direct_supervised_frame(history, known_driver_cols, lags, max_horizon=max_horizon)
    model_predictions: dict[str, dict[str, list[float]]] = {s.name: {} for s in specs}
    fitted_for_importance: list[tuple[str, Pipeline, pd.DataFrame, pd.Series]] = []

    fitted: dict[str, Pipeline] = {}
    for spec in specs:
        if spec.kind != "ml" or len(X_all) < 12:
            continue
        try:
            pipe = _make_pipeline(spec.estimator, X_all)
            pipe.fit(X_all, y_all)
            fitted[spec.name] = pipe
            fitted_for_importance.append((spec.name, pipe, X_all, y_all))
        except Exception:
            continue

    for item_id, grp in history.groupby("item_id", sort=False):
        item_id = str(item_id)
        grp = grp.sort_values("timestamp").reset_index(drop=True)
        future_item = future_covariates[future_covariates["item_id"].astype(str) == item_id].sort_values("timestamp").reset_index(drop=True)
        target_hist = grp["target"].astype(float).tolist()
        for spec in specs:
            try:
                if spec.kind == "ml" and spec.name in fitted:
                    preds = _direct_predict(
                        fitted[spec.name],
                        target_history=target_hist,
                        future_rows=future_item,
                        lags=lags,
                        known_driver_cols=known_driver_cols,
                        start_time_idx=len(grp),
                        item_id=item_id,
                    )
                elif spec.kind == "ml":
                    preds = _naive_forecast(target_hist, len(future_item), seasonal)
                else:
                    preds = _stat_forecast(spec, target_hist, len(future_item), seasonal)
            except Exception:
                preds = _naive_forecast(target_hist, len(future_item), seasonal)
            model_predictions[spec.name][item_id] = preds
    return model_predictions, fitted_for_importance


def _infer_driver_role(feature: str) -> str:
    external_tokens = {
        "market", "competitor", "inflation", "fx", "eur", "usd", "energy", "pulp",
        "weather", "economic", "gdp", "industry", "industrial", "environment", "logistics", "freight",
    }
    name = feature.lower()
    return "external" if any(token in name for token in external_tokens) else "internal"


def _driver_importance(
    fitted_models,
    weights: dict[str, float],
    allowed_features: list[str],
    driver_roles: dict[str, str] | None = None,
) -> list[dict]:
    aggregate: dict[str, float] = {}
    mass: dict[str, float] = {}
    candidates = sorted(fitted_models, key=lambda x: weights.get(x[0], 0.0), reverse=True)[:2]
    for name, pipe, X, y in candidates:
        if len(X) < 16 or weights.get(name, 0.0) <= 0:
            continue
        sample_n = min(len(X), 90)
        Xs = X.tail(sample_n)
        ys = y.tail(sample_n)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = permutation_importance(
                    pipe,
                    Xs,
                    ys,
                    scoring="neg_mean_absolute_error",
                    n_repeats=1,
                    random_state=42,
                    n_jobs=1,
                )
        except Exception:
            continue
        weight = weights.get(name, 0.0)
        for feature, imp in zip(X.columns, result.importances_mean):
            if feature not in allowed_features:
                continue
            aggregate[feature] = aggregate.get(feature, 0.0) + max(0.0, float(imp)) * weight
            mass[feature] = mass.get(feature, 0.0) + weight
    rows = []
    for feature, total in aggregate.items():
        denom = mass.get(feature, 1.0) or 1.0
        correlations = []
        for _, _, X, y in candidates:
            if feature in X and pd.api.types.is_numeric_dtype(X[feature]):
                corr = pd.to_numeric(X[feature], errors="coerce").corr(pd.Series(y).reset_index(drop=True))
                if pd.notna(corr):
                    correlations.append(float(corr))
        direction_score = float(np.mean(correlations)) if correlations else 0.0
        direction = "up" if direction_score > 0.08 else "down" if direction_score < -0.08 else "mixed"
        role = (driver_roles or {}).get(feature, _infer_driver_role(feature))
        rows.append({
            "feature": feature,
            "importance": total / denom,
            "role": role if role in {"internal", "external"} else _infer_driver_role(feature),
            "direction": direction,
            "direction_score": direction_score,
        })
    rows.sort(key=lambda r: r["importance"], reverse=True)
    return rows[:14]


def run_forecast(
    *,
    history: pd.DataFrame,
    future_covariates: pd.DataFrame,
    known_driver_cols: list[str],
    horizon: int,
    frequency: str,
    profile: str,
    runs_dir: Path,
    driver_roles: dict[str, str] | None = None,
    scenario_adjustment_pct: float = 0.0,
    method_selection: str = "recommended",
) -> dict:
    if profile not in {"fast", "deep"}:
        raise ValueError("Unknown analysis profile.")

    run_id = uuid.uuid4().hex[:12]
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    (
        specs,
        weights,
        recommended_weights,
        series_weights,
        metrics,
        leaderboard,
        residuals,
        calibration,
        series_diagnostics,
    ) = _fit_backtest(
        history=history,
        known_driver_cols=known_driver_cols,
        horizon=horizon,
        frequency=frequency,
        profile=profile,
        method_selection=method_selection,
    )
    model_predictions, fitted_for_importance = _fit_full_models_and_predict(
        history=history,
        future_covariates=future_covariates,
        known_driver_cols=known_driver_cols,
        frequency=frequency,
        specs=specs,
    )

    global_abs_residuals = np.abs(residuals)
    if len(global_abs_residuals):
        global_spread = float(np.quantile(global_abs_residuals, 0.80))
    else:
        global_spread = 0.0

    global_step_residuals: dict[int, list[float]] = defaultdict(list)
    for item_id, item_steps in calibration.items():
        if item_id == "__portfolio__":
            continue
        for step_text, values in item_steps.items():
            global_step_residuals[int(step_text)].extend(values)

    def calibrated_spread(item_id: str, step: int, disagreement: float) -> float:
        candidates: list[tuple[float, float]] = []
        if global_spread > 0:
            candidates.append((1.0, global_spread))
        global_step = global_step_residuals.get(step, [])
        if len(global_step) >= 3:
            candidates.append((1.25, float(np.quantile(np.abs(global_step), 0.80))))
        item_steps = calibration.get(item_id, {})
        item_all = [x for values in item_steps.values() for x in values]
        if len(item_all) >= 3:
            candidates.append((1.5, float(np.quantile(np.abs(item_all), 0.80))))
        item_step = item_steps.get(str(step), [])
        if len(item_step) >= 2:
            candidates.append((2.0, float(np.quantile(np.abs(item_step), 0.80))))
        if candidates:
            spread = sum(weight * value for weight, value in candidates) / sum(weight for weight, _ in candidates)
        else:
            spread = disagreement
        validation_h = max(1, int(metrics.get("validation_horizon") or 1))
        if step + 1 > validation_h:
            spread *= math.sqrt((step + 1) / validation_h)
        return max(0.0, spread + 0.35 * disagreement)

    pred_rows: list[dict] = []
    for item_id in history["item_id"].astype(str).unique():
        future_item = future_covariates[future_covariates["item_id"].astype(str) == item_id].sort_values("timestamp").reset_index(drop=True)
        active_weights = series_weights.get(item_id, weights)
        for step, (_, future_row) in enumerate(future_item.iterrows()):
            weighted = []
            for name, weight in active_weights.items():
                preds = model_predictions.get(name, {}).get(item_id, [])
                if step < len(preds):
                    weighted.append((float(weight), float(preds[step])))
            if weighted:
                mass = sum(w for w, _ in weighted) or 1.0
                baseline = sum(w * p for w, p in weighted) / mass
                model_values = np.array([p for _, p in weighted], dtype=float)
                disagreement = float(np.std(model_values))
            else:
                baseline, disagreement = 0.0, 0.0
            adjustment_multiplier = max(0.0, 1.0 + float(scenario_adjustment_pct) / 100.0)
            p50 = baseline * adjustment_multiplier
            spread = calibrated_spread(item_id, step, disagreement) * adjustment_multiplier
            p10 = max(0.0, p50 - spread)
            p90 = max(p50, p50 + spread)
            pred_rows.append(
                {
                    "item_id": item_id,
                    "timestamp": pd.Timestamp(future_row["timestamp"]),
                    "baseline_mean": max(0.0, baseline),
                    "scenario_adjustment_pct": float(scenario_adjustment_pct),
                    "mean": max(0.0, p50),
                    "p10": p10,
                    "p50": max(0.0, p50),
                    "p90": p90,
                }
            )

    pred = pd.DataFrame(pred_rows)
    drivers = _driver_importance(fitted_for_importance, weights, known_driver_cols, driver_roles)

    history_out = history[["item_id", "timestamp", "target"]].copy()
    history_out["timestamp"] = pd.to_datetime(history_out["timestamp"]).dt.strftime("%Y-%m-%d")
    pred_out = pred.copy()
    pred_out["timestamp"] = pd.to_datetime(pred_out["timestamp"]).dt.strftime("%Y-%m-%d")

    merge_cols = ["item_id", "timestamp"] + [c for c in known_driver_cols if c in future_covariates.columns]
    future_export = future_covariates[merge_cols].copy()
    future_export["timestamp"] = pd.to_datetime(future_export["timestamp"]).dt.strftime("%Y-%m-%d")
    pred_export = pred_out.merge(future_export, on=["item_id", "timestamp"], how="left")

    history_out.to_csv(run_dir / "history_clean.csv", index=False)
    pred_export.to_csv(run_dir / "forecast.csv", index=False)
    pd.DataFrame(leaderboard).to_csv(run_dir / "model_leaderboard.csv", index=False)
    pd.DataFrame(drivers).to_csv(run_dir / "driver_importance.csv", index=False)

    with pd.ExcelWriter(run_dir / "forecast_package.xlsx", engine="openpyxl") as writer:
        pred_export.to_excel(writer, sheet_name="Forecast", index=False)
        history_out.to_excel(writer, sheet_name="Clean History", index=False)
        pd.DataFrame(leaderboard).to_excel(writer, sheet_name="Models", index=False)
        pd.DataFrame(drivers).to_excel(writer, sheet_name="Drivers", index=False)
        pd.DataFrame.from_dict(series_diagnostics, orient="index").rename_axis("item_id").reset_index().to_excel(
            writer, sheet_name="Series Diagnostics", index=False
        )
        pd.DataFrame(
            [
                {"setting": "frequency", "value": frequency},
                {"setting": "horizon", "value": horizon},
                {"setting": "profile", "value": profile},
                {"setting": "rolling_backtest_folds", "value": metrics.get("rolling_folds")},
                {"setting": "known_drivers", "value": ", ".join(known_driver_cols)},
                {"setting": "method_selection", "value": method_selection},
                {"setting": "scenario_adjustment_pct", "value": float(scenario_adjustment_pct)},
                {"setting": "validation_horizon", "value": metrics.get("validation_horizon")},
                {"setting": "interval_target_pct", "value": metrics.get("interval_target_pct")},
                {"setting": "lightgbm_available", "value": LIGHTGBM_AVAILABLE},
            ]
        ).to_excel(writer, sheet_name="Run Settings", index=False)

    series_payload = {}
    for item_id in history_out["item_id"].unique():
        hist_item = history_out[history_out["item_id"] == item_id].tail(48)
        pred_item = pred_out[pred_out["item_id"] == item_id]
        method_rows = {}
        future_item = future_covariates[future_covariates["item_id"].astype(str) == str(item_id)].sort_values("timestamp")
        for model_name, by_item in model_predictions.items():
            values = by_item.get(str(item_id), [])
            method_rows[model_name] = [
                {"timestamp": pd.Timestamp(ts).strftime("%Y-%m-%d"), "mean": max(0.0, float(value))}
                for ts, value in zip(future_item["timestamp"], values)
            ]
        series_payload[str(item_id)] = {
            "history": hist_item.to_dict(orient="records"),
            "forecast": pred_item[["item_id", "timestamp", "baseline_mean", "scenario_adjustment_pct", "mean", "p10", "p50", "p90"]].to_dict(orient="records"),
            "methods": method_rows,
        }

    total_hist = history_out.groupby("timestamp", as_index=False)["target"].sum().tail(48)
    portfolio_calibration = calibration.get("__portfolio__", {})
    portfolio_all = [value for values in portfolio_calibration.values() for value in values]
    total_rows = []
    for step, (timestamp, grp) in enumerate(pred_out.groupby("timestamp", sort=True)):
        mean = float(grp["mean"].sum())
        baseline_mean = float(grp["baseline_mean"].sum())
        portfolio_step = portfolio_calibration.get(str(step), [])
        if len(portfolio_step) >= 2:
            aggregate_spread = float(np.quantile(np.abs(portfolio_step), 0.80))
        elif len(portfolio_all) >= 3:
            aggregate_spread = float(np.quantile(np.abs(portfolio_all), 0.80))
        else:
            # A conservative fallback: item errors are rarely independent in a plant.
            aggregate_spread = float(np.sqrt(np.square(grp["mean"] - grp["p10"]).sum()) * 1.25)
        validation_h = max(1, int(metrics.get("validation_horizon") or 1))
        if step + 1 > validation_h:
            aggregate_spread *= math.sqrt((step + 1) / validation_h)
        total_rows.append({
            "timestamp": timestamp,
            "baseline_mean": baseline_mean,
            "scenario_adjustment_pct": float(scenario_adjustment_pct),
            "mean": mean,
            "p50": mean,
            "p10": max(0.0, mean - aggregate_spread),
            "p90": mean + aggregate_spread,
        })
    total_pred = pd.DataFrame(total_rows)
    series_payload["__all__"] = {
        "history": [{"item_id": "All series", **r} for r in total_hist.to_dict(orient="records")],
        "forecast": [{"item_id": "All series", **r} for r in total_pred.to_dict(orient="records")],
        "methods": {},
    }

    for model_name in model_predictions:
        totals_by_step: list[dict] = []
        all_values = model_predictions[model_name]
        for step, timestamp in enumerate(sorted(pd.to_datetime(future_covariates["timestamp"]).unique())):
            total = sum(values[step] for values in all_values.values() if step < len(values))
            totals_by_step.append({"timestamp": pd.Timestamp(timestamp).strftime("%Y-%m-%d"), "mean": float(total)})
        series_payload["__all__"]["methods"][model_name] = totals_by_step

    selected_names = [name for name, weight in weights.items() if weight > 0]
    if method_selection == "recommended":
        if int(metrics.get("ensemble_gate_series") or 0) > 0:
            best_model = "Recommended guarded selection"
        else:
            best_model = "Recommended ensemble" if len(selected_names) > 1 else (selected_names[0] if selected_names else "Seasonal naive")
    elif len(selected_names) == 1:
        best_model = selected_names[0]
    else:
        best_model = f"{method_selection.title()} ensemble"
    result = {
        "run_id": run_id,
        "best_model": best_model,
        "metrics": metrics,
        "leaderboard": leaderboard,
        "drivers": drivers,
        "series_diagnostics": series_diagnostics,
        "series": series_payload,
        "items": [str(x) for x in history_out["item_id"].unique()],
        "forecast_rows": pred_export.to_dict(orient="records"),
        "ensemble_weights": weights,
        "recommended_ensemble_weights": recommended_weights,
        "series_ensemble_weights": series_weights,
        "method_selection": method_selection,
        "scenario": {
            "adjustment_pct": float(scenario_adjustment_pct),
            "baseline_preserved": True,
        },
        "methodology": {
            "selection": "User-selected method family evaluated on expanding-window backtests at the requested horizon",
            "intervals": "80% residual-calibrated planning interval by series and forecast step",
            "seasonality": "Frequency-aware Fourier/calendar features plus seasonal statistical models",
            "hierarchy": "Bottom-up reconciliation keeps item, portfolio, category, and customer totals coherent",
            "machine_learning": "Direct multi-horizon predictions avoid recursively feeding forecasts into later periods",
        },
    }
    with open(run_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, default=_json_safe, indent=2)
    return result

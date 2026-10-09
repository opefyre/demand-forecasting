from __future__ import annotations

import json
import hashlib
import math
import os
import time
import uuid
from .runtime import checkpoint
import warnings
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd

from .data import fit_history_window
from .sales_conventions import month_label, shift_month
from .uncertainty import range_parameters, bounds as range_bounds, check_ranges

if not os.environ.get("LOKY_MAX_CPU_COUNT"):
    os.environ["LOKY_MAX_CPU_COUNT"] = str(os.cpu_count() or 1)
warnings.filterwarnings("ignore", message="Could not find the number of physical cores.*")

from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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
    predictors: tuple[str, ...] | None = None


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


def _method_settings(frequency):
    return {
        'weighted_average': {'window': 3, 'weights_oldest_to_newest': [1, 2, 3], 'horizon_policy': 'constant'},
        'holt': {'error_type': 'A', 'season_length': 1},
        'holt_winters': {'error_type': 'A', 'season_length': _seasonal_lag(frequency), 'minimum_cycles': 2},
        'mstl': {'frequency': 'daily_only', 'season_lengths': [7, 365], 'minimum_training_periods': 731, 'trend_forecaster': 'AutoETS', 'trend_model': 'ZZN', 'calendar_year_approximation': '365 days, not a movable holiday calendar'},
        'elastic_net': {'alpha': 0.1, 'l1_ratio': 0.5, 'max_iter': 10000, 'numeric_scaling': 'training_fold_only', 'horizon_policy': 'direct'},
    }


def _engine_versions():
    return {'revision': '2026-10-new-customer-selection-4', 'statistical_library': 'StatsForecast',
            'statistical_version': __import__('statsforecast').__version__,
            'ml_library': 'scikit-learn', 'ml_version': __import__('sklearn').__version__,
            'numpy_version': np.__version__, 'statsmodels_version': __import__('statsmodels').__version__,
            'lightgbm_version': __import__('lightgbm').__version__ if LIGHTGBM_AVAILABLE else None, 'seed': 42}


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
        ModelSpec("Last observed", "last"),
        ModelSpec("Recent average", "average"),
        ModelSpec("Weighted recent average", "weighted_average"),
        ModelSpec("Seasonal naive", "naive"),
        ModelSpec("Holt trend", "holt"),
        ModelSpec("Holt-Winters seasonal", "holt_winters"),
        ModelSpec("MSTL weekly + yearly", "mstl"),
        ModelSpec("AutoETS", "ets"),
        ModelSpec("AutoARIMA", "arima"),
        ModelSpec("Theta", "theta"),
        ModelSpec("Croston", "croston"),
        ModelSpec("Croston SBA", "sba"),
        ModelSpec("TSB intermittent", "tsb"),
        ModelSpec("Ridge + drivers", "ml", Ridge(alpha=2.0)),
        ModelSpec("Elastic Net + drivers", "ml", ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=10000, random_state=seed)),
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


def _factor_specs(profile, drivers):
    """Use existing statistical models plus bounded sklearn factor variants."""
    from .factor_evaluation import MAX_FACTORS
    if not drivers or len(drivers) > MAX_FACTORS or len(set(drivers)) != len(drivers):
        raise ValueError('Automatic factor testing needs one to eight distinct reviewed factors.')
    originals = _model_specs(profile)
    specs = [spec for spec in originals if spec.kind != 'ml']
    # Existing regularised/nonlinear models. Bound search; no exponential subsets.
    bundles = [(), *[(driver,) for driver in sorted(drivers)]]
    if len(drivers) > 1:
        bundles.append(tuple(sorted(drivers)))
    for model in originals:
        if model.name not in {'Ridge + drivers', 'Elastic Net + drivers', 'Histogram gradient boosting'}:
            continue
        for columns in bundles:
            label = ', '.join(columns) if columns else 'history only'
            specs.append(ModelSpec(f'{model.name} [{label}]', 'ml', model.estimator, columns))
    return specs


def _spec_drivers(spec, defaults):
    return list(spec.predictors) if spec.predictors is not None else defaults


def _make_pipeline(estimator, X: pd.DataFrame) -> Pipeline:
    numeric = [c for c in X.columns if pd.api.types.is_numeric_dtype(X[c])]
    categorical = [c for c in X.columns if c not in numeric]
    transformers = []
    if numeric:
        num_steps = [("imputer", SimpleImputer(strategy="median"))]
        if isinstance(estimator, (Ridge, ElasticNet)):
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


def _fit_pipeline(pipe, X, y):
    # An unfinished optimizer is not quietly recorded as a successful candidate.
    with warnings.catch_warnings():
        warnings.filterwarnings('error', category=ConvergenceWarning)
        pipe.fit(X, y)
    return pipe


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
    """An explicit last-observation fallback, never a recursively averaged curve."""
    from statsforecast.models import Naive
    y = np.asarray(target_history, dtype=float)
    return np.maximum(0., Naive().forecast(y=y, h=steps)["mean"]).astype(float).tolist()


def _stat_forecast(spec: ModelSpec, target_history: list[float], steps: int, seasonal_lag: int, frequency: str | None = None) -> list[float]:
    """Model mathematics belong to StatsForecast; this layer only sets policy."""
    from statsforecast.models import (
        AutoARIMA, AutoETS, CrostonClassic, CrostonSBA, Naive, SeasonalNaive,
        Theta, TSB, WindowAverage, Holt, HoltWinters, MSTL,
    )
    y = np.asarray(target_history, dtype=float)
    minimum = {"naive": seasonal_lag, "last": 1, "average": 3, "ets": 6,
               "arima": 8, "theta": 8, "croston": 4, "sba": 4, "tsb": 4,
               "weighted_average": 3, "holt": 6, "holt_winters": 2 * seasonal_lag, "mstl": 731}
    if spec.kind == 'mstl' and frequency != 'daily':
        raise ValueError('Weekly + yearly MSTL requires daily observations. Monthly and weekly data do not have a seven-day cycle.')
    if len(y) < minimum[spec.kind]:
        raise ValueError(f"{spec.name} needs at least {minimum[spec.kind]} training periods.")
    season_length = seasonal_lag if len(y) >= 2 * seasonal_lag else 1
    if not np.isfinite(y).all() or (y < 0).any():
        raise ValueError('Forecast methods require finite, nonnegative training quantities.')
    if spec.kind == 'weighted_average':
        # NumPy supplies weighted averaging; this policy uses weights 1:2:3
        # oldest to newest, repeated at every horizon (not recursive smoothing).
        return np.full(steps, np.average(y[-3:], weights=[1, 2, 3])).tolist()
    factories = {
        "last": lambda: Naive(),
        "naive": lambda: SeasonalNaive(season_length=seasonal_lag),
        "average": lambda: WindowAverage(window_size=3),
        "holt": lambda: Holt(error_type='A'),
        "holt_winters": lambda: HoltWinters(season_length=seasonal_lag, error_type='A'),
        "mstl": lambda: MSTL(season_length=[7, 365], trend_forecaster=AutoETS(season_length=1, model='ZZN')),
        "ets": lambda: AutoETS(season_length=season_length, model="ZZZ"),
        "arima": lambda: AutoARIMA(season_length=season_length, seasonal=season_length > 1,
                                   max_p=3, max_q=3, nmodels=30),
        "theta": lambda: Theta(season_length=season_length, decomposition_type="additive"),
        "croston": lambda: CrostonClassic(),
        "sba": lambda: CrostonSBA(),
        "tsb": lambda: TSB(alpha_d=.18, alpha_p=.12),
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        values = np.asarray(factories[spec.kind]().forecast(y=y, h=steps)["mean"], dtype=float)
    if len(values) != steps or not np.isfinite(values).all():
        raise ValueError(f"{spec.name} did not return a complete finite forecast.")
    return np.maximum(0., values).tolist()


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
    # Internal selection loss: on an all-zero window, compare MAE in source
    # units. Public percentage metrics must remain undefined for that window.
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
    has_denominator = float(np.abs(actual).sum()) > 1e-9
    return {
        "wape_pct": _wape(actual, pred) * 100.0 if has_denominator else None,
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "smape_pct": _smape(actual, pred) * 100.0,
        "bias_pct": _bias(actual, pred) * 100.0 if has_denominator else None,
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
        return {"Last observed": 1.0}
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
    "seasonal": {"Seasonal naive", "AutoETS", "Theta", "AutoARIMA", "Holt-Winters seasonal", "MSTL weekly + yearly"},
    "trend": {"AutoETS", "Theta", "AutoARIMA", "Holt trend"},
    "intermittent": {"Croston", "Croston SBA", "TSB intermittent", "Last observed"},
    "driver": {
        "Ridge + drivers",
        "Elastic Net + drivers",
        "Histogram gradient boosting",
        "LightGBM + drivers",
        "Random forest",
        "Extra trees",
    },
}


def _select_method_weights(wapes: dict[str, float], method: str) -> dict[str, float]:
    method = (method or "recommended").strip()
    if method == 'factor_test':
        eligible = {k:v for k,v in wapes.items() if np.isfinite(v)}
        if not eligible:
            raise ValueError('No complete automatic factor candidates are available.')
        return {min(eligible, key=lambda k:(eligible[k],k)):1.0}
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
    # Extra complete windows separate range fitting from method selection. Do
    # not sacrifice the first two seasonal cycles merely to add these windows.
    if profile == 'deep' and len(dates) >= max(min_train, 2 * seasonal) + 4 * horizon:
        max_folds = min(5, (len(dates) - max(min_train, 2 * seasonal)) // horizon)
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


def _validation_factor_rows(train, validation, drivers):
    """Never expose realized holdout-period factors to a historical prediction.

    Calendar columns remain known by date. Uploaded factor release/revision
    archives are unavailable, so this is a disclosed persistence approximation,
    not a claim of publication-time correctness.
    """
    rows = validation.copy()
    for factor in drivers:
        raw = f'raw_driver__{factor}'
        values = train[raw if raw in train else factor].dropna()
        if values.empty:
            raise ValueError(f'{factor}: no factor value before the test cutoff.')
        rows[factor] = values.iloc[-1]
    return rows


def _fit_backtest(
    history: pd.DataFrame,
    known_driver_cols: list[str],
    horizon: int,
    frequency: str,
    profile: str,
    method_selection: str,
):
    factor_test = method_selection == 'factor_test'
    specs = _factor_specs(profile, known_driver_cols) if factor_test else _model_specs(profile)
    records: dict[str, dict[tuple[str, str], tuple[float, float]]] = {spec.name: {} for spec in specs}
    actual_by_key: dict[tuple[str, str], float] = {}
    fit_times: dict[str, float] = {spec.name: 0.0 for spec in specs}
    seasonal = _seasonal_lag(frequency)
    # Opting into factor selection needs two selection windows plus the reserved
    # check even when the underlying model catalog uses the faster profile.
    folds, validation_horizon = _rolling_folds(history, frequency, 'deep' if factor_test else profile, horizon)
    residuals_by_item_step: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    step_by_key: dict[tuple[str, str], int] = {}
    failures: dict[str, list[str]] = defaultdict(list)

    for fold_index, (val_start, val_dates) in enumerate(folds):
        checkpoint(f'Testing against past actuals · check {fold_index + 1} of {len(folds)}')
        train_history = history[pd.to_datetime(history["timestamp"]) < val_start].copy()
        val_history = history[pd.to_datetime(history["timestamp"]).isin(val_dates)].copy()
        if train_history.empty or val_history.empty:
            continue
        train_history = fit_history_window(train_history)
        min_train = int(train_history.groupby("item_id").size().min())
        lags = _lag_set(frequency, min_train)
        X_all, y_all = _global_direct_supervised_frame(
            train_history,
            known_driver_cols,
            lags,
            max_horizon=max(1, len(val_dates)),
        )

        fitted_ml: dict[str, Pipeline] = {}
        feature_frames = {tuple(known_driver_cols): (X_all, y_all)}
        for spec in specs:
            checkpoint()
            columns = _spec_drivers(spec, known_driver_cols)
            if spec.kind != 'ml':
                continue
            if tuple(columns) not in feature_frames:
                feature_frames[tuple(columns)] = _global_direct_supervised_frame(train_history, columns, lags, max_horizon=max(1,len(val_dates)))
            X_spec, y_spec = feature_frames[tuple(columns)]
            if len(X_spec) < 12: continue
            started = time.perf_counter()
            try:
                pipe = _make_pipeline(spec.estimator, X_spec)
                _fit_pipeline(pipe, X_spec, y_spec)
                fitted_ml[spec.name] = pipe
            except Exception as exc:
                failures[spec.name].append(f"Training before {val_start.date()}: {str(exc)[:180]}")
            fit_times[spec.name] += time.perf_counter() - started

        for item_id, val_grp in val_history.groupby("item_id", sort=False):
            item_id = str(item_id)
            val_grp = val_grp.sort_values("timestamp").reset_index(drop=True)
            train_grp = train_history[train_history["item_id"].astype(str) == item_id].sort_values("timestamp").reset_index(drop=True)
            if train_grp.empty:
                continue
            target_hist = train_grp["target"].astype(float).tolist()
            y_actual = val_grp.get("observed_target", val_grp["target"]).astype(float).to_numpy()
            for idx, row in val_grp.iterrows():
                key = (item_id, pd.Timestamp(row["timestamp"]).strftime("%Y-%m-%d"))
                if np.isfinite(y_actual[idx]):
                    actual_by_key[key] = float(y_actual[idx])
                    step_by_key[key] = val_dates.index(pd.Timestamp(row["timestamp"]))
            for spec in specs:
                checkpoint()
                started = time.perf_counter()
                try:
                    if spec.kind == "ml" and spec.name in fitted_ml:
                        preds = _direct_predict(
                            fitted_ml[spec.name],
                            target_history=target_hist,
                            future_rows=_validation_factor_rows(train_grp, val_grp, _spec_drivers(spec, known_driver_cols)),
                            lags=lags,
                            known_driver_cols=_spec_drivers(spec, known_driver_cols),
                            start_time_idx=len(train_grp),
                            item_id=item_id,
                        )
                    elif spec.kind == "ml":
                        raise ValueError("Not enough training examples, or model fitting failed.")
                    else:
                        preds = _stat_forecast(spec, target_hist, len(val_grp), seasonal, frequency)
                except Exception as exc:
                    failures[spec.name].append(f"{item_id} before {val_start.date()}: {str(exc)[:180]}")
                    continue
                fit_times[spec.name] += time.perf_counter() - started
                for idx, pred in enumerate(preds):
                    row = val_grp.iloc[idx]
                    key = (item_id, pd.Timestamp(row["timestamp"]).strftime("%Y-%m-%d"))
                    if np.isfinite(y_actual[idx]):
                        records[spec.name][key] = (float(y_actual[idx]), float(pred))

    model_wapes: dict[str, float] = {}
    model_metrics: dict[str, dict] = {}
    # Reserve the last complete window. Its quantities must not influence
    # method selection, ensemble weights, or interval calibration.
    confirmation_dates = {d.strftime("%Y-%m-%d") for d in folds[-1][1]} if len(folds) >= 2 else set()
    range_dates = {d.strftime('%Y-%m-%d') for _, dates in folds[2:-1] for d in dates} if len(folds) >= 4 else set()
    selection_keys = {key for key in actual_by_key if key[1] not in confirmation_dates | range_dates}
    range_keys = {key for key in actual_by_key if key[1] in range_dates} if range_dates else selection_keys
    evaluation_keys = {key for key in actual_by_key if key[1] in confirmation_dates} if confirmation_dates else set(actual_by_key)
    for spec in specs:
        pairs = [pair for key, pair in records[spec.name].items() if key in selection_keys]
        actual = np.array([p[0] for p in pairs], dtype=float)
        pred = np.array([p[1] for p in pairs], dtype=float)
        complete = bool(selection_keys) and len(pairs) == len(selection_keys)
        model_wapes[spec.name] = _wape(actual, pred) if complete else math.inf
        model_metrics[spec.name] = _metric_bundle(actual, pred)
        model_metrics[spec.name]["status"] = "tested" if complete else "unavailable"
        model_metrics[spec.name]['selection_loss'] = 'wape' if float(np.abs(actual).sum()) > 1e-9 else 'mae_zero_actuals'
        model_metrics[spec.name]["failure_count"] = len(failures[spec.name])
        model_metrics[spec.name]["failure_examples"] = failures[spec.name][:3]
        confirmation = [pair for key, pair in records[spec.name].items() if key in evaluation_keys]
        model_metrics[spec.name]["confirmation"] = _metric_bundle(np.array([p[0] for p in confirmation]), np.array([p[1] for p in confirmation])) if confirmation_dates else None
        if not complete:
            model_metrics[spec.name]["wape_pct"] = None
        horizon_rows = []
        for step in range(max(validation_horizon, 1)):
            step_pairs = [pair for key, pair in records[spec.name].items() if key in selection_keys and step_by_key.get(key) == step]
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
    untested_selection_series = []
    factor_choices = []
    factor_sets = {spec.name: list(spec.predictors or ()) for spec in specs}
    ensemble_gate_count = 0
    item_ids = sorted({key[0] for key in actual_by_key})
    for item_id in item_ids:
        item_wapes: dict[str, float] = {}
        for spec in specs:
            pairs = [pair for key, pair in records[spec.name].items() if key[0] == item_id and key in selection_keys]
            if pairs and len(pairs) == sum(key[0] == item_id for key in selection_keys):
                actual = np.array([p[0] for p in pairs], dtype=float)
                pred = np.array([p[1] for p in pairs], dtype=float)
                item_wapes[spec.name] = _wape(actual, pred)
            else:
                item_wapes[spec.name] = math.inf
        item_selection_keys = [key for key in selection_keys if key[0] == item_id]
        if not item_selection_keys and method_selection.startswith('model:'):
            # A recently acquired customer may appear only in confirmation.
            # Honour the explicit method without using confirmation to choose it.
            # Full-history fitting below still enforces that model's data needs.
            selected_weights = dict(weights)
            untested_selection_series.append(item_id)
        else:
            selected_weights = _select_method_weights(item_wapes, method_selection)
        if factor_test:
            from .factor_evaluation import choose_candidate
            choice = choose_candidate(item_wapes, factor_sets,
                eligible=len(folds)>=3 and validation_horizon>=horizon)
            choice['item_id'] = item_id
            choice['selection_loss'] = 'wape' if sum(abs(actual_by_key[k]) for k in selection_keys if k[0]==item_id)>1e-9 else 'mae_zero_actuals'
            factor_choices.append(choice)
            selected_weights = {choice['selected_model']:1.0}
        if len(selected_weights) > 1:
            keys = [key for key in selection_keys if key[0] == item_id]
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
            # Family choices must also beat their best eligible member. Do not
            # switch a seasonal/driver choice to a model outside that family.
            best_name = min(selected_weights, key=item_wapes.get)
            if ensemble_actual and _wape(np.asarray(ensemble_actual), np.asarray(ensemble_predicted)) >= item_wapes[best_name]:
                selected_weights = {best_name: 1.0}
                ensemble_gate_count += 1
        series_weights[item_id] = selected_weights

    if factor_test:
        weights = {}
        for active in series_weights.values():
            for name, weight in active.items():
                weights[name] = weights.get(name,0.) + weight / len(series_weights)
        recommended_weights = dict(weights)

    ensemble_residuals: list[float] = []
    ensemble_actual: list[float] = []
    ensemble_pred: list[float] = []
    ensemble_by_step: dict[int, dict[str, list[float]]] = defaultdict(lambda: {"actual": [], "predicted": []})
    portfolio_residual_by_date: dict[str, float] = defaultdict(float)
    portfolio_step_by_date: dict[str, int] = {}
    confirmation_failures = []
    range_rows = []
    confirmation_rows = []
    for key, actual in actual_by_key.items():
        item_id = key[0]
        active_weights = series_weights.get(item_id, weights)
        weighted = []
        for name, weight in active_weights.items():
            pair = records.get(name, {}).get(key)
            if pair is not None:
                weighted.append((weight, pair[1]))
        if len(weighted) != len(active_weights):
            if key in evaluation_keys:
                confirmation_failures.append(key)
            continue
        mass = sum(w for w, _ in weighted) or 1.0
        pred = sum(w * p for w, p in weighted) / mass
        residual = actual - pred
        step = step_by_key[key]
        row = {'item_id': item_id, 'timestamp': key[1], 'step': step + 1, 'actual': actual, 'predicted': pred}
        if key in range_keys:
            range_rows.append(row)
        if confirmation_dates and key in evaluation_keys:
            confirmation_rows.append(row)
        if key in evaluation_keys:
            ensemble_actual.append(actual)
            ensemble_pred.append(pred)
            ensemble_by_step[step]["actual"].append(actual)
            ensemble_by_step[step]["predicted"].append(pred)
        if key in selection_keys:
            ensemble_residuals.append(residual)
            residuals_by_item_step[item_id][step].append(residual)
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
        "preprocessing": "Training-window-only; unchanged observed actuals scored; missing actuals excluded",
        "factor_test_policy": "last_training_value" if known_driver_cols else "no_extra_factors",
        "factor_release_dates_verified": not bool(known_driver_cols),
        "factor_test_note": ("Tests hold each extra factor at its last recorded training-period value. Original publication dates and revisions are not verified; this is not a real-time data replay. Future forecasts use your supplied assumptions."
                             if known_driver_cols else "No extra factors; calendar and demand history remain in use."),
        "evaluation_type": "reserved_confirmation_window" if confirmation_dates else "model_selection_backtest",
        "independent_accuracy_verified": bool(confirmation_dates and not confirmation_failures and len(actual_arr)),
        "selection_periods": sorted({key[1] for key in selection_keys}),
        "confirmation_periods": sorted(confirmation_dates),
        "selection_points": len(selection_keys),
        "untested_selection_series": untested_selection_series,
        "range_fitting_periods": sorted(range_dates or {key[1] for key in selection_keys}),
        "range_fitting_separate": bool(range_dates),
        "confirmation_failed_points": len(confirmation_failures),
        "evaluation_signature": hashlib.sha256(json.dumps([
            [str(key[0]), str(key[1]), int(step_by_key[key]), float(actual_by_key[key])]
            for key in sorted(evaluation_keys) if key not in confirmation_failures
        ], ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
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
    if confirmation_failures:
        evidence_level = "limited"
        evidence_reason = "The selected method failed in the reserved check. Choose another method before approval."
        metrics["wape_pct"] = None
    elif fold_count >= 3 and requested_horizon_covered:
        evidence_level = "strong"
        evidence_reason = "Two selection windows and one separate confirmation window cover the requested horizon. Additional windows fit planning ranges when available. This is historical evidence, not a future accuracy guarantee."
    elif fold_count >= 2 and requested_horizon_covered:
        evidence_level = "moderate"
        evidence_reason = "One selection window and one separate confirmation window cover the requested horizon. More observations are needed to establish stability."
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
        "automatic_publish_allowed": False,
    })
    range_model = range_parameters(range_rows, item_ids, validation_horizon)
    range_check = check_ranges(range_model, confirmation_rows, item_ids)
    range_check.update({'fitting_separate_from_selection': bool(range_dates),
        'fitting_periods': metrics['range_fitting_periods'], 'check_periods': sorted(confirmation_dates),
        'target_pct': 80.0, 'future_coverage_guaranteed': False,
        'missing_prediction_points': len(confirmation_failures)})
    metrics['range_check'] = range_check
    if factor_test:
        from .factor_evaluation import POLICY, NOTE, MIN_GAIN
        for choice in factor_choices:
            keys = sorted(k for k in evaluation_keys if k[0] == choice['item_id'])
            def confirmation(name):
                pairs = [records[name][k] for k in keys if k in records[name]]
                if not confirmation_dates or len(pairs) != len(keys) or not keys:
                    return None
                return _metric_bundle(np.array([p[0] for p in pairs]),np.array([p[1] for p in pairs]))
            choice['confirmation_baseline'] = confirmation(choice['baseline_model'])
            choice['confirmation_selected'] = confirmation(choice['selected_model'])
            choice['confirmation_points'] = len(keys) if choice['confirmation_selected'] else 0
            old, new = choice['confirmation_baseline'], choice['confirmation_selected']
            choice['confirmation_improved'] = new['mae'] < old['mae'] if old and new else None
        metrics['factor_evaluation'] = {'policy':POLICY,'minimum_gain_pct':100*MIN_GAIN,
            'tested_factors':sorted(known_driver_cols), 'search':'No factors, each factor separately, and all factors together; not every subset.',
            'selection_periods':metrics['selection_periods'],'confirmation_periods':metrics['confirmation_periods'],
            'future_factor_policy':'reviewed_values_required','note':NOTE,'rows':factor_choices}
    metrics['interval_coverage_pct'] = range_check['items']['coverage_pct']
    metrics['interval_target_pct'] = 80.0
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
            if key[0] != str(item_id) or key not in evaluation_keys:
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
        profile_row['method_selection_tested'] = str(item_id) not in untested_selection_series
        wape = profile_row.get("wape_pct")
        bias = profile_row.get("bias_pct")
        short_penalty = 12.0 if len(values) < seasonal * 2 else 0.0
        profile_row["quality_score"] = round(
            max(0.0, 100.0 - min(70.0, float(wape or 0.0) * 2.0) - min(15.0, abs(float(bias or 0.0)) * 0.5) - short_penalty),
            1,
        ) if wape is not None and bias is not None else None
        series_diagnostics[str(item_id)] = profile_row

    calibration = {
        item: {str(step): vals for step, vals in steps.items()}
        for item, steps in residuals_by_item_step.items()
    }
    portfolio_steps: dict[int, list[float]] = defaultdict(list)
    for date, residual in portfolio_residual_by_date.items():
        portfolio_steps[portfolio_step_by_date[date]].append(residual)
    calibration["__portfolio__"] = {str(step): values for step, values in portfolio_steps.items()}
    calibration['__range_model__'] = range_model
    calibration['__range_rows__'] = range_rows
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
    checkpoint('Calculating the outlook')
    seasonal = _seasonal_lag(frequency)
    min_points = int(history.groupby("item_id").size().min())
    lags = _lag_set(frequency, min_points)
    max_horizon = max(1, int(future_covariates.groupby("item_id").size().max()))
    X_all, y_all = _global_direct_supervised_frame(history, known_driver_cols, lags, max_horizon=max_horizon)
    model_predictions: dict[str, dict[str, list[float]]] = {s.name: {} for s in specs}
    fitted_for_importance: list[tuple[str, Pipeline, pd.DataFrame, pd.Series]] = []
    failures = []

    fitted: dict[str, Pipeline] = {}
    fitting_errors = {}
    for spec in specs:
        checkpoint()
        columns = _spec_drivers(spec, known_driver_cols)
        if spec.kind != 'ml':
            continue
        X_spec, y_spec = (X_all,y_all) if columns == known_driver_cols else _global_direct_supervised_frame(history,columns,lags,max_horizon=max_horizon)
        if len(X_spec) < 12: continue
        try:
            pipe = _make_pipeline(spec.estimator, X_spec)
            _fit_pipeline(pipe, X_spec, y_spec)
            fitted[spec.name] = pipe
            fitted_for_importance.append((spec.name, pipe, X_spec, y_spec))
        except Exception as exc:
            fitting_errors[spec.name] = str(exc)[:180]
            continue

    for item_id, grp in history.groupby("item_id", sort=False):
        item_id = str(item_id)
        grp = grp.sort_values("timestamp").reset_index(drop=True)
        future_item = future_covariates[future_covariates["item_id"].astype(str) == item_id].sort_values("timestamp").reset_index(drop=True)
        target_hist = grp["target"].astype(float).tolist()
        for spec in specs:
            checkpoint()
            try:
                if spec.kind == "ml" and spec.name in fitted:
                    preds = _direct_predict(
                        fitted[spec.name],
                        target_history=target_hist,
                        future_rows=future_item,
                        lags=lags,
                        known_driver_cols=_spec_drivers(spec, known_driver_cols),
                        start_time_idx=len(grp),
                        item_id=item_id,
                    )
                elif spec.kind == "ml":
                    raise ValueError(fitting_errors.get(spec.name, "Not enough training examples."))
                else:
                    preds = _stat_forecast(spec, target_hist, len(future_item), seasonal, frequency)
            except Exception as exc:
                failures.append({"model": spec.name, "item_id": item_id, "reason": str(exc)[:180]})
                continue
            model_predictions[spec.name][item_id] = preds
    return model_predictions, fitted_for_importance, failures


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
    evidence_policy: str = "standard",
) -> dict:
    if profile not in {"fast", "deep"}:
        raise ValueError("Unknown analysis profile.")
    if evidence_policy not in {'standard', 'reviewed_what_if'}:
        raise ValueError('Unknown forecast evidence policy.')
    if evidence_policy == 'reviewed_what_if':
        from .live_factor_alignment import FACTOR_METHODS
        if not known_driver_cols or method_selection not in {'model:' + name for name in FACTOR_METHODS}:
            raise ValueError('A what-if requires extra factors and one user-chosen factor-aware method.')
    if method_selection == 'factor_test':
        for name in known_driver_cols:
            for frame in (history, future_covariates):
                values = pd.to_numeric(frame.get(name,pd.Series(dtype=float)),errors='coerce')
                if len(values)!=len(frame) or values.isna().any() or not np.isfinite(values).all():
                    raise ValueError(f'{name}: complete finite reviewed factor values are required; missing is not zero.')

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
    if evidence_policy == 'reviewed_what_if':
        from .live_factor_alignment import WHAT_IF_POLICY
        # Remove unsupported evidence BEFORE writing any result or download.
        score_keys = ('wape_pct', 'mae', 'rmse', 'smape_pct', 'bias_pct')
        metrics.update({key: None for key in score_keys})
        metrics.update(evidence_policy=evidence_policy, independent_accuracy_verified=False,
            evidence_level='limited', evidence_reason=WHAT_IF_POLICY, factor_test_note=WHAT_IF_POLICY,
            factor_test_policy='retrospective_sensitivity_not_accuracy', factor_release_dates_verified=False,
            automatic_publish_allowed=False, horizon_metrics=[], interval_coverage_pct=None,
            interval_target_pct=None, range_fitting_periods=[], range_fitting_separate=False)
        calibration = {'__range_model__': {'parameters': {}, 'target_pct': None,
                       'validated_horizon': 0}, '__range_rows__': []}
        metrics['range_check'] = check_ranges(calibration['__range_model__'], [], history.item_id.astype(str).unique().tolist())
        recommended_weights = {}
        # These rows identify the selected method, not an accuracy ranking.
        leaderboard = [{'model': row['model'], 'weight': row['weight'],
                        **{key: None for key in score_keys}, 'score': None,
                        'recommended_weight': None} for row in leaderboard if row['weight'] > 0]
        for diagnostic in series_diagnostics.values():
            diagnostic.update({key: None for key in (*score_keys, 'quality_score')})
    model_predictions, fitted_for_importance, model_failures = _fit_full_models_and_predict(
        history=history,
        future_covariates=future_covariates,
        known_driver_cols=known_driver_cols,
        frequency=frequency,
        specs=specs,
    )

    checkpoint('Preparing results and planning ranges')
    range_model = calibration['__range_model__']

    pred_rows: list[dict] = []
    for item_id in history["item_id"].astype(str).unique():
        future_item = future_covariates[future_covariates["item_id"].astype(str) == item_id].sort_values("timestamp").reset_index(drop=True)
        active_weights = series_weights.get(item_id, weights)
        missing_models = [name for name in active_weights if item_id not in model_predictions.get(name, {})]
        if missing_models:
            raise ValueError(f"The selected method could not forecast {item_id}: {', '.join(missing_models)}. Choose another tested method. No replacement forecast was silently substituted.")
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
            p10, p90 = range_bounds(range_model, item_id, step + 1, p50, adjustment_multiplier)
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
    if method_selection == 'factor_test':
        # Factor selection evidence is per-series; pooled associations are not a
        # reliable explanation of which factors were used in each forecast.
        drivers = []

    history_out = history[["item_id", "timestamp", "target"]].copy()
    if "observed_target" in history:
        values = history["observed_target"]
        history_out["target"] = values.astype(object).where(values.notna(), None)
    history_out["timestamp"] = pd.to_datetime(history_out["timestamp"]).dt.strftime("%Y-%m-%d")
    pred_out = pred.copy()
    # Preserve unavailable ranges as JSON null and blank workbook cells, not
    # NaN, zero-width confidence or invented extrapolation beyond tested steps.
    for column in ('p10', 'p90'):
        pred_out[column] = pred_out[column].astype(object).where(pred_out[column].notna(), None)
    pred_out["timestamp"] = pd.to_datetime(pred_out["timestamp"]).dt.strftime("%Y-%m-%d")

    merge_cols = ["item_id", "timestamp"] + [c for c in known_driver_cols if c in future_covariates.columns]
    future_export = future_covariates[merge_cols].copy()
    future_export["timestamp"] = pd.to_datetime(future_export["timestamp"]).dt.strftime("%Y-%m-%d")
    pred_export = pred_out.merge(future_export, on=["item_id", "timestamp"], how="left")
    if evidence_policy == 'reviewed_what_if':
        pred_export['forecast_use'] = 'what_if_unvalidated'

    basis = history.attrs.get('calendar_profile', {}).get('month_basis', 'gregorian')
    if frequency == 'monthly':
        for exported in (history_out, pred_export):
            exported['planning_calendar'] = basis
            exported['period_label'] = exported.timestamp.map(lambda value: month_label(value, basis))
            exported['period_end'] = exported.timestamp.map(
                lambda value: (shift_month(value, 1, basis).date() - timedelta(days=1)).isoformat())

    history_out.to_csv(run_dir / "history_clean.csv", index=False)
    pred_export.to_csv(run_dir / "forecast.csv", index=False)
    pd.DataFrame(leaderboard).to_csv(run_dir / "model_leaderboard.csv", index=False)
    pd.DataFrame(drivers).to_csv(run_dir / "driver_importance.csv", index=False)

    with pd.ExcelWriter(run_dir / "forecast_package.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([{'setting': key, 'value': json.dumps(value, ensure_ascii=False)}
            for key, value in history.attrs.get('sales_conventions', {}).items()]).to_excel(
                writer, sheet_name='Sales meaning', index=False)
        pd.DataFrame(metrics['range_check']['rows']).to_excel(writer, sheet_name='Range check', index=False)
        pd.DataFrame(calibration['__range_rows__']).to_excel(writer, sheet_name='Range fitting', index=False)
        pd.DataFrame([{'item_id': item, 'step': int(step), **values}
            for item, steps in range_model['parameters'].items() for step, values in steps.items()]).to_excel(writer, sheet_name='Range parameters', index=False)
        pd.DataFrame([{'setting': key, 'value': json.dumps(value)} for key, value in {
            'target_pct': metrics['interval_target_pct'], 'fitting_separate_from_selection': metrics['range_fitting_separate'],
            'fitting_periods': metrics['range_fitting_periods'], 'check_periods': metrics['confirmation_periods'],
            'future_coverage_guaranteed': False,
            'policy': metrics['evidence_reason'] if evidence_policy == 'reviewed_what_if' else 'Absolute residual order statistic; own-item or joint portfolio errors; same horizon when at least 5 scores, otherwise pooled horizons; unavailable beyond tested horizon.'}.items()]).to_excel(writer, sheet_name='Range policy', index=False)
        pd.DataFrame([{'setting': key, 'value': value} for key, value in _engine_versions().items()]).to_excel(writer, sheet_name='Engine', index=False)
        pd.DataFrame([{'method': name, 'settings': json.dumps(settings, sort_keys=True)} for name, settings in _method_settings(frequency).items()]).to_excel(writer, sheet_name='Method settings', index=False)
        pred_export.to_excel(writer, sheet_name="Forecast", index=False)
        history_out.to_excel(writer, sheet_name="Clean History", index=False)
        pd.DataFrame(leaderboard).to_excel(writer, sheet_name="Models", index=False)
        pd.DataFrame(drivers).to_excel(writer, sheet_name="Drivers", index=False)
        if metrics.get('factor_evaluation'):
            evidence = metrics['factor_evaluation']
            pd.DataFrame([{**row,'selected_factors':json.dumps(row['selected_factors']),
                'confirmation_baseline':json.dumps(row['confirmation_baseline']),
                'confirmation_selected':json.dumps(row['confirmation_selected'])} for row in evidence['rows']]).to_excel(
                    writer,sheet_name='Factor choices',index=False)
            pd.DataFrame([{'setting':key,'value':json.dumps(value)} for key,value in evidence.items() if key!='rows']).to_excel(
                    writer,sheet_name='Factor test policy',index=False)
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
                {"setting": "factor_test_policy", "value": metrics['factor_test_policy']},
                {"setting": "factor_release_dates_verified", "value": metrics['factor_release_dates_verified']},
                {"setting": "factor_test_note", "value": metrics['factor_test_note']},
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

    total_hist = history_out.groupby("timestamp", as_index=False)["target"].sum(min_count=1).tail(48)
    total_rows = []
    for step, (timestamp, grp) in enumerate(pred_out.groupby("timestamp", sort=True)):
        mean = float(grp["mean"].sum())
        baseline_mean = float(grp["baseline_mean"].sum())
        low, high = range_bounds(range_model, '__portfolio__', step + 1, mean, max(0.0, 1 + float(scenario_adjustment_pct) / 100))
        total_rows.append({
            "timestamp": timestamp,
            "baseline_mean": baseline_mean,
            "scenario_adjustment_pct": float(scenario_adjustment_pct),
            "mean": mean,
            "p50": mean,
            "p10": low,
            "p90": high,
        })
    total_pred = pd.DataFrame(total_rows)
    for column in ('p10', 'p90'):
        total_pred[column] = total_pred[column].astype(object).where(total_pred[column].notna(), None)
    series_payload["__all__"] = {
        "history": [{"item_id": "All series", **r} for r in total_hist.to_dict(orient="records")],
        "forecast": [{"item_id": "All series", **r} for r in total_pred.to_dict(orient="records")],
        "methods": {},
    }

    for model_name in model_predictions:
        totals_by_step: list[dict] = []
        all_values = model_predictions[model_name]
        for step, timestamp in enumerate(sorted(pd.to_datetime(future_covariates["timestamp"]).unique())):
            if len(all_values) != history_out.item_id.nunique():
                continue
            total = 0.
            for item_id, values in all_values.items():
                dates = pd.to_datetime(future_covariates.loc[future_covariates.item_id.astype(str).eq(item_id), "timestamp"]).sort_values().tolist()
                if pd.Timestamp(timestamp) in dates:
                    total += values[dates.index(pd.Timestamp(timestamp))]
            totals_by_step.append({"timestamp": pd.Timestamp(timestamp).strftime("%Y-%m-%d"), "mean": float(total)})
        series_payload["__all__"]["methods"][model_name] = totals_by_step

    selected_names = sorted({name for active in series_weights.values() for name, weight in active.items() if weight > 0})
    if method_selection == 'factor_test':
        best_model = 'Automatic factor testing'
    elif method_selection == "recommended":
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
        "evidence_policy": evidence_policy,
        "metrics": metrics,
        "model_failures": model_failures,
        "engine": _engine_versions(),
        "method_settings": _method_settings(frequency),
        "range_model": range_model,
        "range_fitting_rows": calibration['__range_rows__'],
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
            "selection": "User-chosen factor-aware method; retrospective sensitivity, not validated model selection" if evidence_policy == 'reviewed_what_if' else "User-selected method family evaluated on expanding-window backtests at the requested horizon",
            "intervals": "Unavailable: downloaded historical factors have unverified release dates" if evidence_policy == 'reviewed_what_if' else "Nominal 80% empirical range using own-item and joint portfolio errors. Separate range-fitting windows where history permits, otherwise selection residuals. Later coverage is measured without refitting widths. Pooled horizons and small samples limit evidence; future coverage is not guaranteed. Missing ranges are not extrapolated.",
            "seasonality": "Frequency-aware Fourier/calendar features plus seasonal statistical models",
            "hierarchy": "Bottom-up reconciliation keeps item, portfolio, category, and customer totals coherent",
            "machine_learning": "Direct multi-horizon predictions avoid recursively feeding forecasts into later periods",
        },
    }
    if method_selection == 'factor_test':
        result['methodology']['selection'] = metrics['factor_evaluation']['note']
        result['factor_evaluation'] = metrics['factor_evaluation']
        (run_dir/'factor_evaluation.json').write_text(json.dumps(metrics['factor_evaluation'],default=_json_safe,indent=2))
    with open(run_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, default=_json_safe, indent=2)
    return result

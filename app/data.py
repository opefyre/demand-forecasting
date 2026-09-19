from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


FREQ_MAP = {
    "monthly": "MS",
    "weekly": "W-MON",
    "daily": "D",
}


def period_dates(values: pd.Series, frequency: str) -> pd.Series:
    """Align observations to the requested period before grouping or matching."""
    dates = pd.to_datetime(values, errors="coerce")
    if frequency == "monthly":
        return dates.dt.to_period("M").dt.to_timestamp()
    if frequency == "weekly":
        return dates.dt.to_period("W-SUN").dt.start_time
    return dates.dt.normalize()


def _detect_header_row(raw: pd.DataFrame) -> int:
    """Find a likely header row without penalising normal row-zero CSV-style sheets."""
    keywords = {
        "date", "month", "week", "period", "time", "demand", "sales", "volume",
        "quantity", "customer", "article", "item", "sku", "category", "price",
    }
    best_row, best_score = 0, -1.0
    for idx, row in raw.head(25).iterrows():
        values = [str(v).strip().lower() for v in row.tolist() if pd.notna(v) and str(v).strip()]
        if not values:
            continue
        keyword_hits = sum(any(token in value for token in keywords) for value in values)
        unique_ratio = len(set(values)) / max(len(values), 1)
        score = keyword_hits * 8 + min(len(values), 30) + unique_ratio
        if score > best_score:
            best_row, best_score = int(idx), score
    return best_row


def _select_excel_sheet(book: pd.ExcelFile) -> str:
    """Prefer a detailed demand/actual sheet, then fall back to the first visible table."""
    preferred = {
        "actual + forecast": 80,
        "demand": 45,
        "history": 45,
        "sales": 35,
        "forecast": 25,
        "budget": 15,
    }
    ranked: list[tuple[float, str]] = []
    for sheet in book.sheet_names:
        name = sheet.strip().lower()
        name_score = sum(weight for token, weight in preferred.items() if token in name)
        try:
            probe = pd.read_excel(book, sheet_name=sheet, header=None, nrows=25)
            density = float(probe.notna().sum().sum())
            width = float(probe.notna().sum(axis=1).max()) if len(probe) else 0.0
            ranked.append((name_score + min(density / 20.0, 25.0) + min(width, 30.0), sheet))
        except Exception:
            continue
    return max(ranked)[1] if ranked else book.sheet_names[0]


def _reshape_forecast_matrix(df: pd.DataFrame, raw: pd.DataFrame, header_row: int, sheet_name: str) -> pd.DataFrame:
    """Convert the supplied commercial workbook's wide item/month matrix to canonical long data."""
    required = {"Article Number", "Customer Name", "Customer Summary"}
    if not required.issubset(set(df.columns)):
        return df
    date_columns: list[str] = []
    parsed_dates: dict[str, pd.Timestamp] = {}
    for col in df.columns:
        text = str(col)
        if text.endswith(".1"):
            continue
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.notna(parsed) and 2020 <= parsed.year <= 2100:
            date_columns.append(col)
            parsed_dates[col] = pd.Timestamp(parsed).to_period("M").to_timestamp()
    if len(date_columns) < 3:
        return df

    header_positions = {str(value).strip(): idx for idx, value in enumerate(raw.iloc[header_row].tolist()) if pd.notna(value)}
    status_row_idx = max(0, header_row - 2)
    status_values = raw.iloc[status_row_idx].ffill().tolist() if status_row_idx < len(raw) else []
    metadata_map = {
        "sku": "Article Number",
        "customer": "Customer Name",
        "customer_group": "Customer Summary",
        "category": "Category",
        "brand_family": "Brand Family",
        "technology": "Technology",
        "article_description": "Article Description",
        "selling_price": "Price 2026",
    }
    rows: list[dict] = []
    for _, source in df.iterrows():
        article = source.get("Article Number")
        customer = source.get("Customer Name")
        if pd.isna(article) or pd.isna(customer):
            continue
        series_id = f"{article} · {customer}"
        for col in date_columns:
            demand = pd.to_numeric(pd.Series([source.get(col)]), errors="coerce").iloc[0]
            if pd.isna(demand):
                continue
            position = header_positions.get(str(col).strip())
            status = str(status_values[position]).strip().lower() if position is not None and position < len(status_values) else ""
            record_type = "forecast" if "forecast" in status else "actual"
            row = {
                "date": parsed_dates[col],
                "demand": float(demand),
                "series_id": series_id,
                "record_type": record_type,
                "source_sheet": sheet_name,
            }
            for target, source_col in metadata_map.items():
                if source_col in df.columns:
                    row[target] = source.get(source_col)
            rows.append(row)
    if not rows:
        return df
    out = pd.DataFrame(rows)
    out.attrs.update(df.attrs)
    out.attrs["wide_forecast_matrix"] = True
    return out


def read_table(filename: str, payload: bytes, *, sheet_name: str | None = None) -> pd.DataFrame:
    suffix = Path(filename or "data.csv").suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        book = pd.ExcelFile(BytesIO(payload))
        if sheet_name is not None and sheet_name not in book.sheet_names:
            raise ValueError('The selected worksheet was not found. Choose a worksheet from this file.')
        selected = sheet_name if sheet_name in book.sheet_names else _select_excel_sheet(book)
        raw = pd.read_excel(book, sheet_name=selected, header=None, nrows=25)
        header_row = _detect_header_row(raw)
        out = pd.read_excel(book, sheet_name=selected, header=header_row)
        out = out.dropna(axis=0, how="all").dropna(axis=1, how="all")
        out.columns = [str(c).strip() for c in out.columns]
        out.attrs["sheet_name"] = selected
        out.attrs["sheet_names"] = book.sheet_names
        out.attrs["header_row"] = header_row + 1
        return _reshape_forecast_matrix(out, raw, header_row, selected)
    if suffix in {".csv", ".txt", ".tsv"}:
        try:
            return pd.read_csv(BytesIO(payload), sep="\t" if suffix == ".tsv" else None, engine="python")
        except UnicodeDecodeError:
            return pd.read_csv(BytesIO(payload), encoding="latin-1", sep="\t" if suffix == ".tsv" else None, engine="python")
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return pd.read_json(BytesIO(payload), lines=suffix in {".jsonl", ".ndjson"})
    raise ValueError("Unsupported file type. Use CSV, TSV, JSON, or Excel (.xlsx).")


def preview_table(filename: str, payload: bytes, *, sheet_name: str | None = None) -> dict:
    df = read_table(filename, payload, sheet_name=sheet_name)
    sample = df.head(6).replace({np.nan: None}).to_dict(orient="records")
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    date_candidates: list[str] = []
    for col in df.columns:
        name = str(col).lower()
        if any(token in name for token in ["date", "month", "week", "period", "time"]):
            date_candidates.append(str(col))
    return {
        "rows": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "numeric_columns": [str(c) for c in numeric],
        "date_candidates": date_candidates,
        "sample": sample,
        "selected_sheet": df.attrs.get("sheet_name"),
        "sheets": df.attrs.get("sheet_names", []),
        "header_row": df.attrs.get("header_row"),
        "wide_forecast_matrix": bool(df.attrs.get("wide_forecast_matrix", False)),
    }


def _coerce_driver_types(df: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            continue
        converted = pd.to_numeric(out[col], errors="coerce")
        # Treat as numeric when a clear majority is numeric.
        if converted.notna().mean() >= 0.8:
            out[col] = converted.astype(float)
        else:
            out[col] = out[col].astype("string").fillna("Unknown")
    return out


def prepare_history(
    df: pd.DataFrame,
    *,
    date_col: str,
    target_col: str,
    item_col: str | None,
    driver_cols: list[str],
    frequency: str,
    missing_strategy: str = "auto",
    outlier_strategy: str = "winsorize",
) -> tuple[pd.DataFrame, list[str]]:
    if missing_strategy not in {"auto", "zero", "interpolate", "carry"}:
        raise ValueError("Missing-period treatment must be auto, zero, interpolate, or carry.")
    if outlier_strategy not in {"none", "winsorize"}:
        raise ValueError("Outlier treatment must be none or winsorize.")
    required = [date_col, target_col]
    if item_col:
        required.append(item_col)
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    use_cols = list(dict.fromkeys(required + [c for c in driver_cols if c in df.columns]))
    work = df[use_cols].copy()
    work[date_col] = period_dates(work[date_col], frequency)
    work[target_col] = pd.to_numeric(work[target_col], errors="coerce")
    invalid_rows = int(work[[date_col, target_col]].isna().any(axis=1).sum())
    work = work.dropna(subset=[date_col, target_col])
    if work.empty:
        raise ValueError("No valid dated demand rows were found after cleaning.")

    if item_col:
        work[item_col] = work[item_col].astype("string").fillna("Unassigned")
    else:
        item_col = "__series__"
        work[item_col] = "Total demand"

    work = _coerce_driver_types(work, driver_cols)
    work = work.rename(columns={date_col: "timestamp", item_col: "item_id", target_col: "target"})

    # Aggregate duplicate item/date rows. Demand sums; numeric drivers average; categorical drivers use last observation.
    agg: dict[str, str] = {"target": "sum"}
    for col in driver_cols:
        if col not in work.columns:
            continue
        agg[col] = "mean" if pd.api.types.is_numeric_dtype(work[col]) else "last"
    duplicates = int(work.duplicated(["item_id", "timestamp"], keep=False).sum())
    work = work.groupby(["item_id", "timestamp"], as_index=False).agg(agg)

    freq = FREQ_MAP[frequency]
    regularized: list[pd.DataFrame] = []
    fill_warnings: list[str] = []
    if invalid_rows:
        fill_warnings.append(f"Removed {invalid_rows} row(s) with an invalid date or demand value")
    if duplicates:
        fill_warnings.append(f"Combined {duplicates} rows within the same item and period; quantities were added")
    negative_count = int((work["target"] < 0).sum())
    if negative_count:
        work.loc[work["target"] < 0, "target"] = 0.0
        fill_warnings.append(f"Clipped {negative_count} negative demand value(s) to zero")
    for item_id, grp in work.groupby("item_id", sort=False):
        grp = grp.sort_values("timestamp").set_index("timestamp")
        full_index = pd.date_range(grp.index.min(), grp.index.max(), freq=freq)
        before = len(grp)
        grp = grp.reindex(full_index)
        inserted = len(grp) - before
        grp["was_imputed"] = grp["target"].isna()
        grp["was_outlier"] = False
        if inserted > 0:
            original = work[work["item_id"].astype(str) == str(item_id)]["target"].astype(float)
            resolved_strategy = missing_strategy
            if resolved_strategy == "auto":
                resolved_strategy = "zero" if float((original <= 1e-9).mean()) >= 0.20 else "interpolate"
            if resolved_strategy == "zero":
                grp["target"] = grp["target"].fillna(0.0)
            elif resolved_strategy == "carry":
                grp["target"] = grp["target"].ffill().bfill()
            else:
                grp["target"] = grp["target"].interpolate(method="time", limit_direction="both")
            fill_warnings.append(
                f"{item_id}: repaired {inserted} missing period(s) using {resolved_strategy} treatment"
            )
        grp["item_id"] = str(item_id)
        grp["target"] = grp["target"].fillna(0.0)
        if outlier_strategy == "winsorize" and len(grp) >= 8:
            values = grp["target"].astype(float)
            median = float(values.median())
            mad = float((values - median).abs().median())
            if mad > 1e-9:
                robust_sigma = 1.4826 * mad
                lower = max(0.0, median - 6.0 * robust_sigma)
                upper = median + 6.0 * robust_sigma
                outlier_mask = (values < lower) | (values > upper)
                if bool(outlier_mask.any()):
                    grp.loc[outlier_mask, "was_outlier"] = True
                    grp.loc[outlier_mask, "target"] = values.clip(lower, upper)
                    fill_warnings.append(f"{item_id}: capped {int(outlier_mask.sum())} extreme demand value(s)")
        for col in driver_cols:
            if col not in grp.columns:
                continue
            if pd.api.types.is_numeric_dtype(grp[col]):
                grp[col] = grp[col].interpolate(limit_direction="both").ffill().bfill()
            else:
                grp[col] = grp[col].ffill().bfill().fillna("Unknown")
        grp.index.name = "timestamp"
        regularized.append(grp.reset_index())

    clean = pd.concat(regularized, ignore_index=True)
    clean["item_id"] = clean["item_id"].astype(str)
    clean = add_calendar_covariates(clean, frequency=frequency)

    min_points = clean.groupby("item_id").size().min()
    if min_points < 6:
        raise ValueError(
            f"The shortest series has only {int(min_points)} observations. "
            "At least 6 periods per item are required."
        )
    if min_points < 12:
        fill_warnings.append(
            f"Short-history mode: only {int(min_points)} periods are available per series. "
            "The engine will use pooled cross-series ML and short-lag validation; treat accuracy as illustrative."
        )
    return clean, fill_warnings


def add_calendar_covariates(df: pd.DataFrame, *, frequency: str) -> pd.DataFrame:
    out = df.copy()
    ts = pd.to_datetime(out["timestamp"])
    if frequency == "monthly":
        month = ts.dt.month.astype(float)
        for harmonic in (1, 2):
            out[f"calendar_sin_{harmonic}"] = np.sin(2 * np.pi * harmonic * month / 12.0)
            out[f"calendar_cos_{harmonic}"] = np.cos(2 * np.pi * harmonic * month / 12.0)
        out["calendar_month"] = month
        out["calendar_quarter"] = ts.dt.quarter.astype(float)
        out["calendar_days_in_period"] = ts.dt.days_in_month.astype(float)
    elif frequency == "weekly":
        week = ts.dt.isocalendar().week.astype(float)
        for harmonic in (1, 2):
            out[f"calendar_sin_{harmonic}"] = np.sin(2 * np.pi * harmonic * week / 52.0)
            out[f"calendar_cos_{harmonic}"] = np.cos(2 * np.pi * harmonic * week / 52.0)
        out["calendar_week"] = week
        out["calendar_month"] = ts.dt.month.astype(float)
    else:
        day = ts.dt.dayofyear.astype(float)
        weekday = ts.dt.dayofweek.astype(float)
        for harmonic in (1, 2):
            out[f"calendar_year_sin_{harmonic}"] = np.sin(2 * np.pi * harmonic * day / 365.25)
            out[f"calendar_year_cos_{harmonic}"] = np.cos(2 * np.pi * harmonic * day / 365.25)
        out["calendar_week_sin"] = np.sin(2 * np.pi * weekday / 7.0)
        out["calendar_week_cos"] = np.cos(2 * np.pi * weekday / 7.0)
        out["calendar_is_weekend"] = (weekday >= 5).astype(float)
        out["calendar_month"] = ts.dt.month.astype(float)
    return out


def build_future_covariates(
    history: pd.DataFrame,
    future_df: pd.DataFrame | None,
    *,
    future_date_col: str | None,
    future_item_col: str | None,
    known_driver_cols: list[str],
    frequency: str,
    horizon: int,
    missing_future_policy: str = "require",
) -> tuple[pd.DataFrame, list[str]]:
    if missing_future_policy not in {"require", "carry", "median"}:
        raise ValueError("Future-driver policy must be require, carry, or median.")
    freq = FREQ_MAP[frequency]
    rows: list[dict] = []
    warnings: list[str] = []
    coverage: dict[str, dict[str, object]] = {
        col: {"expected": 0, "provided": 0, "assumed": 0, "policy": missing_future_policy}
        for col in known_driver_cols
    }
    missing_examples: list[str] = []

    parsed_future: pd.DataFrame | None = None
    if future_df is not None and not future_df.empty and future_date_col:
        parsed_future = future_df.copy()
        if future_date_col not in parsed_future.columns:
            raise ValueError(f"Future file does not contain date column '{future_date_col}'.")
        parsed_future[future_date_col] = period_dates(parsed_future[future_date_col], frequency)
        if parsed_future[future_date_col].isna().any():
            raise ValueError("Future factors contain unreadable dates. Correct them before continuing.")
        if future_item_col and future_item_col not in parsed_future.columns:
            raise ValueError(f"Future file does not contain item column '{future_item_col}'.")
        if future_item_col and future_item_col in parsed_future.columns:
            parsed_future[future_item_col] = parsed_future[future_item_col].astype(str)
        keys = [future_date_col] + ([future_item_col] if future_item_col else [])
        if known_driver_cols and parsed_future.duplicated(keys).any():
            raise ValueError("Future factors need one row per item and period. Combine duplicate rows or select the item column.")
        parsed_future = _coerce_driver_types(parsed_future, known_driver_cols)

    for item_id, grp in history.groupby("item_id", sort=False):
        last_ts = pd.to_datetime(grp["timestamp"]).max()
        future_dates = pd.date_range(last_ts + pd.tseries.frequencies.to_offset(freq), periods=horizon, freq=freq)
        item_future = None
        if parsed_future is not None:
            item_future = parsed_future
            if future_item_col and future_item_col in parsed_future.columns:
                item_future = parsed_future[parsed_future[future_item_col] == str(item_id)]

        for dt in future_dates:
            row = {"item_id": str(item_id), "timestamp": dt}
            for col in known_driver_cols:
                coverage[col]["expected"] = int(coverage[col]["expected"]) + 1
                val = None
                if item_future is not None and col in item_future.columns:
                    matched = item_future[item_future[future_date_col] == dt]
                    if not matched.empty:
                        val = matched.iloc[-1][col]
                        if not pd.isna(val):
                            coverage[col]["provided"] = int(coverage[col]["provided"]) + 1
                if pd.isna(val) if val is not None else True:
                    hist_col = grp[col] if col in grp.columns else None
                    if missing_future_policy == "require":
                        if len(missing_examples) < 8:
                            missing_examples.append(f"{col} · {item_id} · {dt.date()}")
                        val = np.nan
                    elif hist_col is not None and hist_col.notna().any():
                        if missing_future_policy == "median":
                            numeric_history = pd.to_numeric(hist_col, errors="coerce")
                            if float(numeric_history.notna().mean()) >= 0.8:
                                val = numeric_history.median()
                                assumption = "historical median"
                            else:
                                val = hist_col.dropna().mode().iloc[0]
                                assumption = "historical mode"
                        else:
                            val = hist_col.dropna().iloc[-1]
                            assumption = "last observed value"
                        coverage[col]["assumed"] = int(coverage[col]["assumed"]) + 1
                        warning = f"{col}: missing future value(s); used {assumption} by explicit policy"
                        if warning not in warnings:
                            warnings.append(warning)
                    else:
                        val = 0.0
                        coverage[col]["assumed"] = int(coverage[col]["assumed"]) + 1
                row[col] = val
            rows.append(row)

    if missing_examples and missing_future_policy == "require":
        preview = "; ".join(missing_examples)
        remaining = sum(
            int(values["expected"]) - int(values["provided"])
            for values in coverage.values()
        ) - len(missing_examples)
        suffix = f"; and {remaining} more" if remaining > 0 else ""
        raise ValueError(
            "Future values are missing for selected drivers. Provide values for the full horizon, "
            "choose an explicit assumption policy, or remove those drivers. "
            f"Examples: {preview}{suffix}."
        )

    future = pd.DataFrame(rows)
    future = add_calendar_covariates(future, frequency=frequency)
    for values in coverage.values():
        expected = max(1, int(values["expected"]))
        values["coverage_pct"] = round(int(values["provided"]) / expected * 100.0, 1)
    future.attrs["driver_coverage"] = coverage
    return future, warnings


def summarize_history(df: pd.DataFrame) -> dict:
    zero_share = float((df["target"] == 0).mean())
    imputed = int(df.get("was_imputed", pd.Series(False, index=df.index)).sum())
    outliers = int(df.get("was_outlier", pd.Series(False, index=df.index)).sum())
    min_points = int(df.groupby("item_id").size().min())
    quality_penalty = min(35.0, imputed / max(len(df), 1) * 160.0 + outliers / max(len(df), 1) * 80.0)
    quality_penalty += 12.0 if min_points < 12 else 0.0
    return {
        "series": int(df["item_id"].nunique()),
        "rows": int(len(df)),
        "start": str(pd.to_datetime(df["timestamp"]).min().date()),
        "end": str(pd.to_datetime(df["timestamp"]).max().date()),
        "total_demand": float(df["target"].sum()),
        "zero_share": zero_share,
        "imputed_periods": imputed,
        "outliers_adjusted": outliers,
        "shortest_series": min_points,
        "data_quality_score": round(max(0.0, 100.0 - quality_penalty), 1),
    }

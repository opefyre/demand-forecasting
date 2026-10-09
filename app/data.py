from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable
from functools import lru_cache
from datetime import date as calendar_date, timedelta

import numpy as np
import pandas as pd
from .sales_conventions import normalize_history, month_range, period_start, shift_month


FREQ_MAP = {
    "monthly": "MS",
    "weekly": "W-MON",
    "daily": "D",
}


def period_dates(values: pd.Series, frequency: str, month_basis: str = 'gregorian') -> pd.Series:
    """Align observations to the requested period before grouping or matching."""
    dates = pd.to_datetime(values, errors="coerce")
    if frequency == "monthly":
        if month_basis == 'jalali':
            return dates.map(lambda value: period_start(value, month_basis) if pd.notna(value) else pd.NaT)
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
    required = {"Article Number", "Customer Name"}
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

    # Repeated dates usually identify a second measure (e.g. revenue). Keep the
    # FIRST occurrence, including its labels, rather than joining by date text.
    header_positions = {}
    for idx, value in enumerate(raw.iloc[header_row].tolist()):
        if pd.notna(value):
            header_positions.setdefault(str(value).strip(), idx)
    status_values = []
    for idx in range(header_row - 1, -1, -1):
        candidate = raw.iloc[idx].tolist()
        if any(str(v).strip().lower() in {"actual", "actuals", "forecast", "budget", "plan"} for v in candidate):
            status_values = candidate
            break
    planned_sheet = any(word in sheet_name.lower() for word in ("budget", "pessimist", "optimist", "mps", "scenario")) or sheet_name.lower().startswith("fc")
    metadata_map = {
        "sku": "Article Number",
        "customer": "Customer Name",
        "customer_group": "Customer Summary",
        "category": "Category",
        "brand_family": "Brand Family",
        "technology": "Technology",
        "article_description": "Article Description",
        "selling_price": "Price 2026",
        "unit": "UOM",
    }
    rows: list[dict] = []
    from openpyxl.utils import get_column_letter
    for source_index, source in df.iterrows():
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
            if planned_sheet:
                record_type = "plan"
            elif status in {"actual", "actuals"}:
                record_type = "actual"
            elif status in {"forecast", "budget", "plan"}:
                record_type = status
            else:
                record_type = "unconfirmed"
            row = {
                "date": parsed_dates[col],
                "demand": float(demand),
                "series_id": series_id,
                "record_type": record_type,
                "source_sheet": sheet_name,
                "source_cell": f"{get_column_letter(position + 1)}{source_index + header_row + 2}" if position is not None else None,
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


def actual_history(frame: pd.DataFrame, *, unit_filter: str | None = None, excluded_items: list[str] | None = None, item_col: str | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Fail closed on labelled plans; this gate is shared by every run endpoint."""
    result = frame.copy()
    messages = []
    if "record_type" in result:
        mask = result.record_type.astype(str).str.strip().str.lower().isin({"actual", "actuals"})
        if not mask.any():
            raise ValueError("This sheet contains plans, forecasts or unconfirmed values, not labelled actuals. Choose an actual-sales worksheet. Plans can be kept for comparison, but cannot train the forecast.")
        result = result.loc[mask].copy()
    if "unit" in result:
        units = result.unit.fillna("").astype(str).str.strip()
        if unit_filter:
            result = result.loc[units.eq(unit_filter)].copy()
            if result.empty:
                raise ValueError("No actual rows match the selected quantity unit.")
        elif units.nunique() > 1:
            raise ValueError("This file mixes quantity units. Choose one unit in the import settings; quantities with different units must not be added.")
        if result.unit.isna().any() or result.unit.astype(str).str.strip().isin({"", "-", "?"}).any():
            raise ValueError("Some actual rows have no quantity unit. Confirm the missing units in the source before forecasting.")
    if excluded_items:
        column = item_col or ("series_id" if "series_id" in result else "item_id")
        if column not in result or not isinstance(excluded_items, list):
            raise ValueError("Choose an item column before leaving items out of this forecast.")
        mask = result[column].astype(str).isin(excluded_items)
        messages.append(f"Left {result.loc[mask, column].nunique()} item(s) out of this forecast, as selected in the import settings.")
        result = result.loc[~mask].copy()
        if result.empty:
            raise ValueError("No actual rows remain in the selected scope.")
    if "record_type" in frame:
        messages.insert(0, f"{len(result):,} actual rows in this scope. Existing planned and unconfirmed values were excluded from training.")
    return result, messages


def source_review(frame: pd.DataFrame) -> dict:
    """Explain recognized workbook structure without summing incompatible units."""
    review = {"record_types": {}, "units": [], "periods": {}, "warnings": [], "quantity_issues": []}
    if frame.attrs.get('wide_forecast_matrix'):
        review['input_grain'] = 'monthly_totals'
        review['input_calendar'] = 'gregorian'
    if "unit" in frame:
        review["units"] = sorted(frame.unit.dropna().astype(str).str.strip().unique().tolist())
    if "record_type" in frame and {"date", "demand"}.issubset(frame.columns):
        review["record_types"] = {str(k): int(v) for k, v in frame.record_type.value_counts().items()}
        for kind, group in frame.groupby("record_type"):
            dates = pd.to_datetime(group.date)
            review["periods"][str(kind)] = {"start": str(dates.min().date()), "end": str(dates.max().date()), "months": int(dates.nunique())}
        if not review["record_types"].get("actual"):
            review["warnings"].append("No confirmed actual sales in this sheet. Choose a different worksheet to train a forecast.")
        actual_months = review["periods"].get("actual", {}).get("months", 0)
        if 0 < actual_months < 24:
            review["warnings"].append(f"{actual_months} months of actual sales: not enough to establish an annual pattern. Upload more history when available.")
        actuals = frame.loc[frame.record_type.eq('actual')]
        for _, row in actuals.loc[pd.to_numeric(actuals.demand, errors='coerce') < 0].iterrows():
            review['quantity_issues'].append({'item': str(row.get('series_id', '')), 'cell': row.get('source_cell'), 'unit': row.get('unit'), 'value': float(row.demand)})
        if review['quantity_issues']:
            review['warnings'].append(f"{len(review['quantity_issues'])} negative actual quantities need review. Choose a returns policy, correct them, or explicitly leave those items out. They are not silently treated as demand.")
    if len(review["units"]) > 1:
        review["warnings"].append("Mixed units: forecast one unit at a time, or supply reviewed conversions.")
    return review


def _infer_lossless_numbers(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep text identifiers intact while retaining numeric measures for previews.

    pandas' default inference discards leading zeroes and treats codes such as
    NA/NULL as missing. Parsing text first also prevents irreversible rounding of
    long numeric identifiers. Actual model measures are coerced at mapping time.
    """
    for col in frame.columns:
        values = frame[col]
        if values.isna().any():
            continue  # Do not turn nullable integer identifiers into e.g. '123.0'.
        strings = values.map(lambda value: isinstance(value, str))
        text = values.astype(str)
        protected = text.str.match(r'^[+-]?0\d') | text.str.match(r'^[+-]?\d{16,}$')
        if (strings & protected).any():
            continue
        numeric = pd.to_numeric(values, errors='coerce')
        if numeric.notna().all():
            frame[col] = numeric
    return frame


def read_table(filename: str, payload: bytes, *, sheet_name: str | None = None) -> pd.DataFrame:
    suffix = Path(filename or "data.csv").suffix.lower()
    if suffix in {".xlsx", ".xlsm", ".xls"}:
        book = pd.ExcelFile(BytesIO(payload))
        if sheet_name is not None and sheet_name not in book.sheet_names:
            raise ValueError('The selected worksheet was not found. Choose a worksheet from this file.')
        selected = sheet_name if sheet_name in book.sheet_names else _select_excel_sheet(book)
        raw = pd.read_excel(book, sheet_name=selected, header=None, nrows=25)
        header_row = _detect_header_row(raw)
        out = pd.read_excel(book, sheet_name=selected, header=header_row,
                            dtype=object, keep_default_na=False, na_values=[''])
        out = out.dropna(axis=0, how="all").dropna(axis=1, how="all")
        out.columns = [str(c).strip() for c in out.columns]
        out.attrs["sheet_name"] = selected
        out.attrs["sheet_names"] = book.sheet_names
        out.attrs["header_row"] = header_row + 1
        return _reshape_forecast_matrix(_infer_lossless_numbers(out), raw, header_row, selected)
    if suffix in {".csv", ".txt", ".tsv"}:
        try:
            return _infer_lossless_numbers(pd.read_csv(BytesIO(payload), sep="\t" if suffix == ".tsv" else None,
                engine="python", dtype=object, keep_default_na=False, na_values=['']))
        except UnicodeDecodeError:
            return _infer_lossless_numbers(pd.read_csv(BytesIO(payload), encoding="latin-1", sep="\t" if suffix == ".tsv" else None,
                engine="python", dtype=object, keep_default_na=False, na_values=['']))
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return pd.read_json(BytesIO(payload), lines=suffix in {".jsonl", ".ndjson"}, dtype=False)
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
        "source_review": source_review(df),
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
    calendar_country: str | None = "IR",
    weekend_days: tuple[int, ...] = (4,),
    shutdown_dates: tuple[str, ...] = (),
    history_calendar: str = 'gregorian',
    history_grain: str = 'transactions',
    month_basis: str = 'gregorian',
    sales_measure: str = 'unspecified',
    returns_policy: str = 'reject',
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

    if 'sales_conventions' not in df.attrs:
        df, _ = normalize_history(df, dict(date_col=date_col, target_col=target_col,
            history_calendar=history_calendar, history_grain=history_grain, month_basis=month_basis,
            sales_measure=sales_measure, returns_policy=returns_policy, frequency=frequency))
    receipt = df.attrs['sales_conventions']
    returns_policy = receipt['returns_policy']
    use_cols = list(dict.fromkeys(required + [c for c in driver_cols if c in df.columns]))
    work = df[use_cols].copy()
    work[date_col] = period_dates(work[date_col], frequency, month_basis)
    work[target_col] = pd.to_numeric(work[target_col], errors="coerce").astype(float)
    invalid_rows = int(work[[date_col, target_col]].isna().any(axis=1).sum())
    if invalid_rows or (~np.isfinite(work[target_col])).any() or (returns_policy != 'net_returns' and (work[target_col] < 0).any()):
        raise ValueError("History contains missing, negative or invalid quantities/dates. Correct the source before forecasting; missing periods can be handled separately.")
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
    fill_warnings: list[str] = list(df.attrs.get('sales_convention_warnings', []))
    if invalid_rows:
        fill_warnings.append(f"Removed {invalid_rows} row(s) with an invalid date or demand value")
    if duplicates:
        fill_warnings.append(f"Combined {duplicates} rows within the same item and period; quantities were added")
    negative_count = int((work["target"] < 0).sum())
    if negative_count:
        raise ValueError('Returns exceed sales in an item/period. Review the original transaction dates; negative demand is not clipped.')
    for item_id, grp in work.groupby("item_id", sort=False):
        grp = grp.sort_values("timestamp").set_index("timestamp")
        full_index = month_range(grp.index.min(), grp.index.max(), basis=month_basis) if frequency == 'monthly' else pd.date_range(grp.index.min(), grp.index.max(), freq=freq)
        before = len(grp)
        grp = grp.reindex(full_index)
        inserted = len(grp) - before
        grp["observed_target"] = grp["target"]
        for col in driver_cols:
            if col in grp:
                grp[f"raw_driver__{col}"] = grp[col]
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
    clean = add_calendar_covariates(clean, frequency=frequency, country=calendar_country, weekend_days=weekend_days, shutdown_dates=shutdown_dates, month_basis=month_basis)

    min_points = clean.groupby("item_id").size().min()
    if min_points < 6:
        raise ValueError(
            f"The shortest series has only {int(min_points)} observations. "
            "At least 6 periods per item are required."
        )
    if min_points < 12:
        fill_warnings.append(
            f"Short-history mode: only {int(min_points)} periods are available per series. "
            "Short forecasts can be explored, but annual seasonality and long-horizon accuracy are not established."
        )
    clean.attrs["preprocessing"] = {"missing_strategy": missing_strategy, "outlier_strategy": outlier_strategy, "drivers": driver_cols}
    clean.attrs["calendar_profile"] = {"country": calendar_country, "weekend_days": list(weekend_days), "shutdown_dates": list(shutdown_dates), 'month_basis':month_basis}
    clean.attrs['sales_conventions'] = receipt
    return clean, fill_warnings


def fit_history_window(history: pd.DataFrame) -> pd.DataFrame:
    """Refit data treatment using only a backtest's training observations.

    observed_target is immutable and is the only permitted scoring target.
    DataFrames supplied directly by callers without preparation remain unchanged.
    """
    if "observed_target" not in history:
        return history.copy()
    settings = history.attrs.get("preprocessing", {})
    pieces = []
    for _, group in history.groupby("item_id", sort=False):
        group = group.sort_values("timestamp").copy()
        values = group.observed_target.astype(float)
        strategy = settings.get("missing_strategy", "auto")
        if strategy == "auto":
            strategy = "zero" if (values.dropna() <= 1e-9).mean() >= .2 else "interpolate"
        if strategy == "zero":
            values = values.fillna(0.)
        elif strategy == "carry":
            values = values.ffill().bfill()
        else:
            # Periods are equally spaced. Interpolation cannot cross the cutoff:
            # this function only receives the training slice.
            values = values.interpolate().ffill().bfill()
        if values.isna().any():
            raise ValueError("An item has no observed demand before a validation cutoff.")
        group["was_outlier"] = False
        if settings.get("outlier_strategy") == "winsorize" and len(values) >= 8:
            median = float(values.median())
            mad = float((values - median).abs().median())
            if mad > 1e-9:
                lower, upper = max(0., median - 6 * 1.4826 * mad), median + 6 * 1.4826 * mad
                group["was_outlier"] = ~values.between(lower, upper)
                values = values.clip(lower, upper)
        group["target"] = values
        for col in settings.get("drivers", []):
            raw = f"raw_driver__{col}"
            if raw in group:
                values = group[raw]
                group[col] = values.interpolate().ffill().bfill() if pd.api.types.is_numeric_dtype(values) else values.ffill().bfill().fillna("Unknown")
        pieces.append(group)
    out = pd.concat(pieces, ignore_index=True)
    out.attrs = history.attrs.copy()
    return out


@lru_cache(maxsize=128)
def _holidays(country: str, year: int):
    import holidays
    return holidays.country_holidays(country, years=[year], observed=True)


def add_calendar_covariates(df: pd.DataFrame, *, frequency: str, country: str | None = None,
                           weekend_days: tuple[int, ...] = (5, 6), shutdown_dates: tuple[str, ...] = (), month_basis='gregorian') -> pd.DataFrame:
    if not isinstance(weekend_days, (list, tuple)) or any(type(day) is not int or day not in range(7) for day in weekend_days):
        raise ValueError("Weekend days must be numbers from 0 (Monday) to 6 (Sunday).")
    if shutdown_dates and not country:
        raise ValueError("Choose a country calendar before adding site closure dates.")
    out = df.copy()
    ts = pd.to_datetime(out["timestamp"])
    if frequency == "monthly":
        from persiantools.jdatetime import JalaliDate
        month = ts.map(lambda d: JalaliDate(d.date()).month).astype(float) if month_basis == 'jalali' else ts.dt.month.astype(float)
        for harmonic in (1, 2):
            out[f"calendar_sin_{harmonic}"] = np.sin(2 * np.pi * harmonic * month / 12.0)
            out[f"calendar_cos_{harmonic}"] = np.cos(2 * np.pi * harmonic * month / 12.0)
        out["calendar_month"] = month
        out["calendar_quarter"] = ((month - 1) // 3 + 1)
        out["calendar_days_in_period"] = ts.map(lambda d: (shift_month(d, 1, month_basis) - d).days).astype(float)
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
        out["calendar_is_weekend"] = weekday.isin(weekend_days).astype(float)
        out["calendar_month"] = ts.dt.month.astype(float)
    if country:
        from persiantools.jdatetime import JalaliDate
        try:
            shutdowns = {calendar_date.fromisoformat(value) for value in shutdown_dates if value.strip()}
        except (ValueError, TypeError):
            raise ValueError("Enter closure dates as YYYY-MM-DD, separated by commas.")
        features = {}
        for start in sorted(ts.unique()):
            start = pd.Timestamp(start)
            end = shift_month(start, 1, month_basis) if frequency == "monthly" else pd.Timestamp(start.date() + timedelta(days=7 if frequency == "weekly" else 1))
            days = pd.date_range(start, end, inclusive="left", freq="D")
            holidays_in_period = sum(day.date() in _holidays(country, day.year) for day in days)
            working = sum(day.dayofweek not in weekend_days and day.date() not in _holidays(country, day.year) and day.date() not in shutdowns for day in days)
            row = {"calendar_holiday_days": holidays_in_period, "calendar_working_days": working,
                   "calendar_shutdown_days": sum(day.date() in shutdowns for day in days)}
            if country == "IR":
                month = JalaliDate(start.date()).month
                row.update({"calendar_jalali_month": month, "calendar_jalali_sin": np.sin(2 * np.pi * month / 12), "calendar_jalali_cos": np.cos(2 * np.pi * month / 12),
                            "calendar_nowruz_days": sum(JalaliDate(day.date()).month == 1 and JalaliDate(day.date()).day <= 4 for day in days)})
            features[start] = row
        for key in next(iter(features.values()), {}):
            out[key] = ts.map(lambda value: features[pd.Timestamp(value)][key]).astype(float)
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
    input_calendar: str = 'gregorian',
) -> tuple[pd.DataFrame, list[str]]:
    if missing_future_policy not in {"require", "carry", "median"}:
        raise ValueError("Future-driver policy must be require, carry, or median.")
    freq = FREQ_MAP[frequency]
    basis = history.attrs.get('calendar_profile', {}).get('month_basis', 'gregorian')
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
        from .sales_conventions import dates
        parsed_future[future_date_col] = period_dates(dates(parsed_future[future_date_col], input_calendar), frequency, basis)
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
        future_dates = month_range(shift_month(last_ts, 1, basis), periods=horizon, basis=basis) if frequency == 'monthly' else pd.date_range(last_ts + pd.tseries.frequencies.to_offset(freq), periods=horizon, freq=freq)
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
                        raise ValueError(f'{col}: no historical value is available to fill a missing future factor. Provide values or remove this factor; missing is not zero.')
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
    calendar = history.attrs.get("calendar_profile", {})
    future = add_calendar_covariates(future, frequency=frequency, country=calendar.get("country"),
                                    weekend_days=tuple(calendar.get("weekend_days", [5, 6])), shutdown_dates=tuple(calendar.get("shutdown_dates", [])), month_basis=basis)
    future.attrs["calendar_profile"] = calendar
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

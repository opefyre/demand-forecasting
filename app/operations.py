from __future__ import annotations

import io
import math
from collections import defaultdict
from datetime import timedelta

import pandas as pd


SHEET_ALIASES = {
    "bom": {"bom", "bill of materials", "bill_of_materials"},
    "materials": {"materials", "material master", "material_master"},
    "open_pos": {"open pos", "open_po", "purchase orders", "open purchase orders"},
    "capacity": {"capacity", "capacity calendar", "production calendar"},
    "relationships": {"relationships", "product relationships", "substitutions"},
    "promotions": {"promotions", "promotion calendar", "events"},
}


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [
        str(col).strip().lower().replace("%", "pct").replace("/", "_").replace(" ", "_")
        for col in out.columns
    ]
    return out.dropna(how="all")


def read_operations_workbook(filename: str, payload: bytes) -> dict[str, pd.DataFrame]:
    if not filename.lower().endswith((".xlsx", ".xlsm")):
        raise ValueError("The operations master must be an .xlsx workbook with named sheets.")
    book = pd.ExcelFile(io.BytesIO(payload), engine="openpyxl")
    found: dict[str, pd.DataFrame] = {}
    for sheet in book.sheet_names:
        key = next((name for name, aliases in SHEET_ALIASES.items() if sheet.strip().lower() in aliases), None)
        if key:
            found[key] = _normalise_columns(book.parse(sheet))
    required = {"bom", "materials", "capacity"}
    missing = sorted(required - found.keys())
    if missing:
        raise ValueError(f"Operations workbook is missing required sheet(s): {', '.join(missing)}")
    return found


def operations_preview(filename: str, payload: bytes) -> dict:
    sheets = read_operations_workbook(filename, payload)
    return {
        "filename": filename,
        "sheets": [
            {"name": name, "rows": int(len(frame)), "columns": list(frame.columns)}
            for name, frame in sheets.items()
        ],
        "rows": int(sum(len(frame) for frame in sheets.values())),
    }


def _number(value, default=0.0) -> float:
    try:
        number = float(value)
        return default if math.isnan(number) else number
    except (TypeError, ValueError):
        return default


def _records(frame: pd.DataFrame | None) -> list[dict]:
    if frame is None or frame.empty:
        return []
    clean = frame.copy()
    for col in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[col]):
            clean[col] = clean[col].dt.strftime("%Y-%m-%d")
    clean = clean.where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


def calculate_operations(result: dict, sheets: dict[str, pd.DataFrame]) -> dict:
    metadata = result.get("metadata", {})
    forecast_by_sku: dict[str, dict[str, float]] = defaultdict(dict)
    line_forecast: dict[tuple[str, str], float] = defaultdict(float)
    for item, payload in result.get("series", {}).items():
        if item == "__all__":
            continue
        sku = str(metadata.get(item, {}).get("sku") or item)
        for row in payload.get("forecast", []):
            period = pd.Timestamp(row["timestamp"]).to_period("M").to_timestamp()
            key = period.strftime("%Y-%m-%d")
            demand = _number(row.get("mean"))
            forecast_by_sku[sku][key] = forecast_by_sku[sku].get(key, 0.0) + demand
            line = str(metadata.get(item, {}).get("production_line") or "Unmapped")
            line_forecast[(line, key)] += demand

    bom = sheets["bom"].copy()
    materials = sheets["materials"].copy()
    capacity = sheets["capacity"].copy()
    open_pos = sheets.get("open_pos", pd.DataFrame())
    relationships = sheets.get("relationships", pd.DataFrame())
    promotions = sheets.get("promotions", pd.DataFrame())

    required_bom = {"sku", "material_id", "quantity_per_tonne"}
    required_materials = {"material_id", "material_name", "inventory_on_hand", "safety_stock", "lead_time_days", "moq"}
    required_capacity = {"production_line", "period", "available_tonnes"}
    for label, frame, required in [("BOM", bom, required_bom), ("Materials", materials, required_materials), ("Capacity", capacity, required_capacity)]:
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} sheet is missing column(s): {', '.join(missing)}")
        if frame[list(required)].isna().any().any():
            raise ValueError(f'{label} has blank required values. Fill them before continuing.')
    numeric_fields = [('BOM',bom,['quantity_per_tonne']),('Materials',materials,['inventory_on_hand','safety_stock','lead_time_days','moq']),('Capacity',capacity,['available_tonnes'])]
    for label, frame, columns in numeric_fields:
        for col in columns:
            values=pd.to_numeric(frame[col],errors='coerce')
            if (values.isna() | ~values.between(0,float('inf')) | values.eq(float('inf'))).any():
                raise ValueError(f'{label}: {col} needs finite, nonnegative numbers.')
    if materials.material_id.duplicated().any():
        raise ValueError('Materials must contain one row per material identifier.')
    if bom.duplicated(['sku','material_id']).any():
        raise ValueError('BOM must contain one row per product and material. Combine repeated components first.')
    capacity_dates=pd.to_datetime(capacity.period,errors='coerce')
    if capacity_dates.isna().any(): raise ValueError('Capacity contains unreadable period dates.')
    capacity['period']=capacity_dates.dt.to_period('M').dt.to_timestamp()
    if capacity.duplicated(['production_line','period']).any():
        raise ValueError('Capacity must contain one row per line and month.')
    if not open_pos.empty:
        if not {'material_id','due_date','quantity'}.issubset(open_pos.columns):
            raise ValueError('Open POs needs material_id, due_date and quantity columns.')
        values=pd.to_numeric(open_pos.quantity,errors='coerce')
        if (values.isna() | ~values.between(0,float('inf')) | values.eq(float('inf'))).any() or pd.to_datetime(open_pos.due_date,errors='coerce').isna().any():
            raise ValueError('Open POs has unreadable dates or invalid quantities.')
    missing_bom=set(forecast_by_sku)-set(bom.sku.astype(str))
    if missing_bom: raise ValueError('BOM is missing forecast products: '+', '.join(sorted(missing_bom)))
    available_keys={(str(r.production_line),r.period.strftime('%Y-%m-%d')) for r in capacity.itertuples()}
    missing_capacity=set(line_forecast)-available_keys
    if missing_capacity:
        raise ValueError('Capacity is missing forecast line/months: '+', '.join(f'{line} · {period}' for line,period in sorted(missing_capacity)[:5]))

    material_master = {str(row["material_id"]): row for row in materials.to_dict(orient="records")}
    receipt_by_material_period: dict[tuple[str, str], float] = defaultdict(float)
    if not open_pos.empty and {"material_id", "due_date", "quantity"}.issubset(open_pos.columns):
        for row in open_pos.to_dict(orient="records"):
            if str(row.get("status", "open")).lower() in {"cancelled", "closed", "received"}:
                continue
            period = pd.Timestamp(row["due_date"]).to_period("M").to_timestamp().strftime("%Y-%m-%d")
            receipt_by_material_period[(str(row["material_id"]), period)] += _number(row.get("quantity"))

    gross: dict[tuple[str, str], float] = defaultdict(float)
    for row in bom.to_dict(orient="records"):
        sku = str(row["sku"])
        material = str(row["material_id"])
        factor = _number(row.get("quantity_per_tonne")) * (1 + _number(row.get("scrap_pct")) / 100)
        for period, demand in forecast_by_sku.get(sku, {}).items():
            gross[(material, period)] += demand * factor

    material_rows: list[dict] = []
    action_rows: list[dict] = []
    for material_id, master in material_master.items():
        on_hand = _number(master.get("inventory_on_hand")) - _number(master.get("quality_hold_qty"))
        planned_balance = on_hand
        safety = _number(master.get("safety_stock"))
        moq = max(0.0, _number(master.get("moq")))
        lead = max(0, int(round(_number(master.get("lead_time_days")))))
        periods = sorted({period for mat, period in gross if mat == material_id} | {period for mat, period in receipt_by_material_period if mat == material_id})
        for period in periods:
            demand = gross[(material_id, period)]
            receipts = receipt_by_material_period[(material_id, period)]
            opening = on_hand
            on_hand = opening + receipts - demand
            shortfall = max(0.0, safety - on_hand)
            planned_balance += receipts - demand
            uncovered = max(0.0, safety - planned_balance)
            recommended = math.ceil(uncovered / moq) * moq if uncovered > 0 and moq > 0 else uncovered
            planned_balance += recommended
            release = (pd.Timestamp(period) - timedelta(days=lead)).strftime("%Y-%m-%d") if recommended > 0 else None
            row = {
                "material_id": material_id,
                "material_name": master.get("material_name"),
                "supplier": master.get("supplier"),
                "period": period,
                "opening": round(opening, 3),
                "gross_requirement": round(demand, 3),
                "scheduled_receipts": round(receipts, 3),
                "quality_hold_qty": round(_number(master.get("quality_hold_qty")), 3),
                "projected_balance": round(on_hand, 3),
                "balance_with_proposed_orders": round(planned_balance, 3),
                "safety_stock": round(safety, 3),
                "shortage": round(shortfall, 3),
                "recommended_order": round(recommended, 3),
                "planned_release_date": release,
                "lead_time_days": lead,
                "moq": moq,
                "unit": master.get("unit", "unit"),
                "status": "shortage" if shortfall > 0 else "covered",
            }
            material_rows.append(row)
            if recommended > 0:
                action_rows.append({
                    "priority": "high" if on_hand < 0 else "medium",
                    "type": "material_shortage",
                    "subject": str(master.get("material_name") or material_id),
                    "period": period,
                    "action": f"Release {recommended:,.1f} {master.get('unit', 'units')} by {release}",
                    "owner": "Procurement",
                })

    capacity_rows: list[dict] = []
    for row in capacity.to_dict(orient="records"):
        line = str(row["production_line"])
        period = pd.Timestamp(row["period"]).to_period("M").to_timestamp().strftime("%Y-%m-%d")
        available = _number(row.get("available_tonnes"))
        demand = line_forecast.get((line, period), 0.0)
        utilisation = demand / available * 100 if available > 0 else None
        status = "bottleneck" if demand > available else "watch" if utilisation is not None and utilisation > 90 else "available"
        capacity_row = {
            "production_line": line,
            "period": period,
            "forecast_tonnes": round(demand, 3),
            "available_tonnes": round(available, 3),
            "utilisation_pct": round(utilisation, 2) if utilisation is not None else None,
            "planned_downtime_hours": round(_number(row.get("planned_downtime_hours")), 2),
            "working_days": round(_number(row.get("working_days")), 1),
            "oee_target": round(_number(row.get("oee_target")), 3),
            "gap_tonnes": round(available - demand, 3),
            "status": status,
        }
        capacity_rows.append(capacity_row)
        if status in {"bottleneck", "watch"}:
            action_rows.append({
                "priority": "high" if status == "bottleneck" else "medium",
                "type": "capacity",
                "subject": line,
                "period": period,
                "action": f"Resolve {max(0, demand - available):,.1f} tonne capacity gap" if status == "bottleneck" else "Review sequence and planned downtime",
                "owner": "Production planning",
            })

    relationship_rows = _records(relationships)
    for row in relationship_rows:
        row["evidence"] = "master-data relationship"
        row["causality"] = "not inferred"
    promotion_rows = _records(promotions)
    return {
        "source": "uploaded operations master",
        "materials": material_rows,
        "capacity": capacity_rows,
        "actions": sorted(action_rows, key=lambda row: (row["priority"] != "high", row.get("period") or "")),
        "relationships": relationship_rows,
        "promotions": promotion_rows,
        "summary": {
            "material_shortages": sum(row["status"] == "shortage" for row in material_rows),
            "materials_at_risk": len({row["material_id"] for row in material_rows if row["status"] == "shortage"}),
            "capacity_bottlenecks": sum(row["status"] == "bottleneck" for row in capacity_rows),
            "capacity_watches": sum(row["status"] == "watch" for row in capacity_rows),
            "open_purchase_orders": int(len(open_pos)),
            "quality_hold_total": round(sum(_number(row.get("quality_hold_qty")) for row in material_master.values()), 3),
        },
    }


def append_operations_export(path, operations: dict) -> None:
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        pd.DataFrame(operations.get("materials", [])).to_excel(writer, sheet_name="Material Requirements", index=False)
        pd.DataFrame(operations.get("capacity", [])).to_excel(writer, sheet_name="Capacity Plan", index=False)
        pd.DataFrame(operations.get("actions", [])).to_excel(writer, sheet_name="Operational Actions", index=False)
        pd.DataFrame(operations.get("relationships", [])).to_excel(writer, sheet_name="Relationships", index=False)
        pd.DataFrame(operations.get("promotions", [])).to_excel(writer, sheet_name="Promotions", index=False)

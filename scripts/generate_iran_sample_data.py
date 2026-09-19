from __future__ import annotations

from pathlib import Path
import math

import holidays
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sample_data"
OUT.mkdir(exist_ok=True)
RNG = np.random.default_rng(1405)

history_dates = pd.date_range("2021-09-01", "2026-08-01", freq="MS")
future_dates = pd.date_range("2026-09-01", "2027-08-01", freq="MS")
all_dates = list(history_dates) + list(future_dates)

products = [
    ("PKG-KRAFT-120", "Kraft liner 120gsm", "Packaging paper", "Domestic", "Paper line A", 142, 1.10),
    ("PKG-BOARD-300", "Folding boxboard 300gsm", "Packaging board", "Domestic", "Board line", 116, 1.18),
    ("PKG-BOARD-350", "Folding boxboard 350gsm", "Packaging board", "Export", "Board line", 88, 1.16),
    ("OFF-UWF-080", "Uncoated woodfree 80gsm", "Writing paper", "Domestic", "Paper line B", 164, 0.92),
    ("OFF-UWF-070", "Uncoated woodfree 70gsm", "Writing paper", "Public sector", "Paper line B", 103, 0.96),
    ("COA-ART-135", "Coated art paper 135gsm", "Commercial print", "Domestic", "Coating line", 95, 1.04),
    ("COA-ART-170", "Coated art paper 170gsm", "Commercial print", "Domestic", "Coating line", 78, 1.02),
    ("LBL-STOCK-090", "Label stock 90gsm", "Labels", "FMCG", "Coating line", 73, 1.22),
    ("IND-CORE-250", "Industrial core board", "Industrial", "Domestic", "Board line", 82, 1.12),
    ("FOD-GRADE-110", "Food-grade paper 110gsm", "Food packaging", "FMCG", "Paper line A", 91, 1.20),
    ("NCR-SET-080", "NCR forms 80gsm", "Specialty", "Public sector", "Specialty line", 43, 0.86),
    ("EXP-KRAFT-140", "Export kraft 140gsm", "Packaging paper", "Export", "Paper line A", 68, 1.28),
]

events = {
    "2022-03-01": ("NOWRUZ_SHUTDOWN", 48),
    "2022-07-01": ("POWER_CURTAILMENT", 62),
    "2022-10-01": ("FX_PRESSURE", 51),
    "2023-03-01": ("NOWRUZ_SHUTDOWN", 50),
    "2023-07-01": ("POWER_CURTAILMENT", 70),
    "2023-11-01": ("IMPORT_DELAY", 58),
    "2024-03-01": ("NOWRUZ_SHUTDOWN", 53),
    "2024-06-01": ("PULP_COST_SHOCK", 65),
    "2024-08-01": ("POWER_CURTAILMENT", 76),
    "2025-03-01": ("NOWRUZ_SHUTDOWN", 55),
    "2025-05-01": ("EXPORT_ORDER", 47),
    "2025-07-01": ("POWER_CURTAILMENT", 72),
    "2025-12-01": ("FX_PRESSURE", 68),
    "2026-03-01": ("NOWRUZ_SHUTDOWN", 56),
    "2026-07-01": ("POWER_CURTAILMENT", 79),
    "2026-09-01": ("BACK_TO_BUSINESS", 32),
    "2026-10-01": ("FX_PRESSURE", 66),
    "2026-11-01": ("IMPORT_DELAY", 61),
    "2027-01-01": ("GAS_CURTAILMENT", 57),
    "2027-03-01": ("NOWRUZ_SHUTDOWN", 58),
    "2027-05-01": ("EXPORT_ORDER", 45),
    "2027-07-01": ("POWER_CURTAILMENT", 73),
}

notes = {
    "NOWRUZ_SHUTDOWN": "Synthetic Nowruz production calendar and customer closure effect.",
    "POWER_CURTAILMENT": "Synthetic summer electricity curtailment at the Qazvin site.",
    "GAS_CURTAILMENT": "Synthetic winter gas constraint reduces available production capacity.",
    "FX_PRESSURE": "Synthetic IRR exchange-rate pressure affects imported pulp and chemicals.",
    "IMPORT_DELAY": "Synthetic customs and supplier delay extends imported-material lead times.",
    "PULP_COST_SHOCK": "Synthetic global pulp-price increase raises input cost and customer prices.",
    "EXPORT_ORDER": "Synthetic confirmed export order increases selected packaging demand.",
    "BACK_TO_BUSINESS": "Synthetic post-summer demand recovery in industrial and commercial channels.",
}


def iran_working_days(month: pd.Timestamp) -> int:
    days = pd.date_range(month, month + pd.offsets.MonthEnd(0), freq="D")
    iran_holidays = holidays.country_holidays("IR", years=[month.year])
    return sum(1 for day in days if day.dayofweek != 4 and day.date() not in iran_holidays)


def macro(date: pd.Timestamp, idx: int) -> dict:
    key = date.strftime("%Y-%m-%d")
    event, severity = events.get(key, ("NORMAL", 8))
    years = idx / 12
    month_angle = (date.month - 1) / 12 * 2 * math.pi
    usd_irr = 265_000 * (1.17 ** years) * (1 + 0.025 * math.sin(idx / 3.7))
    cpi = 36 + 7 * math.sin(idx / 7.5) + 0.6 * years
    ppi = 100 * (1.21 ** years) * (1 + 0.018 * math.sin(idx / 4.8))
    industrial = 100 + 0.7 * years + 2.3 * math.sin(idx / 5.4)
    pulp_usd = 760 + 36 * math.sin(idx / 4.4) + 10 * years
    temperature = 16 + 14 * math.sin(month_angle - 1.25)
    curtailment = max(0, 4 + 20 * math.sin(month_angle - 1.1))
    import_lead = 48 + 4 * math.sin(idx / 4.1)
    supplier_fill = 0.94 - 0.025 * math.sin(idx / 5.3)
    logistics = 100 + 2.7 * years + 3 * math.sin(idx / 3.9)
    if event == "POWER_CURTAILMENT":
        curtailment += 54
    elif event == "GAS_CURTAILMENT":
        curtailment += 32
    elif event == "FX_PRESSURE":
        usd_irr *= 1.12
        cpi += 5
    elif event == "IMPORT_DELAY":
        import_lead += 29
        supplier_fill -= 0.12
        logistics += 12
    elif event == "PULP_COST_SHOCK":
        pulp_usd += 145
        logistics += 7
    return {
        "usd_irr_synthetic": round(usd_irr),
        "iran_cpi_yoy_synthetic": round(max(20, cpi), 1),
        "producer_price_index_synthetic": round(ppi, 1),
        "industrial_production_index_synthetic": round(industrial, 1),
        "global_pulp_price_usd_synthetic": round(pulp_usd, 1),
        "qazvin_temperature_c_synthetic": round(temperature, 1),
        "energy_curtailment_hours_synthetic": round(curtailment, 1),
        "import_lead_time_days_synthetic": round(import_lead, 1),
        "supplier_fill_rate_synthetic": round(max(0.65, supplier_fill), 3),
        "logistics_cost_index_synthetic": round(logistics, 1),
        "working_days": iran_working_days(date),
        "event_code": event,
        "event_severity": severity,
    }


history_rows: list[dict] = []
future_rows: list[dict] = []
for idx, dt in enumerate(all_dates):
    m = macro(dt, idx)
    future = dt > history_dates[-1]
    month_factor = {1: .95, 2: .94, 3: .72, 4: .92, 5: 1.02, 6: 1.04, 7: .98, 8: .91, 9: 1.12, 10: 1.15, 11: 1.10, 12: 1.04}[dt.month]
    for pidx, (sku, name, category, customer, line, base, growth) in enumerate(products):
        export = customer == "Export"
        specialty = category == "Specialty"
        trend = growth ** (idx / 60)
        price_irr = (410_000_000 + pidx * 21_000_000) * (m["producer_price_index_synthetic"] / 100)
        orders = 100 + (month_factor - 1) * 48 + 0.5 * (m["industrial_production_index_synthetic"] - 100)
        if m["event_code"] == "EXPORT_ORDER" and export:
            orders += 25
        if m["event_code"] in {"FX_PRESSURE", "IMPORT_DELAY"} and not export:
            orders -= 6
        if m["event_code"] == "BACK_TO_BUSINESS":
            orders += 8
        orders += RNG.normal(0, 2.2)
        open_orders = max(0, base * max(0.25, orders / 100) * RNG.uniform(.17, .31))
        backlog = max(0, open_orders * (1 - m["supplier_fill_rate_synthetic"]) * RNG.uniform(1.5, 2.4))
        maintenance = max(0, RNG.normal(6, 2) + (10 if m["event_code"] in {"POWER_CURTAILMENT", "GAS_CURTAILMENT"} else 0))
        promotion = max(0, RNG.normal(.04, .018))
        inventory = round(base * RNG.uniform(1.1, 1.8), 1)
        safety = round(base * RNG.uniform(.55, .82), 1)
        lead_time = round(m["import_lead_time_days_synthetic"] * RNG.uniform(.85, 1.2), 1)
        capacity = round(base * RNG.uniform(1.18, 1.42), 1)
        common = {
            "date": dt.strftime("%Y-%m-%d"),
            "series_id": f"{sku} · {customer}",
            "sku": sku,
            "product_name": name,
            "category": category,
            "customer": customer,
            "site": "Qazvin Manufacturing Site",
            "province": "Qazvin",
            "warehouse": "Qazvin Finished Goods",
            "production_line": line,
            "supplier": "Mixed domestic/imported supply",
            "inventory_on_hand_tonnes": inventory,
            "safety_stock_tonnes": safety,
            "lead_time_days": lead_time,
            "monthly_capacity_tonnes": capacity,
            "unit_cost_irr": round(price_irr * .73),
            "service_level_target": .96 if customer in {"FMCG", "Export"} else .93,
            "selling_price_irr_per_tonne": round(price_irr),
            "customer_orders_index": round(orders, 1),
            "open_orders_tonnes": round(open_orders, 1),
            "backlog_tonnes": round(backlog, 1),
            "maintenance_hours": round(maintenance, 1),
            "promotion_index": round(promotion, 3),
            **m,
        }
        if future:
            future_rows.append(common)
            continue
        demand = base * trend * month_factor
        demand *= 1 + .010 * (orders - 100)
        demand *= .90 + .0045 * m["working_days"]
        demand *= max(.74, 1 - .0022 * m["energy_curtailment_hours_synthetic"])
        demand *= .88 + .13 * m["supplier_fill_rate_synthetic"]
        if export:
            demand *= 1 + .0000011 * (m["usd_irr_synthetic"] - 265_000)
        if specialty and idx % 4 == 0:
            demand *= RNG.uniform(.08, .25)
        demand = max(0, demand + RNG.normal(0, 3.2 if not specialty else 5.0))
        history_rows.append({"demand_tonnes": round(demand, 2), **common})

history = pd.DataFrame(history_rows)
future = pd.DataFrame(future_rows)
history.to_csv(OUT / "iran_manufacturing_history_60m.csv", index=False)
future.to_csv(OUT / "iran_manufacturing_scenario_12m.csv", index=False)

event_rows = []
for dt in all_dates:
    code, severity = events.get(dt.strftime("%Y-%m-%d"), ("NORMAL", 8))
    if code != "NORMAL":
        event_rows.append({
            "phase": "historical" if dt <= history_dates[-1] else "scenario",
            "date": dt.strftime("%Y-%m-%d"),
            "event_code": code,
            "severity_0_100": severity,
            "scenario_note": notes[code],
        })
pd.DataFrame(event_rows).to_csv(OUT / "iran_scenario_event_notes.csv", index=False)

# A compact, fully synthetic operational master used to exercise BOM/MRP, supplier,
# purchase-order, capacity, lifecycle and relationship workflows end to end.
materials = pd.DataFrame([
    {"material_id": "PULP-HW", "material_name": "Hardwood pulp", "unit": "tonne", "inventory_on_hand": 720, "safety_stock": 260, "supplier": "Caspian Fibre Co.", "lead_time_days": 58, "moq": 120, "unit_cost_irr": 510_000_000, "quality_hold_qty": 42},
    {"material_id": "PULP-SW", "material_name": "Softwood pulp", "unit": "tonne", "inventory_on_hand": 510, "safety_stock": 210, "supplier": "Nordic Fibre Trading", "lead_time_days": 82, "moq": 100, "unit_cost_irr": 690_000_000, "quality_hold_qty": 0},
    {"material_id": "REC-FIBRE", "material_name": "Recovered fibre", "unit": "tonne", "inventory_on_hand": 980, "safety_stock": 300, "supplier": "Alborz Recycling", "lead_time_days": 18, "moq": 80, "unit_cost_irr": 165_000_000, "quality_hold_qty": 85},
    {"material_id": "STARCH", "material_name": "Industrial starch", "unit": "tonne", "inventory_on_hand": 118, "safety_stock": 52, "supplier": "Qazvin Starch", "lead_time_days": 21, "moq": 25, "unit_cost_irr": 310_000_000, "quality_hold_qty": 6},
    {"material_id": "CLAY", "material_name": "Coating clay", "unit": "tonne", "inventory_on_hand": 145, "safety_stock": 60, "supplier": "Central Minerals", "lead_time_days": 35, "moq": 30, "unit_cost_irr": 245_000_000, "quality_hold_qty": 0},
    {"material_id": "CHEM-WET", "material_name": "Wet-end chemicals", "unit": "tonne", "inventory_on_hand": 76, "safety_stock": 28, "supplier": "Pars Chemical", "lead_time_days": 29, "moq": 15, "unit_cost_irr": 425_000_000, "quality_hold_qty": 3},
])

bom_rows = []
for sku, _, category, _, _, _, _ in products:
    if category in {"Packaging paper", "Food packaging"}:
        mix = [("PULP-SW", .38), ("REC-FIBRE", .61), ("STARCH", .045), ("CHEM-WET", .018)]
    elif category in {"Packaging board", "Industrial"}:
        mix = [("REC-FIBRE", .82), ("PULP-HW", .19), ("STARCH", .052), ("CHEM-WET", .015)]
    elif category in {"Commercial print", "Labels"}:
        mix = [("PULP-HW", .57), ("PULP-SW", .36), ("CLAY", .24), ("STARCH", .038), ("CHEM-WET", .021)]
    else:
        mix = [("PULP-HW", .64), ("PULP-SW", .34), ("STARCH", .04), ("CHEM-WET", .019)]
    bom_rows.extend({"sku": sku, "material_id": material, "quantity_per_tonne": qty, "scrap_pct": 2.5} for material, qty in mix)
bom = pd.DataFrame(bom_rows)

open_pos = pd.DataFrame([
    {"po_number": "PO-260901", "material_id": "PULP-HW", "due_date": "2026-10-12", "quantity": 300, "status": "open"},
    {"po_number": "PO-260902", "material_id": "PULP-SW", "due_date": "2026-11-03", "quantity": 240, "status": "confirmed"},
    {"po_number": "PO-260903", "material_id": "REC-FIBRE", "due_date": "2026-09-18", "quantity": 420, "status": "confirmed"},
    {"po_number": "PO-260904", "material_id": "STARCH", "due_date": "2026-10-05", "quantity": 50, "status": "open"},
    {"po_number": "PO-260905", "material_id": "CLAY", "due_date": "2026-11-14", "quantity": 90, "status": "open"},
])

capacity_rows = []
line_base = {"Paper line A": 330, "Paper line B": 340, "Board line": 315, "Coating line": 300, "Specialty line": 86}
for dt in future_dates:
    for line, tonnes in line_base.items():
        curtail = macro(dt, all_dates.index(dt))["energy_curtailment_hours_synthetic"]
        downtime = (18 if dt.month in {3, 7} else 7) + curtail * .22
        capacity_rows.append({
            "production_line": line,
            "period": dt.strftime("%Y-%m-%d"),
            "available_tonnes": round(tonnes * max(.68, 1 - downtime / 240), 1),
            "planned_downtime_hours": round(downtime, 1),
            "working_days": iran_working_days(dt),
            "oee_target": .82 if line != "Specialty line" else .76,
        })
capacity = pd.DataFrame(capacity_rows)

relationships = pd.DataFrame([
    {"sku": "PKG-BOARD-300", "related_sku": "PKG-BOARD-350", "relationship_type": "substitute", "expected_effect_pct": -22, "effective_from": "2026-09-01", "effective_to": "2027-08-31"},
    {"sku": "OFF-UWF-080", "related_sku": "OFF-UWF-070", "relationship_type": "cannibalisation_watch", "expected_effect_pct": -12, "effective_from": "2026-09-01", "effective_to": "2027-08-31"},
    {"sku": "FOD-GRADE-110", "related_sku": "PKG-KRAFT-120", "relationship_type": "new_product_analog", "expected_effect_pct": 18, "effective_from": "2026-09-01", "effective_to": "2027-08-31"},
])
promotions = pd.DataFrame([
    {"promotion_id": "PROMO-001", "sku": "LBL-STOCK-090", "start_date": "2026-10-01", "end_date": "2026-11-30", "uplift_pct": 9, "status": "approved", "channel": "FMCG"},
    {"promotion_id": "TENDER-001", "sku": "OFF-UWF-070", "start_date": "2027-01-01", "end_date": "2027-03-31", "uplift_pct": 14, "status": "proposed", "channel": "Public sector"},
])
with pd.ExcelWriter(OUT / "iran_operations_master.xlsx", engine="openpyxl") as writer:
    bom.to_excel(writer, sheet_name="BOM", index=False)
    materials.to_excel(writer, sheet_name="Materials", index=False)
    open_pos.to_excel(writer, sheet_name="Open POs", index=False)
    capacity.to_excel(writer, sheet_name="Capacity Calendar", index=False)
    relationships.to_excel(writer, sheet_name="Relationships", index=False)
    promotions.to_excel(writer, sheet_name="Promotions", index=False)

# Three closed periods are intentionally synthetic and only used to demonstrate FVA.
actual_rows = []
for row in future_rows:
    if row["date"] > "2026-11-01":
        continue
    base = next(product[5] for product in products if product[0] == row["sku"])
    actual = base * (row["customer_orders_index"] / 100) * (0.96 + RNG.normal(0, .035))
    actual_rows.append({"item_id": row["series_id"], "timestamp": row["date"], "actual": round(max(0, actual), 2)})
pd.DataFrame(actual_rows).to_csv(OUT / "iran_actuals_followup_3m.csv", index=False)

print(f"Wrote {len(history)} history rows, {len(future)} future rows and the Iran operations master sample.")

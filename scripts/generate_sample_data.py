from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "sample_data"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(260909)

products = {
    "Coated 135gsm": {"base": 124.0, "price": 1110.0, "elasticity": 0.58, "segment": "commercial", "growth": 0.018},
    "Coated 170gsm": {"base": 99.0, "price": 1180.0, "elasticity": 0.61, "segment": "commercial", "growth": 0.012},
    "Uncoated 80gsm": {"base": 168.0, "price": 930.0, "elasticity": 0.44, "segment": "office", "growth": -0.010},
    "Board 300gsm": {"base": 96.0, "price": 1290.0, "elasticity": 0.39, "segment": "packaging", "growth": 0.040},
    "Kraft 120gsm": {"base": 84.0, "price": 1010.0, "elasticity": 0.35, "segment": "packaging", "growth": 0.052},
    "Newsprint 48.8gsm": {"base": 140.0, "price": 760.0, "elasticity": 0.50, "segment": "publishing", "growth": -0.035},
    "NCR 80gsm": {"base": 50.0, "price": 1420.0, "elasticity": 0.52, "segment": "forms", "growth": -0.012, "intermittent": True},
    "Labelstock 90gsm": {"base": 71.0, "price": 1560.0, "elasticity": 0.31, "segment": "labels", "growth": 0.060},
}

segment_month_factor = {
    "commercial": {1:.88,2:1.00,3:1.03,4:1.00,5:1.08,6:1.03,7:.96,8:.78,9:1.18,10:1.20,11:1.13,12:.96},
    "office": {1:.90,2:1.03,3:1.02,4:1.01,5:1.03,6:1.00,7:.91,8:.72,9:1.19,10:1.08,11:1.02,12:.83},
    "packaging": {1:.91,2:.99,3:1.00,4:1.03,5:1.05,6:1.04,7:1.02,8:.90,9:1.08,10:1.17,11:1.26,12:1.34},
    "publishing": {1:.86,2:1.00,3:1.07,4:1.03,5:1.01,6:.97,7:.90,8:.76,9:1.14,10:1.10,11:1.04,12:.92},
    "forms": {1:.93,2:1.02,3:1.01,4:1.00,5:1.02,6:1.00,7:.95,8:.80,9:1.12,10:1.06,11:1.02,12:.88},
    "labels": {1:.96,2:1.02,3:1.02,4:1.04,5:1.05,6:1.06,7:1.04,8:.94,9:1.08,10:1.12,11:1.17,12:1.20},
}

history_dates = pd.date_range("2023-09-01", "2026-08-01", freq="MS")
future_dates = pd.date_range("2026-09-01", "2027-02-01", freq="MS")
all_dates = list(history_dates) + list(future_dates)

incident_map = {
    "2023-10-01": ("FREIGHT_DISRUPTION", 38),
    "2023-12-01": ("HOLIDAY_MIX", 34),
    "2024-02-01": ("CUSTOMER_TENDER_LOSS", 44),
    "2024-04-01": ("ENERGY_SPIKE", 51),
    "2024-06-01": ("PULP_MAINTENANCE", 55),
    "2024-09-01": ("MAJOR_CUSTOMER_CAMPAIGN", 46),
    "2024-11-01": ("PACKAGING_PEAK", 40),
    "2025-01-01": ("INDUSTRIAL_SLOWDOWN", 47),
    "2025-03-01": ("FX_VOLATILITY", 42),
    "2025-05-01": ("COMPETITOR_DISCOUNT", 39),
    "2025-07-01": ("HEATWAVE_RISK", 58),
    "2025-09-01": ("BACK_TO_BUSINESS_UPLIFT", 36),
    "2025-11-01": ("MAJOR_CONTRACT_WIN", 52),
    "2026-01-01": ("LOGISTICS_NORMALIZATION", 22),
    "2026-04-01": ("ENERGY_SPIKE", 38),
    "2026-05-01": ("PROMO_UPLIFT", 28),
    "2026-06-01": ("PULP_MAINTENANCE", 52),
    "2026-07-01": ("HEATWAVE_RISK", 63),
    "2026-08-01": ("SUMMER_SLOWDOWN", 42),
    "2026-09-01": ("SEASONAL_UPLIFT", 28),
    "2026-10-01": ("PULP_SUPPLY_SHOCK", 78),
    "2026-11-01": ("FX_ENERGY_SQUEEZE", 69),
    "2026-12-01": ("HOLIDAY_MIX", 46),
    "2027-01-01": ("PORT_CONGESTION", 73),
    "2027-02-01": ("RECOVERY", 24),
}

notes_text = {
    "NORMAL": "Baseline month with no material synthetic shock.",
    "FREIGHT_DISRUPTION": "Synthetic freight disruption raises logistics cost and supply uncertainty.",
    "HOLIDAY_MIX": "Packaging and label demand strengthens while office/commercial printing loses working days.",
    "CUSTOMER_TENDER_LOSS": "A synthetic large tender loss reduces office/forms order pipeline for several months.",
    "ENERGY_SPIKE": "Regional energy-cost shock raises conversion costs and selling prices.",
    "PULP_MAINTENANCE": "Supplier maintenance tightens pulp availability and raises pulp/logistics costs.",
    "MAJOR_CUSTOMER_CAMPAIGN": "Large customer campaign lifts commercial print and label order pipeline.",
    "PACKAGING_PEAK": "Retail and e-commerce activity drives an unusually strong packaging month.",
    "INDUSTRIAL_SLOWDOWN": "Industrial activity and B2B order intake soften broadly.",
    "FX_VOLATILITY": "EUR volatility increases imported input cost and pricing uncertainty.",
    "COMPETITOR_DISCOUNT": "A synthetic competitor price campaign pressures price-sensitive categories.",
    "HEATWAVE_RISK": "Heatwave/wildfire exposure increases energy and environmental risk.",
    "BACK_TO_BUSINESS_UPLIFT": "Autumn campaigns and business reopening lift commercial and office demand.",
    "MAJOR_CONTRACT_WIN": "A large packaging/label contract creates confirmed demand and backlog.",
    "LOGISTICS_NORMALIZATION": "Freight and logistics conditions normalize after prior volatility.",
    "PROMO_UPLIFT": "Commercial campaign activity and promotions lift selected print categories.",
    "SUMMER_SLOWDOWN": "Holiday shutdowns reduce working days and commercial print demand.",
    "SEASONAL_UPLIFT": "Back-to-school, catalogue and autumn campaign demand lifts orders.",
    "PULP_SUPPLY_SHOCK": "Synthetic pulp mill disruption plus forestry constraints cause a sharp raw-material shock.",
    "FX_ENERGY_SQUEEZE": "EUR weakens while energy costs rise; price-sensitive customer demand softens.",
    "PORT_CONGESTION": "Synthetic port congestion raises logistics costs and delays customer commitments.",
    "RECOVERY": "Supply conditions normalize; customer-order pipeline and activity recover.",
}


def working_days_for(date: pd.Timestamp) -> int:
    # Plausible monthly business-day pattern; deliberately simplified for a dummy dataset.
    base = {1:21,2:20,3:22,4:20,5:21,6:21,7:23,8:17,9:22,10:22,11:21,12:18}[date.month]
    return base + (1 if date.year == 2024 and date.month in {1,7,10} else 0)


def macro_for(date: pd.Timestamp, idx: int) -> dict:
    year_progress = idx / 12.0
    key = date.strftime("%Y-%m-%d")
    event, severity = incident_map.get(key, ("NORMAL", 8))

    eur = 1.085 + 0.022 * math.sin(idx / 4.4) - 0.004 * year_progress
    pulp = 112 + 2.6 * year_progress + 4.5 * math.sin(idx / 3.8)
    energy = 101 + 6.5 * math.cos((date.month - 1) / 12 * 2 * math.pi) + 1.2 * year_progress
    inflation = max(1.7, 3.4 - 0.55 * year_progress + 0.18 * math.sin(idx / 5.0))
    activity = 101.0 + 1.4 * math.sin(idx / 5.2) + 0.45 * year_progress
    env = 14 + (30 if date.month in {6,7,8} else 5 if date.month in {5,9} else 0) + 4 * math.sin(idx / 2.7)
    supply = 13 + 3 * math.sin(idx / 3.1)
    logistics = 103 + 0.18 * (energy - 100) + 0.15 * supply + 0.8 * year_progress
    competitor = 100 + 1.7 * year_progress + 0.06 * (pulp - 112) + 0.025 * (energy - 100)
    paper_market = 100 + 0.7 * year_progress + 1.8 * math.sin(idx / 4.8)

    if event == "FREIGHT_DISRUPTION": supply += 28; logistics += 15
    elif event == "ENERGY_SPIKE": energy += 18; logistics += 4
    elif event == "PULP_MAINTENANCE": pulp += 12; supply += 30; logistics += 8
    elif event == "INDUSTRIAL_SLOWDOWN": activity -= 3.6; paper_market -= 2.5
    elif event == "FX_VOLATILITY": eur -= 0.042
    elif event == "COMPETITOR_DISCOUNT": competitor -= 5.5
    elif event == "HEATWAVE_RISK": env += 38; energy += 10; supply += 16
    elif event == "LOGISTICS_NORMALIZATION": supply -= 6; logistics -= 8
    elif event == "PULP_SUPPLY_SHOCK": pulp += 18; env += 30; supply += 54; logistics += 17
    elif event == "FX_ENERGY_SQUEEZE": eur -= 0.052; energy += 22; supply += 25; logistics += 14; activity -= 1.5
    elif event == "PORT_CONGESTION": supply += 47; logistics += 24; activity -= 1.0
    elif event == "RECOVERY": supply -= 5; logistics -= 5; activity += 1.0

    return {
        "eur_usd": round(max(0.98, eur), 3),
        "pulp": round(max(95, pulp), 1),
        "energy": round(max(85, energy), 1),
        "inflation": round(inflation, 2),
        "activity": round(activity, 1),
        "env": round(max(5, env), 1),
        "supply": round(max(5, supply), 1),
        "logistics": round(max(90, logistics), 1),
        "workdays": working_days_for(date),
        "competitor": round(max(90, competitor), 1),
        "paper_market": round(paper_market, 1),
        "event": event,
        "severity": severity,
    }

macro = {d.strftime("%Y-%m-%d"): macro_for(d, i) for i, d in enumerate(all_dates)}

segment_bias = {"commercial":2,"office":0,"packaging":4,"publishing":-2,"forms":-1,"labels":3}
contract_share = {"commercial":.24,"office":.20,"packaging":.36,"publishing":.18,"forms":.28,"labels":.40}


def product_signals(product: str, cfg: dict, date: pd.Timestamp, m: dict, month_idx: int, future: bool):
    seasonal = segment_month_factor[cfg["segment"]][date.month]
    trend = (1 + cfg["growth"]) ** (month_idx / 12.0)
    orders = 100 + segment_bias[cfg["segment"]] + (seasonal - 1) * 45 + 2.0 * (m["activity"] - 101) + rng.normal(0, 2.1)
    quote = 100 + (seasonal - 1) * 40 + 1.3 * (m["paper_market"] - 100) + rng.normal(0, 2.4)
    promo = max(0.0, rng.normal(0.065, 0.022))

    e = m["event"]
    seg = cfg["segment"]
    if e == "CUSTOMER_TENDER_LOSS" and seg in {"office","forms"}: orders -= 15; quote -= 12
    if e == "MAJOR_CUSTOMER_CAMPAIGN" and seg in {"commercial","labels"}: orders += 13; quote += 11; promo += .13
    if e == "PACKAGING_PEAK" and seg in {"packaging","labels"}: orders += 11; quote += 8; promo += .05
    if e == "INDUSTRIAL_SLOWDOWN": orders -= 8; quote -= 9
    if e == "COMPETITOR_DISCOUNT" and seg in {"commercial","office","publishing","forms"}: orders -= 8; quote -= 7
    if e == "BACK_TO_BUSINESS_UPLIFT" and seg in {"commercial","office","publishing"}: orders += 9; quote += 8; promo += .06
    if e == "MAJOR_CONTRACT_WIN" and seg in {"packaging","labels"}: orders += 14; quote += 10
    if e == "PROMO_UPLIFT" and seg in {"commercial","labels"}: orders += 9; quote += 7; promo += .17
    if e == "SUMMER_SLOWDOWN" and seg in {"commercial","office","publishing","forms"}: orders -= 12; quote -= 9
    if e == "SEASONAL_UPLIFT": orders += 8 if seg in {"commercial","office","publishing"} else 4; quote += 6; promo += .08 if seg in {"commercial","office"} else .03
    if e == "PULP_SUPPLY_SHOCK": orders += 3 if seg in {"packaging","labels"} else -2
    if e == "FX_ENERGY_SQUEEZE": orders -= 8 if seg in {"commercial","office","publishing","forms"} else 3; quote -= 6
    if e == "HOLIDAY_MIX": orders += 10 if seg in {"packaging","labels"} else -6; promo += .08 if seg in {"packaging","labels"} else .01
    if e == "PORT_CONGESTION": orders -= 7; quote -= 5
    if e == "RECOVERY": orders += 6; quote += 5

    contract = max(2.0, cfg["base"] * seasonal * trend * contract_share[seg] * (orders / 100) + rng.normal(0, 2.2))
    backlog = max(0.0, cfg["base"] * max(0, orders - 92) / 100 * 0.20 + 0.10 * m["supply"] + rng.normal(0, 1.8))

    cost_pressure = (
        0.0017 * (m["pulp"] - 112)
        + 0.0009 * (m["energy"] - 100)
        + 0.34 * max(0, 1.075 - m["eur_usd"])
        + 0.0008 * (m["logistics"] - 103)
    )
    price = cfg["price"] * (1 + cost_pressure)
    if future and e in {"PULP_SUPPLY_SHOCK","FX_ENERGY_SQUEEZE"}: price *= 1.022
    price *= 1 + rng.normal(0, .005)

    return orders, quote, min(.45, promo), contract, backlog, price, trend


def demand_from_signals(cfg: dict, date: pd.Timestamp, m: dict, orders: float, quote: float, promo: float, contract: float, backlog: float, price: float, trend: float, month_idx: int):
    seasonal = segment_month_factor[cfg["segment"]][date.month]
    price_ratio = price / cfg["price"]
    macro_demand = 1 + .013 * (m["activity"] - 100) - .006 * (m["inflation"] - 2.0) + .004 * (m["paper_market"] - 100)
    order_effect = 1 + .0105 * (orders - 100) + .0035 * (quote - 100)
    promo_effect = 1 + .33 * promo
    price_effect = max(.68, 1 - cfg["elasticity"] * (price_ratio - 1))
    workday_effect = .93 + .0035 * m["workdays"]
    disruption_effect = max(.75, 1 - .0009 * m["supply"] - .00035 * m["env"])
    contract_effect = 1 + .09 * (contract / max(cfg["base"], 1))
    competitor_effect = 1 + .0035 * (m["competitor"] - 100)
    backlog_effect = 1 + .025 * min(1.0, backlog / max(cfg["base"], 1))

    demand = cfg["base"] * trend * seasonal * macro_demand * order_effect * promo_effect * price_effect * workday_effect * disruption_effect * contract_effect * competitor_effect * backlog_effect

    if cfg.get("intermittent"):
        # Project/tender-driven series: deliberately sparse so intermittent-demand models have a reason to exist.
        active = ((month_idx + 1) % 4 != 0) or m["event"] in {"MAJOR_CUSTOMER_CAMPAIGN","MAJOR_CONTRACT_WIN","SEASONAL_UPLIFT"}
        if not active:
            demand *= rng.uniform(0.04, 0.15)
        elif month_idx % 7 == 0:
            demand *= rng.uniform(1.35, 1.75)

    noise_scale = 2.6 if not cfg.get("intermittent") else 3.5
    return max(0.0, demand + rng.normal(0, noise_scale))

history_rows = []
future_rows = []
for month_idx, date in enumerate(all_dates):
    date_str = date.strftime("%Y-%m-%d")
    m = macro[date_str]
    is_future = date > history_dates[-1]
    for product, cfg in products.items():
        orders, quote, promo, contract, backlog, price, trend = product_signals(product, cfg, date, m, month_idx, is_future)
        common = {
            "date": date_str,
            "series_id": product,
            "selling_price_eur_per_tonne": round(price, 2),
            "eur_usd": m["eur_usd"],
            "pulp_price_index": m["pulp"],
            "energy_price_index": m["energy"],
            "inflation_yoy": m["inflation"],
            "industrial_activity_index": m["activity"],
            "paper_market_demand_index": m["paper_market"],
            "customer_orders_index": round(orders, 2),
            "quote_pipeline_index": round(quote, 2),
            "confirmed_contract_tonnes": round(contract, 2),
            "backlog_tonnes": round(backlog, 2),
            "promotion_index": round(promo, 3),
            "environmental_risk_index": m["env"],
            "supply_disruption_index": m["supply"],
            "logistics_cost_index": m["logistics"],
            "working_days": m["workdays"],
            "competitor_price_index": m["competitor"],
            "event_code": m["event"],
            "event_severity": m["severity"],
        }
        if is_future:
            future_rows.append(common)
        else:
            demand = demand_from_signals(cfg, date, m, orders, quote, promo, contract, backlog, price, trend, month_idx)
            row = {"date": date_str, "series_id": product, "demand_tonnes": round(demand, 2), **{k:v for k,v in common.items() if k not in {"date","series_id"}}}
            row["revenue_eur"] = round(demand * price, 2)
            history_rows.append(row)

history = pd.DataFrame(history_rows)
future = pd.DataFrame(future_rows)
history.to_csv(OUT / "paper_printing_history_36m.csv", index=False)
future.to_csv(OUT / "paper_printing_scenario_6m.csv", index=False)
history.to_csv(OUT / "paper_printing_history.csv", index=False)
future.to_csv(OUT / "paper_printing_future_drivers.csv", index=False)

notes = []
for date in all_dates:
    date_str = date.strftime("%Y-%m-%d")
    m = macro[date_str]
    if m["event"] == "NORMAL":
        continue
    notes.append({
        "phase": "historical" if date <= history_dates[-1] else "scenario",
        "date": date_str,
        "event_code": m["event"],
        "severity_0_100": m["severity"],
        "scenario_note": notes_text[m["event"]],
    })
pd.DataFrame(notes).to_csv(OUT / "scenario_event_notes.csv", index=False)

readme = f"""Paper & printing dummy data\n\nHistory: {history_dates[0].date()} to {history_dates[-1].date()} (36 monthly periods)\nScenario: {future_dates[0].date()} to {future_dates[-1].date()} (6 monthly periods)\nSeries: {len(products)}\nHistory rows: {len(history)}\nScenario rows: {len(future)}\n\nAll events and values are synthetic and intended only for the forecasting POC.\n"""
(OUT / "README.md").write_text(readme, encoding="utf-8")
print(f"Wrote {len(history)} history rows and {len(future)} scenario rows to {OUT}")

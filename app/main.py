from __future__ import annotations

# Acquire before importing stores, which can initialize or migrate databases.
from .workspace_lock import WorkspaceLease
from pathlib import Path as _WorkspacePath
_WORKSPACE_LEASE = WorkspaceLease(_WorkspacePath(__file__).resolve().parent.parent)

import json
import os
import hashlib
from io import BytesIO
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from threading import RLock
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from persiantools.jdatetime import JalaliDate

from .data import build_future_covariates, preview_table, prepare_history, read_table, summarize_history, actual_history, source_review
from .forecast_engine import run_forecast
from .assistant import answer_planning_question, suggest_mapping
from .integrations import IntegrationStore
from .folder_inputs import FolderInputs
from .decisions import DecisionStore, DecisionConflict
from .monitoring import build_monitoring, forecast_value_add
from .operations import append_operations_export, calculate_operations, operations_preview, read_operations_workbook
from .planning import PlanStore
from .today import build_today
from .security import AccessControl, SecurityConfig, install_access, identity_fields
from .plan_outputs import resolve_plan, plan_workbook
from .datasets import DatasetStore
from .scenarios import quantity_scenario
from .factors import FactorStore, CATALOG
from .supply_pressure import freshness as supply_freshness
from .weather import WeatherStore, weather_csv
from .runtime import output_directory, checkpoint
from . import jobs
from .inventory import InventoryStore, inventory_preview, project_inventory, raw_table, text_value
from .units import UnitStore, STANDARD
from .production_mapping import production_schema as get_production_schema
from .actuals import ActualsStore, export_actuals
from .assumptions import preview_assumptions, save_assumptions
from .sales_conventions import normalize_history


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
RUNS_DIR = BASE_DIR / "runs"
SAMPLES_DIR = BASE_DIR / "sample_data"
DATA_DIR = BASE_DIR / "data"
RUNS_DIR.mkdir(exist_ok=True)
PLAN_STORE = PlanStore(DATA_DIR / "plans.json")
DECISION_STORE = DecisionStore(DATA_DIR / 'decisions.sqlite3')
UNIT_STORE = UnitStore(DATA_DIR / 'units.sqlite3')
DATASET_STORE = DatasetStore(DATA_DIR / "datasets", UNIT_STORE)
INVENTORY_STORE = InventoryStore(DATA_DIR / 'inventory.sqlite3', DATASET_STORE)
ACTUALS_STORE = ActualsStore(DATA_DIR / 'actuals.sqlite3', DATASET_STORE)
FACTOR_STORE = FactorStore(DATA_DIR / "factors")
WEATHER_STORE = WeatherStore(DATA_DIR / 'weather')
INTEGRATION_STORE = IntegrationStore(DATA_DIR / "integrations.json")
FOLDER_INPUTS = FolderInputs(DATA_DIR / 'folder-inputs.sqlite3', DATASET_STORE,
    json.loads(os.getenv('DEMANDLAB_IMPORT_ROOTS', json.dumps([str(SAMPLES_DIR)]))))
if not INTEGRATION_STORE.list():
    INTEGRATION_STORE.upsert({
        "id": "sample-folder",
        "name": "Bundled sample-data folder",
        "type": "folder",
        "path": str(SAMPLES_DIR),
        "enabled": False,
        "schedule_minutes": 0,
        "status": "not_tested",
    })

app = FastAPI(title="DemandLab", version="1.0.0")
ACCESS = AccessControl(SecurityConfig.from_env(), DATA_DIR)
install_access(app, ACCESS)
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@app.on_event('startup')
def start_integrations():
    if ACCESS.config.mode == 'better_auth':
        return
    INTEGRATION_STORE.restore_schedules()
    for config in FOLDER_INPUTS.list():
        schedule_folder(config)


def scheduled_folder_check(identifier):
    return FOLDER_INPUTS.scheduled_check(identifier, lambda dataset_id, candidate_id:
        create_job(JobRequest(dataset_id=dataset_id, request_id='folder-draft:'+candidate_id)))


def schedule_folder(config):
    scheduler = INTEGRATION_STORE.scheduler
    key = 'folder-input-'+config['id']
    if scheduler.get_job(key): scheduler.remove_job(key)
    if config['enabled'] and config['minutes']:
        scheduler.add_job(scheduled_folder_check, 'interval', minutes=config['minutes'],
            args=[config['id']], id=key, max_instances=1, coalesce=True)


@app.on_event("shutdown")
def shutdown_integrations():
    INTEGRATION_STORE.close()

SITE_PROFILE = {
    "id": "iran-site-01",
    "name": "Manufacturing site",
    "country": "Iran",
    "province": "Not set",
    "timezone": "Asia/Tehran",
    "currency": "IRR",
    "currency_display": "rial",
    "calendar": "Jalali + Gregorian",
    "latitude": None,
    "longitude": None,
}
SITE_PATH = DATA_DIR / 'site.json'
SITE_LOCK = RLock()
if SITE_PATH.exists():
    SITE_PROFILE.update(json.loads(SITE_PATH.read_text(encoding='utf-8')))


class SiteConfig(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    province: str = Field(min_length=2, max_length=100)
    timezone: str = Field(min_length=2, max_length=80)


@app.put('/api/site')
def save_site(payload: SiteConfig):
    try:
        ZoneInfo(payload.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(400, 'Use a recognised time zone, such as Asia/Tehran.')
    if not payload.name.strip() or not payload.province.strip():
        raise HTTPException(400, 'Enter a site name and province.')
    with SITE_LOCK:
        updated = {**SITE_PROFILE, **{k:v.strip() for k,v in payload.model_dump().items()}}
        temp = SITE_PATH.with_suffix('.tmp')
        temp.write_text(json.dumps(updated,ensure_ascii=False),encoding='utf-8')
        temp.replace(SITE_PATH)
        SITE_PROFILE.update(updated)
    return {'site':updated}


class PlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    run_id: str
    site_id: str = SITE_PROFILE["id"]
    owner: str = "Planning team"


class PlanTransition(BaseModel):
    status: str
    actor: str = "Planning team"
    note: str = ""


class PlanRevision(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=3, max_length=500)
    request_id: str


class ForecastOverride(BaseModel):
    item_id: str
    period: str
    value: float = Field(ge=0, allow_inf_nan=False)
    reason: str = Field(min_length=3, max_length=500)
    actor: str = "Planning team"


class PlanComment(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    actor: str = "Planning team"


class OverrideReversal(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    actor: str = "Planning team"


class IntegrationConfig(BaseModel):
    id: str | None = None
    name: str = Field(min_length=2, max_length=120)
    type: str
    enabled: bool = False
    schedule_minutes: int = Field(default=0, ge=0, le=10080)
    path: str | None = None
    url: str | None = None
    secret_env: str | None = None
    query: str | None = None


class AssistantQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    run_id: str | None = None


class MappingQuestion(BaseModel):
    columns: list[str]
    numeric_columns: list[str] = Field(default_factory=list)
    date_candidates: list[str] = Field(default_factory=list)


class DatasetConfig(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sources: dict[str,str]
    settings: dict
    classification: str = "user_provided"
    accept_warnings: bool = False
    parent_dataset_id: str | None = None
    import_candidate_id: str | None = None
    request_id: str | None = Field(default=None,min_length=1,max_length=200)


class DecisionUpdate(BaseModel):
    run_id: str = Field(min_length=1,max_length=100)
    plan_id: str | None = None
    decision_id: str = Field(min_length=1,max_length=1000)
    evidence_token: str = Field(pattern=r'^[0-9a-f]{64}$')
    version: int = Field(ge=0,strict=True)
    owner: str = Field(min_length=1,max_length=120)
    due_date: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    status: str
    note: str = Field(min_length=3,max_length=2000)
    request_id: str = Field(min_length=1,max_length=200)


class SavedRunConfig(BaseModel):
    dataset_id: str
    method: str | None = None
    adjustment: float = Field(default=0,ge=-90,le=300)
    scenario_name: str | None = None
    base_run_id: str | None = None
    sales_input_id: str | None = Field(default=None, min_length=32, max_length=32)
    forecast_group_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    forecast_name: str | None = Field(default=None, min_length=1, max_length=160)


async def _read_upload(file: UploadFile) -> bytes:
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("File is larger than the 50 MB local-processing limit.")
    if not payload:
        raise ValueError("The uploaded file is empty.")
    return payload


def _safe_text(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "<na>"}:
        return None
    return text


def _series_metadata(df, *, item_col: str, sku_col: str, category_col: str, customer_col: str) -> dict:
    if not item_col or item_col not in df.columns:
        return {"Total demand": {"sku": "Total demand", "category": None, "customer": None}}
    cols = [c for c in [item_col, sku_col, category_col, customer_col] if c and c in df.columns]
    work = df[cols].dropna(subset=[item_col]).copy()
    if work.empty:
        return {}
    work[item_col] = work[item_col].astype(str)
    out = {}
    operational_fields = [
        "site", "province", "warehouse", "production_line", "supplier",
        "inventory_on_hand_tonnes", "safety_stock_tonnes", "lead_time_days",
        "monthly_capacity_tonnes", "unit_cost_irr", "service_level_target",
    ]
    for item_id, grp in work.groupby(item_col, sort=False):
        source_row = df[df[item_col].astype(str) == str(item_id)].iloc[-1]
        row = grp.iloc[-1]
        out[str(item_id)] = {
            "sku": _safe_text(row.get(sku_col)) if sku_col else str(item_id),
            "category": _safe_text(row.get(category_col)) if category_col else None,
            "customer": _safe_text(row.get(customer_col)) if customer_col else None,
        }
        for field in operational_fields:
            if field in df.columns:
                value = source_row.get(field)
                out[str(item_id)][field] = _json_value(value)
    return out


def _json_value(value):
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    try:
        if value != value:
            return None
    except Exception:
        pass
    return value


@app.get("/api/health")
def health():
    try:
        import sklearn
        return {
            "ok": True,
            "engine_ready": True,
            "engine_name": "Hybrid statistical + ML ensemble",
            "engine_version": getattr(sklearn, "__version__", None),
            "engine_error": None,
        }
    except Exception as exc:
        return {
            "ok": True,
            "engine_ready": False,
            "engine_name": "Hybrid statistical + ML ensemble",
            "engine_version": None,
            "engine_error": str(exc),
        }


@app.post("/api/preview")
async def preview(file: UploadFile = File(...)):
    try:
        payload = await _read_upload(file)
        return preview_table(file.filename or "data.csv", payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/operations/preview")
async def preview_operations(file: UploadFile = File(...)):
    try:
        payload = await _read_upload(file)
        return operations_preview(file.filename or "operations.xlsx", payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/run")
async def run(
    historical_file: UploadFile = File(...),
    future_file: UploadFile | None = File(None),
    operations_file: UploadFile | None = File(None),
    date_col: str = Form(...),
    target_col: str = Form(...),
    item_col: str = Form(""),
    sku_col: str = Form(""),
    category_col: str = Form(""),
    customer_col: str = Form(""),
    future_date_col: str = Form(""),
    future_item_col: str = Form(""),
    driver_cols_json: str = Form("[]"),
    known_driver_cols_json: str = Form("[]"),
    driver_roles_json: str = Form("{}"),
    frequency: str = Form("monthly"),
    horizon: int = Form(6),
    profile: str = Form("deep"),
    missing_strategy: str = Form("auto"),
    outlier_strategy: str = Form("winsorize"),
    scenario_adjustment_pct: float = Form(0.0),
    method_selection: str = Form("recommended"),
    future_driver_policy: str = Form("require"),
    source_classification: str = Form("user_provided"),
    unit_filter: str = Form(""),
    calendar_json: str = Form('{"country":"IR","weekend_days":[4],"shutdown_dates":[]}'),
    excluded_items_json: str = Form('[]'),
    quantity_unit: str = Form('units'),
    operations_mapping_json: str = Form('null'),
    production_line_col: str = Form('production_line'),
    sales_conventions_json: str = Form('{}'),
    evidence_policy: str = Form('standard'),
):
    return await _calculate_upload(**locals())


async def _calculate_upload(
    historical_file: UploadFile = File(...),
    future_file: UploadFile | None = File(None),
    operations_file: UploadFile | None = File(None),
    date_col: str = Form(...),
    target_col: str = Form(...),
    item_col: str = Form(""),
    sku_col: str = Form(""),
    category_col: str = Form(""),
    customer_col: str = Form(""),
    future_date_col: str = Form(""),
    future_item_col: str = Form(""),
    driver_cols_json: str = Form("[]"),
    known_driver_cols_json: str = Form("[]"),
    driver_roles_json: str = Form("{}"),
    frequency: str = Form("monthly"),
    horizon: int = Form(6),
    profile: str = Form("deep"),
    missing_strategy: str = Form("auto"),
    outlier_strategy: str = Form("winsorize"),
    scenario_adjustment_pct: float = Form(0.0),
    method_selection: str = Form("recommended"),
    future_driver_policy: str = Form("require"),
    source_classification: str = Form("user_provided"),
    unit_filter: str = Form(""),
    calendar_json: str = Form('{"country":"IR","weekend_days":[4],"shutdown_dates":[]}'),
    excluded_items_json: str = Form('[]'),
    quantity_unit: str = Form('units'),
    operations_mapping_json: str = Form('null'),
    production_line_col: str = Form('production_line'),
    sales_conventions_json: str = Form('{}'),
    evidence_policy: str = Form('standard'),
    workspace=None,
):
    RUNS_DIR = workspace.runs if workspace else globals()['RUNS_DIR']
    UNIT_STORE = workspace.units if workspace else globals()['UNIT_STORE']
    SITE_PROFILE = workspace.site if workspace else globals()['SITE_PROFILE']
    try:
        if frequency not in {"monthly", "weekly", "daily"}:
            raise ValueError("Frequency must be monthly, weekly, or daily.")
        if not 1 <= horizon <= 24:
            raise ValueError("Forecast horizon must be between 1 and 24 periods.")
        if profile not in {"fast", "deep"}:
            raise ValueError("Profile must be fast or deep.")
        if future_driver_policy not in {"require", "carry", "median"}:
            raise ValueError("Future-driver policy must be require, carry, or median.")
        if source_classification not in {"user_provided", "synthetic_sample"}:
            raise ValueError("Unknown source classification.")

        driver_cols = json.loads(driver_cols_json)
        known_driver_cols = json.loads(known_driver_cols_json)
        driver_roles = json.loads(driver_roles_json)
        calendar = json.loads(calendar_json) if isinstance(calendar_json, str) else {"country": "IR", "weekend_days": [4], "shutdown_dates": []}
        if not isinstance(driver_cols, list) or not isinstance(known_driver_cols, list):
            raise ValueError("Driver selections must be lists.")
        if not isinstance(driver_roles, dict):
            raise ValueError("Driver roles must be an object.")
        if not -90.0 <= scenario_adjustment_pct <= 300.0:
            raise ValueError("Scenario adjustment must be between -90% and +300%.")
        known_driver_cols = [c for c in known_driver_cols if c in driver_cols]
        driver_roles = {str(k): str(v) for k, v in driver_roles.items() if k in driver_cols}

        hist_payload = await _read_upload(historical_file)
        checkpoint('Checking saved inputs')
        raw_history = read_table(historical_file.filename or "history.csv", hist_payload)
        exclusions = json.loads(excluded_items_json) if isinstance(excluded_items_json, str) else []
        model_history, workbook_warnings = actual_history(raw_history, unit_filter=unit_filter if isinstance(unit_filter, str) else None, excluded_items=exclusions, item_col=item_col)
        conventions = json.loads(sales_conventions_json) if isinstance(sales_conventions_json, str) else {}
        group_settings = {**conventions, 'date_col':date_col, 'target_col':target_col,
                          'item_col':item_col if isinstance(item_col,str) else '',
                          'sku_col':sku_col if isinstance(sku_col,str) else '',
                          'customer_col':customer_col if isinstance(customer_col,str) else '',
                          'future_item_col':future_item_col if isinstance(future_item_col,str) else '',
                          'frequency':frequency}
        model_history, _ = normalize_history(model_history, group_settings)
        from .sales_groups import series_column, customer_product_future
        item_col = series_column(group_settings) or ''
        if isinstance(production_line_col, str) and production_line_col in model_history:
            model_history = model_history.copy()
            model_history['production_line'] = model_history[production_line_col]
        metadata = _series_metadata(
            model_history,
            item_col=item_col,
            sku_col=sku_col,
            category_col=category_col,
            customer_col=customer_col,
        )
        clean_history, cleaning_warnings = prepare_history(
            model_history,
            date_col=date_col,
            target_col=target_col,
            item_col=item_col or None,
            driver_cols=driver_cols,
            frequency=frequency,
            missing_strategy=missing_strategy,
            outlier_strategy=outlier_strategy,
            calendar_country=calendar.get('country') or None,
            weekend_days=tuple(calendar.get('weekend_days',[4])),
            shutdown_dates=tuple(calendar.get('shutdown_dates',[])),
            month_basis=conventions.get('month_basis','gregorian'),
        )

        raw_future = None
        if future_file is not None and future_file.filename:
            future_payload = await _read_upload(future_file)
            raw_future = read_table(future_file.filename, future_payload)
        raw_future, future_item_col = customer_product_future(raw_future, model_history, group_settings)

        operations_sheets = None
        if operations_file is not None and operations_file.filename:
            if frequency != 'monthly':
                raise ValueError('Production calculations currently require monthly quantities.')
            if 'unit' in model_history and str(model_history.unit.iloc[0]).strip() != quantity_unit:
                raise ValueError('The source unit does not match the selected quantity unit. Renaming a unit is not a conversion.')
            operations_payload = await _read_upload(operations_file)
            operations_mapping = json.loads(operations_mapping_json) if isinstance(operations_mapping_json, str) else None
            operations_sheets = read_operations_workbook(operations_file.filename, operations_payload, operations_mapping, UNIT_STORE)

        future_covariates, future_warnings = build_future_covariates(
            clean_history,
            raw_future,
            future_date_col=future_date_col or None,
            future_item_col=future_item_col or None,
            known_driver_cols=known_driver_cols,
            frequency=frequency,
            horizon=horizon,
            missing_future_policy=future_driver_policy,
            input_calendar=conventions.get('future_calendar','gregorian'),
        )
        driver_coverage = future_covariates.attrs.get("driver_coverage", {})

        result = run_forecast(
            history=clean_history,
            future_covariates=future_covariates,
            known_driver_cols=known_driver_cols,
            horizon=horizon,
            frequency=frequency,
            profile=profile,
            runs_dir=output_directory(RUNS_DIR),
            driver_roles=driver_roles,
            scenario_adjustment_pct=scenario_adjustment_pct,
            method_selection=method_selection,
            evidence_policy=evidence_policy if isinstance(evidence_policy, str) else 'standard',
        )
        result["summary"] = summarize_history(clean_history)
        result['issued_at'] = datetime.now(timezone.utc).isoformat()
        result["source_review"] = source_review(raw_history)
        result['unit'] = quantity_unit if isinstance(quantity_unit, str) else 'units'
        if "unit" in model_history:
            result["unit"] = str(model_history.unit.iloc[0]).strip()
        result["warnings"] = workbook_warnings + cleaning_warnings + future_warnings
        untested = result.get('metrics', {}).get('untested_selection_series', [])
        if untested:
            result['warnings'].append('The chosen method has no earlier selection test for ' + ', '.join(untested) + '. Later checks do not select the method; missing uncertainty ranges remain unavailable.')
        result["metadata"] = metadata
        result["dimensions"] = {
            "categories": sorted({m.get("category") for m in metadata.values() if m.get("category")}),
            "customers": sorted({m.get("customer") for m in metadata.values() if m.get("customer")}),
            "skus": sorted({m.get("sku") for m in metadata.values() if m.get("sku")}),
        }
        result["run_settings"] = {
            "frequency": frequency,
            "horizon": horizon,
            "profile": profile,
            "missing_strategy": missing_strategy,
            "outlier_strategy": outlier_strategy,
            "scenario_adjustment_pct": scenario_adjustment_pct,
            "driver_roles": driver_roles,
            "method_selection": method_selection,
            "future_driver_policy": future_driver_policy,
            "calendar_profile": clean_history.attrs.get('calendar_profile', {}),
            "excluded_items": exclusions,
            'sales_conventions':clean_history.attrs.get('sales_conventions',{}),
        }
        result["driver_coverage"] = driver_coverage
        result["site"] = SITE_PROFILE
        result["source_classification"] = source_classification
        if operations_sheets is not None:
            operations = calculate_operations(result, operations_sheets)
            result["operations"] = operations
            result["product_intelligence"] = {
                "lifecycle": [
                    {
                        "item_id": item,
                        "sku": metadata.get(item, {}).get("sku", item),
                        "stage": diag.get("lifecycle", "mature"),
                        "history_points": diag.get("history_points"),
                        "analog": next((row.get("related_sku") for row in operations.get("relationships", []) if row.get("sku") == metadata.get(item, {}).get("sku") and row.get("relationship_type") == "new_product_analog"), None),
                    }
                    for item, diag in result.get("series_diagnostics", {}).items()
                ],
                "relationships": operations.get("relationships", []),
                "promotions": operations.get("promotions", []),
                "note": "Relationships are supplied master data or correlations; the app does not claim causal effects.",
            }
            append_operations_export(output_directory(RUNS_DIR) / result["run_id"] / "forecast_package.xlsx", operations)
        else:
            result["operations"] = {"source": None, "materials": [], "capacity": [], "actions": [], "relationships": [], "promotions": [], "summary": {}}
            result["product_intelligence"] = {
                "lifecycle": [{"item_id": item, "sku": metadata.get(item, {}).get("sku", item), "stage": diag.get("lifecycle", "mature"), "history_points": diag.get("history_points"), "analog": None} for item, diag in result.get("series_diagnostics", {}).items()],
                "relationships": [], "promotions": [], "note": "Upload an operations master to evaluate substitutions, analogs and promotions.",
            }
        checkpoint('Saving forecast')
        result_path = output_directory(RUNS_DIR) / result["run_id"] / "result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/export/{run_id}/{kind}")
def export(run_id: str, kind: str):
    safe_id = "".join(ch for ch in run_id if ch.isalnum())
    if safe_id != run_id:
        raise HTTPException(status_code=400, detail="Invalid run id")
    mapping = {
        "csv": "forecast.csv",
        "xlsx": "forecast_package.xlsx",
        "models": "model_leaderboard.csv",
        "drivers": "driver_importance.csv",
    }
    filename = mapping.get(kind)
    if not filename:
        raise HTTPException(status_code=404, detail="Unknown export")
    path = RUNS_DIR / run_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(path, filename=filename)


def _load_run(run_id: str) -> dict:
    safe_id = "".join(ch for ch in run_id if ch.isalnum())
    if safe_id != run_id:
        raise HTTPException(status_code=400, detail="Invalid run id")
    path = RUNS_DIR / run_id / "result.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Forecast run not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/runs/latest")
def latest_run():
    candidates = sorted(RUNS_DIR.glob("*/result.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise HTTPException(status_code=404, detail="No forecast run exists yet")
    return json.loads(candidates[0].read_text(encoding="utf-8"))


@app.get("/api/workspace")
def workspace():
    today = datetime.now(ZoneInfo(SITE_PROFILE.get('timezone', 'Asia/Tehran'))).date()
    jalali = JalaliDate(today)
    plans = PLAN_STORE.list()
    return {
        "site": SITE_PROFILE,
        "today": today.isoformat(),
        "jalali_today": str(jalali),
        "plans": plans,
        "plan_counts": {status: sum(1 for plan in plans if plan.get("status") == status) for status in ["draft", "review", "approved", "published"]},
        "integrations": INTEGRATION_STORE.list(),
    }


@app.get("/api/plans")
def list_plans():
    return {"plans": PLAN_STORE.list()}


@app.get('/api/today')
def today_decisions(run_id: str | None = None, plan_id: str | None = None):
    run = _load_run(run_id) if run_id else None
    plan, operations, failure = None, None, None
    if plan_id:
        plan = PLAN_STORE.get(plan_id)
        if not plan: raise HTTPException(404, 'Plan not found')
        if not run or plan['run_id'] != run['run_id']:
            raise HTTPException(400, 'Choose a plan from the selected forecast.')
        try:
            _, _, operations = _plan_output(plan_id, supply=True)
        except (ValueError, HTTPException) as exc:
            failure = str(exc.detail if isinstance(exc, HTTPException) else exc)
    elif run:
        operations = run.get('operations')
    try:
        return DECISION_STORE.decorate(build_today(run, PLAN_STORE.list(), SITE_PROFILE, plan=plan,
                           operations=operations, operations_error=failure))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/decisions')
def record_decision(payload: DecisionUpdate, request: Request):
    try:
        today=today_decisions(payload.run_id,payload.plan_id)
        return DECISION_STORE.update(today,payload.decision_id,
            evidence_token=payload.evidence_token,version=payload.version,
            owner=payload.owner,due_date=payload.due_date,status=payload.status,
            note=payload.note,request_id=payload.request_id,identity=request.state.principal)
    except DecisionConflict as exc: raise HTTPException(409,str(exc)) from exc
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc


@app.post("/api/plans")
def create_plan(payload: PlanCreate, request: Request):
    run = _load_run(payload.run_id)
    plan_settings = {
        **run.get("run_settings", {}),
        "site": run.get("site", SITE_PROFILE),
        "scope": run.get("dimensions", {}),
        "unit": run.get("unit", "tonnes"),
        "currency": run.get("site", SITE_PROFILE).get("currency", "IRR"),
        "calendar": run.get("site", SITE_PROFILE).get("calendar", "Jalali + Gregorian"),
        "data_snapshot": run.get("summary", {}),
        "source_classification": run.get("source_classification", "user_provided"),
    }
    return PLAN_STORE.create(
        name=payload.name,
        run_id=payload.run_id,
        site_id=payload.site_id,
        owner=identity_fields(request, payload.owner)['actor'],
        identity=request.state.principal,
        settings=plan_settings,
        metrics=run.get("metrics", {}),
    )


def _plan_output(plan_id: str, *, supply: bool = False):
    plan = PLAN_STORE.get(plan_id)
    if not plan:
        raise HTTPException(404, 'Plan not found')
    source = _load_run(plan['run_id'])
    resolved, rows = resolve_plan(source, plan)
    operations = None
    if supply:
        if plan['status'] not in {'approved', 'published'}:
            raise ValueError('Approve the plan before using it for supply calculations.')
        if source.get('run_settings', {}).get('frequency') != 'monthly':
            raise ValueError('Supply currently needs monthly quantities.')
        manifest = next((entry for entry in source.get('input_manifest', {}).get('sources', [])
                         if entry['role'] == 'operations'), None)
        if not manifest or not manifest.get('sha256'):
            raise ValueError('This forecast has no verified production-file snapshot. Rerun it with production data first.')
        saved, content = DATASET_STORE.source(manifest['id'])
        if hashlib.sha256(content).hexdigest() != manifest['sha256']:
            raise ValueError('The production-file snapshot has changed. Supply calculation was stopped.')
        operations = calculate_operations(resolved, read_operations_workbook(saved['name'], content, source.get('input_manifest', {}).get('settings', {}).get('operations_mapping'), UNIT_STORE))
        operations['quantity_basis'] = resolved['plan']
    return plan, rows, operations


@app.get('/api/plans/{plan_id}/supply')
def plan_supply(plan_id: str):
    try:
        return _plan_output(plan_id, supply=True)[2]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/plans/{plan_id}/quantities')
def plan_quantities(plan_id: str):
    try:
        plan, rows, _ = _plan_output(plan_id)
        return {'plan_id': plan['id'], 'run_id': plan['run_id'], 'updated_at': plan['updated_at'],
                'status': plan['status'], 'rows': rows}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/plans/{plan_id}/versions', status_code=201)
def revise_plan(plan_id: str, payload: PlanRevision, request: Request):
    try:
        _plan_output(plan_id)  # Validate the source forecast and its effective adjustments.
        values = payload.model_dump()
        values['owner'] = identity_fields(request, payload.owner)['actor']
        return PLAN_STORE.revise(plan_id, **values, identity=request.state.principal)
    except KeyError as exc:
        raise HTTPException(404, 'Plan not found') from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/plans/{plan_id}/export')
def export_plan(plan_id: str, include_supply: bool = False):
    try:
        plan, rows, operations = _plan_output(plan_id, supply=include_supply)
        return Response(plan_workbook(plan, rows, operations),
                        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition': f'attachment; filename="plan-{plan["id"]}-{plan["status"]}.xlsx"'})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.patch("/api/plans/{plan_id}/status")
def transition_plan(plan_id: str, payload: PlanTransition, request: Request):
    try:
        principal = request.state.principal
        if principal and payload.status in {'approved','published'} and principal['role'] not in {'reviewer','admin'}:
            raise HTTPException(403, 'A reviewer must approve or publish this plan.')
        if not principal and payload.status in {'approved','published'}:
            plan = PLAN_STORE.get(plan_id)
            if plan and plan.get('settings', {}).get('source_classification') != 'synthetic_sample':
                raise HTTPException(403, 'Company sign-in is required to approve real operating quantities. Local approval is only available for labelled sample plans.')
        return PLAN_STORE.transition(plan_id, status=payload.status, note=payload.note, **identity_fields(request,payload.actor))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plans/{plan_id}/overrides")
def add_override(plan_id: str, payload: ForecastOverride, request: Request):
    try:
        plan = PLAN_STORE.get(plan_id)
        if not plan: raise KeyError(plan_id)
        source = _load_run(plan['run_id'])
        periods = source.get('series',{}).get(payload.item_id,{}).get('forecast',[])
        if payload.item_id == '__all__' or not any(r['timestamp'][:10] == payload.period[:10] for r in periods):
            raise ValueError('Select an item and period from this plan’s forecast.')
        return PLAN_STORE.add_override(
            plan_id,
            item_id=payload.item_id,
            period=payload.period[:10],
            value=payload.value,
            reason=payload.reason,
            **identity_fields(request,payload.actor),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plans/{plan_id}/comments")
def add_plan_comment(plan_id: str, payload: PlanComment, request: Request):
    try:
        return PLAN_STORE.add_comment(plan_id, text=payload.text, **identity_fields(request,payload.actor))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plans/{plan_id}/overrides/{override_id}/revert")
def revert_override(plan_id: str, override_id: str, payload: OverrideReversal, request: Request):
    try:
        return PLAN_STORE.revert_override(
            plan_id,
            override_id,
            reason=payload.reason,
            **identity_fields(request,payload.actor),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan or override not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/integrations")
def list_integrations():
    return {"integrations": INTEGRATION_STORE.list()}


@app.get('/api/integrations/folders')
def folder_inputs():
    return {'connections':FOLDER_INPUTS.list(), 'approved_roots':[str(p) for p in FOLDER_INPUTS.roots]}


@app.post('/api/integrations/folders')
def create_folder_input(payload: dict, request: Request):
    try:
        config = FOLDER_INPUTS.create(payload, request.state.principal)
        schedule_folder(config)
        return config
    except (ValueError, OSError, TypeError) as exc:
        raise HTTPException(400,str(exc)) from exc


@app.post('/api/integrations/folders/{identifier}/check')
def check_folder_input(identifier: str):
    try: return FOLDER_INPUTS.check(identifier)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc


@app.post('/api/integrations/folders/{identifier}/enabled')
def enable_folder_input(identifier: str, payload: dict):
    if type(payload.get('enabled')) is not bool: raise HTTPException(400,'Choose whether automatic checks are enabled.')
    try:
        config = FOLDER_INPUTS.set_enabled(identifier,payload['enabled'])
        schedule_folder(config)
        return config
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc


@app.get('/api/integrations/folders/candidates/{identifier}')
def folder_candidate(identifier: str):
    try: return FOLDER_INPUTS.candidate(identifier)
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc


@app.post('/api/integrations/folders/{identifier}/auto-draft')
def configure_folder_drafts(identifier: str, payload: dict):
    try: return FOLDER_INPUTS.set_auto_draft(identifier, payload.get('enabled'))
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc


@app.post('/api/integrations/folders/candidates/{identifier}/forecast', status_code=202)
def folder_draft_forecast(identifier: str):
    try:
        dataset = FOLDER_INPUTS.draft_dataset(identifier)
        return create_job(JobRequest(dataset_id=dataset['id'],
                                    request_id='folder-draft:'+identifier))
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from exc


@app.post("/api/integrations")
def save_integration(payload: IntegrationConfig):
    try:
        return INTEGRATION_STORE.upsert(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/integrations/{connector_id}/sync")
def sync_integration(connector_id: str):
    try:
        connector = INTEGRATION_STORE.sync(connector_id)
        if connector.get("status") == "failed":
            raise HTTPException(status_code=400, detail=connector.get("last_error") or "Connector check failed")
        return connector
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Connector not found") from exc


@app.get("/api/monitoring")
def monitoring(run_id: str | None = None):
    run = _load_run(run_id) if run_id else None
    return build_monitoring(RUNS_DIR, run)


@app.post("/api/fva/{run_id}")
async def calculate_fva(run_id: str, actuals_file: UploadFile = File(...)):
    raise HTTPException(410, 'Use the reviewed Actual results workflow to confirm units, closed periods and the plan to compare.')


@app.post('/api/actuals/sources')
async def upload_actual_source(file: UploadFile = File(...)):
    try:
        return DATASET_STORE.upload(file.filename or 'actuals.csv', await _read_upload(file), 'actuals')
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/actuals/sources/{source_id}/preview')
def preview_actual_source(source_id: str, payload: dict):
    try:
        source, content = DATASET_STORE.source(source_id)
        if source['role'] != 'actuals':
            raise ValueError('Choose an actual-results source.')
        return inventory_preview(source['name'], content, payload.get('sheet'), payload.get('header_row', 1))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


def actual_comparison_inputs(run_id, payload):
    run = _load_run(run_id)
    plan = PLAN_STORE.get(payload['plan_id']) if payload.get('plan_id') else None
    if payload.get('plan_id') and (not plan or plan['run_id'] != run_id):
        raise ValueError('Choose a plan belonging to this forecast.')
    return run, plan


@app.post('/api/actuals/{run_id}/review')
def review_actuals(run_id: str, payload: dict):
    try:
        run, plan = actual_comparison_inputs(run_id, payload)
        result = ACTUALS_STORE.inspect(payload, run, plan)
        return {**result, 'rows': result['rows'][:30]}
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/actuals/{run_id}')
def save_actuals(run_id: str, payload: dict):
    try:
        run, plan = actual_comparison_inputs(run_id, payload)
        return ACTUALS_STORE.save(payload, run, plan)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/actuals/{run_id}')
def list_actuals(run_id: str):
    return {'evaluations': ACTUALS_STORE.list(run_id)}


@app.get('/api/actual-results/{evaluation_id}')
def get_actuals(evaluation_id: str):
    try:
        return ACTUALS_STORE.get(evaluation_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get('/api/actual-results/{evaluation_id}/export')
def export_actual_results(evaluation_id: str):
    try:
        report = ACTUALS_STORE.get(evaluation_id)
        return Response(export_actuals(report), media_type='text/csv',
                        headers={'Content-Disposition': 'attachment; filename="actual-results.csv"'})
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/assistant/query")
def assistant_query(payload: AssistantQuestion):
    try:
        run = _load_run(payload.run_id) if payload.run_id else latest_run()
        return answer_planning_question(payload.question, run, PLAN_STORE.list(), build_monitoring(RUNS_DIR, run))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/assistant/mapping")
def assistant_mapping(payload: MappingQuestion):
    return suggest_mapping(payload.columns, payload.numeric_columns, payload.date_candidates)


@app.post('/api/sources')
async def upload_source(file: UploadFile=File(...), role: str=Form('history'), sheet: str=Form('')):
    try:
        return DATASET_STORE.upload(file.filename or 'data.csv',await _read_upload(file),role,sheet or None)
    except Exception as exc:
        raise HTTPException(400,str(exc)) from exc


@app.get('/api/sources/{source_id}')
def get_source(source_id: str):
    try: return DATASET_STORE.source(source_id)[0]
    except ValueError as exc: raise HTTPException(404,str(exc)) from exc


@app.post('/api/sources/{source_id}/sheet')
def choose_source_sheet(source_id: str, payload: dict):
    try:
        source,content=DATASET_STORE.source(source_id)
        if payload.get('sheet') not in source['preview'].get('sheets',[]): raise ValueError('Choose a sheet from this workbook.')
        return DATASET_STORE.upload(source['name'],content,source['role'],payload['sheet'])
    except Exception as exc: raise HTTPException(400,str(exc)) from exc


@app.get('/api/datasets')
def datasets(): return {'datasets':DATASET_STORE.list()}


@app.post('/api/inventory/sources')
async def upload_inventory_source(file: UploadFile = File(...)):
    try:
        return DATASET_STORE.upload(file.filename or 'inventory.csv', await _read_upload(file), 'inventory')
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/inventory/sources/{source_id}/preview')
def preview_inventory_source(source_id: str, payload: dict):
    try:
        source, content = DATASET_STORE.source(source_id)
        if source['role'] != 'inventory':
            raise ValueError('Choose an inventory source.')
        return inventory_preview(source['name'], content, payload.get('sheet'), payload.get('header_row', 1))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/inventory/validate')
def validate_inventory(payload: dict):
    try:
        review = INVENTORY_STORE.inspect(payload)
        return {**review, 'rows': review['rows'][:30]}
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/inventory/sources/{source_id}/values')
def inventory_column_values(source_id: str, payload: dict):
    try:
        source, content = DATASET_STORE.source(source_id)
        if source['role'] != 'inventory':
            raise ValueError('Choose an inventory source.')
        table = raw_table(source['name'], content, payload.get('sheet'), payload.get('header_row', 1))
        column = payload.get('column')
        if column not in {col['id'] for col in table['columns']}:
            raise ValueError('Choose a column from this sheet.')
        values = sorted({text_value(row['values'].get(column)) for row in table['rows']})
        if len(values) > 100:
            raise ValueError('This column has more than 100 distinct values. Choose a stock-status column.')
        return {'values': values}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/inventory')
def inventory_list():
    return {'snapshots': INVENTORY_STORE.list()}


@app.get('/api/units')
def unit_versions():
    return {'versions': UNIT_STORE.list(), 'standard_labels': list(STANDARD)}


@app.get('/api/production/schema')
def production_schema(mode: str = 'tonnes'):
    try:
        return get_production_schema(mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/production/sources/{source_id}/preview')
def production_table_preview(source_id: str, payload: dict):
    try:
        source, content = DATASET_STORE.source(source_id)
        if source['role'] != 'operations':
            raise ValueError('Choose a production workbook.')
        return inventory_preview(source['name'], content, payload.get('sheet'), payload.get('header_row', 1))
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/production/sources/{source_id}')
def production_workbook_preview(source_id: str):
    try:
        source, content = DATASET_STORE.source(source_id)
        if source['role'] != 'operations':
            raise ValueError('Choose a production workbook.')
        return operations_preview(source['name'], content)
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/units')
def save_unit_version(payload: dict):
    try:
        return UNIT_STORE.save(payload)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/inventory')
def save_inventory(payload: dict):
    try:
        snapshot = INVENTORY_STORE.save(payload)
        return {key: value for key, value in snapshot.items() if key != 'rows'}
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/inventory/{snapshot_id}')
def inventory_snapshot(snapshot_id: str):
    try:
        return INVENTORY_STORE.get(snapshot_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get('/api/inventory/{snapshot_id}/projection')
def inventory_projection(snapshot_id: str, run_id: str, plan_id: str | None = None, unit_version_id: str | None = None, receipt_version_id: str | None = None):
    try:
        run = _load_run(run_id)
        if plan_id:
            plan = PLAN_STORE.get(plan_id)
            if not plan or plan['run_id'] != run_id or plan['status'] not in {'approved', 'published'}:
                raise ValueError('Choose an approved plan belonging to this forecast.')
            run, _ = resolve_plan(run, plan)
        snapshot = INVENTORY_STORE.get(snapshot_id)
        return project_inventory(run, snapshot, UNIT_STORE.get(unit_version_id) if unit_version_id else None,
                                 INVENTORY_STORE.receipt_version(snapshot_id, receipt_version_id) if receipt_version_id else None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/inventory/{snapshot_id}/receipts')
def receipt_schedules(snapshot_id: str):
    try:
        return {'versions': INVENTORY_STORE.receipt_versions(snapshot_id)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/receipts/sources')
async def upload_receipt_source(file: UploadFile = File(...)):
    try:
        return DATASET_STORE.upload(file.filename or 'receipts.csv', await _read_upload(file), 'receipts')
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/receipts/sources/{source_id}/preview')
def preview_receipt_source(source_id: str, payload: dict):
    try:
        source, content = DATASET_STORE.source(source_id)
        if source['role'] != 'receipts': raise ValueError('Choose a receipt export.')
        table = inventory_preview(source['name'], content, payload.get('sheet'), payload.get('header_row', 1))
        if payload.get('value_columns'):
            full = raw_table(source['name'], content, payload.get('sheet'), payload.get('header_row', 1))
            table['values'] = {}
            for column in payload['value_columns']:
                if column not in {c['id'] for c in full['columns']}: raise ValueError('Choose an existing column.')
                values = sorted({text_value(row['values'].get(column)) for row in full['rows']})
                if len(values) > 100: raise ValueError('Type/status columns must have at most 100 distinct values.')
                table['values'][column] = values
        return table
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/inventory/{snapshot_id}/receipts/validate')
def validate_receipt_schedule(snapshot_id: str, payload: dict):
    try:
        checked = INVENTORY_STORE.prepare_receipts(snapshot_id, {**payload, 'reviewed': True, 'request_id': 'preview',
                                                   'name': 'Preview', 'reason': 'Preview only'})
        return {**checked, 'rows': checked['rows'][:30], 'row_count': len(checked['rows'])}
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/inventory/{snapshot_id}/receipts')
def save_receipt_schedule(snapshot_id: str, payload: dict, request: Request):
    try:
        return INVENTORY_STORE.save_receipts(snapshot_id, payload, getattr(request.state, 'principal', None))
    except (ValueError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/factors')
def factors():
    from .factor_imports import freshness as imported_freshness
    return {'catalog': list(CATALOG.values()), 'snapshots': [
        {**{key: value for key, value in row.items() if key != 'points'},'freshness':imported_freshness(row)} if row.get('kind') == 'imported_observations' else
        {**row, 'freshness': supply_freshness(row)} if row.get('factor_id') == 'global_supply_pressure' else row
        for row in FACTOR_STORE.list()]}


@app.post('/api/factor-imports/table')
def factor_import_table(payload: dict):
    from .factor_imports import source_table
    try:
        return source_table(DATASET_STORE, payload, preview=True)[1]
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/factor-imports/preview')
def preview_factor_import(payload: dict):
    from .factor_imports import review_import
    try:
        result = review_import(DATASET_STORE, payload)
        return {**result, 'points': result['points'][:30]}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/factor-imports')
def save_factor_import(payload: dict):
    from .factor_imports import save_import
    try:
        result = save_import(DATASET_STORE, FACTOR_STORE, payload)
        return {key: value for key, value in result.items() if key != 'points'}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/factor-imports/{snapshot_id}/available')
def available_factor_import(snapshot_id: str, cutoff: str):
    from .factor_imports import iso_date
    from .factors import observations_available_at
    try:
        snapshot = FACTOR_STORE.get(snapshot_id)
        day = iso_date(cutoff).isoformat()
        rows = observations_available_at(snapshot, day + 'T23:59:59.999999+00:00')
        return {'cutoff': day, 'count': len(rows), 'points': rows.head(100).to_dict('records'),
                'limitation': snapshot['limitation']}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/weather')
def weather_snapshots():
    return {'snapshots': WEATHER_STORE.list()}


@app.post('/api/weather/refresh')
def refresh_weather(payload: dict):
    try:
        return WEATHER_STORE.refresh(payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, 'Weather data could not be fetched. Saved snapshots are unchanged; try again later.') from exc


@app.get('/api/weather/{snapshot_id}/export')
def export_weather(snapshot_id: str):
    try:
        return Response(weather_csv(WEATHER_STORE.get(snapshot_id)), media_type='text/csv',
                        headers={'Content-Disposition': f'attachment; filename="weather-{snapshot_id}.csv"'})
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/factors/{factor_id}/refresh')
def refresh_factor(factor_id: str):
    try:
        row = FACTOR_STORE.refresh(factor_id)
        return {**row, 'freshness': supply_freshness(row)} if factor_id == 'global_supply_pressure' else row
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, 'The public source could not be reached. Existing local snapshots are unchanged; try again later.') from exc


@app.post('/api/datasets/validate')
def validate_dataset(payload: DatasetConfig):
    from .input_review import validate_import
    try:
        review=validate_import(DATASET_STORE,payload.sources,payload.settings,payload.classification)
        if payload.parent_dataset_id and not payload.import_candidate_id:
            from .input_refresh import repeat_review
            review['repeat_upload']=repeat_review(DATASET_STORE,payload.parent_dataset_id,payload.sources,payload.settings,payload.classification)
        return review
    except Exception as exc: raise HTTPException(400,str(exc)) from exc


@app.post('/api/datasets')
def save_dataset(payload: DatasetConfig):
    try:
        if payload.classification not in {'user_provided','synthetic_sample'}: raise ValueError('Invalid source classification.')
        if payload.import_candidate_id:
            return FOLDER_INPUTS.accept(payload.import_candidate_id,name=payload.name,sources=payload.sources,
                settings=payload.settings,classification=payload.classification,accept_warnings=payload.accept_warnings,
                parent_dataset_id=payload.parent_dataset_id)
        provenance=None
        if payload.parent_dataset_id:
            from .input_refresh import repeat_review
            receipt=repeat_review(DATASET_STORE,payload.parent_dataset_id,payload.sources,payload.settings,payload.classification)
            if receipt:
                if payload.accept_warnings is not True: raise ValueError('Review and acknowledge the repeat-upload changes before saving.')
                provenance={'kind':'repeat_history_review','review':receipt}
        return DATASET_STORE.save(payload.name,payload.sources,payload.settings,payload.classification,payload.accept_warnings,
                                  parent_dataset_id=payload.parent_dataset_id,request_id=payload.request_id,import_provenance=provenance)
    except Exception as exc: raise HTTPException(400,str(exc)) from exc


class ForecastSettings(BaseModel):
    horizon: int = Field(ge=1,le=24,strict=True)
    month_basis: str = Field(pattern=r'^(gregorian|jalali)$')
    calendar_country: str = Field(default='IR',pattern=r'^(IR)?$')
    request_id: str = Field(min_length=8,max_length=80)


@app.post('/api/datasets/{dataset_id}/forecast-settings')
def update_forecast_settings(dataset_id: str,payload: ForecastSettings):
    try:
        dataset=DATASET_STORE.get(dataset_id)
        if dataset.get('scenario_provenance') or dataset['sources'].get('operations'):
            raise ValueError('Choose sales history, not a production or scenario input.')
        settings={**dataset['settings'],**payload.model_dump(exclude={'request_id'})}
        if settings==dataset['settings']: return dataset
        return DATASET_STORE.save(dataset['name'],dataset['sources'],settings,dataset['classification'],True,
            parent_dataset_id=dataset_id,import_provenance={'type':'forecast_settings'},request_id=payload.request_id)
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc


def validate_forecast_group(payload, runs_dir=None):
    if not payload.forecast_group_id:
        return
    for path in (runs_dir if runs_dir is not None else RUNS_DIR).glob('*/result.json'):
        prior=json.loads(path.read_text())
        if prior.get('forecast_group_id')==payload.forecast_group_id and (
            prior.get('dataset_id')!=payload.dataset_id or
            prior.get('forecast_order_inputs_id')!=payload.sales_input_id or
            prior.get('forecast_name')!=payload.forecast_name
        ):
            raise ValueError('These methods belong to different inputs. Start a new forecast.')


@app.post('/api/run-saved')
async def run_saved(payload: SavedRunConfig):
    return await calculate_saved(payload)


async def calculate_saved(payload: SavedRunConfig, workspace=None):
    DATASET_STORE = workspace.datasets if workspace else globals()['DATASET_STORE']
    SALES_STORE = workspace.sales if workspace else globals()['SALES_STORE']
    UNIT_STORE = workspace.units if workspace else globals()['UNIT_STORE']
    RUNS_DIR = workspace.runs if workspace else globals()['RUNS_DIR']
    _load_run = workspace.load_run if workspace else globals()['_load_run']
    if workspace and (payload.scenario_name or payload.base_run_id or payload.adjustment):
        raise HTTPException(400, 'Company quantity scenarios are not available yet.')
    try:
        dataset=DATASET_STORE.get(payload.dataset_id)
        if bool(payload.forecast_group_id) != bool(payload.forecast_name):
            raise ValueError('A forecast group needs an identifier and a name.')
        if payload.forecast_group_id and (not payload.sales_input_id or payload.scenario_name or payload.adjustment or dataset.get('scenario_provenance')):
            raise ValueError('Group methods only with the same reviewed forecast inputs.')
        validate_forecast_group(payload, RUNS_DIR)
        if payload.sales_input_id:
            from .forecast_orders import reviewed
            if dataset.get('scenario_provenance') or payload.scenario_name or payload.adjustment:
                raise ValueError('Use reviewed orders with a new forecast, not a quantity scenario.')
            reviewed(DATASET_STORE, SALES_STORE, dataset['id'], payload.sales_input_id, site=workspace.site if workspace else None)
        assumption = dataset.get('scenario_provenance')
        if workspace and assumption:
            raise ValueError('Choose reviewed forecast inputs, not a legacy scenario.')
        if assumption and (payload.scenario_name or payload.adjustment or payload.method):
            raise ValueError('An assumption scenario keeps its baseline method. Start a new baseline to change methods or demand percentages.')
        if assumption and assumption.get('type')=='factor_batch':
            from .factor_batch import calculate_batch
            if payload.base_run_id and payload.base_run_id!=assumption['base_run_id']:
                raise ValueError('This batch belongs to another baseline.')
            async def calculate_group(identifier):
                return await run_saved(SavedRunConfig(dataset_id=identifier,base_run_id=assumption['base_run_id']))
            return await calculate_batch(_load_run(assumption['base_run_id']),dataset,
                DATASET_STORE,FACTOR_STORE,LIVE_SOURCES,FACTOR_PROFILES,calculate_group,output_directory(RUNS_DIR))
        if payload.scenario_name is not None:
            if not payload.base_run_id: raise ValueError('Select a forecast before creating a scenario.')
            base=_load_run(payload.base_run_id)
            if base.get('dataset_id')!=dataset['id']: raise ValueError('The forecast and saved dataset do not match.')
            operations=None
            if dataset['sources'].get('operations'):
                source,content=DATASET_STORE.source(dataset['sources']['operations'])
                operations=read_operations_workbook(source['name'],content,dataset['settings'].get('operations_mapping'), UNIT_STORE)
            return quantity_scenario(base,name=payload.scenario_name,adjustment=payload.adjustment,runs_dir=output_directory(RUNS_DIR),source_runs_dir=RUNS_DIR,operations=operations)
        s=dataset['settings']; uploads={}
        effective_conventions={k:s[k] for k in ('history_calendar','history_grain','month_basis','sales_measure','returns_policy','future_calendar','customer_aliases','series_mode') if k in s}
        for role,key in dataset['sources'].items():
            source,content=DATASET_STORE.source(key)
            # Canonicalise the selected Excel sheet once, preserving the saved selection.
            if role!='operations':
                frame=read_table(source['name'],content,sheet_name=source.get('sheet'))
                if role=='history' and s.get('history_cell_corrections'):
                    from .input_corrections import apply_cell_corrections
                    if s.get('history_corrections_sha256') != source['sha256']:
                        raise ValueError('Formatting corrections belong to another history file. Review again.')
                    frame=apply_cell_corrections(frame,s)
                if role=='history' and frame.attrs.get('wide_forecast_matrix'):
                    effective_conventions.update(history_calendar='gregorian',history_grain='monthly_totals')
                content=frame.to_csv(index=False).encode('utf-8')
            uploads[role]=UploadFile(BytesIO(content),filename=source['name'] if role=='operations' else role+'.csv')
        # Keep the legacy upload boundary compatible; scoped workers use the
        # same calculation with explicit stores, not the public legacy handler.
        from functools import partial
        calculate = run if workspace is None else partial(_calculate_upload, workspace=workspace)
        result=await calculate(historical_file=uploads['history'],future_file=uploads.get('future'),operations_file=uploads.get('operations'),
            quantity_unit=s.get('unit','units'),operations_mapping_json=json.dumps(s.get('operations_mapping')),production_line_col=s.get('production_line_col') or 'production_line',
            sales_conventions_json=json.dumps(effective_conventions),
            evidence_policy='reviewed_what_if' if s.get('evidence_policy') == 'reviewed_what_if' or (assumption and assumption.get('alignment',{}).get('retrospective')) else 'standard',
            date_col=s['date_col'],target_col=s['target_col'],item_col=s.get('item_col',''),sku_col=s.get('sku_col',''),category_col=s.get('category_col',''),customer_col=s.get('customer_col',''),
            future_date_col=s.get('future_date_col',''),future_item_col=s.get('future_item_col',''),driver_cols_json=json.dumps(s.get('drivers',[])),known_driver_cols_json=json.dumps(s.get('drivers',[])),driver_roles_json=json.dumps(s.get('driver_roles',{})),
            frequency=s.get('frequency','monthly'),horizon=s.get('horizon',6),profile=s.get('profile','deep'),missing_strategy=s.get('missing_strategy','auto'),outlier_strategy=s.get('outlier_strategy','none'),scenario_adjustment_pct=payload.adjustment,method_selection=payload.method or s.get('method_selection','recommended'),future_driver_policy=s.get('future_driver_policy','require'),source_classification=dataset['classification'],unit_filter=s.get('unit_filter',''),calendar_json=json.dumps({'country':s.get('calendar_country','IR'),'weekend_days':s.get('weekend_days',[4]),'shutdown_dates':s.get('shutdown_dates',[])}),excluded_items_json=json.dumps(s.get('excluded_items',[])))
        result['dataset_id']=dataset['id']; result['dataset_name']=dataset['name']; result['unit']=s.get('unit','units')
        result['input_manifest'] = {'dataset_id': dataset['id'], 'saved_at': dataset['created_at'],
            'import_provenance': dataset.get('import_provenance'),
            'settings': s, 'sources': [
                {'role': role, 'id': key, 'name': DATASET_STORE.source(key)[0]['name'],
                 'sheet': DATASET_STORE.source(key)[0].get('sheet'), 'sha256': DATASET_STORE.source(key)[0].get('sha256')}
                for role, key in dataset['sources'].items() if key]}
        result['scenario_name']=payload.scenario_name
        if payload.forecast_group_id:
            result.update(forecast_group_id=payload.forecast_group_id,forecast_name=payload.forecast_name.strip())
        if assumption:
            base = _load_run(assumption['base_run_id'])
            if result.get('engine') != base.get('engine') or result.get('metrics', {}).get('evaluation_signature') != base.get('metrics', {}).get('evaluation_signature'):
                raise ValueError('The forecasting engine or historical test periods changed. Run a fresh baseline before comparing assumptions.')
            result['scenario_name'] = assumption['name']
            result['base_run_id'] = assumption['base_run_id']
            result['scenario'] = assumption
            result['warnings'] = list(dict.fromkeys(result.get('warnings', []) + assumption.get('inherited_warnings', [])))
            result['site'] = base.get('site', result.get('site'))
            if assumption.get('type') == 'factor_link' and assumption['alignment'].get('series_ids'):
                from .factor_scope import apply_factor_scope
                apply_factor_scope(result, base, assumption['alignment']['series_ids'],
                                   output_directory(RUNS_DIR) / result['run_id'])
            if assumption.get('type')=='factor_link':
                from .factor_links import accuracy_comparison
                result['factor_validation']=accuracy_comparison(base,result)
            import pandas as pd
            with pd.ExcelWriter(output_directory(RUNS_DIR) / result['run_id'] / 'forecast_package.xlsx', engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                pd.DataFrame(assumption['changes']).to_excel(writer, sheet_name='Changed assumptions', index=False)
                pd.DataFrame(assumption['definitions']).to_excel(writer, sheet_name='Factor sources', index=False)
                pd.DataFrame([{key: assumption.get(key, dataset['created_at'] if key == 'recorded_at' else None) for key in ('base_run_id', 'name', 'owner', 'reason', 'recorded_at', 'identity_basis')}]).to_excel(writer, sheet_name='Scenario', index=False)
                if assumption.get('type') == 'factor_comparison':
                    pd.DataFrame([{'factor':f,'treatment':'Excluded from comparison'} for f in assumption['removed_factors']]).to_excel(writer,sheet_name='Factor comparison',index=False)
                if assumption.get('type') == 'factor_link':
                    pd.DataFrame(assumption['alignment']['rows']).to_excel(writer,sheet_name='Factor alignment',index=False)
                    proof=result['factor_validation']
                    pd.DataFrame([{k:v for k,v in proof.items() if k not in ('rows','series')}]).to_excel(writer,sheet_name='Factor accuracy',index=False)
                    pd.DataFrame(proof['rows']).to_excel(writer,sheet_name='Factor test evidence',index=False)
                for sheet in [writer.book[name] for name in ('Changed assumptions', 'Factor sources', 'Scenario', 'Factor comparison', 'Factor alignment','Factor accuracy','Factor test evidence') if name in writer.book.sheetnames]:
                    for row in sheet:
                        for cell in row:
                            if cell.data_type == 'f':
                                cell.data_type = 's'
        if payload.sales_input_id and output_directory(RUNS_DIR) == RUNS_DIR:
            from .forecast_orders import finalize
            finalize(DATASET_STORE, SALES_STORE, result, payload.sales_input_id, RUNS_DIR / result['run_id'], site=workspace.site if workspace else None)
        (output_directory(RUNS_DIR) / result['run_id'] / 'result.json').write_text(json.dumps(result,ensure_ascii=False,default=str),encoding='utf-8')
        return result
    except HTTPException: raise
    except Exception as exc: raise HTTPException(400,str(exc)) from exc


@app.get('/api/runs/{run_id}')
def get_run(run_id: str): return _load_run(run_id)


@app.get('/api/runs/{run_id}/assumptions')
def get_assumptions(run_id: str):
    try:
        return preview_assumptions(_load_run(run_id), DATASET_STORE)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/runs/{run_id}/factors')
def get_factor_review(run_id: str):
    from .factor_review import review_factors
    try:
        return review_factors(_load_run(run_id), DATASET_STORE)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/runs/{run_id}/factor-comparison')
def create_factor_comparison(run_id: str, payload: dict):
    from .factor_review import save_factor_comparison
    try:
        return save_factor_comparison(_load_run(run_id), DATASET_STORE, payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/runs/{run_id}/factor-links')
def factor_link_choices(run_id: str):
    from .factor_links import choices
    try:
        return choices(_load_run(run_id), DATASET_STORE, FACTOR_STORE)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/datasets/{dataset_id}/forecast-factors')
def forecast_factor_options(dataset_id: str):
    from .forecast_inputs import factor_options
    try:
        return factor_options(DATASET_STORE, FACTOR_STORE, dataset_id, LIVE_SOURCES)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/datasets/{dataset_id}/forecast-factors/preview')
def preview_forecast_factors(dataset_id: str, payload: dict):
    from .forecast_inputs import preview_inputs
    try:
        return preview_inputs(DATASET_STORE, FACTOR_STORE, dataset_id, payload, LIVE_SOURCES)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/datasets/{dataset_id}/forecast-factors')
def save_forecast_factors(dataset_id: str, payload: dict):
    from .forecast_inputs import save_inputs
    try:
        return save_inputs(DATASET_STORE, FACTOR_STORE, dataset_id, payload, LIVE_SOURCES)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/runs/{run_id}/factor-links/preview')
def preview_factor_link(run_id: str, payload: dict):
    from .factor_links import preview_link
    try:
        return preview_link(_load_run(run_id), DATASET_STORE, FACTOR_STORE, payload, LIVE_SOURCES, FACTOR_PROFILES)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/runs/{run_id}/factor-links')
def create_factor_link(run_id: str, payload: dict):
    from .factor_links import save_link
    try:
        return save_link(_load_run(run_id), DATASET_STORE, FACTOR_STORE, payload, LIVE_SOURCES, FACTOR_PROFILES)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/runs/{run_id}/assumptions')
def create_assumptions(run_id: str, payload: dict):
    try:
        return save_assumptions(_load_run(run_id), DATASET_STORE, payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/runs/{run_id}/factor-preparation')
def prepare_forecast_sources(run_id: str, payload: dict):
    from .factor_preparation import preparation_report
    try:
        return preparation_report(_load_run(run_id), DATASET_STORE, FACTOR_STORE, LIVE_SOURCES, payload, FACTOR_PROFILES)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/runs/{run_id}/factor-profiles')
def forecast_factor_profiles(run_id: str):
    try:return FACTOR_PROFILES.for_run(_load_run(run_id))
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc


@app.post('/api/runs/{run_id}/factor-batch/preview')
def preview_factor_batch(run_id: str,payload: dict):
    from .factor_batch import preview_batch
    try:return preview_batch(_load_run(run_id),DATASET_STORE,FACTOR_STORE,payload,LIVE_SOURCES,FACTOR_PROFILES)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc


@app.post('/api/runs/{run_id}/factor-batch')
def create_factor_batch(run_id: str,payload: dict):
    from .factor_batch import save_batch
    try:return save_batch(_load_run(run_id),DATASET_STORE,FACTOR_STORE,payload,LIVE_SOURCES,FACTOR_PROFILES)
    except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc


class JobRequest(SavedRunConfig):
    request_id: str = Field(min_length=8, max_length=80)


@app.get('/api/jobs')
def list_jobs():
    jobs.STORE.recover()
    return {'jobs': jobs.STORE.list(), 'worker_available': jobs.STORE.worker_available()}


@app.post('/api/jobs', status_code=202)
def create_job(payload: JobRequest):
    try:
        dataset = DATASET_STORE.get(payload.dataset_id)
        if bool(payload.forecast_group_id) != bool(payload.forecast_name):
            raise ValueError('A forecast group needs an identifier and a name.')
        if payload.forecast_group_id and (not payload.sales_input_id or payload.scenario_name or payload.adjustment or dataset.get('scenario_provenance')):
            raise ValueError('Group methods only with the same reviewed forecast inputs.')
        validate_forecast_group(payload)
        if payload.forecast_group_id:
            for prior in jobs.STORE.list():
                values=prior.get('payload',{})
                if values.get('forecast_group_id')==payload.forecast_group_id and any(values.get(k)!=getattr(payload,k) for k in ('dataset_id','sales_input_id','forecast_name')):
                    raise ValueError('These methods belong to different inputs. Start a new forecast.')
        if payload.sales_input_id:
            from .forecast_orders import reviewed
            if dataset.get('scenario_provenance') or payload.scenario_name or payload.adjustment:
                raise ValueError('Use reviewed orders with a new forecast, not a quantity scenario.')
            reviewed(DATASET_STORE, SALES_STORE, dataset['id'], payload.sales_input_id)
        values = payload.model_dump(exclude={'request_id'})
        assumption = dataset.get('scenario_provenance')
        if assumption:
            if payload.scenario_name or payload.adjustment or payload.method or (payload.base_run_id and payload.base_run_id != assumption['base_run_id']):
                raise ValueError('An assumption scenario must use its recorded baseline and method.')
            values['base_run_id'] = assumption['base_run_id']
        if payload.scenario_name:
            base = _load_run(payload.base_run_id or '')
            if base.get('dataset_id') != dataset['id']:
                raise ValueError('The forecast and saved dataset do not match.')
        label=payload.forecast_name or payload.scenario_name or dataset['name']
        return jobs.submit(values, label+' · '+(payload.method or 'recommended'), payload.request_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    try:
        jobs.STORE.recover()
        return jobs.STORE.get(job_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id: str):
    try:
        return jobs.STORE.cancel(job_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post('/api/jobs/{job_id}/retry', status_code=202)
def retry_job(job_id: str, payload: dict):
    try:
        previous = jobs.STORE.get(job_id)
        if previous['state'] not in {'failed', 'cancelled', 'interrupted'}:
            raise ValueError('Only stopped jobs can be retried.')
        request = JobRequest(**previous['payload'], request_id=payload.get('request_id', ''))
        DATASET_STORE.get(request.dataset_id)
        return jobs.submit(previous['payload'], previous['name'], request.request_id, retry_of=job_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/run-list')
def run_list():
    rows=[]
    for path in RUNS_DIR.glob('*/result.json'):
        r=json.loads(path.read_text())
        rows.append({'run_id':r['run_id'],'base_run_id':r.get('base_run_id'),'dataset_id':r.get('dataset_id'),'name':r.get('forecast_name') or r.get('scenario_name') or r.get('dataset_name') or 'Earlier forecast','scenario_name':r.get('scenario_name'),'created_at':path.stat().st_mtime,'summary':r.get('summary',{}),'metrics':r.get('metrics',{}),**{k:r.get(k) for k in ('forecast_group_id','forecast_name','method_selection','forecast_order_inputs_id','sales_input_snapshot_id','unit')}})
    return {'runs':sorted(rows,key=lambda x:x['created_at'],reverse=True)}


@app.get("/api/sample/{name}")
def sample(name: str):
    allowed = {
        "history": "paper_printing_history_36m.csv",
        "future": "paper_printing_scenario_6m.csv",
        "notes": "scenario_event_notes.csv",
        "iran_history": "iran_manufacturing_history_60m.csv",
        "iran_future": "iran_manufacturing_scenario_12m.csv",
        "iran_notes": "iran_scenario_event_notes.csv",
        "iran_operations": "iran_operations_master.xlsx",
        "iran_actuals": "iran_actuals_followup_3m.csv",
    }
    filename = allowed.get(name)
    if not filename:
        raise HTTPException(status_code=404, detail="Unknown sample")
    path = SAMPLES_DIR / filename
    return FileResponse(path, filename=filename)


from .sales_demand import DemandStore
from .customers import CustomerStore, install_customer_routes
CUSTOMER_STORE = CustomerStore(DATA_DIR / 'customers.sqlite3')
install_customer_routes(app, CUSTOMER_STORE)
from .order_books import OrderBooks, install_order_books
ORDER_BOOKS = OrderBooks(DATA_DIR / 'orders.sqlite3', DATASET_STORE, CUSTOMER_STORE)
install_order_books(app, ORDER_BOOKS)
from .factor_profiles import FactorProfiles, install_profile_routes
FACTOR_PROFILES = FactorProfiles(CUSTOMER_STORE)
install_profile_routes(app, FACTOR_PROFILES)
from .sales_api import install_sales_routes
SALES_STORE = DemandStore(DATA_DIR / 'sales-demand.sqlite3')
from .demand_releases import DemandReleases, install_demand_releases
DEMAND_RELEASES = DemandReleases(SALES_STORE, lambda key:_load_run(key))
install_demand_releases(app, DEMAND_RELEASES)
from .order_folders import OrderFolders, install_order_folders
ORDER_FOLDERS = OrderFolders(DATA_DIR / 'order-folders.sqlite3', DATASET_STORE, FOLDER_INPUTS.roots, SALES_STORE, _load_run)
install_order_folders(app, ORDER_FOLDERS, INTEGRATION_STORE.scheduler, allow_schedule=lambda: ACCESS.config.mode != 'better_auth')
from .factor_folders import FactorFolders, install_factor_folders
FACTOR_FOLDERS = FactorFolders(DATA_DIR / 'factor-folders.sqlite3', DATASET_STORE, FOLDER_INPUTS.roots, FACTOR_STORE)
install_factor_folders(app, FACTOR_FOLDERS, INTEGRATION_STORE.scheduler, allow_schedule=lambda: ACCESS.config.mode != 'better_auth')
from .live_sources import LiveSources, install_live_sources
LIVE_SOURCES = LiveSources(DATA_DIR / 'live-sources.sqlite3', FACTOR_STORE)
install_live_sources(app, LIVE_SOURCES, INTEGRATION_STORE.scheduler, enabled=lambda: ACCESS.config.mode != 'better_auth')
sales_outlook = install_sales_routes(app, SALES_STORE, DATASET_STORE, _load_run, run_list)


@app.get('/api/datasets/{dataset_id}/forecast-orders')
def forecast_order_starter(dataset_id: str):
    from .forecast_orders import starter
    from .order_reuse import compatible
    try:
        data = ORDER_BOOKS.get(dataset_id)
        data['saved_orders'] = []
        for row in run_list()['runs']:
            base = _load_run(row['run_id'])
            if compatible(base, data['context']):
                versions = SALES_STORE.list(base['run_id'])
                if versions:
                    book = versions[0]
                    data['saved_orders'].append({'id': book['id'], 'name': book['inputs']['name'],
                                                 'as_of': book['inputs']['as_of']})
        return data
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get('/api/datasets/{dataset_id}/forecast-orders/template/{role}')
def forecast_order_template(dataset_id: str, role: str):
    from .forecast_orders import context
    from .sales_api import template_customers
    from .sales_demand import SCHEMAS
    from io import StringIO
    import csv
    try:
        if role not in SCHEMAS:
            raise ValueError('Unknown template.')
        value = context(DATASET_STORE, dataset_id)
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=list(SCHEMAS[role].model_fields))
        writer.writeheader()
        if role == 'customers':
            for row in template_customers(value):
                writer.writerow({k: "'"+v if v.lstrip().startswith(('=', '+', '-', '@')) else v for k,v in row.items()})
        return Response(output.getvalue(), media_type='text/csv', headers={
            'Content-Disposition': f'attachment; filename="{role}.csv"'})
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/datasets/{dataset_id}/forecast-orders/preview')
def preview_forecast_orders(dataset_id: str, payload: dict):
    from .forecast_orders import prepare
    try:
        return prepare(DATASET_STORE, SALES_STORE, dataset_id, payload, _load_run)[0]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post('/api/datasets/{dataset_id}/forecast-orders')
def save_forecast_orders(dataset_id: str, payload: dict, request: Request):
    from .forecast_orders import save
    try:
        principal = request.state.principal
        actor = json.dumps([principal.get('issuer'), principal.get('subject')]) if principal else 'Local session'
        return save(DATASET_STORE, SALES_STORE, dataset_id, payload, _load_run, actor)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
from .monthly_refresh import MonthlyRefresh, install_monthly_refresh
MONTHLY_REFRESH = MonthlyRefresh(DATA_DIR / 'monthly-updates.sqlite3', DATASET_STORE,
    _load_run, SALES_STORE, sales_outlook, jobs.STORE, jobs.submit, LIVE_SOURCES)
install_monthly_refresh(app, MONTHLY_REFRESH)
from .recurring_forecasts import RecurringForecasts, install_recurring_forecasts
def recurring_owner_authorized(actor):
    if actor=='Local session':return ACCESS.config.mode=='local'
    issuer,subject=json.loads(actor)
    return issuer==ACCESS.config.issuer and ACCESS.config.members().get(subject)=='admin'
RECURRING_FORECASTS=RecurringForecasts(DATA_DIR/'recurring-forecasts.sqlite3',MONTHLY_REFRESH,FOLDER_INPUTS,recurring_owner_authorized)
install_recurring_forecasts(app,RECURRING_FORECASTS,INTEGRATION_STORE.scheduler,enabled=lambda: ACCESS.config.mode != 'better_auth')
from .forecast_views import ViewStore, install_view_routes
install_view_routes(app, ViewStore(SALES_STORE.path), _load_run, SALES_STORE.get)
from .ai_workspace import AIJournal, install_ai_routes
install_ai_routes(app, AIJournal(DATA_DIR / 'ai-workspace.sqlite3'), _load_run,
                  sales_outlook, DATASET_STORE, jobs.submit, SALES_STORE, run_list, FACTOR_STORE,
                  LIVE_SOURCES, FACTOR_PROFILES, jobs.STORE.get)


# Explicit UI paths: refreshing a page serves the workspace, not a static-file 404.
# Do not use a catch-all that could mask missing API or asset routes.
@app.get('/today', include_in_schema=False)
@app.get('/demand', include_in_schema=False)
@app.get('/forecast', include_in_schema=False)
@app.get('/data', include_in_schema=False)
@app.get('/plans', include_in_schema=False)
@app.get('/settings', include_in_schema=False)
@app.get('/customers', include_in_schema=False)
@app.get('/help', include_in_schema=False)
@app.get('/new', include_in_schema=False)
@app.get('/assistant', include_in_schema=False)
@app.get('/')
@app.get('/index.html', include_in_schema=False)
def frontend():
    client=STATIC_DIR / 'client' / 'index.html'
    if not client.is_file():
        raise HTTPException(503, 'The workspace interface has not been built. Build the frontend before starting the app.')
    return FileResponse(client)


app.mount('/ui',StaticFiles(directory=STATIC_DIR / 'client',check_dir=False),name='client')
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

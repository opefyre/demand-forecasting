from __future__ import annotations

import json
from io import BytesIO
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from threading import RLock
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from persiantools.jdatetime import JalaliDate

from .data import build_future_covariates, preview_table, prepare_history, read_table, summarize_history
from .forecast_engine import run_forecast
from .assistant import answer_planning_question, suggest_mapping
from .integrations import IntegrationStore
from .monitoring import build_monitoring, forecast_value_add
from .operations import append_operations_export, calculate_operations, operations_preview, read_operations_workbook
from .planning import PlanStore
from .datasets import DatasetStore
from .scenarios import quantity_scenario


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
RUNS_DIR = BASE_DIR / "runs"
SAMPLES_DIR = BASE_DIR / "sample_data"
DATA_DIR = BASE_DIR / "data"
RUNS_DIR.mkdir(exist_ok=True)
PLAN_STORE = PlanStore(DATA_DIR / "plans.json")
DATASET_STORE = DatasetStore(DATA_DIR / "datasets")
INTEGRATION_STORE = IntegrationStore(DATA_DIR / "integrations.json")
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
INTEGRATION_STORE.restore_schedules()

app = FastAPI(title="DemandLab", version="1.0.0")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@app.on_event("shutdown")
def shutdown_integrations():
    INTEGRATION_STORE.close()

SITE_PROFILE = {
    "id": "qazvin-01",
    "name": "Qazvin Manufacturing Site",
    "country": "Iran",
    "province": "Qazvin",
    "timezone": "Asia/Tehran",
    "currency": "IRR",
    "currency_display": "toman",
    "calendar": "Jalali + Gregorian",
    "latitude": 36.2797,
    "longitude": 50.0049,
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


class SavedRunConfig(BaseModel):
    dataset_id: str
    method: str | None = None
    adjustment: float = Field(default=0,ge=-90,le=300)
    scenario_name: str | None = None
    base_run_id: str | None = None


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
):
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
        if not isinstance(driver_cols, list) or not isinstance(known_driver_cols, list):
            raise ValueError("Driver selections must be lists.")
        if not isinstance(driver_roles, dict):
            raise ValueError("Driver roles must be an object.")
        if not -90.0 <= scenario_adjustment_pct <= 300.0:
            raise ValueError("Scenario adjustment must be between -90% and +300%.")
        known_driver_cols = [c for c in known_driver_cols if c in driver_cols]
        driver_roles = {str(k): str(v) for k, v in driver_roles.items() if k in driver_cols}

        hist_payload = await _read_upload(historical_file)
        raw_history = read_table(historical_file.filename or "history.csv", hist_payload)
        metadata = _series_metadata(
            raw_history,
            item_col=item_col,
            sku_col=sku_col,
            category_col=category_col,
            customer_col=customer_col,
        )
        model_history = raw_history
        workbook_warnings: list[str] = []
        if "record_type" in raw_history.columns:
            actual_mask = raw_history["record_type"].astype(str).str.lower().eq("actual")
            if bool(actual_mask.any()):
                model_history = raw_history[actual_mask].copy()
                workbook_warnings.append(
                    f"Imported {int(actual_mask.sum())} actual workbook rows; existing forecast cells were kept out of model training"
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
        )

        raw_future = None
        if future_file is not None and future_file.filename:
            future_payload = await _read_upload(future_file)
            raw_future = read_table(future_file.filename, future_payload)

        operations_sheets = None
        if operations_file is not None and operations_file.filename:
            operations_payload = await _read_upload(operations_file)
            operations_sheets = read_operations_workbook(operations_file.filename, operations_payload)

        future_covariates, future_warnings = build_future_covariates(
            clean_history,
            raw_future,
            future_date_col=future_date_col or None,
            future_item_col=future_item_col or None,
            known_driver_cols=known_driver_cols,
            frequency=frequency,
            horizon=horizon,
            missing_future_policy=future_driver_policy,
        )
        driver_coverage = future_covariates.attrs.get("driver_coverage", {})

        result = run_forecast(
            history=clean_history,
            future_covariates=future_covariates,
            known_driver_cols=known_driver_cols,
            horizon=horizon,
            frequency=frequency,
            profile=profile,
            runs_dir=RUNS_DIR,
            driver_roles=driver_roles,
            scenario_adjustment_pct=scenario_adjustment_pct,
            method_selection=method_selection,
        )
        result["summary"] = summarize_history(clean_history)
        result["warnings"] = workbook_warnings + cleaning_warnings + future_warnings
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
            append_operations_export(RUNS_DIR / result["run_id"] / "forecast_package.xlsx", operations)
        else:
            result["operations"] = {"source": None, "materials": [], "capacity": [], "actions": [], "relationships": [], "promotions": [], "summary": {}}
            result["product_intelligence"] = {
                "lifecycle": [{"item_id": item, "sku": metadata.get(item, {}).get("sku", item), "stage": diag.get("lifecycle", "mature"), "history_points": diag.get("history_points"), "analog": None} for item, diag in result.get("series_diagnostics", {}).items()],
                "relationships": [], "promotions": [], "note": "Upload an operations master to evaluate substitutions, analogs and promotions.",
            }
        result_path = RUNS_DIR / result["run_id"] / "result.json"
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
    today = date.today()
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


@app.post("/api/plans")
def create_plan(payload: PlanCreate):
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
        owner=payload.owner,
        settings=plan_settings,
        metrics=run.get("metrics", {}),
    )


@app.patch("/api/plans/{plan_id}/status")
def transition_plan(plan_id: str, payload: PlanTransition):
    try:
        return PLAN_STORE.transition(plan_id, status=payload.status, actor=payload.actor, note=payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plans/{plan_id}/overrides")
def add_override(plan_id: str, payload: ForecastOverride):
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
            actor=payload.actor,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plans/{plan_id}/comments")
def add_plan_comment(plan_id: str, payload: PlanComment):
    try:
        return PLAN_STORE.add_comment(plan_id, text=payload.text, actor=payload.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plans/{plan_id}/overrides/{override_id}/revert")
def revert_override(plan_id: str, override_id: str, payload: OverrideReversal):
    try:
        return PLAN_STORE.revert_override(
            plan_id,
            override_id,
            reason=payload.reason,
            actor=payload.actor,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Plan or override not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/integrations")
def list_integrations():
    return {"integrations": INTEGRATION_STORE.list()}


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
    try:
        payload = await _read_upload(actuals_file)
        actuals = read_table(actuals_file.filename or "actuals.csv", payload)
        return forecast_value_add(_load_run(run_id), PLAN_STORE.list(), actuals)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@app.post('/api/datasets/validate')
def validate_dataset(payload: DatasetConfig):
    try: return DATASET_STORE.inspect(payload.sources,payload.settings)
    except Exception as exc: raise HTTPException(400,str(exc)) from exc


@app.post('/api/datasets')
def save_dataset(payload: DatasetConfig):
    try:
        if payload.classification not in {'user_provided','synthetic_sample'}: raise ValueError('Invalid source classification.')
        return DATASET_STORE.save(payload.name,payload.sources,payload.settings,payload.classification,payload.accept_warnings)
    except Exception as exc: raise HTTPException(400,str(exc)) from exc


@app.post('/api/run-saved')
async def run_saved(payload: SavedRunConfig):
    try:
        dataset=DATASET_STORE.get(payload.dataset_id)
        if payload.scenario_name is not None:
            if not payload.base_run_id: raise ValueError('Select a forecast before creating a scenario.')
            base=_load_run(payload.base_run_id)
            if base.get('dataset_id')!=dataset['id']: raise ValueError('The forecast and saved dataset do not match.')
            operations=None
            if dataset['sources'].get('operations'):
                source,content=DATASET_STORE.source(dataset['sources']['operations'])
                operations=read_operations_workbook(source['name'],content)
            return quantity_scenario(base,name=payload.scenario_name,adjustment=payload.adjustment,runs_dir=RUNS_DIR,operations=operations)
        s=dataset['settings']; uploads={}
        for role,key in dataset['sources'].items():
            source,content=DATASET_STORE.source(key)
            # Canonicalise the selected Excel sheet once, preserving the saved selection.
            if role!='operations':
                frame=read_table(source['name'],content,sheet_name=source.get('sheet'))
                content=frame.to_csv(index=False).encode('utf-8')
            uploads[role]=UploadFile(BytesIO(content),filename=source['name'] if role=='operations' else role+'.csv')
        result=await run(historical_file=uploads['history'],future_file=uploads.get('future'),operations_file=uploads.get('operations'),
            date_col=s['date_col'],target_col=s['target_col'],item_col=s.get('item_col',''),sku_col=s.get('sku_col',''),category_col=s.get('category_col',''),customer_col=s.get('customer_col',''),
            future_date_col=s.get('future_date_col',''),future_item_col=s.get('future_item_col',''),driver_cols_json=json.dumps(s.get('drivers',[])),known_driver_cols_json=json.dumps(s.get('drivers',[])),driver_roles_json=json.dumps(s.get('driver_roles',{})),
            frequency=s.get('frequency','monthly'),horizon=s.get('horizon',6),profile=s.get('profile','deep'),missing_strategy=s.get('missing_strategy','auto'),outlier_strategy=s.get('outlier_strategy','none'),scenario_adjustment_pct=payload.adjustment,method_selection=payload.method or s.get('method_selection','recommended'),future_driver_policy=s.get('future_driver_policy','require'),source_classification=dataset['classification'])
        result['dataset_id']=dataset['id']; result['dataset_name']=dataset['name']; result['unit']=s.get('unit','units')
        result['scenario_name']=payload.scenario_name
        (RUNS_DIR / result['run_id'] / 'result.json').write_text(json.dumps(result,ensure_ascii=False,default=str),encoding='utf-8')
        return result
    except HTTPException: raise
    except Exception as exc: raise HTTPException(400,str(exc)) from exc


@app.get('/api/runs/{run_id}')
def get_run(run_id: str): return _load_run(run_id)


@app.get('/api/run-list')
def run_list():
    rows=[]
    for path in RUNS_DIR.glob('*/result.json'):
        r=json.loads(path.read_text())
        rows.append({'run_id':r['run_id'],'base_run_id':r.get('base_run_id'),'dataset_id':r.get('dataset_id'),'name':r.get('scenario_name') or r.get('dataset_name') or 'Earlier forecast','scenario_name':r.get('scenario_name'),'created_at':path.stat().st_mtime,'summary':r.get('summary',{}),'metrics':r.get('metrics',{})})
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


@app.get('/')
def frontend():
    client=STATIC_DIR / 'client' / 'index.html'
    return FileResponse(client if client.exists() else STATIC_DIR / 'index.html')


app.mount('/ui',StaticFiles(directory=STATIC_DIR / 'client',check_dir=False),name='client')
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

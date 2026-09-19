from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

import httpx
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import create_engine, text


SUPPORTED_TYPES = {"folder", "database", "http_api", "erp_api"}


class IntegrationStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        self.scheduler = BackgroundScheduler(timezone="Asia/Tehran")
        self.scheduler.start(paused=False)
        if not self.path.exists():
            self._write({"connectors": []})

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {"connectors": []}

    def _write(self, data: dict) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def list(self) -> list[dict]:
        return self._read().get("connectors", [])

    def upsert(self, connector: dict) -> dict:
        kind = connector.get("type")
        if kind not in SUPPORTED_TYPES:
            raise ValueError("Connector type must be folder, database, HTTP API, or ERP API.")
        connector = {**connector}
        connector.setdefault("id", f"src-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}")
        connector.setdefault("enabled", False)
        connector.setdefault("schedule_minutes", 0)
        connector.setdefault("status", "not_tested")
        connector["updated_at"] = datetime.now(timezone.utc).isoformat()
        with self.lock:
            data = self._read()
            rows = data.get("connectors", [])
            rows = [row for row in rows if row.get("id") != connector["id"]] + [connector]
            data["connectors"] = rows
            self._write(data)
        self._schedule(connector)
        return connector

    def _schedule(self, connector: dict) -> None:
        job_id = f"connector-{connector['id']}"
        existing = self.scheduler.get_job(job_id)
        if existing:
            self.scheduler.remove_job(job_id)
        minutes = int(connector.get("schedule_minutes") or 0)
        if connector.get("enabled") and minutes > 0:
            self.scheduler.add_job(self.sync, "interval", minutes=minutes, args=[connector["id"]], id=job_id, replace_existing=True, max_instances=1)

    def restore_schedules(self) -> None:
        for connector in self.list():
            self._schedule(connector)

    def sync(self, connector_id: str) -> dict:
        rows = self.list()
        connector = next((row for row in rows if row.get("id") == connector_id), None)
        if not connector:
            raise KeyError(connector_id)
        try:
            result = self._execute(connector)
            connector.update({"status": "healthy", "last_sync": datetime.now(timezone.utc).isoformat(), "last_result": result, "last_error": None})
        except Exception as exc:
            connector.update({"status": "failed", "last_sync": datetime.now(timezone.utc).isoformat(), "last_error": str(exc)[:500]})
        return self.upsert(connector)

    def _execute(self, connector: dict) -> dict:
        kind = connector["type"]
        if kind == "folder":
            folder = Path(str(connector.get("path", ""))).expanduser().resolve()
            if not folder.is_dir():
                raise ValueError("Folder path does not exist.")
            files = sorted([*folder.glob("*.csv"), *folder.glob("*.xlsx")], key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                raise ValueError("No supported CSV or Excel file was found in the folder.")
            latest = files[0]
            frame = pd.read_csv(latest, nrows=5) if latest.suffix.lower() == ".csv" else pd.read_excel(latest, nrows=5)
            return {"resource": latest.name, "columns": list(frame.columns), "sample_rows": int(len(frame))}
        if kind == "database":
            env_name = str(connector.get("secret_env", "")).strip()
            dsn = os.environ.get(env_name)
            if not env_name or not dsn:
                raise ValueError("Database connection environment variable is not set.")
            query = str(connector.get("query") or "SELECT 1 AS connection_ok")
            if not query.lstrip().lower().startswith("select"):
                raise ValueError("Only read-only SELECT queries are allowed.")
            with create_engine(dsn).connect() as connection:
                result = connection.execute(text(query)).fetchmany(5)
            return {"sample_rows": len(result), "read_only": True}
        if kind in {"http_api", "erp_api"}:
            url = str(connector.get("url", "")).strip()
            if not url.startswith(("https://", "http://")):
                raise ValueError("A valid HTTP or HTTPS URL is required.")
            headers = {}
            env_name = str(connector.get("secret_env", "")).strip()
            if env_name and os.environ.get(env_name):
                headers["Authorization"] = f"Bearer {os.environ[env_name]}"
            response = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
            response.raise_for_status()
            size = len(response.content)
            return {"http_status": response.status_code, "bytes": size, "content_type": response.headers.get("content-type"), "read_only": True}
        raise ValueError("Unsupported connector type.")

    def close(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

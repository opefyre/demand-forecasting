from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock


VALID_PLAN_STATES = {"draft", "review", "approved", "published", "archived"}
VALID_TRANSITIONS = {
    "draft": {"review", "archived"},
    "review": {"draft", "approved", "archived"},
    "approved": {"review", "published", "archived"},
    "published": {"archived"},
    "archived": set(),
}


class PlanStore:
    """Small local plan registry with atomic JSON persistence.

    DemandLab is currently a local deployment. This repository-backed store keeps
    plan state reproducible without introducing a bespoke database layer. It can
    later be replaced by PostgreSQL behind the same API.
    """

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _write(self, plans: list[dict]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def list(self) -> list[dict]:
        with self._lock:
            return sorted(self._read(), key=lambda row: row.get("updated_at", ""), reverse=True)

    def get(self, plan_id: str) -> dict | None:
        return next((row for row in self.list() if row.get("id") == plan_id), None)

    def create(
        self,
        *,
        name: str,
        run_id: str,
        site_id: str,
        owner: str,
        settings: dict,
        metrics: dict,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        plan = {
            "id": uuid.uuid4().hex[:10],
            "name": name.strip() or "Untitled plan",
            "run_id": run_id,
            "site_id": site_id,
            "owner": owner.strip() or "Planning team",
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "settings": settings,
            "metrics": metrics,
            "overrides": [],
            "comments": [],
            "history": [{"status": "draft", "actor": owner or "Planning team", "note": "Plan created", "at": now}],
        }
        with self._lock:
            plans = self._read()
            plans.append(plan)
            self._write(plans)
        return plan

    def transition(self, plan_id: str, *, status: str, actor: str, note: str = "") -> dict:
        if status not in VALID_PLAN_STATES:
            raise ValueError(f"Unknown plan status: {status}")
        with self._lock:
            plans = self._read()
            plan = next((row for row in plans if row.get("id") == plan_id), None)
            if plan is None:
                raise KeyError(plan_id)
            current_status = str(plan.get("status", "draft"))
            if status not in VALID_TRANSITIONS.get(current_status, set()):
                raise ValueError(f"A plan cannot move directly from {current_status} to {status}.")
            evidence = str(plan.get("metrics", {}).get("evidence_level", "limited"))
            if status in {"approved", "published"} and evidence == "limited":
                raise ValueError("This plan has limited forecast evidence and must be rerun with more history or a shorter horizon before approval.")
            now = datetime.now(timezone.utc).isoformat()
            plan["status"] = status
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": status,
                "actor": actor.strip() or "Planning team",
                "note": note.strip(),
                "at": now,
            })
            self._write(plans)
            return plan

    def add_comment(self, plan_id: str, *, text: str, actor: str) -> dict:
        if not text.strip():
            raise ValueError("A comment cannot be empty.")
        with self._lock:
            plans = self._read()
            plan = next((row for row in plans if row.get("id") == plan_id), None)
            if plan is None:
                raise KeyError(plan_id)
            now = datetime.now(timezone.utc).isoformat()
            comment = {
                "id": uuid.uuid4().hex[:10],
                "text": text.strip(),
                "actor": actor.strip() or "Planning team",
                "at": now,
            }
            plan.setdefault("comments", []).append(comment)
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": plan.get("status", "draft"),
                "actor": comment["actor"],
                "note": f"Comment: {comment['text']}",
                "at": now,
            })
            self._write(plans)
            return plan

    def revert_override(self, plan_id: str, override_id: str, *, reason: str, actor: str) -> dict:
        if not reason.strip():
            raise ValueError("A reason is required to reverse an override.")
        with self._lock:
            plans = self._read()
            plan = next((row for row in plans if row.get("id") == plan_id), None)
            if plan is None:
                raise KeyError(plan_id)
            if plan.get("status") in {"approved", "published", "archived"}:
                raise ValueError("Approved, published or archived plans cannot be edited. Create a new version instead.")
            override = next((row for row in plan.get("overrides", []) if row.get("id") == override_id), None)
            if override is None:
                raise KeyError(override_id)
            if override.get("reverted_at"):
                raise ValueError("This override has already been reversed.")
            now = datetime.now(timezone.utc).isoformat()
            override.update({
                "reverted_at": now,
                "reverted_by": actor.strip() or "Planning team",
                "revert_reason": reason.strip(),
            })
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": plan.get("status", "draft"),
                "actor": override["reverted_by"],
                "note": f"Override {override_id} reversed: {reason.strip()}",
                "at": now,
            })
            self._write(plans)
            return plan

    def add_override(
        self,
        plan_id: str,
        *,
        item_id: str,
        period: str,
        value: float,
        reason: str,
        actor: str,
    ) -> dict:
        if not reason.strip():
            raise ValueError("A reason is required for every forecast override.")
        with self._lock:
            plans = self._read()
            plan = next((row for row in plans if row.get("id") == plan_id), None)
            if plan is None:
                raise KeyError(plan_id)
            if plan.get("status") in {"approved", "published", "archived"}:
                raise ValueError("Approved, published or archived plans cannot be edited. Create a new version instead.")
            now = datetime.now(timezone.utc).isoformat()
            override = {
                "id": uuid.uuid4().hex[:10],
                "item_id": item_id,
                "period": period,
                "value": max(0.0, float(value)),
                "reason": reason.strip(),
                "actor": actor.strip() or "Planning team",
                "at": now,
            }
            plan.setdefault("overrides", []).append(override)
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": plan.get("status", "draft"),
                "actor": override["actor"],
                "note": f"Override added for {item_id} · {period}: {reason.strip()}",
                "at": now,
            })
            self._write(plans)
            return plan

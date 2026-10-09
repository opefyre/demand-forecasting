from __future__ import annotations

import math
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from .plan_storage import PlanStorage


VALID_PLAN_STATES = {"draft", "review", "approved", "published", "archived"}
VALID_TRANSITIONS = {
    "draft": {"review", "archived"},
    "review": {"draft", "approved", "archived"},
    "approved": {"review", "published", "archived"},
    "published": {"archived"},
    "archived": set(),
}


class PlanStore:
    """Local plan registry with transactional SQLite persistence."""

    def __init__(self, path: Path):
        self.path = path
        self.storage = PlanStorage(path)

    def list(self) -> list[dict]:
        return self.storage.list()

    def get(self, plan_id: str) -> dict | None:
        return self.storage.get(plan_id)

    def create(
        self,
        *,
        name: str,
        run_id: str,
        site_id: str,
        owner: str,
        settings: dict,
        metrics: dict,
        identity: dict | None = None,
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
        if identity:
            plan['created_by'] = deepcopy(identity)
            plan['history'][0]['identity'] = deepcopy(identity)
        with self.storage.transaction() as plans:
            plans.append(plan)
        return plan

    def transition(self, plan_id: str, *, status: str, actor: str, note: str = "", identity: dict | None = None) -> dict:
        if status not in VALID_PLAN_STATES:
            raise ValueError(f"Unknown plan status: {status}")
        with self.storage.transaction() as plans:
            plan = next((row for row in plans if row.get("id") == plan_id), None)
            if plan is None:
                raise KeyError(plan_id)
            current_status = str(plan.get("status", "draft"))
            if status not in VALID_TRANSITIONS.get(current_status, set()):
                raise ValueError(f"A plan cannot move directly from {current_status} to {status}.")
            evidence = str(plan.get("metrics", {}).get("evidence_level", "limited"))
            if status in {"approved", "published"} and evidence == "limited":
                raise ValueError("This plan has limited forecast evidence and must be rerun with more history or a shorter horizon before approval.")
            if identity and status in {'approved','published'}:
                if identity.get('role') not in {'reviewer','admin'}:
                    raise ValueError('A reviewer must approve or publish this plan.')
                creator = plan.get('created_by')
                if not creator:
                    raise ValueError('This plan has no verified creator. Save a new plan while signed in before approval.')
                if any(not change.get('identity') and not change.get('inherited_from') for change in plan.get('overrides', [])):
                    raise ValueError('This plan contains unverified edits. Save a new signed-in plan before approval.')
                same = lambda person: person and (person.get('issuer'),person.get('subject')) == (identity['issuer'],identity['subject'])
                if same(creator) or any(same(change.get('identity')) or same(change.get('reverted_identity')) for change in plan.get('overrides', [])):
                    raise ValueError('A different reviewer must approve a plan they did not create or adjust.')
                if status == 'published':
                    approval = next((event for event in reversed(plan.get('history', [])) if event['status']=='approved'),None)
                    if not approval or not approval.get('identity'):
                        raise ValueError('This plan needs authenticated approval before publication.')
            now = datetime.now(timezone.utc).isoformat()
            plan["status"] = status
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": status,
                "actor": actor.strip() or "Planning team",
                "note": note.strip(),
                "at": now,
                **({'identity':deepcopy(identity)} if identity else {}),
            })
            return plan

    def revise(self, plan_id: str, *, name: str, owner: str, reason: str, request_id: str, identity: dict | None = None) -> dict:
        """Branch a locked version without editing its record or approval trail."""
        values = {key: value.strip() for key, value in {'name': name, 'owner': owner, 'reason': reason}.items()}
        if not all(values.values()) or len(values['reason']) < 3:
            raise ValueError('Enter a name, owner and reason for the new version.')
        try:
            request_id = str(uuid.UUID(request_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError('Use a valid revision request identifier.') from exc
        with self.storage.transaction() as plans:
            existing = next((p for p in plans if p.get('revision_request_id') == request_id), None)
            if existing:
                if (existing.get('parent_plan_id') != plan_id or existing.get('revision_request') != values
                        or existing.get('created_by') != identity):
                    raise ValueError('This revision request was already used for different details.')
                return existing
            parent = next((p for p in plans if p['id'] == plan_id), None)
            if parent is None:
                raise KeyError(plan_id)
            if parent['status'] not in {'approved', 'published'}:
                raise ValueError('Create a new version from an approved or published plan. Edit an existing draft directly.')
            root_id = parent.get('root_plan_id', parent['id'])
            version = 1 + max(p.get('version', 1) for p in plans
                              if p['id'] == root_id or p.get('root_plan_id') == root_id)
            now = datetime.now(timezone.utc).isoformat()
            active = {}
            for change in parent.get('overrides', []):
                if not change.get('reverted_at'):
                    active[(change['item_id'], change['period'][:10])] = change
            inherited = []
            for change in active.values():
                inherited.append({'id': uuid.uuid4().hex[:10], 'item_id': change['item_id'],
                    'period': change['period'][:10], 'value': change['value'], 'reason': change['reason'],
                    'actor': values['owner'], 'at': now, 'inherited_from': {'plan_id': parent['id'],
                    'override_id': change['id'], 'actor': change.get('actor'), 'at': change.get('at')}})
            draft = {'id': uuid.uuid4().hex[:10], 'name': values['name'], 'owner': values['owner'],
                     'status': 'draft', 'run_id': parent['run_id'], 'site_id': parent['site_id'],
                     'settings': deepcopy(parent['settings']), 'metrics': deepcopy(parent['metrics']),
                     'created_at': now, 'updated_at': now, 'overrides': inherited, 'comments': [],
                     'parent_plan_id': parent['id'], 'root_plan_id': root_id, 'version': version,
                     'revision_baseline': {'run_id': parent['run_id'], 'status': parent['status'],
                         'updated_at': parent['updated_at'], 'overrides': deepcopy(list(active.values()))},
                     'revision_reason': values['reason'], 'revision_request_id': request_id,
                     'revision_request': values,
                     'history': [{'status': 'draft', 'actor': values['owner'], 'at': now,
                                  'note': f"Version {version} created from {parent['name']}: {values['reason']}"}]}
            plans.append(draft)
            if identity:
                draft['created_by'] = deepcopy(identity)
                draft['history'][0]['identity'] = deepcopy(identity)
            return draft

    def add_comment(self, plan_id: str, *, text: str, actor: str, identity: dict | None = None) -> dict:
        if not text.strip():
            raise ValueError("A comment cannot be empty.")
        with self.storage.transaction() as plans:
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
            if identity: comment['identity'] = deepcopy(identity)
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": plan.get("status", "draft"),
                "actor": comment["actor"],
                "note": f"Comment: {comment['text']}",
                "at": now,
                **({'identity':deepcopy(identity)} if identity else {}),
            })
            return plan

    def revert_override(self, plan_id: str, override_id: str, *, reason: str, actor: str, identity: dict | None = None) -> dict:
        if not reason.strip():
            raise ValueError("A reason is required to reverse an override.")
        with self.storage.transaction() as plans:
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
            if identity: override['reverted_identity'] = deepcopy(identity)
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": plan.get("status", "draft"),
                "actor": override["reverted_by"],
                "note": f"Override {override_id} reversed: {reason.strip()}",
                "at": now,
                **({'identity':deepcopy(identity)} if identity else {}),
            })
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
        identity: dict | None = None,
    ) -> dict:
        if not reason.strip():
            raise ValueError("A reason is required for every forecast override.")
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError('Plan quantities must be finite and nonnegative.')
        with self.storage.transaction() as plans:
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
                "value": float(value),
                "reason": reason.strip(),
                "actor": actor.strip() or "Planning team",
                "at": now,
            }
            plan.setdefault("overrides", []).append(override)
            if identity: override['identity'] = deepcopy(identity)
            plan["updated_at"] = now
            plan.setdefault("history", []).append({
                "status": plan.get("status", "draft"),
                "actor": override["actor"],
                "note": f"Override added for {item_id} · {period}: {reason.strip()}",
                "at": now,
                **({'identity':deepcopy(identity)} if identity else {}),
            })
            return plan

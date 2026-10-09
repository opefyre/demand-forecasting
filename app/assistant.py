from __future__ import annotations

import json
import os
import re

import httpx


MUTATION_WORDS = re.compile(r"\b(approve|publish|change|override|edit|delete|create order|place order|update plan)\b", re.I)


def suggest_mapping(columns: list[str], numeric_columns: list[str], date_candidates: list[str]) -> dict:
    lower = {str(col).lower(): str(col) for col in columns}

    def pick(tokens: list[str], candidates: list[str] | None = None):
        pool = candidates or columns
        for token in tokens:
            for column in pool:
                if token == str(column).lower() or token in str(column).lower():
                    return column
        return None

    suggestions = {
        "date": pick(["date", "month", "period", "week"], date_candidates or columns),
        "target": pick(["demand_tonnes", "demand", "sales", "shipment", "consumption", "target"], numeric_columns),
        "item": pick(["series_id", "item_id", "sku", "product", "material"]),
        "sku": pick(["sku", "stock_keeping_unit"]),
        "category": pick(["category", "family", "product_group"]),
        "customer": pick(["customer", "market", "channel"]),
    }
    used = {value for value in suggestions.values() if value}
    drivers = [column for column in columns if column not in used and (column in numeric_columns or any(token in str(column).lower() for token in ["event", "holiday", "promotion"]))]
    return {
        "suggestions": suggestions,
        "drivers": drivers,
        "explanation": "Suggestions are grounded only in the uploaded column names and detected data types; the user remains responsible for confirming them.",
        "provider": "local schema mapper",
    }


def _ollama_answer(question: str, evidence: dict, citations: list[str]) -> str | None:
    url = os.environ.get("DEMANDLAB_OLLAMA_URL", "").rstrip("/")
    model = os.environ.get("DEMANDLAB_OLLAMA_MODEL", "").strip()
    if not url or not model:
        return None
    prompt = (
        "You are a read-only manufacturing planning analyst. Answer only from EVIDENCE. "
        "Do not invent values, modify data, or recommend that a plan was approved. Use plain language in under 140 words.\n"
        f"QUESTION: {question}\nEVIDENCE: {json.dumps(evidence, ensure_ascii=False, default=str)}\n"
        f"AVAILABLE SOURCE LABELS: {json.dumps(citations)}"
    )
    try:
        response = httpx.post(f"{url}/api/generate", json={"model": model, "prompt": prompt, "stream": False}, timeout=25)
        response.raise_for_status()
        answer = str(response.json().get("response", "")).strip()
        return answer or None
    except Exception:
        return None


def answer_planning_question(question: str, run: dict, plans: list[dict], monitoring: dict) -> dict:
    question = question.strip()
    if not question:
        raise ValueError("Ask a planning question first.")
    if MUTATION_WORDS.search(question):
        return {
            "answer": "I’m read-only. I can explain the evidence and prepare a proposed action, but a planner must make, review and approve every numerical change in the governed plan workspace.",
            "citations": ["Planning governance policy"],
            "read_only": True,
            "action_taken": False,
        }
    lower = question.lower()
    metrics = run.get("metrics", {})
    operations = run.get("operations", {})
    if any(word in lower for word in ["shortage", "material", "procurement", "supplier"]):
        actions = [row for row in operations.get("actions", []) if row.get("type") == "material_shortage"][:5]
        if not actions:
            answer = "No material shortage is present in the current operations calculation. This conclusion only covers the uploaded BOM, material balances, quality holds and open purchase orders."
        else:
            summary = "; ".join(f"{row['subject']} ({row['period']}): {row['action']}" for row in actions)
            answer = f"The current plan has {operations.get('summary', {}).get('materials_at_risk', 0)} material(s) at risk. Highest-priority actions: {summary}."
        citations = ["Current run · Material Requirements", "Current run · Operational Actions"]
    elif any(word in lower for word in ["capacity", "bottleneck", "line"]):
        rows = [row for row in operations.get("capacity", []) if row.get("status") != "available"][:5]
        answer = "No line exceeds the watch threshold in the uploaded capacity calendar." if not rows else "Capacity exceptions: " + "; ".join(f"{row['production_line']} in {row['period']} at {row['utilisation_pct']:.1f}%" for row in rows) + "."
        citations = ["Current run · Capacity Plan"]
    elif any(word in lower for word in ["accur", "model", "method", "retrain", "drift"]):
        error = metrics.get('wape_pct')
        error_text = f'{error:.1f}%' if error is not None else 'not available'
        answer = f"Historical forecast error is {error_text} with {metrics.get('evidence_level', 'limited')} evidence. This run uses {run.get('best_model', 'an unrecorded method')}. {' '.join(monitoring.get('retrain', {}).get('reasons', []))}"
        citations = ["Current run · Rolling validation", "Performance · Champion/challenger monitor"]
    elif any(word in lower for word in ["factor", "driver", "why", "explain"]):
        drivers = run.get("drivers", [])[:5]
        answer = "The strongest associations in this run are " + (", ".join(f"{row['feature']} ({row.get('direction', 'mixed')})" for row in drivers) if drivers else "not available because no usable future factors were selected") + ". These are predictive associations, not proof of causation."
        citations = ["Current run · Driver importance", "Current run · Future-factor coverage"]
    else:
        risks = len(operations.get("actions", []))
        plan = plans[0] if plans else None
        answer = f"The current forecast has {metrics.get('evidence_level', 'limited')} evidence, {float(metrics.get('wape_pct') or 0):.1f}% validation WAPE and {risks} operational exception(s). " + (f"The latest governed plan is {plan.get('status')} ({plan.get('name')})." if plan else "No governed plan has been created yet.")
        citations = ["Current run · Forecast metrics", "Current run · Operational Actions", "Plan register"]
    evidence = {
        "run_id": run.get("run_id"),
        "metrics": metrics,
        "operations_summary": operations.get("summary", {}),
        "operational_actions": operations.get("actions", [])[:8],
        "drivers": run.get("drivers", [])[:8],
        "latest_plan": plans[0] if plans else None,
        "monitoring": monitoring,
    }
    generated = _ollama_answer(question, evidence, citations)
    return {"answer": generated or answer, "citations": citations, "read_only": True, "action_taken": False, "provider": "ollama" if generated else "grounded local rules"}

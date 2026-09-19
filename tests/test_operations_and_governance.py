from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.assistant import answer_planning_question, suggest_mapping
from app.integrations import IntegrationStore
from app.monitoring import forecast_value_add
from app.operations import calculate_operations, read_operations_workbook


ROOT = Path(__file__).resolve().parent.parent


class OperationsAndGovernanceTests(unittest.TestCase):
    def setUp(self):
        payload = (ROOT / "sample_data" / "iran_operations_master.xlsx").read_bytes()
        self.sheets = read_operations_workbook("iran_operations_master.xlsx", payload)
        self.run = {
            "run_id": "test-run",
            "metrics": {"wape_pct": 8.0, "evidence_level": "strong"},
            "best_model": "AutoETS",
            "metadata": {"SKU-1 · Domestic": {"sku": "PKG-KRAFT-120", "production_line": "Paper line A"}},
            "series": {"SKU-1 · Domestic": {"forecast": [{"timestamp": "2026-09-01", "mean": 250.0}]}},
            "forecast_rows": [{"item_id": "SKU-1 · Domestic", "timestamp": "2026-09-01", "baseline_mean": 100.0}],
        }

    def test_operations_master_produces_mrp_and_capacity(self):
        result = calculate_operations(self.run, self.sheets)
        self.assertTrue(result["materials"])
        self.assertTrue(result["capacity"])
        self.assertIn("material_shortages", result["summary"])
        self.assertTrue(all("recommended_order" in row for row in result["materials"]))

    def test_assistant_is_read_only_even_when_asked_to_publish(self):
        response = answer_planning_question("Approve and publish this plan", self.run, [], {})
        self.assertTrue(response["read_only"])
        self.assertFalse(response["action_taken"])
        self.assertIn("planner must", response["answer"])

    def test_mapping_assistance_is_grounded_in_uploaded_schema(self):
        result = suggest_mapping(
            ["month", "sku", "demand_tonnes", "promotion_code"],
            ["demand_tonnes"],
            ["month"],
        )
        self.assertEqual(result["suggestions"]["date"], "month")
        self.assertEqual(result["suggestions"]["target"], "demand_tonnes")
        self.assertIn("promotion_code", result["drivers"])

    def test_fva_keeps_statistical_baseline_untouched(self):
        actuals = pd.DataFrame([{"item_id": "SKU-1 · Domestic", "timestamp": "2026-09-01", "actual": 120.0}])
        plans = [{"id": "p1", "run_id": "test-run", "status": "published", "overrides": [{"item_id": "SKU-1 · Domestic", "period": "2026-09-01", "value": 118.0}]}]
        result = forecast_value_add(self.run, plans, actuals)
        self.assertGreater(result["fva_points"], 0)
        self.assertAlmostEqual(self.run["forecast_rows"][0]["baseline_mean"], 100.0)

    def test_folder_connector_is_read_only_and_testable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            pd.DataFrame([{"date": "2026-01-01", "demand": 10}]).to_csv(path / "history.csv", index=False)
            store = IntegrationStore(path / "integrations.json")
            connector = store.upsert({"id": "folder", "name": "Folder", "type": "folder", "path": str(path), "enabled": False})
            checked = store.sync(connector["id"])
            store.close()
            self.assertEqual(checked["status"], "healthy")
            self.assertEqual(checked["last_result"]["resource"], "history.csv")


if __name__ == "__main__":
    unittest.main()

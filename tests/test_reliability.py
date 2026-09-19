import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

import numpy as np
import pandas as pd

from app.data import add_calendar_covariates, build_future_covariates, prepare_history, read_table
from app.forecast_engine import _global_direct_supervised_frame, _metric_bundle, _rolling_folds, _series_profile
from app.planning import PlanStore


class ReliabilityTests(unittest.TestCase):
    def test_supplied_workbook_is_converted_to_canonical_series(self):
        workbook = Path(__file__).resolve().parents[1] / "Sales Forecast-2026.xlsx"
        frame = read_table(workbook.name, workbook.read_bytes())
        self.assertTrue(frame.attrs.get("wide_forecast_matrix"))
        self.assertTrue({"date", "demand", "series_id", "record_type"}.issubset(frame.columns))
        self.assertGreater(frame["series_id"].nunique(), 300)
        self.assertEqual(set(frame["record_type"].unique()), {"actual", "forecast"})

    def test_backtest_uses_requested_horizon_when_history_allows(self):
        dates = pd.date_range("2023-01-01", periods=36, freq="MS")
        history = pd.DataFrame({
            "item_id": ["A"] * len(dates),
            "timestamp": dates,
            "target": np.arange(len(dates), dtype=float),
        })
        folds, validation_horizon = _rolling_folds(history, "monthly", "deep", 6)
        self.assertEqual(validation_horizon, 6)
        self.assertEqual(len(folds), 3)
        self.assertTrue(all(len(validation_dates) == 6 for _, validation_dates in folds))

    def test_metrics_report_bias_and_scaled_error(self):
        actual = np.array([10.0, 20.0, 30.0])
        predicted = np.array([11.0, 21.0, 31.0])
        metrics = _metric_bundle(actual, predicted)
        self.assertAlmostEqual(metrics["wape_pct"], 5.0)
        self.assertGreater(metrics["bias_pct"], 0.0)
        self.assertIn("smape_pct", metrics)

    def test_smart_gap_repair_and_robust_outlier_flagging(self):
        raw = pd.DataFrame({
            "date": pd.to_datetime([
                "2025-01-01", "2025-02-01", "2025-04-01", "2025-05-01",
                "2025-06-01", "2025-07-01", "2025-08-01", "2025-09-01",
            ]),
            "item": ["A"] * 8,
            "demand": [10, 11, 13, 12, 11, 12, 400, 12],
        })
        clean, warnings = prepare_history(
            raw,
            date_col="date",
            target_col="demand",
            item_col="item",
            driver_cols=[],
            frequency="monthly",
            missing_strategy="auto",
            outlier_strategy="winsorize",
        )
        march = clean.loc[clean["timestamp"] == pd.Timestamp("2025-03-01"), "target"].iloc[0]
        self.assertAlmostEqual(march, 12.0, delta=0.1)
        self.assertEqual(int(clean["was_imputed"].sum()), 1)
        self.assertEqual(int(clean["was_outlier"].sum()), 1)
        self.assertTrue(any("missing period" in warning for warning in warnings))

    def test_calendar_features_capture_multiple_seasonalities(self):
        frame = pd.DataFrame({"timestamp": pd.date_range("2026-01-01", periods=3, freq="D")})
        enriched = add_calendar_covariates(frame, frequency="daily")
        self.assertIn("calendar_week_sin", enriched.columns)
        self.assertIn("calendar_year_sin_2", enriched.columns)
        self.assertIn("calendar_is_weekend", enriched.columns)

    def test_intermittent_demand_is_classified(self):
        values = np.array([0, 0, 8, 0, 0, 0, 7, 0, 0, 6], dtype=float)
        profile = _series_profile(values, seasonal_lag=12)
        self.assertIn(profile["demand_class"], {"intermittent", "lumpy"})

    def test_lifecycle_break_and_possible_stockout_are_flagged(self):
        values = np.array([10, 11, 10, 12, 11, 10, 12, 11, 10, 11, 10, 12, 21, 0, 23, 22, 24, 23], dtype=float)
        profile = _series_profile(values, seasonal_lag=6)
        self.assertEqual(profile["lifecycle"], "growth")
        self.assertTrue(profile["structural_break_suspected"])
        self.assertTrue(profile["stockout_or_lost_sales_suspected"])

    def test_missing_future_drivers_are_never_silently_filled(self):
        history = pd.DataFrame({
            "item_id": ["A"] * 12,
            "timestamp": pd.date_range("2025-01-01", periods=12, freq="MS"),
            "target": np.arange(12, dtype=float),
            "exchange_rate": np.linspace(50, 60, 12),
        })
        with self.assertRaisesRegex(ValueError, "Future values are missing"):
            build_future_covariates(
                history,
                None,
                future_date_col=None,
                future_item_col=None,
                known_driver_cols=["exchange_rate"],
                frequency="monthly",
                horizon=3,
                missing_future_policy="require",
            )

        future, warnings = build_future_covariates(
            history,
            None,
            future_date_col=None,
            future_item_col=None,
            known_driver_cols=["exchange_rate"],
            frequency="monthly",
            horizon=3,
            missing_future_policy="carry",
        )
        self.assertEqual(future.attrs["driver_coverage"]["exchange_rate"]["assumed"], 3)
        self.assertTrue(any("explicit policy" in warning for warning in warnings))

    def test_direct_ml_training_contains_real_multi_step_horizons(self):
        history = pd.DataFrame({
            "item_id": ["A"] * 36,
            "timestamp": pd.date_range("2023-01-01", periods=36, freq="MS"),
            "target": 100 + np.sin(np.arange(36) * 2 * np.pi / 12) * 10,
        })
        features, target = _global_direct_supervised_frame(
            history,
            known_driver_cols=[],
            lags=[1, 2, 3, 6, 12],
            max_horizon=6,
        )
        self.assertEqual(len(features), len(target))
        self.assertEqual(int(features["forecast_step"].max()), 6)
        self.assertGreater(int((features["forecast_step"] > 1).sum()), 0)

    def test_limited_evidence_plan_cannot_be_approved(self):
        with TemporaryDirectory() as temp_dir:
            store = PlanStore(Path(temp_dir) / "plans.json")
            plan = store.create(
                name="Limited sample",
                run_id="run-1",
                site_id="qazvin-main",
                owner="Planner",
                settings={},
                metrics={"evidence_level": "limited"},
            )
            store.transition(plan["id"], status="review", actor="Planner")
            with self.assertRaisesRegex(ValueError, "limited forecast evidence"):
                store.transition(plan["id"], status="approved", actor="Approver")

    def test_plan_workflow_rejects_skipped_governance_states(self):
        with TemporaryDirectory() as temp_dir:
            store = PlanStore(Path(temp_dir) / "plans.json")
            plan = store.create(
                name="Governed sample",
                run_id="run-3",
                site_id="qazvin-main",
                owner="Planner",
                settings={},
                metrics={"evidence_level": "strong"},
            )
            with self.assertRaisesRegex(ValueError, "cannot move directly"):
                store.transition(plan["id"], status="published", actor="Planner")

    def test_plan_override_requires_an_audit_reason(self):
        with TemporaryDirectory() as temp_dir:
            store = PlanStore(Path(temp_dir) / "plans.json")
            plan = store.create(
                name="Strong sample",
                run_id="run-2",
                site_id="qazvin-main",
                owner="Planner",
                settings={},
                metrics={"evidence_level": "strong"},
            )
            with self.assertRaisesRegex(ValueError, "reason is required"):
                store.add_override(
                    plan["id"],
                    item_id="SKU-A",
                    period="2026-10-01",
                    value=120,
                    reason="",
                    actor="Planner",
                )

    def test_plan_comments_and_override_reversal_remain_auditable(self):
        with TemporaryDirectory() as temp_dir:
            store = PlanStore(Path(temp_dir) / "plans.json")
            plan = store.create(
                name="Reviewable sample",
                run_id="run-4",
                site_id="qazvin-main",
                owner="Planner",
                settings={},
                metrics={"evidence_level": "strong"},
            )
            plan = store.add_override(
                plan["id"], item_id="SKU-A", period="2026-10-01",
                value=120, reason="Maintenance buffer", actor="Planner",
            )
            override_id = plan["overrides"][0]["id"]
            plan = store.add_comment(plan["id"], text="Supplier confirmed the buffer", actor="Buyer")
            plan = store.revert_override(
                plan["id"], override_id, reason="Maintenance moved to November", actor="Planner",
            )
            self.assertEqual(plan["comments"][0]["actor"], "Buyer")
            self.assertEqual(plan["overrides"][0]["revert_reason"], "Maintenance moved to November")
            self.assertTrue(any("reversed" in row["note"] for row in plan["history"]))


if __name__ == "__main__":
    unittest.main()

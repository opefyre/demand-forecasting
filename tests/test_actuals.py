from copy import deepcopy
from datetime import date
from pathlib import Path
import json
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
import app.main as main
from app.actuals import ActualsStore, evaluate_actuals, score, export_actuals
from app.datasets import DatasetStore
from app.inventory import raw_table
from app.monitoring import build_monitoring, comparison_key
from app.forecast_engine import _metric_bundle
import numpy as np


class ActualsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sources = DatasetStore(self.root / 'inputs')
        self.store = ActualsStore(self.root / 'actuals.sqlite3', self.sources)
        self.content = b'Item,Period,Quantity\n001,2026-01-01,100\n002,2026-01-01,200\n001,2026-02-01,150\n002,2026-02-01,0\n'
        self.source = self.sources.upload('actuals.csv', self.content, 'actuals')
        self.config = {'source_id': self.source['id'], 'mapping': {'item_id': 'A', 'timestamp': 'B', 'actual': 'C'}, 'unit': 'pieces',
                       'closed_through': '2026-02-28', 'classification': 'user_provided', 'reviewed': True, 'owner': 'Planner'}
        self.run = {'run_id': 'test', 'issued_at': '2025-12-20T12:00:00+00:00', 'site': {'id': 'tehran', 'timezone': 'Asia/Tehran'},
                    'unit': 'pieces', 'source_classification': 'user_provided', 'run_settings': {'frequency': 'monthly'},
                    'metadata': {'001': {'category': 'A', 'customer': 'Factory'}, '002': {'category': 'B', 'customer': 'Factory'}},
                    'series': {'001': {'forecast': [{'timestamp': '2026-01-01', 'mean': 110}, {'timestamp': '2026-02-01', 'mean': 120}]},
                               '002': {'forecast': [{'timestamp': '2026-01-01', 'mean': 190}, {'timestamp': '2026-02-01', 'mean': 10}]}}}
        self.plan = {'id': 'plan', 'name': 'Approved', 'run_id': 'test', 'status': 'approved', 'updated_at': '2025-12-22',
                     'history': [{'status': 'approved', 'at': '2025-12-22T12:00:00+00:00'}],
                     'overrides': [{'item_id': '001', 'period': '2026-02-01', 'value': 150}]}

    def tearDown(self):
        self.store.engine.dispose()
        self.tmp.cleanup()

    def evaluate(self, content=None, config=None, run=None, plan=None):
        return evaluate_actuals(run or self.run, raw_table('actuals.csv', content or self.content), config or self.config, plan, today=date(2026, 9, 21))

    def test_weighted_metrics_and_breakdowns_reconcile(self):
        result = self.evaluate(plan=self.plan)
        self.assertEqual(result['diagnostic']['actual_total'], 450)
        self.assertEqual(result['diagnostic']['absolute_error'], 60)
        self.assertAlmostEqual(result['diagnostic']['wape_pct'], 60 / 450 * 100)
        self.assertAlmostEqual(result['diagnostic']['bias_pct'], -20 / 450 * 100)
        self.assertAlmostEqual(result['improvement_points'], 30 / 450 * 100)
        for rows in result['breakdowns'].values():
            self.assertEqual(sum(r['actual_total'] for r in rows), 450)
            self.assertEqual(sum(r['absolute_error'] for r in rows), 60)
        self.assertEqual(result['rows'][0]['item_id'], '001')
        self.assertEqual(result['rows'][0]['source_cell'], 'C2')
        self.assertEqual(self.run['series']['001']['forecast'][1]['mean'], 120)

    def test_duplicates_unknown_items_and_invalid_quantities_are_blocking(self):
        for line in (b'001,2026-01-01,100', b'wrong,2026-01-01,100', b'001,2026-03-01,100'):
            self.assertEqual(self.evaluate(self.content + line + b'\n')['issue_count'], 1)
        for value in ('', '-1', 'NaN', 'inf', '#VALUE!'):
            content = f'Item,Period,Quantity\n001,2026-01-01,{value}\n'.encode()
            self.assertEqual(self.evaluate(content)['issue_count'], 1)
        bad_dates = b'Item,Period,Quantity\n001,01/02/2026,100\n001,46000,100\n'
        self.assertEqual(self.evaluate(bad_dates)['issue_count'], 2)

    def test_partial_coverage_is_explicit_and_needs_confirmation(self):
        partial = self.sources.upload('partial.csv', b'Item,Period,Quantity\n001,2026-01-01,0\n', 'actuals')
        config = {**self.config, 'source_id': partial['id']}
        report = self.store.inspect(config, self.run)
        self.assertEqual(report['coverage']['missing'], 3)
        self.assertEqual(report['coverage']['pct'], 25)
        self.assertIsNone(report['diagnostic']['wape_pct'])
        self.assertEqual(report['diagnostic']['mae'], 110)
        with self.assertRaisesRegex(ValueError, 'partial comparison'):
            self.store.save(config, self.run)
        saved = self.store.save({**config, 'accept_partial': True}, self.run)
        self.assertEqual(saved['diagnostic']['observations'], 1)

    def test_closed_periods_units_and_sample_class_are_enforced(self):
        for config in ({'closed_through': '2026-09-30'}, {'closed_through': '2026-02-15'}, {'closed_through': ''},
                       {'unit': 'boxes'}, {'classification': 'synthetic_sample'}):
            with self.assertRaises(ValueError):
                self.evaluate(config={**self.config, **config})

    def test_late_and_undated_forecasts_do_not_claim_prospective_accuracy(self):
        for issued, expected in [(None, 0), ('2026-01-15T00:00:00+00:00', 2), ('2026-02-01T00:00:00+00:00', 0)]:
            result = self.evaluate(run={**self.run, 'issued_at': issued}, plan=self.plan)
            self.assertEqual(result['prospective']['observations'], expected)
            self.assertEqual(result['paired_baseline']['observations'], expected)
            self.assertEqual(result['diagnostic']['observations'], 4)

    def test_approval_must_predate_each_period_and_reapproval_resets_eligibility(self):
        plan = deepcopy(self.plan)
        plan['history'].append({'status': 'approved', 'at': '2026-01-15T00:00:00+00:00'})
        report = self.evaluate(plan=plan)
        self.assertEqual(report['paired_baseline']['observations'], 2)
        plan['history'] = []
        self.assertIsNone(self.evaluate(plan=plan)['improvement_points'])
        plan['status'] = 'draft'
        with self.assertRaisesRegex(ValueError, 'approved'):
            self.evaluate(plan=plan)

    def test_timezone_boundary_uses_site_local_date(self):
        run = {**self.run, 'issued_at': '2025-12-31T22:00:00+00:00'}
        self.assertEqual(self.evaluate(run=run)['prospective']['observations'], 2)

    def test_saved_versions_survive_restart_and_cannot_mutate_baseline(self):
        original = deepcopy(self.run)
        first = self.store.save(self.config, self.run, self.plan)
        second = self.store.save(self.config, self.run)
        self.assertNotEqual(first['id'], second['id'])
        self.plan['overrides'][0]['value'] = 0
        restored = ActualsStore(self.root / 'actuals.sqlite3', self.sources)
        self.assertEqual(restored.get(first['id']), first)
        self.assertEqual(len(restored.list('test')), 2)
        self.assertEqual(self.run, original)
        self.assertEqual(len(first['run_sha256']), 64)
        restored.engine.dispose()

    def test_weekly_and_daily_end_dates(self):
        run = deepcopy(self.run)
        run['series'] = {'001': {'forecast': [{'timestamp': '2026-01-05', 'mean': 3}]}}
        content = b'Item,Period,Quantity\n001,2026-01-05,2\n'
        for frequency, end in [('weekly', '2026-01-11'), ('daily', '2026-01-05')]:
            run['run_settings']['frequency'] = frequency
            report = self.evaluate(content, {**self.config, 'closed_through': end}, run)
            self.assertEqual(report['diagnostic']['absolute_error'], 1)

    def test_persian_month_actuals_and_digits_keep_real_boundaries(self):
        from persiantools.jdatetime import JalaliDate
        run=deepcopy(self.run)
        run['run_settings']['calendar_profile']={'month_basis':'jalali'}
        start=JalaliDate(1403,12,1).to_gregorian().isoformat()
        end=JalaliDate(1403,12,30).to_gregorian().isoformat()
        run['series']={'001':{'forecast':[{'timestamp':start,'mean':110}]}}
        content='Item,Period,Quantity\n001,۱۴۰۳/۱۲/۰۱,۱۰۰\n'.encode()
        report=self.evaluate(content,{**self.config,'calendar':'jalali','closed_through':end},run)
        self.assertEqual(report['issue_count'],0)
        self.assertEqual(report['diagnostic']['absolute_error'],10)
        self.assertEqual(report['rows'][0]['period_label'],'1403-12')
        self.assertIn(b'1403-12',export_actuals({**report,'id':'test-comparison'}))
        with self.assertRaisesRegex(ValueError,'No forecast period|partially completed'):
            self.evaluate(content,{**self.config,'calendar':'jalali','closed_through':end[:8]+'19'},run)

    def test_no_arbitrary_plan_and_api_uses_reviewed_snapshots(self):
        with patch.object(main, 'DATASET_STORE', self.sources), patch.object(main, 'ACTUALS_STORE', self.store), patch.object(main, '_load_run', return_value=self.run), TestClient(main.app) as client:
            review = client.post('/api/actuals/test/review', json=self.config)
            self.assertEqual(review.status_code, 200, review.text)
            self.assertIsNone(review.json()['plan'])
            saved = client.post('/api/actuals/test', json=self.config)
            self.assertEqual(saved.status_code, 200, saved.text)
            key = saved.json()['id']
            self.assertEqual(client.get(f'/api/actual-results/{key}').json()['diagnostic']['absolute_error'], 60)
            self.assertEqual(len(client.get('/api/actuals/test').json()['evaluations']), 1)
            legacy = client.post('/api/fva/test', files={'actuals_file': ('actual.csv', self.content)})
            self.assertEqual(legacy.status_code, 410)

    def test_actual_sources_do_not_enter_training(self):
        with self.assertRaisesRegex(ValueError, 'wrong role'):
            self.sources.inspect({'history': self.source['id']}, {})

    def test_export_keeps_exact_evidence_and_neutralizes_spreadsheet_formulas(self):
        report = self.store.save(self.config, self.run)
        report['rows'][0]['item_id'] = '=HYPERLINK("unsafe")'
        payload = export_actuals(report).decode('utf-8-sig')
        self.assertIn("'=HYPERLINK", payload)
        self.assertIn('source_cell', payload)
        self.assertIn('C2', payload)
        self.assertIn('prospective', payload)

    def test_large_totals_fail_clearly_instead_of_producing_infinity(self):
        with self.assertRaisesRegex(ValueError, 'totals are too large'):
            score([{'actual': 1e308, 'forecast': 1e308}] * 3)

    def test_network_retry_reuses_the_saved_version(self):
        config = {**self.config, 'request_id': str(uuid.uuid4())}
        first = self.store.save(config, self.run)
        self.assertEqual(self.store.save(config, self.run), first)
        self.assertEqual(len(self.store.list('test')), 1)
        with self.assertRaisesRegex(ValueError, 'different inputs'):
            self.store.save({**config, 'owner': 'Changed reviewer'}, self.run)

    def test_historical_zero_demand_does_not_label_unit_error_as_a_percentage(self):
        metrics = _metric_bundle(np.array([0., 0.]), np.array([2., 0.]))
        self.assertIsNone(metrics['wape_pct'])
        self.assertIsNone(metrics['bias_pct'])
        self.assertEqual(metrics['mae'], 1)

    def test_monitor_only_compares_matching_evidence_not_other_runs(self):
        current = deepcopy(self.run)
        current['metrics'] = {'evaluation_signature': 'same-periods-values-steps', 'requested_horizon': 2, 'evaluation_type': 'reserved_confirmation_window', 'wape_pct': 10}
        previous = deepcopy(current)
        previous['run_id'] = 'older'
        previous['metrics']['wape_pct'] = 7
        p = self.root / 'older'
        p.mkdir()
        (p / 'result.json').write_text(json.dumps(previous))
        report = build_monitoring(self.root, current)
        self.assertEqual(report['comparison']['wape_change_points'], 3)
        self.assertIsNone(report['model_drift_wape_points'])
        self.assertIsNone(report['retrain']['recommended'])
        for field, value in [('unit', 'boxes'), ('source_classification', 'synthetic_sample'), ('site', {'id': 'other'})]:
            changed = {**current, field: value}
            self.assertIsNone(build_monitoring(self.root, changed)['comparison']['previous_run_id'])
        current['metrics'].pop('evaluation_signature')
        self.assertIsNone(comparison_key(current))


if __name__ == '__main__':
    unittest.main()

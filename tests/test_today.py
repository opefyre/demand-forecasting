from copy import deepcopy
from datetime import datetime
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
import app.main as main
from app.today import build_today


class TodayTests(unittest.TestCase):
    def setUp(self):
        self.site = {'id':'tehran', 'timezone':'Asia/Tehran'}
        self.run = {'run_id':'r1', 'site':self.site, 'source_classification':'synthetic_sample',
            'summary':{'end':'2026-08-01'}, 'run_settings':{'frequency':'monthly'}, 'unit':'tonnes',
            'metrics':{'wape_pct':5, 'independent_accuracy_verified':True, 'evidence_level':'strong'}}
        self.plan = {'id':'p1', 'run_id':'r1', 'site_id':'tehran', 'name':'Reviewed plan', 'owner':'A',
            'status':'review', 'settings':{'source_classification':'synthetic_sample'},
            'history':[{'at':'2026-09-15', 'actor':'A', 'note':'Submitted'}]}
        self.op = {'source':'uploaded', 'materials':[
            {'material_id':'pulp', 'material_name':'Pulp', 'period':'2026-10-01', 'shortage':30, 'unit':'kg', 'status':'shortage'},
            {'material_id':'pulp', 'material_name':'Pulp', 'period':'2026-09-01', 'shortage':10, 'unit':'kg', 'status':'shortage'}],
            'capacity':[{'production_line':'Line A', 'period':'2026-10-01', 'gap_quantity':-8, 'capacity_unit':'hours', 'status':'bottleneck'}]}

    def build(self, **kwargs):
        return build_today(self.run, [self.plan], self.site, now=datetime(2026,9,21), **kwargs)

    def test_empty_workspace_has_one_working_import_action(self):
        result = build_today(None, [], self.site)
        self.assertIsNone(result['context'])
        self.assertEqual(result['metrics'], {})
        self.assertEqual(result['decisions'][0]['action'], {'page':'data', 'import':True})

    def test_risks_distinct_and_earliest_period_actions_preserve_quantity(self):
        result = self.build(operations=self.op)
        self.assertEqual(result['metrics']['materials_at_risk'],1)
        self.assertEqual(result['metrics']['constrained_lines'],1)
        row = next(d for d in result['decisions'] if d['id']=='materials:pulp')
        self.assertEqual(row['affected_periods'],2)
        self.assertEqual(row['action'],{'page':'supply','tab':'materials','period':'2026-09-01','search':'Pulp'})
        self.assertIn('10.0 kg',row['detail'])
        self.assertEqual(result['decisions'][0]['id'],'review:p1')

    def test_missing_checks_not_zero_and_no_selection_only_accuracy_claim(self):
        self.run['metrics']['independent_accuracy_verified'] = False
        result = self.build()
        self.assertIsNone(result['metrics']['historical_error_pct'])
        self.assertIsNone(result['metrics']['materials_at_risk'])
        self.assertIn('evidence', [d['id'] for d in result['decisions']])
        result = self.build(operations={'source':'uploaded', 'materials':[], 'capacity':[]})
        self.assertIsNone(result['metrics']['constrained_lines'])
        self.assertIn('missing:capacity',[d['id'] for d in result['decisions']])

    def test_other_run_site_and_sample_records_cannot_enter_review_or_activity(self):
        variants = [{**self.plan,'run_id':'r2'}, {**self.plan,'site_id':'other'},
                    {**self.plan,'settings':{'source_classification':'user_provided'}}]
        result = build_today(self.run,variants,self.site)
        self.assertEqual(result['activity'],[])
        self.assertFalse(any(d['id'].startswith('review:') for d in result['decisions']))
        with self.assertRaises(ValueError): build_today(self.run, [self.plan], {'id':'other'})

    def test_monthly_freshness_counts_completed_months_not_upload_date(self):
        self.assertNotIn('history',[d['id'] for d in self.build()['decisions']])
        self.run['summary']['end'] = '2026-06-01'
        self.run['issued_at'] = '2026-09-21'
        row = next(d for d in self.build()['decisions'] if d['id']=='history')
        self.assertIn('2 completed months',row['title'])

    def test_diagnostics_are_suspicions_and_open_exact_item(self):
        self.run['series_diagnostics'] = {'A':{'stockout_or_lost_sales_suspected':True}}
        row = next(d for d in self.build()['decisions'] if d['id']=='pattern:A')
        self.assertIn('not confirmed',row['detail'])
        self.assertEqual(row['action']['item'],'A')

    def test_draft_and_mismatched_basis_rejected(self):
        with self.assertRaises(ValueError): self.build(plan=self.plan)
        with self.assertRaises(ValueError): self.build(plan={**self.plan,'id':'other','status':'approved'})

    def test_api_uses_verified_plan_supply_and_does_not_fallback_on_failure(self):
        plan = {**self.plan,'status':'approved'}
        with patch.object(main,'SITE_PROFILE',self.site), patch.object(main,'_load_run',return_value=self.run), \
             patch.object(main.PLAN_STORE,'list',return_value=[plan]), patch.object(main.PLAN_STORE,'get',return_value=plan), \
             patch.object(main,'_plan_output',return_value=(plan,[],self.op)) as output, TestClient(main.app) as client:
            response = client.get('/api/today?run_id=r1&plan_id=p1')
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['context']['plan_id'],'p1')
            output.assert_called_once_with('p1',supply=True)
            output.side_effect=ValueError('Source changed')
            result=client.get('/api/today?run_id=r1&plan_id=p1').json()
            self.assertIsNone(result['metrics']['materials_at_risk'])
            self.assertIn('Source changed',[d['detail'] for d in result['decisions']])
            self.assertEqual(client.get('/api/today?plan_id=p1').status_code,400)


if __name__ == '__main__': unittest.main()

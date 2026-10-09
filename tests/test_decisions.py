from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from app.decisions import DecisionStore, DecisionConflict


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'decisions.sqlite3'
        self.store=DecisionStore(self.path)
        self.evidence={'date':'2026-09-21','site':{'id':'tehran'},
            'context':{'run_id':'r1','plan_id':None,'unit':'tonnes','frequency':'monthly','source_classification':'synthetic_sample'},
            'metrics':{'materials_at_risk':1},'decisions':[{'id':'materials:pulp','kind':'materials',
                'title':'Pulp','detail':'10.0 tonnes below target','source_signature':'exact-10.01',
                'action':{'page':'supply','tab':'materials'}}]}

    def tearDown(self): self.temp.cleanup()

    def current(self): return self.store.decorate(deepcopy(self.evidence))

    def save(self, today=None, **changes):
        today=today or self.current(); d=today['decisions'][0]
        values=dict(evidence_token=d['evidence_token'],version=d['tracking']['version'],owner='Sample planner',
            due_date='2026-09-20',status='in_progress',note='Check open orders',request_id='first')
        return self.store.update(today,d['id'],**{**values,**changes})

    def test_owner_due_history_and_restart_do_not_change_quantities(self):
        before=deepcopy(self.evidence)
        first=self.save()
        self.assertEqual(first['version'],1)
        reopened=DecisionStore(self.path).decorate(deepcopy(self.evidence))
        tracked=reopened['decisions'][0]['tracking']
        self.assertTrue(tracked['overdue'])
        self.assertEqual(tracked['owner'],'Sample planner')
        self.assertEqual(tracked['history'][0]['actor']['basis'],'local_session')
        self.assertEqual(reopened['metrics'],before['metrics'])
        self.assertEqual(self.evidence,before)

    def test_reviewed_and_reopened_remain_auditable(self):
        self.save(status='reviewed',identity={'name':'Verified planner','subject':'s1','issuer':'https://company','role':'planner'})
        self.assertFalse(self.current()['decisions'][0]['tracking']['overdue'])
        record=self.save(status='open',note='Recheck supplier delivery',request_id='second')
        self.assertEqual(len(record['history']),2)
        self.assertEqual(record['history'][0]['actor']['subject'],'s1')
        self.assertEqual(record['history'][0]['evidence']['source_signature'],'exact-10.01')
        self.assertTrue(self.current()['decisions'][0]['tracking']['overdue'])

    def test_changed_evidence_reopens_without_rewriting_prior_review(self):
        old=self.current(); self.save(old,status='reviewed')
        self.evidence['decisions'][0]['source_signature']='exact-10.02'
        new=self.current()['decisions'][0]
        self.assertEqual(new['tracking']['status'],'open')
        self.assertTrue(new['tracking']['evidence_changed'])
        self.assertEqual(new['tracking']['history'][0]['status'],'reviewed')
        with self.assertRaises(DecisionConflict):
            self.save(evidence_token=old['decisions'][0]['evidence_token'],request_id='stale-evidence')

    def test_context_isolates_site_run_plan_and_classification(self):
        self.save()
        for field,value in [('run_id','r2'),('plan_id','p1'),('source_classification','user_provided')]:
            altered=deepcopy(self.evidence); altered['context'][field]=value
            self.assertEqual(self.store.decorate(altered)['decisions'][0]['tracking']['version'],0)
        altered=deepcopy(self.evidence); altered['site']['id']='other'
        self.assertEqual(self.store.decorate(altered)['decisions'][0]['tracking']['version'],0)

    def test_retry_is_idempotent_and_concurrent_change_conflicts(self):
        today=self.current(); first=self.save(today)
        self.assertEqual(self.save(today),first)
        with self.assertRaises(DecisionConflict): self.save(today,note='Different note')
        current=self.current()
        def update(index):
            try: return self.save(current,note='Change '+str(index),request_id='parallel-'+str(index))
            except DecisionConflict: return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(update,range(2)))
        self.assertEqual(results.count('conflict'),1)
        self.assertEqual(len(self.current()['decisions'][0]['tracking']['history']),2)

    def test_invalid_fields_and_unavailable_decisions_fail(self):
        for values in ({'owner':''},{'due_date':'2026-02-30'},{'status':[]},{'note':''},{'version':True},{'request_id':''}):
            with self.subTest(values=values),self.assertRaises(ValueError): self.save(**values)
        empty={**self.evidence,'context':None}
        with self.assertRaises(ValueError): self.store.context(empty)
        self.assertEqual(self.store.decorate(empty),empty)

    def test_due_today_is_not_overdue(self):
        self.save(due_date='2026-09-21')
        self.assertFalse(self.current()['decisions'][0]['tracking']['overdue'])

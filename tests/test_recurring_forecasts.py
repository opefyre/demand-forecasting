"""Native monthly scheduling with real stores/engine, never provider calls."""
from copy import deepcopy
from datetime import datetime,timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from app.recurring_forecasts import RecurringForecasts,RecurringConfig,install_recurring_forecasts
from app.monthly_refresh import UpdateStep
from tests import test_monthly_refresh as fixtures


class RecurringTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.MonthlyTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.service=RecurringForecasts(self.f.root/'recurring.sqlite',self.f.service)
        self.body={'run_id':self.f.base['run_id'],'request_id':'monthly-config','day':1,'months':3,'method':'model:Last observed','enabled':True,'confirmed':True}
        self.config=self.service.save(self.f.actor,RecurringConfig(**self.body))
        self.now=datetime.now(timezone.utc)

    def check(self):return self.service.check(self.config['id'],self.f.actor,self.now)

    def test_confirmation_bounds_scope_idempotency_and_pause(self):
        self.assertEqual(self.config,self.service.save(self.f.actor,RecurringConfig(**self.body)))
        for changes in ({'confirmed':False},{'months':True},{'day':29},{'enabled':'true'},{'method':'made up'}):
            with self.assertRaises(ValueError):self.service.save(self.f.actor,RecurringConfig(**{**self.body,**changes,'request_id':'different-config'}))
        with self.assertRaises(ValueError):self.service.config(self.config['id'],'other-owner')
        self.service.save(self.f.actor,RecurringConfig(**{**self.body,'enabled':False,'request_id':'pause-config'}))
        self.assertEqual(self.check()['state'],'paused');self.f.submit.assert_not_called()

    def test_due_tehran_persian_and_gregorian_boundaries(self):
        cfg={**self.config,'day':5}
        with patch.object(self.service,'config',return_value=(self.f.actor,cfg)):
            result=self.service.check(cfg['id'],self.f.actor,datetime(2026,10,3,22,tzinfo=timezone.utc))
            self.assertEqual(result,{'state':'not_due','period':'2026-10'})
        cfg.update(basis='jalali',day=2)
        with patch.object(self.service,'config',return_value=(self.f.actor,cfg)):
            result=self.service.check(cfg['id'],self.f.actor,datetime(2026,3,20,22,tzinfo=timezone.utc))
            self.assertEqual(result,{'state':'not_due','period':'1405-01'})

    def test_real_draft_calculation_recovers_then_stops_at_factor_review(self):
        original=deepcopy(self.f.source);cycle=self.check()
        self.assertEqual(cycle['state'],'calculating',cycle);self.f.submit.assert_called_once()
        again=self.check();self.assertEqual(again['update_id'],cycle['update_id']);self.f.submit.assert_called_once()
        session=self.f.service.get(cycle['update_id'],self.f.actor);job=self.f.jobs.get(session['job_id']);owner=self.f.jobs.claim(job['id'])
        result=self.f.calculate(job['payload']['dataset_id'],method=job['payload']['method'])
        self.f.jobs.begin_publish(job['id'],owner,result['run_id']);self.f.jobs.finish(job['id'],owner,'succeeded')
        self.assertEqual(self.service.listing(self.f.actor)[0]['cycle']['state'],'review')
        final=self.check();self.assertEqual(final['stage'],'factors');self.assertEqual(final['state'],'review')
        session=self.f.service.get(cycle['update_id'],self.f.actor)
        self.assertEqual(session['stage'],'factors');self.assertNotIn('snapshot_id',session)
        self.assertEqual(self.f.datasets.get(original['id']),original)
        self.assertEqual(self.service.listing('wrong-owner'),[])

    def test_latest_reviewed_replacement_records_exact_history_changes(self):
        raw=self.f.history.replace(b',A,0001,10\n',b',A,0001,15\n')
        source=self.f.datasets.upload('updated.csv',raw,'history')
        updated=self.f.datasets.save('Updated synthetic sales',{'history':source['id']},self.f.source['settings'],'synthetic_sample',True,parent_dataset_id=self.f.source['id'])
        cycle=self.check();self.assertEqual(cycle['dataset_id'],updated['id'],cycle)
        self.assertEqual(cycle['changes']['changed_groups'],30);self.assertEqual(cycle['changes']['after_total']-cycle['changes']['before_total'],150)

    def test_missing_latest_period_in_one_series_is_not_zero_sales(self):
        lines=self.f.history.splitlines();raw=b'\n'.join(lines[:-1])+b'\n'
        file=self.f.datasets.upload('missing.csv',raw,'history')
        self.f.datasets.save('Missing B final month',{'history':file['id']},self.f.source['settings'],'synthetic_sample',True,parent_dataset_id=self.f.source['id'])
        cycle=self.check();self.assertEqual(cycle['state'],'attention');self.assertIn('no latest-month',cycle['attention']);self.f.submit.assert_not_called()

    def test_stale_history_changed_base_and_revoked_owner_block(self):
        with patch.object(self.service,'authorized',return_value=False):
            self.assertEqual(self.check()['state'],'attention');self.f.submit.assert_not_called()
        with patch.object(self.f.service,'baseline',return_value=({**self.f.base,'changed':True},self.f.source)):
            self.assertIn('Original forecast changed',self.check()['attention'])
        future=datetime(self.now.year+1,self.now.month,8,tzinfo=timezone.utc)
        self.assertIn('latest completed',self.service.check(self.config['id'],self.f.actor,future)['attention'])

    def test_restart_after_dispatch_before_cycle_publication_recovers_one_job(self):
        cycle=self.check()
        with self.service.db() as db:
            db.execute('DELETE FROM recurring_cycles WHERE id=?',(cycle['id'],))
        recovered=self.check();self.assertEqual(recovered['update_id'],cycle['update_id']);self.f.submit.assert_called_once()

    def test_stopped_job_is_attention_not_permanent_calculating(self):
        cycle=self.check();session=self.f.service.get(cycle['update_id'],self.f.actor)
        self.f.jobs.cancel(session['job_id'])
        checked=self.check();self.assertEqual(checked['state'],'attention')
        self.assertIn('stopped',checked['attention'])
        self.assertEqual(self.service.listing(self.f.actor)[0]['cycle']['state'],'attention')
        self.f.submit.assert_called_once()

    def test_missing_update_does_not_break_other_schedules_or_recalculate(self):
        cycle=self.check()
        with patch.object(self.f.service,'get',side_effect=ValueError('Missing saved update.')):
            listed=self.service.listing(self.f.actor)
            self.assertEqual(listed[0]['cycle']['state'],'attention')
            self.assertEqual(self.check()['state'],'attention')
        self.f.submit.assert_called_once()

    def test_connected_unreviewed_or_failed_history_never_calculates(self):
        folders=MagicMock();folders.get_config.return_value={'dataset_id':self.f.source['id'],'files':{'history':'sales.csv'}}
        self.service.folders=folders
        config=self.service.save(self.f.actor,RecurringConfig(**{**self.body,'connection_id':'connection','request_id':'with-connection'}))
        folders.list.return_value=[{'id':'connection','checks':[{'state':'ready','id':'candidate'}]}]
        folders.candidate.return_value={'accepted_dataset_id':None}
        self.assertIn('needs review',self.check()['attention']);self.f.submit.assert_not_called()
        folders.list.return_value[0]['checks'][0]['state']='failed'
        self.assertIn('connection needs attention',self.check()['attention']);self.f.submit.assert_not_called()

    def test_routes_owner_and_scheduler_registration(self):
        app=FastAPI();scheduler=MagicMock()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal={'issuer':'test','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_recurring_forecasts(app,self.service,scheduler)
        with TestClient(app) as client:
            scheduler.add_job.assert_called_once()
            self.assertEqual(client.get('/api/recurring-forecasts').json()['schedules'][0]['id'],self.config['id'])
            self.assertEqual(client.post('/api/recurring-forecasts/'+self.config['id']+'/check',headers={'actor':'bob'}).status_code,400)
            self.assertEqual(client.post('/api/recurring-forecasts',json={**self.body,'confirmed':False}).status_code,400)

if __name__=='__main__':unittest.main()

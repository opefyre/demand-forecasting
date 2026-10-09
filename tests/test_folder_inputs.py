import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from app.datasets import DatasetStore
from app.folder_inputs import FolderInputs


class FolderInputTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.exports = self.root/'exports'
        self.exports.mkdir()
        self.datasets = DatasetStore(self.root/'datasets')
        self.payload = b'date,qty\n2025-01-01,10\n2025-02-01,20\n2025-03-01,30\n2025-04-01,40\n2025-05-01,50\n2025-06-01,60\n'
        source = self.datasets.upload('history.csv',self.payload,'history')
        self.template = self.datasets.save('Template',{'history':source['id']},
            {'date_col':'date','target_col':'qty','unit':'units','frequency':'monthly','horizon':1},accept_warnings=True)
        self.store = FolderInputs(self.root/'folders.sqlite3',self.datasets,[self.exports])
        self.config = dict(name='Monthly export',path=str(self.exports),dataset_id=self.template['id'],
            files={'history':'history.csv'},minutes=15,confirmed_local_access=True)
        self.write(self.payload)

    def tearDown(self): self.temp.cleanup()

    def write(self, payload):
        path = self.exports/'history.csv'
        path.write_bytes(payload)
        os.utime(path,(time.time()-5,time.time()-5))

    def test_ingests_changed_bytes_once_and_keeps_history(self):
        connector = self.store.create(self.config)
        first = self.store.check(connector['id'])
        self.assertEqual(first['state'],'ready')
        self.assertEqual(first['review']['summary']['rows'],6)
        second = self.store.check(connector['id'])
        self.assertEqual(second['state'],'unchanged')
        self.assertEqual(second['candidate_id'],first['id'])
        self.write(self.payload+b'2025-07-01,70\n')
        third = self.store.check(connector['id'])
        self.assertEqual(third['state'],'ready')
        self.assertEqual(third['review']['forecast_start'],'2025-08-01')
        self.assertEqual(len(self.datasets.list()),1)  # No automatic accepted dataset.
        self.assertEqual(self.datasets.get(self.template['id']),self.template)
        self.assertEqual(len(self.store.list()[0]['checks']),3)

    def accepted_candidate(self):
        connector=self.store.create(self.config)
        candidate=self.store.check(connector['id'])
        saved=self.store.accept(candidate['id'],name='Reviewed refresh',sources=candidate['sources'],
            settings=candidate['settings'],classification=candidate['classification'],accept_warnings=True,
            parent_dataset_id=candidate['parent_dataset_id'])
        return candidate,saved

    def test_draft_requires_review_and_current_successful_refresh(self):
        connector=self.store.create(self.config)
        unreviewed=self.store.check(connector['id'])
        with self.assertRaisesRegex(ValueError,'Review and save'):
            self.store.draft_dataset(unreviewed['id'])
        candidate,saved=self.accepted_candidate()
        self.assertEqual(self.store.draft_dataset(candidate['id']),saved)
        self.write(self.payload+b'2025-07-01,70\n')
        with self.assertRaisesRegex(ValueError,'New file contents'):
            self.store.draft_dataset(candidate['id'])
        self.assertEqual(self.datasets.get(saved['id']),saved)
        self.write(b'date,qty\n2025-01-01,-5\n')
        with self.assertRaisesRegex(ValueError,'Refresh failed'):
            self.store.draft_dataset(candidate['id'])

    def test_scheduled_drafts_are_opt_in_reviewed_and_paused(self):
        from unittest.mock import Mock
        candidate,saved=self.accepted_candidate()
        key=candidate['connector_id']
        submit=Mock(return_value={'id':'draft-job'})
        self.store.scheduled_check(key,submit)
        submit.assert_not_called()
        self.store.set_auto_draft(key,True)
        result=self.store.scheduled_check(key,submit)
        submit.assert_called_once_with(saved['id'],candidate['id'])
        self.assertEqual(result['draft_job_id'],'draft-job')
        reopened=FolderInputs(self.root/'folders.sqlite3',self.datasets,[self.exports])
        self.assertTrue(reopened.get_config(key)['auto_draft'])
        self.assertTrue(any(c.get('draft_job_id')=='draft-job' for c in reopened.list()[0]['checks']))
        submit.reset_mock()
        self.store.set_enabled(key,False)
        self.assertIsNone(self.store.scheduled_check(key,submit))
        self.store.set_enabled(key,True)
        self.write(self.payload+b'2025-07-01,70\n')
        self.assertIn('need review',self.store.scheduled_check(key,submit)['draft_message'])
        self.assertIn('need review',self.store.scheduled_check(key,submit)['draft_message'])
        submit.assert_not_called()

    def test_scheduled_draft_configuration_validation_and_failure(self):
        from unittest.mock import Mock
        manual=self.store.create({**self.config,'minutes':0})
        with self.assertRaisesRegex(ValueError,'scheduled connection'):
            self.store.set_auto_draft(manual['id'],True)
        with self.assertRaises(ValueError): self.store.set_auto_draft(manual['id'],'yes')
        candidate,saved=self.accepted_candidate()
        key=candidate['connector_id']
        self.store.set_auto_draft(key,True)
        result=self.store.scheduled_check(key,Mock(side_effect=RuntimeError('private details')))
        self.assertIn('could not start',result['draft_message'])
        self.assertNotIn('private details',str(result))
        self.write(b'date,qty\n2025-01-01,-5\n')
        submit=Mock()
        self.assertIn('fix the input error',self.store.scheduled_check(key,submit)['draft_message'])
        submit.assert_not_called()

    def test_draft_endpoint_retries_reuse_pinned_job(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app import main
        from app.jobs import JobStore
        candidate,saved=self.accepted_candidate()
        ledger=JobStore(self.root/'jobs.sqlite3',self.root/'runs')
        self.addCleanup(ledger.close)
        with patch.object(main,'FOLDER_INPUTS',self.store),patch.object(main,'DATASET_STORE',self.datasets), \
             patch.object(main.jobs,'submit',side_effect=ledger.create),TestClient(main.app) as client:
            url=f"/api/integrations/folders/candidates/{candidate['id']}/forecast"
            first=client.post(url,json={})
            self.assertEqual(first.status_code,202,first.text)
            second=client.post(url,json={})
            self.assertEqual(second.status_code,202,second.text)
            self.assertEqual(first.json()['id'],second.json()['id'])
            self.assertEqual(first.json()['payload']['dataset_id'],saved['id'])
            self.assertEqual(len(ledger.list()),1)
            self.store.set_auto_draft(candidate['connector_id'],True)
            scheduled=main.scheduled_folder_check(candidate['connector_id'])
            self.assertEqual(scheduled['draft_job_id'],first.json()['id'])
            self.assertEqual(len(ledger.list()),1)
            self.write(self.payload+b'2025-07-01,70\n')
            blocked=client.post(url,json={})
            self.assertEqual(blocked.status_code,400,blocked.text)
            self.assertEqual(len(ledger.list()),1)

    def test_invalid_export_is_logged_without_replacing_good_candidate(self):
        connector = self.store.create(self.config)
        good = self.store.check(connector['id'])
        self.write(b'date,qty\n2025-01-01,-5\n')
        bad = self.store.check(connector['id'])
        self.assertEqual(bad['state'],'failed')
        self.assertIn('negative',bad['message'])
        self.assertEqual(self.store.candidate(good['id'])['sources'],good['sources'])
        self.assertEqual(len(self.datasets.list()),1)

    def test_boundaries_consent_and_exact_filenames(self):
        for patch in ({'confirmed_local_access':False},{'path':str(self.root)},
                      {'files':{'history':'../history.csv'}},{'files':{'history':'*.csv'}},
                      {'files':{'future':'history.csv'}},{'minutes':1}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                self.store.create({**self.config,**patch})

    def test_linked_missing_and_unsettled_files_fail(self):
        connector = self.store.create(self.config)
        file = self.exports/'history.csv'
        file.unlink()
        self.assertEqual(self.store.check(connector['id'])['state'],'failed')
        outside=self.root/'outside.csv'; outside.write_bytes(self.payload)
        file.symlink_to(outside)
        self.assertIn('linked',self.store.check(connector['id'])['message'])
        file.unlink(); file.write_bytes(self.payload)
        self.assertIn('still being written',self.store.check(connector['id'])['message'])

    def test_concurrent_checks_and_restart_reuse_candidate(self):
        config = self.store.create(self.config)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _:self.store.check(config['id']), range(2)))
        self.assertEqual(sorted(r['state'] for r in results),['ready','unchanged'])
        reopened = FolderInputs(self.root/'folders.sqlite3',self.datasets,[self.exports])
        self.assertEqual(reopened.check(config['id'])['state'],'unchanged')
        self.assertFalse(reopened.set_enabled(config['id'],False)['enabled'])

    def test_review_provenance_requires_exact_sources_and_parent(self):
        config=self.store.create(self.config); candidate=self.store.check(config['id'])
        provenance=self.store.verify_candidate(candidate['id'],candidate['sources'],self.template['id'])
        saved=self.datasets.save('Reviewed export',candidate['sources'],candidate['settings'],
            accept_warnings=True,parent_dataset_id=self.template['id'],import_provenance=provenance)
        self.assertEqual(saved['import_provenance']['files']['history']['name'],'history.csv')
        self.store.mark_saved(candidate['id'],saved['id'])
        self.assertEqual(self.store.list()[0]['accepted_dataset_id'],saved['id'])
        with self.assertRaises(ValueError):
            self.store.verify_candidate(candidate['id'],self.template['sources'],self.template['id'])

    def test_scheduler_runs_configured_check_and_pause_removes_job(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from datetime import datetime, timezone
        from threading import Event
        from types import SimpleNamespace
        from unittest.mock import patch
        from app import main
        completed = Event()
        config = self.store.create(self.config)
        scheduler = BackgroundScheduler()
        scheduler.start()
        original = self.store.check
        def observe(key):
            try: return original(key)
            finally: completed.set()
        try:
            with patch.object(main,'FOLDER_INPUTS',self.store), patch.object(main,'INTEGRATION_STORE',SimpleNamespace(scheduler=scheduler)), patch.object(self.store,'check',side_effect=observe):
                main.schedule_folder(config)
                job = scheduler.get_job('folder-input-'+config['id'])
                self.assertEqual(job.max_instances,1)
                job.modify(next_run_time=datetime.now(timezone.utc))
                self.assertTrue(completed.wait(3))
                self.assertEqual(self.store.list()[0]['checks'][0]['state'],'ready')
                main.schedule_folder(self.store.set_enabled(config['id'],False))
                self.assertIsNone(scheduler.get_job(job.id))
        finally: scheduler.shutdown()

    def test_acceptance_recovers_stop_between_dataset_and_acknowledgment(self):
        from unittest.mock import patch
        config=self.store.create(self.config); candidate=self.store.check(config['id'])
        values=dict(name='Reviewed',sources=candidate['sources'],settings=candidate['settings'],
                    classification=candidate['classification'],accept_warnings=True,parent_dataset_id=self.template['id'])
        with patch.object(self.store,'_record_acceptance',side_effect=RuntimeError('simulated stop')):
            with self.assertRaisesRegex(RuntimeError,'simulated stop'):
                self.store.accept(candidate['id'],**values)
        self.assertEqual(len(self.datasets.list()),2)
        self.assertNotIn('accepted_dataset_id',self.store.candidate(candidate['id']))
        reopened=FolderInputs(self.root/'folders.sqlite3',self.datasets,[self.exports])
        saved=reopened.accept(candidate['id'],**values)
        self.assertEqual(len(self.datasets.list()),2)
        self.assertEqual(reopened.accept(candidate['id'],**values),saved)
        self.assertEqual(reopened.candidate(candidate['id'])['accepted_dataset_id'],saved['id'])
        with self.assertRaisesRegex(ValueError,'already saved'):
            reopened.accept(candidate['id'],**{**values,'name':'Different decision'})

    def test_concurrent_acceptance_creates_one_version(self):
        config=self.store.create(self.config); candidate=self.store.check(config['id'])
        values=dict(name='Reviewed',sources=candidate['sources'],settings=candidate['settings'],
                    classification=candidate['classification'],accept_warnings=True,parent_dataset_id=self.template['id'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows=list(pool.map(lambda _:self.store.accept(candidate['id'],**values),range(2)))
        self.assertEqual(rows[0],rows[1])
        self.assertEqual(len(self.datasets.list()),2)

from copy import deepcopy
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

from app.factor_folders import FactorFolders, install_factor_folders
from app.factor_imports import review_import, save_import
from tests import test_factor_links as fixture_module


class FactorFolderTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.FactorLinkTests();self.fixture.setUp()
        f=self.fixture
        self.root,self.datasets,self.factors,self.base=f.root,f.store,f.factors,f.snapshot
        self.export=self.root/'exports';self.export.mkdir()
        self.file=self.export/'factor.csv'
        self.write([{**r,'value':r['value']+1} for r in f.factor_rows])
        self.store=FactorFolders(self.root/'factor-folders.sqlite3',self.datasets,[self.export],self.factors)
        self.config={'path':str(self.export),'filename':'factor.csv','minutes':15,'confirmed_local_access':True}
        self.connection=self.store.configure(self.base['id'],self.config)

    def tearDown(self):self.fixture.tearDown()

    def write(self,rows):
        self.file.write_text(pd.DataFrame(rows).to_csv(index=False))
        os.utime(self.file,(time.time()-5,)*2)

    def review(self):
        reviewed=self.store.review(self.base['id'])
        return reviewed,{'candidate_id':reviewed['candidate_id'],'review_token':reviewed['review']['review_token'],'reviewed':True}

    def test_refresh_review_accept_keeps_contract_and_original_and_retries(self):
        self.write([{**r,'value':r['value']+10} for r in self.fixture.factor_rows])
        review,payload=self.review()
        self.assertEqual(review['review']['changes']['changed_values'],28)
        saved=self.store.accept(self.base['id'],payload)
        self.assertEqual(saved['factor_id'],self.base['factor_id'])
        self.assertEqual(saved['parent_id'],self.base['id'])
        self.assertEqual(saved['points'][0]['value'],self.base['points'][0]['value']+10)
        self.assertEqual(self.store.accept(self.base['id'],payload),saved)
        self.assertEqual(self.factors.get(self.base['id']),self.base)
        self.assertEqual(self.store.review(saved['id'])['saved']['id'],saved['id'])
        self.assertEqual(self.store.get_config(self.base['factor_id'])['snapshot_id'],saved['id'])
        self.assertEqual(len(self.factors.list()),2)

    def test_file_matching_accepted_version_does_not_create_another_version(self):
        self.write(self.fixture.factor_rows)
        self.assertEqual(self.store.check(self.base['factor_id'])['state'],'unchanged')
        self.assertEqual(self.store.review(self.base['id'])['saved']['id'],self.base['id'])
        self.assertEqual(len(self.factors.list()),1)

    def test_invalid_file_does_not_expose_prior_candidate_or_change_factor(self):
        review,payload=self.review()
        bad=deepcopy(self.fixture.factor_rows);bad[0]['value']='nan';self.write(bad)
        check=self.store.check(self.base['factor_id'])
        self.assertEqual(check['state'],'failed')
        self.assertEqual(check['issue_count'],1)
        with self.assertRaises(ValueError):self.store.accept(self.base['id'],payload)
        with self.assertRaises(ValueError):self.store.review(self.base['id'])
        self.assertEqual(self.factors.get(self.base['id']),self.base)
        self.assertEqual(len(self.factors.list()),1)

    def test_review_shows_changed_releases_before_unchanged_history(self):
        rows=deepcopy(self.fixture.factor_rows)
        rows[-2]['value']=175
        removed=rows.pop(0)
        self.write(rows)
        review,_=self.review();report=review['review']
        self.assertEqual(report['points'][0]['value'],175)
        self.assertEqual(report['points'][0]['previous_value'],126)
        self.assertEqual(report['changes']['changed_values'],1)
        self.assertEqual(report['changes']['removed_releases'],1)
        self.assertEqual(report['removed_releases'][0]['period'],removed['period'])

    def test_interrupted_acceptance_recovers_exact_saved_version_without_duplicate(self):
        _,payload=self.review()
        def interrupted(*args,**kwargs):
            save_import(*args,**kwargs)
            raise OSError('Simulated interruption after factor publication')
        with patch('app.factor_folders.save_import',side_effect=interrupted):
            with self.assertRaises(OSError):self.store.accept(self.base['id'],payload)
        self.assertEqual(len(self.factors.list()),2)
        saved=self.store.accept(self.base['id'],payload)
        self.assertEqual(len(self.factors.list()),2)
        self.assertEqual(self.store.accept(self.base['id'],payload),saved)
        self.assertEqual(self.store.get_config(self.base['factor_id'])['snapshot_id'],saved['id'])

    def test_file_changes_during_acceptance_cannot_publish_cached_values(self):
        _,payload=self.review();read=self.store._read_files;calls=0
        def changed(config):
            nonlocal calls
            calls+=1
            if calls==2:self.write([{**r,'value':r['value']+5} for r in self.fixture.factor_rows])
            return read(config)
        with patch.object(self.store,'_read_files',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'export changed'):self.store.accept(self.base['id'],payload)
        self.assertEqual(len(self.factors.list()),1)

    def test_changed_file_configuration_mapping_or_external_factor_blocks_old_review(self):
        _,payload=self.review()
        self.write([{**r,'value':r['value']+20} for r in self.fixture.factor_rows])
        with self.assertRaisesRegex(ValueError,'export changed'):self.store.accept(self.base['id'],payload)
        _,payload=self.review()
        self.store.configure(self.base['id'],self.config)
        with self.assertRaisesRegex(ValueError,'export changed|connection changed'):self.store.accept(self.base['id'],payload)
        self.write([{**r,'different_value':r['value']} for r in self.fixture.factor_rows])
        with self.assertRaisesRegex(ValueError,'headings changed'):self.store.review(self.base['id'])
        self.write([{**r,'value':r['value']+1} for r in self.fixture.factor_rows])
        _,payload=self.review()
        original=self.base['import_config']
        other={**original,'header_row':original.get('header_row') or 1,'parent_id':self.base['id']}
        checked=review_import(self.datasets,other)
        save_import(self.datasets,self.factors,{**other,'reviewed':True,'review_token':checked['review_token'],'request_id':str(uuid.uuid4())})
        with self.assertRaisesRegex(ValueError,'updated elsewhere'):self.store.accept(self.base['id'],payload)

    def test_safe_paths_permissions_files_stability_and_manual_pause(self):
        for patch in ({'path':str(self.root)},{'filename':'../factor.csv'},{'filename':'*.csv'},
                      {'confirmed_local_access':False},{'minutes':True}):
            with self.assertRaises((ValueError,OSError)):self.store.configure(self.base['id'],{**self.config,**patch})
        self.store.set_enabled(self.base['factor_id'],False)
        self.assertIsNone(self.store.scheduled_check(self.base['factor_id']))
        self.store.set_enabled(self.base['factor_id'],True)
        self.assertEqual(self.store.scheduled_check(self.base['factor_id'])['state'],'ready')
        self.assertEqual(len(self.factors.list()),1)
        os.utime(self.file,None)
        with self.assertRaisesRegex(ValueError,'still being written'):self.store.review(self.base['id'])
        os.utime(self.file,(time.time()-5,)*2)
        linked=self.export/'linked.csv';linked.symlink_to(self.file)
        self.store.configure(self.base['id'],{**self.config,'filename':'linked.csv'})
        with self.assertRaisesRegex(ValueError,'linked files'):self.store.review(self.base['id'])
        self.store.configure(self.base['id'],{**self.config,'minutes':0})
        with self.assertRaises(ValueError):self.store.set_enabled(self.base['factor_id'],True)

    def test_restore_schedule_and_api_review_save_reject_old_tokens(self):
        app=FastAPI();scheduler=BackgroundScheduler()
        reopened=FactorFolders(self.store.path,self.datasets,[self.export],self.factors)
        install_factor_folders(app,reopened,scheduler)
        with TestClient(app) as client:
            self.assertIsNotNone(scheduler.get_job('factor-folder-'+self.base['factor_id']))
            url='/api/integrations/factor-folders/'+self.base['id']
            self.assertEqual(client.get(url).status_code,200)
            review=client.post(url+'/review',json={})
            self.assertEqual(review.status_code,200,review.text)
            payload={'candidate_id':review.json()['candidate_id'],'review_token':review.json()['review']['review_token'],'reviewed':True}
            self.assertEqual(client.post(url+'/accept',json={**payload,'review_token':'stale'}).status_code,400)
            saved=client.post(url+'/accept',json=payload)
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertNotIn('points',saved.json())
            self.assertEqual(client.post(url+'/accept',json=payload).json(),saved.json())
            self.assertEqual(client.post(url+'/enabled',json={'enabled':False}).status_code,200)
            self.assertIsNone(scheduler.get_job('factor-folder-'+self.base['factor_id']))
            self.assertEqual(client.post(url+'/enabled',json={'enabled':True}).status_code,200)
            self.assertIsNotNone(scheduler.get_job('factor-folder-'+self.base['factor_id']))
        self.assertEqual(len(self.factors.list()),2)

    def test_public_snapshot_and_nonlatest_snapshot_cannot_be_connected(self):
        public={**self.base,'id':uuid.uuid4().hex,'factor_id':'public','kind':'public_observations'}
        (self.factors.root/(public['id']+'.json')).write_text(__import__('json').dumps(public))
        with self.assertRaisesRegex(ValueError,'public-source'):self.store.configure(public['id'],self.config)
        review,payload=self.review();self.store.accept(self.base['id'],payload)
        with self.assertRaisesRegex(ValueError,'latest reviewed'):self.store.configure(self.base['id'],self.config)

    def test_accepted_factor_runs_reviewed_draft_through_existing_engine_and_export(self):
        import app.main as main
        self.write([{**r,'value':r['value']+10} for r in self.fixture.factor_rows])
        review,payload=self.review();saved=self.store.accept(self.base['id'],payload)
        runs=self.root/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.datasets),patch.object(main,'FACTOR_STORE',self.factors),patch.object(main,'RUNS_DIR',runs),TestClient(main.app) as client:
            baseline=client.post('/api/run-saved',json={'dataset_id':self.fixture.dataset['id']})
            self.assertEqual(baseline.status_code,200,baseline.text)
            run=baseline.json();url=f"/api/runs/{run['run_id']}/factor-links"
            inputs={'links':[{'snapshot_id':saved['id'],'lag_months':2,'future_value':160}]}
            preview=client.post(url+'/preview',json=inputs)
            self.assertEqual(preview.status_code,200,preview.text)
            dataset=client.post(url,json={**inputs,'reviewed':True,'review_token':preview.json()['review_token'],'request_id':str(uuid.uuid4())})
            self.assertEqual(dataset.status_code,200,dataset.text)
            forecast=client.post('/api/run-saved',json={'dataset_id':dataset.json()['id']})
            self.assertEqual(forecast.status_code,200,forecast.text)
            draft=forecast.json();self.assertTrue(draft['factor_validation']['available'])
            evidence=pd.read_excel(runs/draft['run_id']/'forecast_package.xlsx',sheet_name='Factor alignment')
            self.assertEqual(evidence.iloc[0]['value'],110)
            self.assertEqual(client.get(f"/api/runs/{run['run_id']}").json(),run)


if __name__=='__main__':unittest.main()

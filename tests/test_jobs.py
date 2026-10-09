from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main
from app import jobs
from app.datasets import DatasetStore
from app.jobs import JobStore, LEASE_SECONDS, execute_job
from app.runtime import ForecastCancelled, checkpoint, output_directory


class JobTests(unittest.TestCase):
    def test_owned_worker_detects_parent_loss_but_standalone_is_allowed(self):
        from app.worker import parent_is_current
        with patch('app.worker.os.getppid', return_value=123):
            self.assertTrue(parent_is_current(123))
            self.assertTrue(parent_is_current(None))
            self.assertFalse(parent_is_current(456))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = JobStore(self.root / 'jobs.db', self.root / 'runs')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def job(self, key='request-123'):
        return self.store.create({'dataset_id': 'dataset'}, 'Factory demand', key)

    def executor(self, payload):
        folder = output_directory(self.root / 'wrong') / 'testrun'
        folder.mkdir()
        (folder / 'forecast.csv').write_text('date,quantity\n2026-10-01,10\n')
        checkpoint('Preparing test result')
        return {'run_id': 'testrun', 'quantity': 10}

    def test_idempotency_and_restart_persistence(self):
        first = self.job()
        self.assertEqual(first['id'], self.job()['id'])
        with self.assertRaises(ValueError):
            self.store.create({'dataset_id': 'other'}, 'Other', 'request-123')
        second = JobStore(self.root / 'jobs.db', self.root / 'runs')
        self.assertEqual(second.queued(), [first['id']])
        second.close()
        for number in range(31):
            old = self.job(f'closed-{number}')
            self.store.cancel(old['id'])
        self.assertIn(first['id'], [job['id'] for job in self.store.list()])

    def test_two_workers_cannot_claim_or_publish_same_job_twice(self):
        job = self.job()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [pool.submit(execute_job, job['id'], self.store, self.executor) for _ in range(2)]
            for future in results:
                future.result()
        done = self.store.get(job['id'])
        self.assertEqual(done['state'], 'succeeded')
        saved = json.loads((self.root / 'runs/testrun/result.json').read_text())
        self.assertEqual(saved['job_id'], job['id'])
        self.assertEqual(len(list((self.root / 'runs').iterdir())), 1)

    def test_cancel_queued_and_running_never_publishes(self):
        job = self.job()
        self.store.cancel(job['id'])
        with patch.object(self, 'executor') as executor:
            execute_job(job['id'], self.store, executor)
            executor.assert_not_called()
        running = self.job('request-456')
        def cancel_inside(payload):
            self.store.cancel(running['id'])
            return self.executor(payload)
        execute_job(running['id'], self.store, cancel_inside)
        self.assertEqual(self.store.get(running['id'])['state'], 'cancelled')
        self.assertFalse((self.root / 'runs/testrun/result.json').exists())

    def test_failures_are_visible_and_do_not_publish_partial_files(self):
        job = self.job()
        def broken(payload):
            self.executor(payload)
            raise ValueError('Future exchange-rate values are missing.')
        with self.assertLogs('app.jobs', level='ERROR'):
            execute_job(job['id'], self.store, broken)
        result = self.store.get(job['id'])
        self.assertEqual(result['state'], 'failed')
        self.assertIn('missing', result['error'])
        self.assertFalse((self.root / 'runs/testrun').exists())

    def test_interrupted_claim_cannot_later_publish(self):
        job = self.job()
        owner = self.store.claim(job['id'])
        self.store.recover(time.time() + LEASE_SECONDS + 1)
        self.assertEqual(self.store.get(job['id'])['state'], 'interrupted')
        with self.assertRaises(ForecastCancelled):
            self.store.begin_publish(job['id'], owner, 'testrun')
        self.assertIsNone(self.store.claim(job['id']))

    def test_recovery_after_result_saved_before_ledger_commit(self):
        job = self.job()
        owner = self.store.claim(job['id'])
        self.store.begin_publish(job['id'], owner, 'testrun')
        folder = self.root / 'runs/testrun'
        folder.mkdir(parents=True)
        (folder / 'result.json').write_text(json.dumps({'job_id': job['id'], 'job_owner': owner}))
        self.store.recover(time.time() + LEASE_SECONDS + 1)
        self.assertEqual(self.store.get(job['id'])['state'], 'succeeded')
        self.assertEqual(self.store.cancel(job['id'])['state'], 'succeeded')

    def test_api_submission_cancel_retry_and_worker_status(self):
        data = DatasetStore(self.root / 'data')
        source = data.upload('history.csv', b'date,qty\n2026-01-01,1\n2026-02-01,2\n2026-03-01,3\n2026-04-01,4\n2026-05-01,5\n2026-06-01,6\n', 'history')
        dataset = data.save('Test', {'history': source['id']},
            {'date_col': 'date', 'target_col': 'qty', 'unit': 'units'}, accept_warnings=True)
        with patch.object(main, 'DATASET_STORE', data), patch.object(jobs, 'STORE', self.store), patch.object(jobs, 'forecast_job') as dispatch, TestClient(main.app) as client:
            body = {'dataset_id': dataset['id'], 'request_id': 'ui-request-123'}
            first = client.post('/api/jobs', json=body)
            self.assertEqual(first.status_code, 202, first.text)
            self.assertEqual(client.post('/api/jobs', json=body).json()['id'], first.json()['id'])
            url = '/api/jobs/' + first.json()['id']
            self.assertEqual(client.post(url + '/retry', json={'request_id': 'retry-001'}).status_code, 400)
            self.assertEqual(client.post(url + '/cancel').json()['state'], 'cancelled')
            retry = client.post(url + '/retry', json={'request_id': 'retry-002'})
            self.assertEqual(retry.status_code, 202, retry.text)
            self.assertEqual(retry.json()['retry_of'], first.json()['id'])
            self.assertFalse(client.get('/api/jobs').json()['worker_available'])
            self.store.pulse_worker()
            self.assertTrue(client.get('/api/jobs').json()['worker_available'])
            self.assertGreaterEqual(dispatch.call_count, 2)


if __name__ == '__main__':
    unittest.main()

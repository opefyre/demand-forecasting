from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile

from app.recovery import backup, restore, digest
from app.workspace_lock import WorkspaceLease


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.parent = Path(self.temp.name)
        self.root = self.parent / 'workspace'; self.root.mkdir()
        (self.root / 'data/datasets').mkdir(parents=True)
        (self.root / 'runs/sample').mkdir(parents=True)
        (self.root / 'data/datasets/source.bin').write_bytes(b'private source bytes')
        (self.root / 'runs/sample/result.json').write_text('{"run_id":"sample"}')
        (self.root / 'requirements.txt').write_text('example==1\n')
        self.archive = self.parent / 'backup.zip'

    def tearDown(self): self.temp.cleanup()

    def database(self, name, statements):
        with closing(sqlite3.connect(self.root / 'data' / name)) as db:
            for statement in statements: db.execute(statement)
            db.commit()

    def test_roundtrip_and_runtime_sanitization(self):
        self.database('plans.sqlite3', ['CREATE TABLE plans(id TEXT,payload TEXT)', "INSERT INTO plans VALUES ('P1','unchanged')"])
        self.database('identity.sqlite3', ['CREATE TABLE login_sessions(token_hash TEXT)', "INSERT INTO login_sessions VALUES ('old')"])
        self.database('queue.sqlite3', ['CREATE TABLE task(data TEXT)', "INSERT INTO task VALUES ('do not run')"])
        self.database('jobs.sqlite3', ['CREATE TABLE forecast_jobs(id TEXT,state TEXT,message TEXT,owner TEXT,heartbeat_at REAL)',
            "INSERT INTO forecast_jobs VALUES ('active','running','working','worker',123)",
            "INSERT INTO forecast_jobs VALUES ('done','succeeded','ready','worker',123)",
            'CREATE TABLE worker_health(id TEXT)', "INSERT INTO worker_health VALUES ('worker')"])
        self.database('folder-inputs.sqlite3', ['CREATE TABLE folder_inputs(id TEXT,config TEXT)',
            "INSERT INTO folder_inputs VALUES ('f','{\"enabled\":true,\"path\":\"/external\"}')"])
        (self.root / 'data/integrations.json').write_text('{"connectors":[{"id":"http","enabled":true}]}')
        result = backup(self.root, self.archive)
        self.assertEqual(self.archive.stat().st_mode & 0o777, 0o600)
        self.assertEqual(result['sha256'], digest(self.archive))
        destination = self.parent / 'restored'
        report = restore(self.archive, destination)
        self.assertEqual(report['verified_files'], result['files'])
        self.assertEqual((destination / 'data/datasets/source.bin').read_bytes(), b'private source bytes')
        for root in (self.root, destination):
            with closing(sqlite3.connect(root / 'data/plans.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT * FROM plans').fetchall(), [('P1','unchanged')])
        with closing(sqlite3.connect(destination / 'data/identity.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM login_sessions').fetchone()[0], 0)
        with closing(sqlite3.connect(destination / 'data/jobs.sqlite3')) as db:
            self.assertEqual(dict(db.execute('SELECT id,state FROM forecast_jobs')), {'active':'interrupted','done':'succeeded'})
            self.assertEqual(db.execute('SELECT count(*) FROM worker_health').fetchone()[0], 0)
        with closing(sqlite3.connect(destination / 'data/folder-inputs.sqlite3')) as db:
            config = json.loads(db.execute('SELECT config FROM folder_inputs').fetchone()[0])
            self.assertFalse(config['enabled']); self.assertEqual(config['path'], '/external')
        self.assertFalse(json.loads((destination / 'data/integrations.json').read_text())['connectors'][0]['enabled'])
        self.assertFalse((destination / 'data/queue.sqlite3').exists())
        self.assertTrue((self.root / 'data/queue.sqlite3').exists())
        self.assertFalse((destination / 'RESTORE_INCOMPLETE').exists())

    def test_process_lock_prevents_backup_and_app_start(self):
        code = 'from app.workspace_lock import WorkspaceLease; import sys; WorkspaceLease(sys.argv[1])'
        with WorkspaceLease(self.root):
            with self.assertRaisesRegex(RuntimeError, 'in use'): backup(self.root, self.archive)
        with WorkspaceLease(self.root, exclusive=True):
            process = subprocess.run([sys.executable, '-c', code, str(self.root)], capture_output=True, text=True)
            self.assertNotEqual(process.returncode, 0); self.assertIn('in use', process.stderr)
        self.assertFalse(self.archive.exists())

    def test_sales_customers_views_and_ai_journal_survive_restore(self):
        from app.customers import CustomerStore, Customer
        from app.sales_demand import DemandStore
        from app.forecast_views import ViewStore, SavedView
        from app.ai_workspace import AIJournal
        from tests.test_sales_demand import fixture
        run,inputs=fixture()
        customer_store=CustomerStore(self.root/'data/customers.sqlite3')
        customer_store.save([Customer(customer='A',products=[{'sku':'P','unit':'tonnes'}])])
        sales=DemandStore(self.root/'data/sales-demand.sqlite3')
        snapshot=sales.save(inputs,run,'restore-test','local')
        views=ViewStore(sales.path)
        view=views.save('local',SavedView(name='Monthly',run_id=run['run_id'],snapshot_id=snapshot['id'],settings={'unit':'tonnes','display':'pivot'}))
        journal=AIJournal(self.root/'data/ai-workspace.sqlite3')
        turn=journal.put('local',{'answer':'Saved evidence','actions':[]})
        backup(self.root,self.archive)
        restored=self.parent/'sales-restored';restore(self.archive,restored)
        self.assertEqual(CustomerStore(restored/'data/customers.sqlite3').list(),customer_store.list())
        self.assertEqual(DemandStore(restored/'data/sales-demand.sqlite3').get(snapshot['id']),snapshot)
        self.assertEqual(ViewStore(restored/'data/sales-demand.sqlite3').list('local',run['run_id']),[view])
        self.assertEqual(AIJournal(restored/'data/ai-workspace.sqlite3').get(turn,'local')['answer'],'Saved evidence')

    def test_never_overwrites_or_backs_up_inside_live_state(self):
        backup(self.root, self.archive)
        original = digest(self.archive)
        with self.assertRaisesRegex(ValueError, 'already exists'): backup(self.root, self.archive)
        with self.assertRaisesRegex(ValueError, 'outside live'): backup(self.root, self.root / 'data/bad.zip')
        with self.assertRaisesRegex(ValueError, 'new directory'): restore(self.archive, self.root)
        self.assertEqual(digest(self.archive), original)

    def test_every_sales_and_external_schedule_is_paused_after_restore(self):
        for name in ('folder-inputs.sqlite3', 'order-folders.sqlite3', 'factor-folders.sqlite3'):
            self.database(name, ['CREATE TABLE folder_inputs(id TEXT,config TEXT)',
                "INSERT INTO folder_inputs VALUES ('F','{\"enabled\":true,\"auto_draft\":true,\"minutes\":60,\"path\":\"/approved\"}')",
                'CREATE TABLE folder_checks(id TEXT,detail TEXT)',
                "INSERT INTO folder_checks VALUES ('reviewed','unchanged evidence')"])
        self.database('recurring-forecasts.sqlite3', [
            'CREATE TABLE recurring_forecasts(id TEXT,actor TEXT,payload TEXT)',
            "INSERT INTO recurring_forecasts VALUES ('S','owner','{\"enabled\":true,\"day\":5,\"run_id\":\"original\"}')",
            'CREATE TABLE recurring_cycles(id TEXT,payload TEXT)',
            "INSERT INTO recurring_cycles VALUES ('C','{\"state\":\"review\",\"update_id\":\"kept\"}')"])
        self.database('live-sources.sqlite3', ['CREATE TABLE sources(id TEXT,state TEXT)',
            "INSERT INTO sources VALUES ('fx','{\"enabled\":true,\"status\":\"ready\",\"last_success\":\"2026-09-30\"}')",
            "INSERT INTO sources VALUES ('cpi','{\"enabled\":true,\"status\":\"refreshing\",\"permission_confirmed\":true}')",
            'CREATE TABLE quotas(day TEXT,calls INT)', "INSERT INTO quotas VALUES ('2026-10-07',19)"])
        backup(self.root, self.archive)
        restored = self.parent / 'all-schedules'; report = restore(self.archive, restored)
        for name in ('folder-inputs.sqlite3', 'order-folders.sqlite3', 'factor-folders.sqlite3'):
            with closing(sqlite3.connect(restored / 'data' / name)) as db:
                config = json.loads(db.execute('SELECT config FROM folder_inputs').fetchone()[0])
                self.assertFalse(config['enabled']); self.assertFalse(config['auto_draft'])
                self.assertEqual((config['minutes'], config['path']), (60, '/approved'))
                self.assertEqual(db.execute('SELECT detail FROM folder_checks').fetchone()[0], 'unchanged evidence')
        with closing(sqlite3.connect(restored / 'data/recurring-forecasts.sqlite3')) as db:
            config = json.loads(db.execute('SELECT payload FROM recurring_forecasts').fetchone()[0])
            self.assertFalse(config['enabled']); self.assertEqual(config['run_id'], 'original')
            self.assertEqual(json.loads(db.execute('SELECT payload FROM recurring_cycles').fetchone()[0])['update_id'], 'kept')
        with closing(sqlite3.connect(restored / 'data/live-sources.sqlite3')) as db:
            states = {key: json.loads(raw) for key, raw in db.execute('SELECT id,state FROM sources')}
            self.assertFalse(states['fx']['enabled']); self.assertFalse(states['cpi']['enabled'])
            self.assertEqual(states['fx']['last_success'], '2026-09-30')
            self.assertEqual(states['cpi']['status'], 'failed'); self.assertTrue(states['cpi']['permission_confirmed'])
            self.assertEqual(db.execute('SELECT calls FROM quotas').fetchone()[0], 19)
        with closing(sqlite3.connect(self.root / 'data/recurring-forecasts.sqlite3')) as db:
            self.assertTrue(json.loads(db.execute('SELECT payload FROM recurring_forecasts').fetchone()[0])['enabled'])
        self.assertTrue(any('Monthly forecast' in change for change in report['changes']))

    def test_malformed_schedule_leaves_restore_incomplete(self):
        self.database('recurring-forecasts.sqlite3', [
            'CREATE TABLE recurring_forecasts(id TEXT,actor TEXT,payload TEXT)',
            "INSERT INTO recurring_forecasts VALUES ('S','owner','not json')"])
        backup(self.root, self.archive)
        restored = self.parent / 'bad-schedule'
        with self.assertRaises(ValueError): restore(self.archive, restored)
        self.assertTrue((restored / 'RESTORE_INCOMPLETE').exists())
        with self.assertRaises(RuntimeError): WorkspaceLease(restored)

    def test_wal_commits_are_captured_without_journal_copies(self):
        with closing(sqlite3.connect(self.root / 'data/test.sqlite3')) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE records(value TEXT)'); db.execute("INSERT INTO records VALUES ('committed')"); db.commit()
            backup(self.root, self.archive)
            restored = self.parent / 'wal-restored'; restore(self.archive, restored)
            with closing(sqlite3.connect(restored / 'data/test.sqlite3')) as copy:
                self.assertEqual(copy.execute('SELECT value FROM records').fetchone()[0], 'committed')
        with zipfile.ZipFile(self.archive) as archive:
            self.assertFalse(any(n.endswith(('-wal','-shm')) for n in archive.namelist()))

    def rewrite_archive(self, change):
        backup(self.root, self.archive)
        with zipfile.ZipFile(self.archive) as archive: entries = {n:archive.read(n) for n in archive.namelist()}
        change(entries)
        altered = self.parent / 'altered.zip'
        with zipfile.ZipFile(altered, 'w') as archive:
            for name, content in entries.items(): archive.writestr(name, content)
        return altered

    def test_corruption_leaves_marked_nonlaunchable_restore(self):
        def corrupt(entries): entries['data/datasets/source.bin'] = b'X' * len(entries['data/datasets/source.bin'])
        damaged = self.rewrite_archive(corrupt)
        target = self.parent / 'damaged'
        with self.assertRaisesRegex(ValueError, 'checksum'): restore(damaged, target)
        self.assertTrue((target / 'RESTORE_INCOMPLETE').exists())
        with self.assertRaisesRegex(RuntimeError, 'incomplete'): WorkspaceLease(target)

    def test_traversal_and_unlisted_files_are_rejected(self):
        def traversal(entries):
            manifest = json.loads(entries['manifest.json'])
            row = manifest['files'][0]; original = row['path']; row['path'] = 'data/../../escaped'
            entries[row['path']] = entries.pop(original)
            entries['manifest.json'] = json.dumps(manifest).encode()
        damaged = self.rewrite_archive(traversal)
        with self.assertRaisesRegex(ValueError, 'Unsafe'): restore(damaged, self.parent / 'unsafe')
        self.assertFalse((self.parent / 'escaped').exists())

    def test_symlinks_refused_and_source_unchanged(self):
        source = self.root / 'data/datasets/source.bin'
        (self.root / 'data/link').symlink_to(source)
        with self.assertRaisesRegex(ValueError, 'Symbolic'): backup(self.root, self.archive)
        self.assertEqual(source.read_bytes(), b'private source bytes')


if __name__ == '__main__': unittest.main()

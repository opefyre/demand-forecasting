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

    def test_company_notifications_restore_paused_without_replaying_outbound_work(self):
        from app.notifications import Notifications
        from tests.test_notifications import MemoryVault,Sender,body
        originals={}
        for company in ('tehran_a','tehran_b'):
            folder=self.root/'data/companies'/company;folder.mkdir(parents=True)
            store=Notifications(folder/'notifications.sqlite3',vault=MemoryVault(),sender=Sender())
            row=store.save(body(enabled=True,events=['forecast_ready']),'synthetic-owner')
            accepted=store.queue(row['id'],'test','accepted','synthetic-owner');store.drain(lambda _:True,'https://company.test')
            queued=store.queue(row['id'],'test','queued','synthetic-owner')
            sending=store.queue(row['id'],'test','sending','synthetic-owner')
            with store.db() as db:
                record=json.loads(db.execute('SELECT record FROM deliveries WHERE id=?',(sending['id'],)).fetchone()[0]);record.update(state='sending',started_at=1)
                db.execute('UPDATE deliveries SET record=? WHERE id=?',(json.dumps(record),sending['id']))
            originals[company]=(row,store.delivery(accepted['id']),queued,sending)
        backup(self.root,self.archive);destination=self.parent/'notification-restore';restore(self.archive,destination)
        for company,(row,accepted,queued,sending) in originals.items():
            sender=Sender();store=Notifications(destination/'data/companies'/company/'notifications.sqlite3',vault=MemoryVault(),sender=sender)
            self.assertFalse(store.get(row['id'])['enabled']);self.assertEqual(store.get(row['id'])['version'],2)
            self.assertEqual(store.delivery(accepted['id']),accepted)
            self.assertEqual(store.delivery(queued['id'])['state'],'cancelled')
            self.assertEqual(store.delivery(sending['id'])['state'],'unknown')
            self.assertEqual(store.drain(lambda _:True,'https://company.test'),[]);self.assertEqual(sender.calls,[])

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

    def test_company_runtime_restore_preserves_evidence_but_not_execution_authority(self):
        from app.company_workspace import CompanyWorkspaces
        from app.ai_workspace import AIJournal
        from app.business_connections import BusinessConnections, ConnectionInput
        from app.connection_schedules import ImportSchedule, configure, tick
        from app.customers import Customer
        from tests.test_sales_demand import fixture
        from tests.test_notifications import MemoryVault
        workspaces = CompanyWorkspaces(self.root / 'data/companies')
        evidence = {}
        try:
            for company in ('tehran_a', 'tehran_b'):
                ws = workspaces.for_principal({'company_id': company})
                ws.customers.save([Customer(customer=company,products=[{'sku':'P','unit':'tonnes'}])])
                run, inputs = fixture(); run['run_id'] = 'a'*12 if company=='tehran_a' else 'b'*12
                inputs['run_id'] = run['run_id']
                run_folder=ws.runs/run['run_id'];run_folder.mkdir()
                (run_folder/'result.json').write_text(json.dumps(run))
                saved=ws.sales.save(inputs,run,'restore-'+company,company)
                store = BusinessConnections(ws.path('connections.sqlite3'), ws.datasets, vault=MemoryVault())
                connection = store.save(ConnectionInput(name=company, provider='http', role='sales_customers',
                    url='https://erp.example/export', filename='customers.csv', confirmed_read_access=True))
                schedule = configure(store, connection['id'], ImportSchedule(connection_version=1,
                    enabled=True, confirmed=True), company)
                with store.db() as db:
                    db.execute('INSERT INTO pulls VALUES(?,?,?,?,?,?,?,?)',
                               ('active', connection['id'], 'req-active', 1, 'fetching', 1, 'Fetching inputs…', None))
                    db.execute('INSERT INTO pulls VALUES(?,?,?,?,?,?,?,?)',
                               ('done', connection['id'], 'req-done', 1, 'ready', 1, 'Ready to review', None))
                    db.execute('INSERT INTO import_acceptance VALUES(?,?)', ('accepted', '{"id":"original"}'))
                active = [ws.jobs.create({'company': company}, state, state) for state in ('queued','running','publishing','succeeded')]
                with ws.jobs.engine.begin() as db:
                    for job in active:
                        db.exec_driver_sql('UPDATE forecast_jobs SET state=?,owner=?,heartbeat_at=? WHERE id=?',
                                          (job['name'], 'worker', 1, job['id']))
                recurring = ws.path('recurring.sqlite3')
                with closing(sqlite3.connect(recurring)) as db, db:
                    db.execute('CREATE TABLE recurring_forecasts(id TEXT,actor TEXT,payload TEXT)')
                    db.execute('INSERT INTO recurring_forecasts VALUES(?,?,?)', ('monthly', company, '{"enabled":true,"run_id":"original"}'))
                    db.execute('CREATE TABLE recurring_cycles(id TEXT,payload TEXT)')
                    db.execute('INSERT INTO recurring_cycles VALUES(?,?)', ('cycle','{"state":"review","update_id":"kept"}'))
                with closing(sqlite3.connect(ws.path('live-sources.sqlite3'))) as db, db:
                    db.execute('CREATE TABLE sources(id TEXT,state TEXT)')
                    db.execute('INSERT INTO sources VALUES(?,?)', ('cpi','{"enabled":true,"status":"refreshing","last_success":"2026-09-30"}'))
                turn = ws.journal.put(company, {'question':'Prepare a forecast', 'answer':company,
                    'run_id':None, 'snapshot_id':None, 'dataset_id':None, 'actions':[{'type':'forecast'}],
                    'results':{'0':{'run_id':'completed'}}})
                with closing(sqlite3.connect(ws.path('assistant.sqlite3'))) as db:
                    created = db.execute('SELECT created FROM ai_turns WHERE id=?',(turn,)).fetchone()[0]
                evidence[company] = (connection, schedule, active, turn, created, saved, run)
            # An uploaded file with a runtime filename must remain byte-for-byte unchanged.
            upload = self.root / 'data/companies/tehran_a/datasets/notifications.sqlite3'
            upload.write_bytes(b'opaque uploaded source')
            backup(self.root, self.archive)
            target = self.parent / 'company-restore'; report = restore(self.archive, target)
            self.assertEqual((target / upload.relative_to(self.root)).read_bytes(), upload.read_bytes())
            restored = CompanyWorkspaces(target / 'data/companies')
            try:
                for company, (connection, schedule, active, turn, created, saved, run) in evidence.items():
                    ws = restored.for_principal({'company_id':company})
                    store = ws.connections
                    current = store.get(connection['id'])
                    self.assertFalse(current['schedule']['enabled'])
                    self.assertEqual(current['schedule']['version'],schedule['version']+1)
                    self.assertEqual(current['version'],connection['version'])
                    self.assertEqual(tick(store,lambda _:True,now=10**15),[])
                    self.assertEqual(store.acceptance('accepted'),{'id':'original'})
                    self.assertEqual({p['id']:p['state'] for p in current['pulls']},{'active':'failed','done':'ready'})
                    self.assertEqual([ws.jobs.get(j['id'])['state'] for j in active],['interrupted']*3+['succeeded'])
                    self.assertEqual(ws.jobs.queued(),[])
                    self.assertEqual(ws.sales.get(saved['id']),saved)
                    self.assertEqual(ws.load_run(run['run_id']),run)
                    self.assertEqual(ws.customers.list(),workspaces.for_principal({'company_id':company}).customers.list())
                    with closing(sqlite3.connect(ws.path('recurring.sqlite3'))) as db:
                        self.assertEqual(json.loads(db.execute('SELECT payload FROM recurring_forecasts').fetchone()[0]),{'enabled':False,'run_id':'original'})
                        self.assertEqual(db.execute('SELECT payload FROM recurring_cycles').fetchone()[0],'{"state":"review","update_id":"kept"}')
                    with closing(sqlite3.connect(ws.path('live-sources.sqlite3'))) as db:
                        state=json.loads(db.execute('SELECT state FROM sources').fetchone()[0])
                        self.assertFalse(state['enabled']); self.assertEqual(state['status'],'failed')
                        self.assertEqual(state['last_success'],'2026-09-30')
                    with self.assertRaisesRegex(ValueError,'expired'): ws.journal.get(turn,company)
                    turns=ws.journal.conversation(turn,company,None,None,display=True)
                    self.assertTrue(turns[0]['actions_expired']); self.assertEqual(turns[0]['answer'],company)
                    self.assertEqual(turns[0]['results'],{'0':{'run_id':'completed'}})
                    self.assertEqual(ws.journal._read(turn,company)[0],created)
                    self.assertFalse(workspaces.for_principal({'company_id':company}).journal.get(turn,company).get('recovery_action_revoked'))
                    self.assertTrue(any(f'data/companies/{company}' in c for c in report['changes']))
            finally: restored.close()
        finally: workspaces.close()

    def test_call_ledger_only_company_restore(self):
        folder=self.root/'data/companies/tehran_a';folder.mkdir(parents=True)
        with closing(sqlite3.connect(folder/'assistant.sqlite3')) as db,db:
            db.execute('CREATE TABLE ai_calls(id TEXT,state TEXT)')
            db.execute("INSERT INTO ai_calls VALUES('kept','complete')")
        backup(self.root,self.archive);target=self.parent/'ledger-restore';restore(self.archive,target)
        with closing(sqlite3.connect(target/'data/companies/tehran_a/assistant.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT * FROM ai_calls').fetchall(),[('kept','complete')])

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
        restored_journal=AIJournal(restored/'data/ai-workspace.sqlite3')
        self.assertEqual(restored_journal._read(turn,'local')[1]['answer'],'Saved evidence')
        with self.assertRaisesRegex(ValueError,'expired'): restored_journal.get(turn,'local')

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

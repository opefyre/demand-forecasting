from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from copy import deepcopy
from contextlib import closing
import json
import multiprocessing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
import uuid

from app.planning import PlanStore


def append_comments(arguments):
    path, plan_id, worker = arguments
    store = PlanStore(Path(path))
    for index in range(8):
        store.add_comment(plan_id, text=f'{worker}:{index}', actor=f'Worker {worker}')
    return True


class PlanStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'plans.json'
        self.store = PlanStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, store=None):
        return (store or self.store).create(name='Tehran plan', run_id='run', site_id='site',
            owner='Planner', settings={'unit':'tonnes'}, metrics={'evidence_level':'strong'})

    def legacy(self):
        # Make a record through the public interface, but in a different registry.
        return self.create(PlanStore(Path(self.tmp.name) / 'source.json'))

    def test_lazy_exact_migration_once_and_source_untouched(self):
        row = self.legacy()
        row.pop('comments')  # Earlier valid records did not contain this field.
        row['settings']['label'] = 'تهران'
        raw = json.dumps([row], ensure_ascii=False, indent=2).encode()
        self.path.write_bytes(raw)
        self.assertFalse(self.store.storage.path.exists())
        self.assertEqual(self.store.list(), [row])
        self.assertEqual(self.path.read_bytes(), raw)
        self.store.add_comment(row['id'], text='Reviewed', actor='A')
        reopened = PlanStore(self.path)
        self.assertEqual(len(reopened.get(row['id'])['comments']), 1)
        self.assertEqual(len(reopened.list()), 1)
        self.assertEqual(self.path.read_bytes(), raw)
        with closing(sqlite3.connect(self.store.storage.path)) as connection:
            self.assertEqual(connection.execute('SELECT count FROM migration').fetchone()[0], 1)
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 1)

    def test_invalid_legacy_rejects_without_partial_migration(self):
        good = self.legacy()
        for payload in ('broken', '{}', json.dumps([good, good]), json.dumps([good, {'id':'bad'}]),
                        json.dumps([{**good, 'metrics':{'bad':float('nan')}}])):
            with self.subTest(payload=payload[:30]), TemporaryDirectory() as directory:
                path = Path(directory)/'plans.json'
                path.write_text(payload)
                store = PlanStore(path)
                with self.assertRaises(ValueError): store.list()
                self.assertEqual(path.read_text(), payload)
                with closing(sqlite3.connect(store.storage.path)) as connection:
                    self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 0)
                    self.assertEqual(connection.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 0)
                path.write_text(json.dumps([good]))
                self.assertEqual(store.list(), [good])

    def test_transaction_failure_rolls_back_and_next_edit_succeeds(self):
        row = self.create()
        with self.assertRaisesRegex(RuntimeError, 'interruption'):
            with self.store.storage.transaction() as plans:
                plans[0]['name'] = 'Should never appear'
                raise RuntimeError('interruption')
        self.assertEqual(self.store.get(row['id']), row)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store.storage.transaction() as plans:
                request = str(uuid.uuid4())
                plans[0]['revision_request_id'] = request
                duplicate = deepcopy(plans[0])
                duplicate['id'] = 'different'
                plans.append(duplicate)
        self.assertEqual(self.store.list(), [row])
        self.store.add_comment(row['id'], text='Recovered', actor='A')
        self.assertEqual(len(self.store.get(row['id'])['comments']), 1)

    def test_concurrent_processes_preserve_every_comment_and_history_entry(self):
        row = self.create()
        with ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as pool:
            self.assertTrue(all(pool.map(append_comments, [(str(self.path),row['id'],n) for n in range(4)])))
        saved = PlanStore(self.path).get(row['id'])
        self.assertEqual(len(saved['comments']), 32)
        self.assertEqual(len(saved['history']), 33)
        self.assertEqual({r['text'] for r in saved['comments']}, {f'{n}:{i}' for n in range(4) for i in range(8)})

    def test_concurrent_initial_migration_and_creates_preserve_every_plan(self):
        legacy = self.legacy()
        self.path.write_text(json.dumps([legacy]))
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(lambda _: self.create(PlanStore(self.path)), range(16)))
        self.assertEqual(len(self.store.list()), 17)
        self.assertEqual(self.store.get(legacy['id']), legacy)
        self.assertEqual(len({r['id'] for r in records}), 16)

    def test_independent_stores_serialize_revision_retries_and_numbering(self):
        row = self.create()
        self.store.transition(row['id'], status='review', actor='A')
        self.store.transition(row['id'], status='approved', actor='B')
        before = self.store.get(row['id'])
        def revise(request):
            return PlanStore(self.path).revise(row['id'], name='New version', owner='C', reason='New order', request_id=request)
        request = str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(revise, [request]*6))
            branches = list(pool.map(revise, [str(uuid.uuid4()) for _ in range(6)]))
        self.assertEqual(len({r['id'] for r in results}), 1)
        self.assertEqual(sorted(r['version'] for r in branches), list(range(3,9)))
        self.assertEqual(self.store.get(row['id']), before)

    def test_backup_is_consistent_restorable_and_never_overwrites(self):
        row = self.create()
        backup = Path(self.tmp.name)/'restored.sqlite3'
        self.store.storage.backup(backup)
        original = backup.read_bytes()
        with self.assertRaises(FileExistsError): self.store.storage.backup(backup)
        self.assertEqual(backup.read_bytes(), original)
        self.store.add_comment(row['id'], text='After backup', actor='A')
        restored = PlanStore(backup.with_suffix('.json'))
        self.assertEqual(restored.get(row['id']), row)
        restored.add_comment(row['id'], text='Restored copy', actor='B')
        self.assertEqual(self.store.get(row['id'])['comments'][0]['text'], 'After backup')

    def test_corrupt_or_unknown_database_never_falls_back_to_json(self):
        self.create()
        with closing(sqlite3.connect(self.store.storage.path)) as connection:
            connection.execute('PRAGMA user_version=99')
        with self.assertRaisesRegex(RuntimeError, 'Unsupported'): PlanStore(self.path).list()
        self.store.storage.path.write_bytes(b'not a database')
        with self.assertRaises(sqlite3.DatabaseError): PlanStore(self.path).list()

    def test_plan_update_cannot_remove_records(self):
        row = self.create()
        with self.assertRaisesRegex(ValueError, 'cannot be deleted'):
            with self.store.storage.transaction() as plans:
                plans.clear()
        self.assertEqual(self.store.list(), [row])


if __name__ == '__main__':
    unittest.main()

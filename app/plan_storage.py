"""Transactional local plan persistence using Python's standard SQLite library."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import Lock


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _validate(plans):
    if not isinstance(plans, list):
        raise ValueError('Saved plans must be a list. No data was migrated.')
    seen = set()
    for row in plans:
        if not isinstance(row, dict):
            raise ValueError('A saved plan is not a record. No data was migrated.')
        for key in ('id', 'name', 'run_id', 'site_id', 'owner', 'created_at', 'updated_at'):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f'A saved plan has an invalid {key}. No data was migrated.')
        if row['id'] in seen:
            raise ValueError('Duplicate saved plan identifiers. No data was migrated.')
        seen.add(row['id'])
        if row.get('status') not in {'draft', 'review', 'approved', 'published', 'archived'}:
            raise ValueError('A saved plan has an invalid status. No data was migrated.')
        for key in ('settings', 'metrics'):
            if not isinstance(row.get(key), dict):
                raise ValueError(f'A saved plan has invalid {key}. No data was migrated.')
        for key in ('history', 'overrides', 'comments'):
            if not isinstance(row.get(key, []), list):
                raise ValueError(f'A saved plan has invalid {key}. No data was migrated.')
        _encode(row)  # Reject non-finite values rather than silently changing them.


class PlanStorage:
    """One database per registry; JSON input is retained as a migration snapshot.

    Initialization is lazy so importing the application does not migrate live
    data. BEGIN IMMEDIATE protects read-modify-write operations across processes.
    Existing JSON must no longer be written by an older server during migration.
    """

    def __init__(self, legacy_path: Path):
        self.legacy_path = Path(legacy_path)
        self.path = self.legacy_path.with_suffix('.sqlite3')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ready = False
        self._init_lock = Lock()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.execute('PRAGMA synchronous=FULL')
        return connection

    def _initialize(self):
        with self._init_lock:
            if self._ready:
                return
            with self._connection() as connection:
                connection.execute('BEGIN IMMEDIATE')
                version = connection.execute('PRAGMA user_version').fetchone()[0]
                if version not in (0, 1):
                    raise RuntimeError(f'Unsupported plan database version {version}. No data was changed.')
                if version == 0:
                    # DDL and import share the transaction: failure leaves no partial registry.
                    connection.execute('CREATE TABLE plans (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, '
                                       'request_id TEXT UNIQUE, payload TEXT NOT NULL)')
                    connection.execute('CREATE INDEX plans_updated ON plans(updated_at DESC)')
                    connection.execute('CREATE TABLE migration (source TEXT, sha256 TEXT, count INTEGER, at TEXT)')
                    raw = self.legacy_path.read_bytes() if self.legacy_path.exists() else None
                    plans = json.loads(raw) if raw is not None else []
                    _validate(plans)
                    for row in plans:
                        self._save(connection, row)
                    connection.execute('INSERT INTO migration VALUES (?, ?, ?, ?)', (
                        str(self.legacy_path), hashlib.sha256(raw).hexdigest() if raw is not None else None,
                        len(plans), datetime.now(timezone.utc).isoformat()))
                    connection.execute('PRAGMA user_version=1')
                else:
                    # Missing metadata/tables is corruption, never an empty registry.
                    if connection.execute('SELECT count(*) FROM migration').fetchone()[0] != 1:
                        raise RuntimeError('Plan migration metadata is missing or invalid.')
                    connection.execute('SELECT id, updated_at, request_id, payload FROM plans LIMIT 1')
                connection.commit()
            self._ready = True

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _save(connection, row):
        connection.execute('INSERT INTO plans VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET '
                           'updated_at=excluded.updated_at, request_id=excluded.request_id, payload=excluded.payload',
                           (row['id'], row['updated_at'], row.get('revision_request_id'), _encode(row)))

    @contextmanager
    def transaction(self):
        self._initialize()
        with self._connection() as connection:
            connection.execute('BEGIN IMMEDIATE')
            before = dict(connection.execute('SELECT id, payload FROM plans'))
            plans = [json.loads(payload) for payload in before.values()]
            yield plans
            _validate(plans)
            if not set(before).issubset(row['id'] for row in plans):
                raise ValueError('Saved plans cannot be deleted by a plan update.')
            for row in plans:
                if before.get(row['id']) != _encode(row):
                    self._save(connection, row)
            connection.commit()

    def list(self):
        self._initialize()
        with self._connection() as connection:
            return [json.loads(row[0]) for row in connection.execute(
                'SELECT payload FROM plans ORDER BY updated_at DESC, id')]

    def get(self, plan_id):
        self._initialize()
        with self._connection() as connection:
            row = connection.execute('SELECT payload FROM plans WHERE id=?', (plan_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def backup(self, destination: Path):
        """Consistent SQLite snapshot; never overwrite an existing backup."""
        self._initialize()
        destination = Path(destination)
        with destination.open('xb'):
            pass
        try:
            with self._connection() as source:
                target = sqlite3.connect(destination)
                try:
                    source.backup(target)
                    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise RuntimeError('Plan backup failed its integrity check.')
                finally:
                    target.close()
        except BaseException:
            destination.unlink(missing_ok=True)  # Only the new, incomplete destination.
            raise
        return destination

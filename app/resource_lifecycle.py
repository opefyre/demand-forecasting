"""Presentation metadata only. Never rewrite input or forecast evidence."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone


class MetadataConflict(ValueError):
    pass


class ResourceLifecycle:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS resource_metadata (kind TEXT, id TEXT, name TEXT, archived INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL, updated_at TEXT, PRIMARY KEY(kind,id))')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def get(self, kind, key):
        with self.connect() as db:
            row = db.execute('SELECT name,archived,version,updated_at FROM resource_metadata WHERE kind=? AND id=?', (kind,key)).fetchone()
        return dict(row) | {'archived':bool(row['archived'])} if row else dict(name=None,archived=False,version=0,updated_at=None)

    def present(self, kind, key, value):
        meta = self.get(kind,key)
        result = dict(value, lifecycle=meta)
        if meta['name']:
            result['original_name'] = value.get('name')
            result['name'] = meta['name']
        return result

    def update(self, kind, key, version, *, name=None, archived=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM resource_metadata WHERE kind=? AND id=?', (kind,key)).fetchone()
            if (old['version'] if old else 0) != version:
                raise MetadataConflict('This item changed. Reload it before saving.')
            values = (kind,key,name if name is not None else old['name'] if old else None,
                      archived if archived is not None else old['archived'] if old else False,
                      version+1,datetime.now(timezone.utc).isoformat())
            db.execute('INSERT OR REPLACE INTO resource_metadata VALUES (?,?,?,?,?,?)', values)
        return self.get(kind,key)

    def require_active(self, kind, key):
        if self.get(kind,key)['archived']:
            raise ValueError('Restore this item before using it for a new forecast.')


def family(rows, key, parent_field):
    """Return only an explicitly recorded revision family; include branches."""
    by_id = {r['id']:r for r in rows}
    selected = {key}
    while True:
        more = {r['id'] for r in rows if r.get(parent_field) in selected}
        more |= {by_id[k][parent_field] for k in selected if k in by_id and by_id[k].get(parent_field) in by_id}
        if more <= selected:
            return [r for r in rows if r['id'] in selected]
        selected |= more

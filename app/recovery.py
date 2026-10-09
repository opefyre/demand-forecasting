"""Offline, checksummed state backups; restore only into a new staging directory."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import tempfile
import time
import zipfile

from .workspace_lock import WorkspaceLease


FORMAT = 'demandlab-state-v1'
MAX_BYTES = 20 * 1024**3
MAX_FILES = 100_000


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files(root):
    for folder in ('data', 'runs'):
        base = root / folder
        if base.is_symlink(): raise ValueError('State folders must not be symbolic links.')
        if not base.exists(): continue
        for path in sorted(base.rglob('*')):
            if path.is_symlink(): raise ValueError(f'Symbolic links are not supported: {path.relative_to(root)}')
            if path.is_dir(): continue
            if not stat.S_ISREG(path.stat().st_mode): raise ValueError('State contains a non-regular file.')
            # SQLite online-backup API folds journals into a standalone database.
            if path.name.endswith(('-wal', '-shm', '-journal')): continue
            yield path


def check_database(path):
    with closing(sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True)) as db:
        result = db.execute('PRAGMA integrity_check').fetchall()
        if result != [('ok',)]: raise ValueError(f'Database integrity check failed: {path.name}')


def backup(root, destination):
    root, destination = Path(root).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink(): raise ValueError('Backup destination already exists; choose a new file.')
    if not destination.parent.is_dir(): raise ValueError('Backup parent directory must exist.')
    for folder in ('data', 'runs'):
        if destination.resolve().is_relative_to(root / folder): raise ValueError('Keep backups outside live data and runs folders.')
    with WorkspaceLease(root, exclusive=True), tempfile.TemporaryDirectory(prefix='demandlab-backup-') as temporary:
        stage = Path(temporary)
        records = []
        for source in files(root):
            relative = source.relative_to(root).as_posix()
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open('rb') as stream: is_database = stream.read(16) == b'SQLite format 3\x00'
            if is_database:
                with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dst:
                    src.backup(dst)
                check_database(target)
            else:
                shutil.copyfile(source, target)
            records.append(dict(path=relative, size=target.stat().st_size, sha256=digest(target), sqlite=is_database))
        if not records: raise ValueError('No saved workspace data found.')
        if len(records) > MAX_FILES or sum(r['size'] for r in records) > MAX_BYTES:
            raise ValueError('Workspace exceeds the supported backup size.')
        manifest = dict(format=FORMAT, created_at=datetime.now(timezone.utc).isoformat(),
                        original_root=str(root), files=records,
                        requirements_sha256=digest(root / 'requirements.txt') if (root / 'requirements.txt').exists() else None,
                        exclusions=['application code and environment', 'external import folders', 'in-progress .forecast-work',
                                    'Better Auth PostgreSQL identity database', 'Keychain and other external secret vaults'],
                        restore_policy='Disable schedules, invalidate local logins and assistant proposals and clear queued work; retain completed business records. Restore PostgreSQL identity separately and revoke sessions/keys before cutover.')
        # Private file in destination filesystem, published atomically without overwriting.
        with tempfile.NamedTemporaryFile(prefix='.demandlab-', dir=destination.parent, delete=False) as handle:
            pending = Path(handle.name)
        try:
            with zipfile.ZipFile(pending, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
                for row in records: archive.write(stage / row['path'], row['path'])
            with pending.open('rb') as stream: os.fsync(stream.fileno())
            os.link(pending, destination)
        finally:
            pending.unlink(missing_ok=True)
        return dict(path=str(destination), files=len(records), bytes=sum(r['size'] for r in records), sha256=digest(destination))


def verified_archive(archive):
    entries = archive.infolist()
    if len(entries) > MAX_FILES + 1 or sum(e.file_size for e in entries) > MAX_BYTES:
        raise ValueError('Backup exceeds supported restore limits.')
    names = [entry.filename for entry in entries]
    if len(names) != len(set(names)) or 'manifest.json' not in names:
        raise ValueError('Backup has duplicate entries or no manifest.')
    if archive.getinfo('manifest.json').file_size > 32 * 1024**2:
        raise ValueError('Backup manifest is too large.')
    manifest = json.loads(archive.read('manifest.json'))
    if manifest.get('format') != FORMAT or not isinstance(manifest.get('files'), list):
        raise ValueError('Unsupported backup format.')
    expected = {'manifest.json'}
    for row in manifest['files']:
        name = row['path']
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name
                or path.parts[0] not in ('data', 'runs') or path.as_posix() != name or len(path.parts) < 2
                or name in expected):
            raise ValueError('Unsafe or duplicate backup path.')
        expected.add(name)
        if name not in names: raise ValueError('Backup file is missing.')
        entry = archive.getinfo(name)
        mode = entry.external_attr >> 16
        if entry.is_dir() or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)):
            raise ValueError('Only regular backup files are accepted.')
        if entry.file_size != row['size']: raise ValueError('Backup file size does not match its manifest.')
    if expected != set(names): raise ValueError('Backup contains unlisted files.')
    return manifest


def sanitize_restore(stage):
    """Sanitize runtime stores only, never uploaded files with similar names."""
    roots = [stage / 'data']
    companies = stage / 'data/companies'
    if companies.exists():
        from .platform_identity import COMPANY_ID
        for folder in sorted(companies.iterdir()):
            if not folder.is_dir(): continue
            if not COMPANY_ID.fullmatch(folder.name):
                raise ValueError('Invalid restored company storage directory.')
            roots.append(folder)
    changes = []
    for root in roots:
        changes.extend(sanitize_runtime(root, stage))
    return changes


def sanitize_runtime(root, stage):
    """No replayed jobs, live sessions or automatic integrations after recovery."""
    changes = []
    identity = root / 'identity.sqlite3'
    if identity.exists():
        with closing(sqlite3.connect(identity)) as db:
            with db: db.execute('DELETE FROM login_sessions')
        changes.append('All restored sign-in sessions invalidated.')
    # Queue delivery is transient; job history is retained below.
    queue = root / 'queue.sqlite3'
    if queue.exists():
        queue.unlink()
        changes.append('Transient task queue removed; no queued work will auto-run.')
    jobs = root / 'jobs.sqlite3'
    if jobs.exists():
        with closing(sqlite3.connect(jobs)) as db, db:
            db.execute("UPDATE forecast_jobs SET state='interrupted', message='Restored from backup; review and retry manually.', owner=NULL, heartbeat_at=NULL WHERE state IN ('queued','running','publishing')")
            db.execute('DELETE FROM worker_health')
        changes.append('Active jobs marked interrupted and worker leases cleared.')
    integrations = root / 'integrations.json'
    if integrations.exists():
        data = json.loads(integrations.read_text())
        for config in data.get('connectors', []): config['enabled'] = False
        integrations.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        changes.append('Integration schedules disabled; review paths and credentials before enabling.')
    # All three adapters share FolderInputs' schema. Restore must not leave newer
    # order/factor schedules running simply because the original backup tool
    # predates them. Keep accepted records and mappings, not execution authority.
    for name in ('folder-inputs.sqlite3', 'order-folders.sqlite3', 'factor-folders.sqlite3'):
        folders = root / name
        if folders.exists():
            with closing(sqlite3.connect(folders)) as db, db:
                for key, raw in db.execute('SELECT id,config FROM folder_inputs').fetchall():
                    config = json.loads(raw); config['enabled'] = False
                    if 'auto_draft' in config: config['auto_draft'] = False
                    db.execute('UPDATE folder_inputs SET config=? WHERE id=?', (json.dumps(config), key))
            changes.append(f'{name}: schedules and automatic drafts disabled; review paths before enabling.')
    for name in ('recurring-forecasts.sqlite3', 'recurring.sqlite3'):
        recurring = root / name
        if recurring.exists():
            with closing(sqlite3.connect(recurring)) as db, db:
                for key, raw in db.execute('SELECT id,payload FROM recurring_forecasts').fetchall():
                    config = json.loads(raw); config['enabled'] = False
                    db.execute('UPDATE recurring_forecasts SET payload=? WHERE id=?', (json.dumps(config), key))
            changes.append('Monthly forecast schedules paused; confirm settings and access before enabling.')
    connections = root / 'connections.sqlite3'
    if connections.exists():
        with closing(sqlite3.connect(connections)) as db, db:
            for key, raw in db.execute('SELECT connection_id,payload FROM input_schedules').fetchall():
                schedule = json.loads(raw)
                schedule.update(enabled=False, version=schedule['version']+1,
                                last_status='Schedule paused after recovery. Review connection settings and access.',
                                last_started=None)
                db.execute('UPDATE input_schedules SET payload=? WHERE connection_id=?', (json.dumps(schedule), key))
            db.execute("UPDATE pulls SET state='failed',message='Fetch interrupted by recovery. Review and retry manually.' WHERE state='fetching'")
        changes.append('Connected input schedules paused and in-progress fetches stopped; accepted evidence retained.')
    sources = root / 'live-sources.sqlite3'
    if sources.exists():
        with closing(sqlite3.connect(sources)) as db, db:
            for key, raw in db.execute('SELECT id,state FROM sources').fetchall():
                state = json.loads(raw); state['enabled'] = False
                if state.get('status') in {'queued', 'refreshing'}:
                    state.update(status='failed', error='Refresh interrupted by recovery. Review the connection before retrying.')
                db.execute('UPDATE sources SET state=? WHERE id=?', (json.dumps(state), key))
        changes.append('Live external-source refresh paused; cached observation dates remain unchanged.')
    for name in ('assistant.sqlite3', 'ai-workspace.sqlite3'):
        journal = root / name
        if journal.exists():
            with closing(sqlite3.connect(journal)) as db, db:
                # The shared assistant database may contain only the call ledger.
                if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ai_turns'").fetchone(): continue
                for key, raw in db.execute('SELECT id,payload FROM ai_turns').fetchall():
                    payload = json.loads(raw)
                    payload['recovery_action_revoked'] = True
                    db.execute('UPDATE ai_turns SET payload=? WHERE id=?', (json.dumps(payload), key))
            changes.append('Previous assistant proposals revoked; conversations and completed action receipts retained.')
    # A restored outbox must never resume outbound consent or uncertain sends.
    notifications = root / 'notifications.sqlite3'
    if notifications.exists():
        with closing(sqlite3.connect(notifications)) as db,db:
            for key,raw in db.execute('SELECT id,config FROM destinations').fetchall():
                config=json.loads(raw);config['enabled']=False
                db.execute('UPDATE destinations SET config=?,version=version+1,since=? WHERE id=?',(json.dumps(config),time.time(),key))
            for key,raw in db.execute('SELECT id,record FROM deliveries').fetchall():
                record=json.loads(raw)
                if record['state'] not in {'queued','sending'}:continue
                record.update(state='unknown' if record['state']=='sending' else 'cancelled',finished_at=time.time(),
                    message='Delivery is uncertain. Check the destination before retrying.' if record['state']=='sending' else 'Connection settings or access changed.')
                db.execute('UPDATE deliveries SET record=? WHERE id=?',(json.dumps(record),key))
        changes.append('Notifications paused; queued sends cancelled and in-flight sends marked uncertain.')
    return [f'{root.relative_to(stage)}: {change}' for change in changes]


def restore(source, destination):
    source, destination = Path(source).resolve(), Path(destination).absolute()
    if destination.exists() or destination.is_symlink(): raise ValueError('Restore only into a new directory; existing data will not be overwritten.')
    if not destination.parent.is_dir(): raise ValueError('Restore parent directory must exist.')
    # Reserve destination exclusively. On failure leave it with an explicit marker;
    # never recursively delete a path that another process may have touched.
    destination.mkdir(mode=0o700)
    marker = destination / 'RESTORE_INCOMPLETE'
    marker.write_text('Do not start the application from this incomplete restore.\n')
    with WorkspaceLease(destination, exclusive=True), zipfile.ZipFile(source) as archive:
        manifest = verified_archive(archive)
        for row in manifest['files']:
            target = destination / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(row['path']) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst)
            target.chmod(0o600)
            if digest(target) != row['sha256']: raise ValueError(f'Backup checksum failed: {row["path"]}')
            if row.get('sqlite'): check_database(target)
        changes = sanitize_restore(destination)
        report = dict(format=FORMAT, restored_at=datetime.now(timezone.utc).isoformat(),
                      archive_sha256=digest(source), verified_files=len(manifest['files']), changes=changes,
                      original_root=manifest.get('original_root'), requirements_sha256=manifest.get('requirements_sha256'))
        (destination / 'restore-report.json').write_text(json.dumps(report, indent=2))
        marker.unlink()
        return report

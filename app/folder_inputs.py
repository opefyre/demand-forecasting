"""Reviewed local export ingestion; APScheduler supplies scheduling, SQLite state."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import time
import uuid
from contextlib import contextmanager
from fastapi.encoders import jsonable_encoder

MAX_BYTES = 50 * 1024 * 1024
EXTENSIONS = {'.csv', '.tsv', '.json', '.xlsx', '.xls'}


class FolderInputs:
    def __init__(self, path, datasets, roots):
        self.path, self.datasets = Path(path), datasets
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.roots = [Path(root).resolve(strict=True) for root in roots]
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS folder_inputs (id TEXT PRIMARY KEY, config TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS folder_checks (id TEXT PRIMARY KEY, connector_id TEXT NOT NULL, checked REAL NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self):
        with self.connect() as db:
            rows = [json.loads(row[0]) for row in db.execute('SELECT config FROM folder_inputs ORDER BY rowid DESC')]
            for row in rows:
                checks = db.execute('SELECT id,checked,state,detail FROM folder_checks WHERE connector_id=? ORDER BY checked DESC LIMIT 10', (row['id'],)).fetchall()
                row['checks'] = [dict(id=r[0], checked=r[1], state=r[2], **json.loads(r[3])) for r in checks]
                candidate = db.execute("SELECT id FROM folder_checks WHERE connector_id=? AND state='ready' ORDER BY checked DESC LIMIT 1",(row['id'],)).fetchone()
                row['candidate_id'] = candidate[0] if candidate else None
                row['accepted_dataset_id'] = self.candidate(candidate[0]).get('accepted_dataset_id') if candidate else None
        return rows

    def _folder(self, value):
        folder = Path(value)
        if not folder.is_absolute():
            raise ValueError('Choose an absolute path inside an approved export folder.')
        folder = folder.resolve(strict=True)
        if not folder.is_dir() or not any(folder.is_relative_to(root) for root in self.roots):
            raise ValueError('This folder is outside the administrator-approved import locations.')
        return folder

    def get_config(self, key):
        with self.connect() as db:
            row = db.execute('SELECT config FROM folder_inputs WHERE id=?', (key,)).fetchone()
        if not row: raise ValueError('Export connection not found.')
        return json.loads(row[0])

    def set_auto_draft(self, key, enabled):
        if type(enabled) is not bool: raise ValueError('Choose whether to create drafts automatically.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT config FROM folder_inputs WHERE id=?', (key,)).fetchone()
            if not row: raise ValueError('Export connection not found.')
            config = json.loads(row[0])
            if enabled:
                if not config['minutes']: raise ValueError('Choose a scheduled connection first.')
                template = self.datasets.get(config['dataset_id'])
                if set(template['sources'])-{'history','future'} or template.get('scenario_provenance'):
                    raise ValueError('Automatic drafts require sales history and optional future factors only.')
            config['auto_draft'] = enabled
            db.execute('UPDATE folder_inputs SET config=? WHERE id=?', (json.dumps(config),key))
        return config

    def scheduled_check(self, key, submit):
        config = self.get_config(key)
        if not config['enabled']: return None
        check = self.check(key)
        if not config.get('auto_draft'): return check
        message = 'New inputs need review before a draft can start.'
        job_id = None
        if check['state'] == 'failed':
            message = 'Draft not started: fix the input error first.'
        elif check['state'] == 'unchanged':
            candidate = self.candidate(check['candidate_id'])
            if candidate.get('accepted_dataset_id'):
                try:
                    saved = self.draft_dataset(candidate['id'])
                    current = self.get_config(key)
                    if not current['enabled'] or not current.get('auto_draft'): return check
                    job = submit(saved['id'], candidate['id'])
                    job_id = job['id']
                    message = 'Draft requested; follow its status in forecast activity.'
                except ValueError as exc:
                    message = 'Draft not started: '+str(exc)
                except Exception:
                    message = 'Draft could not start. Check forecast activity before retrying.'
        # Store the dispatch outcome with the refresh, surviving app restarts.
        with self.connect() as db:
            row = db.execute('SELECT detail FROM folder_checks WHERE id=?', (check['id'],)).fetchone()
            detail = json.loads(row[0])
            detail.update(draft_message=message, draft_job_id=job_id)
            db.execute('UPDATE folder_checks SET detail=? WHERE id=?', (json.dumps(detail),check['id']))
        return {**check, **detail}

    def create(self, payload, identity=None):
        if payload.get('confirmed_local_access') is not True:
            raise ValueError('Confirm permission to read these export files.')
        folder = self._folder(payload.get('path', ''))
        template = self.datasets.get(payload.get('dataset_id'))
        files = payload.get('files', {})
        if not isinstance(files, dict) or not files.get('history') or set(files) - {'history','future','operations'}:
            raise ValueError('Specify a history export and optional future-factor or production exports.')
        for role, name in files.items():
            if role not in template['sources']:
                raise ValueError(f'Import and review a {role} mapping before connecting this export.')
            if not isinstance(name,str) or Path(name).name != name or any(c in name for c in '*?[]\\') or Path(name).suffix.lower() not in EXTENSIONS:
                raise ValueError('Use exact CSV, TSV, JSON or Excel filenames, without subfolders or wildcards.')
        minutes = payload.get('minutes', 0)
        if type(minutes) is not int or minutes not in {0,15,60,360,1440}:
            raise ValueError('Choose manual checks, 15 minutes, hourly, six-hourly or daily checks.')
        name = str(payload.get('name','')).strip()
        if not name or len(name)>120: raise ValueError('Enter a connection name of up to 120 characters.')
        classification = payload.get('classification', 'user_provided')
        if classification not in {'user_provided','synthetic_sample'}: raise ValueError('Invalid source classification.')
        row = dict(id=uuid.uuid4().hex, name=name, path=str(folder), dataset_id=template['id'],
                   files=files, minutes=minutes, enabled=minutes>0, classification=classification,
                   created_at=time.time(), created_by=identity)
        with self.connect() as db:
            db.execute('INSERT INTO folder_inputs VALUES (?,?)', (row['id'],json.dumps(row)))
        return row

    def set_enabled(self, key, enabled):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT config FROM folder_inputs WHERE id=?',(key,)).fetchone()
            if not row: raise ValueError('Export connection not found.')
            config = json.loads(row[0])
            if enabled and not config['minutes']: raise ValueError('This connection uses manual checks.')
            config['enabled'] = bool(enabled)
            db.execute('UPDATE folder_inputs SET config=? WHERE id=?',(json.dumps(config),key))
        return config

    def _read_files(self, config):
        folder = self._folder(config['path'])
        files = {}
        for role, name in config['files'].items():
            path = folder/name
            if path.is_symlink(): raise ValueError(f'{name}: linked files are not allowed.')
            # O_NOFOLLOW prevents a final-path symlink swap between check and open.
            fd = os.open(path, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
            with os.fdopen(fd,'rb') as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode): raise ValueError(f'{name}: expected a regular file.')
                if before.st_size > MAX_BYTES: raise ValueError(f'{name}: exceeds the 50 MB import limit.')
                if time.time()-before.st_mtime < 2: raise ValueError(f'{name}: still being written; check again shortly.')
                payload = stream.read(MAX_BYTES+1)
                after = os.fstat(stream.fileno())
            if len(payload)>MAX_BYTES or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
                raise ValueError(f'{name}: changed while reading; check again.')
            files[role] = (name, payload, hashlib.sha256(payload).hexdigest())
        return files

    def check(self, key):
        # Serialize checks across app processes. No external network IO is done here.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = db.execute('SELECT config FROM folder_inputs WHERE id=?',(key,)).fetchone()
            if not record: raise ValueError('Export connection not found.')
            config, checked = json.loads(record[0]), time.time()
            detail, state = {}, 'failed'
            try:
                template = self.datasets.get(config['dataset_id'])
                files = self._read_files(config)
                fingerprint = hashlib.sha256(json.dumps({r:v[2] for r,v in files.items()},sort_keys=True).encode()).hexdigest()
                previous = db.execute("SELECT id,detail FROM folder_checks WHERE connector_id=? AND state='ready' ORDER BY checked DESC LIMIT 1",(key,)).fetchone()
                if previous and json.loads(previous[1])['fingerprint']==fingerprint:
                    state, detail = 'unchanged', {'message':'No new file contents.', 'candidate_id':previous[0]}
                else:
                    sources = dict(template['sources'])
                    for role,(name,payload,digest) in files.items():
                        old,_ = self.datasets.source(template['sources'][role])
                        sources[role] = self.datasets.upload(name,payload,role,old.get('sheet'))['id']
                    review = self.datasets.inspect(sources,template['settings'],config['classification'])
                    state = 'ready'
                    detail = dict(message='New inputs ready for review.', fingerprint=fingerprint,
                        sources=sources, settings=template['settings'], review=review,
                        parent_dataset_id=template['id'], name=config['name'], classification=config['classification'],
                        files={r:{'name':v[0],'sha256':v[2]} for r,v in files.items()},
                        retained_roles=sorted(set(sources)-set(files)))
            except Exception as exc:
                detail = {'message':str(exc)[:500]}
            identifier = uuid.uuid4().hex
            detail = jsonable_encoder(detail)
            db.execute('INSERT INTO folder_checks VALUES (?,?,?,?,?)',(identifier,key,checked,state,json.dumps(detail,allow_nan=False)))
        return dict(id=identifier, connector_id=key, checked=checked, state=state, **detail)

    def candidate(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT connector_id,checked,detail FROM folder_checks WHERE id=? AND state='ready'",(identifier,)).fetchone()
        if not row: raise ValueError('These input files are not ready for review.')
        return dict(id=identifier, connector_id=row[0], checked=row[1], **json.loads(row[2]))

    def verify_candidate(self, identifier, sources, parent_dataset_id):
        candidate = self.candidate(identifier)
        if sources != candidate['sources'] or parent_dataset_id != candidate['parent_dataset_id']:
            raise ValueError('The refreshed source files changed. Start a separate import for replacement files.')
        return {key:candidate[key] for key in ('id','connector_id','checked','files','retained_roles')}

    def mark_saved(self, identifier, dataset_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT detail FROM folder_checks WHERE id=?',(identifier,)).fetchone()
            if not row: raise ValueError('Import refresh not found.')
            detail = json.loads(row[0])
            detail['accepted_dataset_id'] = dataset_id
            db.execute('UPDATE folder_checks SET detail=? WHERE id=?',(json.dumps(detail),identifier))

    def accept(self, identifier, *, name, sources, settings, classification, accept_warnings, parent_dataset_id):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT connector_id,checked,detail FROM folder_checks WHERE id=? AND state='ready'",(identifier,)).fetchone()
            if not row: raise ValueError('These input files are not ready for review.')
            detail = json.loads(row[2])
            if sources != detail['sources'] or parent_dataset_id != detail['parent_dataset_id'] or classification != detail['classification']:
                raise ValueError('Keep the refreshed sources, original dataset and classification unchanged. Start a separate import for replacement files.')
            if detail.get('accepted_dataset_id'):
                saved = self.datasets.get(detail['accepted_dataset_id'])
                if saved['name'] != name.strip() or saved['settings'] != settings:
                    raise ValueError('These inputs were already saved. Open the saved data to create another version.')
                return saved
            provenance = dict(id=identifier,connector_id=row[0],checked=row[1],files=detail['files'],retained_roles=detail['retained_roles'])
            saved = self.datasets.save(name,sources,settings,classification,accept_warnings,
                parent_dataset_id=parent_dataset_id,import_provenance=provenance,request_id='folder-candidate:'+identifier)
            # If the process stopped after dataset publication but before this
            # acknowledgment, the deterministic save request recovers that version.
            self._record_acceptance(db,identifier,detail,saved['id'])
            return saved

    def _record_acceptance(self, db, identifier, detail, dataset_id):
        detail['accepted_dataset_id'] = dataset_id
        db.execute('UPDATE folder_checks SET detail=? WHERE id=?',(json.dumps(detail),identifier))

    def draft_dataset(self, identifier):
        """Refresh before dispatch, but never approve changed files implicitly."""
        candidate = self.candidate(identifier)
        if not candidate.get('accepted_dataset_id'):
            raise ValueError('Review and save these inputs before creating a draft forecast.')
        saved = self.datasets.get(candidate['accepted_dataset_id'])
        if set(saved['sources']) - {'history','future'} or saved.get('scenario_provenance'):
            raise ValueError('Choose reviewed sales history and optional future factors only.')
        refreshed = self.check(candidate['connector_id'])
        if refreshed['state'] == 'failed':
            raise ValueError('Refresh failed. No forecast started. ' + refreshed['message'])
        if refreshed['state'] != 'unchanged' or refreshed.get('candidate_id') != identifier:
            raise ValueError('New file contents need review. Open Review inputs before forecasting.')
        # Validate the exact retained data again; the queued job is pinned to it,
        # not to mutable folder files or a latest-dataset pointer.
        self.datasets.inspect(saved['sources'],saved['settings'],saved['classification'])
        return saved

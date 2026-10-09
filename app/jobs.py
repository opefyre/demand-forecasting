"""Huey-backed local jobs with durable state and atomic result publication.

Huey owns task delivery. This small application ledger owns user-visible state,
idempotency, cancellation checkpoints and recovery of interrupted calculations.
"""
from __future__ import annotations

from .workspace_lock import WorkspaceLease
from pathlib import Path as _WorkspacePath
_WORKSPACE_LEASE = WorkspaceLease(_WorkspacePath(__file__).resolve().parent.parent)

import asyncio
import json
import logging
from pathlib import Path
from threading import Event, Thread
import time
import uuid

from huey import SqliteHuey
from sqlalchemy import (Boolean, Column, Float, JSON, MetaData, String, Table,
                        create_engine, select, update)
from sqlalchemy.exc import IntegrityError

from .runtime import ForecastCancelled, execution_context


ROOT = Path(__file__).resolve().parent.parent
ACTIVE = ('queued', 'running', 'publishing')
TERMINAL = ('succeeded', 'failed', 'cancelled', 'interrupted')
LEASE_SECONDS = 120
log = logging.getLogger(__name__)


class JobStore:
    def __init__(self, path: Path, runs_dir: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir = runs_dir
        self.engine = create_engine(f'sqlite:///{path}', connect_args={'timeout': 30})
        metadata = MetaData()
        self.jobs = Table('forecast_jobs', metadata,
            Column('id', String, primary_key=True), Column('request_id', String, unique=True),
            Column('payload', JSON, nullable=False), Column('name', String, nullable=False),
            Column('state', String, nullable=False), Column('message', String, nullable=False),
            Column('created_at', Float, nullable=False), Column('updated_at', Float, nullable=False),
            Column('heartbeat_at', Float), Column('owner', String), Column('run_id', String),
            Column('cancel_requested', Boolean, nullable=False, default=False),
            Column('error', String), Column('retry_of', String))
        self.workers = Table('worker_health', metadata,
            Column('id', String, primary_key=True), Column('heartbeat_at', Float))
        self.groups = Table('forecast_groups', metadata,
            Column('id', String, primary_key=True), Column('request_id', String, unique=True),
            Column('name', String, nullable=False), Column('payloads', JSON, nullable=False),
            Column('job_ids', JSON, nullable=False), Column('created_at', Float, nullable=False))
        with self.engine.begin() as conn:
            conn.exec_driver_sql('PRAGMA journal_mode=WAL')
        # SQLite must serialize schema discovery + creation across app/worker
        # processes, including the first startup after a schema addition.
        with self.engine.begin() as conn:
            conn.exec_driver_sql('BEGIN IMMEDIATE')
            metadata.create_all(conn)

    def close(self):
        self.engine.dispose()

    def get(self, key):
        with self.engine.connect() as conn:
            row = conn.execute(select(self.jobs).where(self.jobs.c.id == key)).mappings().first()
        if not row:
            raise ValueError('Forecast job not found.')
        return dict(row)

    def list(self, limit=30):
        with self.engine.connect() as conn:
            active = list(conn.execute(select(self.jobs).where(self.jobs.c.state.in_(ACTIVE))
                .order_by(self.jobs.c.created_at.desc())).mappings())
            recent = list(conn.execute(select(self.jobs).where(self.jobs.c.state.in_(TERMINAL))
                .order_by(self.jobs.c.created_at.desc()).limit(limit)).mappings())
            return [dict(r) for r in active + recent]

    def queued(self):
        with self.engine.connect() as conn:
            return list(conn.execute(select(self.jobs.c.id).where(self.jobs.c.state == 'queued')).scalars())

    def create(self, payload, name, request_id, retry_of=None):
        now = time.time()
        row = dict(id=uuid.uuid4().hex, request_id=request_id, payload=payload, name=name,
                   state='queued', message='Waiting to start', created_at=now, updated_at=now,
                   cancel_requested=False, retry_of=retry_of)
        try:
            with self.engine.begin() as conn:
                conn.execute(self.jobs.insert().values(**row))
        except IntegrityError:
            with self.engine.connect() as conn:
                existing = conn.execute(select(self.jobs).where(
                    self.jobs.c.request_id == request_id)).mappings().one()
            if existing['payload'] != payload:
                raise ValueError('This request identifier was already used for different inputs.')
            return dict(existing)
        return self.get(row['id'])

    def claim(self, key):
        owner, now = uuid.uuid4().hex, time.time()
        with self.engine.begin() as conn:
            result = conn.execute(update(self.jobs).where(
                self.jobs.c.id == key, self.jobs.c.state == 'queued',
                self.jobs.c.cancel_requested.is_(False)).values(
                    state='running', owner=owner, heartbeat_at=now,
                    updated_at=now, message='Checking saved inputs'))
        return owner if result.rowcount else None

    def create_group(self, payloads, name, request_id):
        """Commit all selected methods together; retries cannot leave half a group."""
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, 'demandlab-group:' + request_id).hex
        now = time.time()
        row = dict(id=identifier, request_id=request_id, name=name, payloads=payloads,
                   job_ids=[uuid.uuid4().hex for _ in payloads], created_at=now)
        try:
            with self.engine.begin() as conn:
                conn.execute(self.groups.insert().values(**row))
                for index, (key, payload) in enumerate(zip(row['job_ids'], payloads)):
                    conn.execute(self.jobs.insert().values(id=key, request_id=f'group:{identifier}:{index}',
                        payload=payload, name=name, state='queued', message='Waiting to start',
                        created_at=now, updated_at=now, cancel_requested=False))
        except IntegrityError:
            with self.engine.connect() as conn:
                old = conn.execute(select(self.groups).where(self.groups.c.request_id == request_id)).mappings().one()
            if old['payloads'] != payloads or old['name'] != name:
                raise ValueError('This request identifier was already used for a different forecast.')
        return self.get_group(identifier)

    def get_group(self, identifier):
        with self.engine.connect() as conn:
            row = conn.execute(select(self.groups).where(self.groups.c.id == identifier)).mappings().first()
        if not row:
            raise ValueError('Forecast not found.')
        return {k:v for k,v in dict(row).items() if k != 'payloads'} | {
            'jobs':[self.get(key) for key in row['job_ids']]}

    def list_groups(self, limit=100, offset=0):
        with self.engine.connect() as conn:
            keys = list(conn.execute(select(self.groups.c.id).order_by(
                self.groups.c.created_at.desc()).limit(limit).offset(offset)).scalars())
        return [self.get_group(key) for key in keys]

    def progress(self, key, owner, message=None):
        values = {'heartbeat_at': time.time()}
        if message:
            values.update(message=message, updated_at=time.time())
        with self.engine.begin() as conn:
            result = conn.execute(update(self.jobs).where(
                self.jobs.c.id == key, self.jobs.c.owner == owner,
                self.jobs.c.state == 'running', self.jobs.c.cancel_requested.is_(False)).values(**values))
        if not result.rowcount:
            raise ForecastCancelled()

    def cancel(self, key):
        with self.engine.begin() as conn:
            conn.execute(update(self.jobs).where(self.jobs.c.id == key,
                self.jobs.c.state == 'queued').values(state='cancelled', cancel_requested=True,
                message='Cancelled', updated_at=time.time()))
            conn.execute(update(self.jobs).where(self.jobs.c.id == key,
                self.jobs.c.state == 'running').values(cancel_requested=True,
                message='Stopping after the current calculation', updated_at=time.time()))
        return self.get(key)

    def begin_publish(self, key, owner, run_id):
        with self.engine.begin() as conn:
            changed = conn.execute(update(self.jobs).where(self.jobs.c.id == key,
                self.jobs.c.owner == owner, self.jobs.c.state == 'running',
                self.jobs.c.cancel_requested.is_(False)).values(state='publishing',
                    run_id=run_id, message='Saving forecast', heartbeat_at=time.time(), updated_at=time.time()))
        if not changed.rowcount:
            raise ForecastCancelled()

    def finish(self, key, owner, state, error=None):
        with self.engine.begin() as conn:
            conn.execute(update(self.jobs).where(self.jobs.c.id == key,
                self.jobs.c.owner == owner, self.jobs.c.state.in_(('running', 'publishing'))).values(
                    state=state, error=error, updated_at=time.time(), message={
                        'succeeded': 'Ready', 'failed': 'Needs attention',
                        'cancelled': 'Cancelled', 'interrupted': 'Interrupted — retry when ready'}[state]))

    def recover(self, now=None):
        now = time.time() if now is None else now
        with self.engine.begin() as conn:
            stale = list(conn.execute(select(self.jobs).where(
                self.jobs.c.state.in_(('running', 'publishing')),
                self.jobs.c.heartbeat_at < now - LEASE_SECONDS)).mappings())
            for job in stale:
                # A crash after atomic rename but before ledger commit still has a valid result.
                path = self.runs_dir / str(job['run_id'] or '') / 'result.json'
                completed = False
                if job['state'] == 'publishing' and path.is_file():
                    try:
                        result = json.loads(path.read_text())
                        completed = result.get('job_id') == job['id'] and result.get('job_owner') == job['owner']
                    except (OSError, ValueError):
                        pass
                state = 'succeeded' if completed else ('cancelled' if job['cancel_requested'] else 'interrupted')
                conn.execute(update(self.jobs).where(self.jobs.c.id == job['id'],
                    self.jobs.c.heartbeat_at == job['heartbeat_at']).values(
                        state=state, updated_at=now,
                        message='Ready' if completed else 'Cancelled' if state == 'cancelled' else 'Interrupted — retry when ready'))

    def pulse_worker(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql('INSERT INTO worker_health (id, heartbeat_at) VALUES (?, ?) '
                'ON CONFLICT(id) DO UPDATE SET heartbeat_at=excluded.heartbeat_at', ('local', time.time()))

    def worker_available(self):
        with self.engine.connect() as conn:
            heartbeat = conn.execute(select(self.workers.c.heartbeat_at).where(self.workers.c.id == 'local')).scalar()
        return bool(heartbeat and time.time() - heartbeat < 30)


STORE = JobStore(ROOT / 'data' / 'jobs.sqlite3', ROOT / 'runs')
huey = SqliteHuey('demandlab_forecasts', filename=str(ROOT / 'data' / 'queue.sqlite3'), results=False)


def execute_job(key, store=STORE, executor=None, finalizer=None):
    owner = store.claim(key)
    if not owner:
        return  # Duplicate delivery and cancellation are safe.
    job = store.get(key)
    staging = store.runs_dir.parent / '.forecast-work' / key / owner
    staging.mkdir(parents=True, exist_ok=True)
    stopped = Event()

    def heartbeat():
        while not stopped.wait(5):
            try:
                store.progress(key, owner)
            except ForecastCancelled:
                return
            except Exception:
                log.exception('Could not refresh forecast job heartbeat')

    thread = Thread(target=heartbeat, daemon=True)
    thread.start()
    target = None
    try:
        with execution_context(staging, lambda message: store.progress(key, owner, message)):
            if executor is None:
                from .main import SavedRunConfig, run_saved
                result = asyncio.run(run_saved(SavedRunConfig(**job['payload'])))
            else:
                result = executor(job['payload'])
            store.progress(key, owner, 'Saving forecast')
            result.update(job_id=key, job_owner=owner)
            folder = staging / result['run_id']
            if job['payload'].get('sales_input_id'):
                if finalizer is not None:
                    finalizer(result, job['payload']['sales_input_id'], folder)
                elif executor is None:
                    from .main import DATASET_STORE, SALES_STORE
                    from .forecast_orders import finalize
                    finalize(DATASET_STORE, SALES_STORE, result, job['payload']['sales_input_id'], folder)
                else:
                    raise ValueError('A scoped order finalizer is required for this worker.')
            (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, default=str))
            target = store.runs_dir / result['run_id']
            store.begin_publish(key, owner, result['run_id'])
            store.runs_dir.mkdir(parents=True, exist_ok=True)
            folder.rename(target)
            store.finish(key, owner, 'succeeded')
    except ForecastCancelled:
        store.finish(key, owner, 'cancelled')
    except Exception as exc:
        if target and (target / 'result.json').exists():
            # Result exists; leave publishing state for explicit recovery, never mark failed.
            log.exception('Result saved; job ledger recovery required')
        else:
            message = getattr(exc, 'detail', None) or str(exc)
            store.finish(key, owner, 'failed', str(message)[:1500])
            log.exception('Forecast job failed')
    finally:
        stopped.set()
        thread.join(timeout=1)


@huey.task()
def forecast_job(key):
    execute_job(key)


def submit(payload, name, request_id, retry_of=None):
    job = STORE.create(payload, name, request_id, retry_of)
    if job['state'] == 'queued':
        forecast_job(job['id'])
    return job

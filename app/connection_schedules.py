"""Permission-rechecked scheduled captures. No automatic acceptance or forecasting."""
import json
import time
from pydantic import Field,StrictBool
from typing import Literal
from .platform_sales_api import StrictInput
from .business_connections import ConnectionError,ConnectionConflict


class ImportSchedule(StrictInput):
    version:int=Field(default=0,ge=0,strict=True)
    connection_version:int=Field(ge=1,strict=True)
    minutes:Literal[60,360,1440]=1440
    enabled:StrictBool=False
    confirmed:StrictBool=False


def configure(store,key,body,owner):
    if not body.confirmed:raise ConnectionError('Confirm scheduled read-only fetching and manual review.')
    config=store.get(key)
    if config['archived'] or config['version']!=body.connection_version:raise ConnectionConflict('Connection changed. Review the schedule again.')
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        # Recheck inside the write lock, not just before it.
        connection=db.execute('SELECT version,archived FROM connections WHERE id=?',(key,)).fetchone()
        if connection['archived'] or connection['version']!=body.connection_version:raise ConnectionConflict('Connection changed. Review the schedule again.')
        prior=db.execute('SELECT payload FROM input_schedules WHERE connection_id=?',(key,)).fetchone()
        version=json.loads(prior[0])['version'] if prior else 0
        if version!=body.version:raise ConnectionConflict('Schedule changed. Reload it before editing.')
        value={'version':version+1,'connection_version':body.connection_version,'minutes':body.minutes,'enabled':body.enabled,
               'owner':owner,'next_due':time.time()+body.minutes*60,'last_status':'Not checked yet','last_started':None}
        db.execute('INSERT OR REPLACE INTO input_schedules VALUES (?,?)',(key,json.dumps(value)))
    return value


def tick(store,authorized,*,now=None,force=None):
    now=time.time() if now is None else now
    with store.db() as db:keys=[r[0] for r in db.execute('SELECT connection_id FROM input_schedules ORDER BY connection_id')]
    results=[]
    for key in keys:
        if force is not None and key not in force:continue
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM input_schedules WHERE connection_id=?',(key,)).fetchone()
            schedule=json.loads(row[0]);connection=db.execute('SELECT version,archived FROM connections WHERE id=?',(key,)).fetchone()
            if not schedule['enabled'] or (force is None and schedule['next_due']>now):continue
            def permitted():
                try:return authorized(schedule['owner']) is True
                except Exception:return False
            if connection is None or connection['archived'] or connection['version']!=schedule['connection_version'] or not permitted():
                schedule.update(enabled=False,last_status='Schedule paused. Review connection settings and access.')
                db.execute('UPDATE input_schedules SET payload=? WHERE connection_id=?',(json.dumps(schedule),key));results.append(schedule);continue
            # A durable per-interval claim prevents two workers fetching twice.
            if schedule.get('last_status')=='Fetching inputs…' and schedule.get('last_started',0)>now-180:continue
            request_id=f'schedule:{key}:{schedule["version"]}:{int(schedule["next_due"])}'
            schedule.update(next_due=now+schedule['minutes']*60,last_started=now,last_status='Fetching inputs…')
            db.execute('UPDATE input_schedules SET payload=? WHERE connection_id=?',(json.dumps(schedule),key))
        def grant():
            if not permitted():return False
            with store.db() as db:
                latest=db.execute('SELECT payload FROM input_schedules WHERE connection_id=?',(key,)).fetchone()
            value=json.loads(latest[0]) if latest else {}
            return value.get('enabled') is True and value.get('version')==schedule['version']
        try:
            pulled=store.pull(key,request_id,authorized=grant)
            status=pulled['message'];pull_id=pulled['id']
        except Exception as exc:
            status=str(exc) if isinstance(exc,ConnectionError) else 'Scheduled fetch failed. Review the connection.'
            pull_id=None
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            latest=json.loads(db.execute('SELECT payload FROM input_schedules WHERE connection_id=?',(key,)).fetchone()[0])
            if latest['version']==schedule['version']:
                latest.update(last_status=status,last_pull_id=pull_id)
                db.execute('UPDATE input_schedules SET payload=? WHERE connection_id=?',(json.dumps(latest),key))
        results.append(latest)
        if len(results)>=20:break
    return results


def install_scheduler(api,workspaces,service):
    if workspaces is None or service is None:return
    from .platform_identity import COMPANY_ID
    from .company_workflows import schedule_authorized
    def check():
        if not workspaces.root.exists():return
        for path in workspaces.root.iterdir():
            if path.is_symlink() or not path.is_dir() or not COMPANY_ID.fullmatch(path.name) or not (path/'connections.sqlite3').is_file():continue
            workspace=workspaces.for_principal({'company_id':path.name})
            try:tick(workspace.connections,lambda owner:schedule_authorized(service,workspace,owner))
            except Exception:continue # fail closed; another company must still be checked
    def start():
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler=BackgroundScheduler(timezone='UTC')
        scheduler.add_job(check,'interval',minutes=5,id='company-input-captures',max_instances=1,coalesce=True)
        scheduler.start();api.state.input_scheduler=scheduler
    def stop():
        scheduler=getattr(api.state,'input_scheduler',None)
        if scheduler:scheduler.shutdown(wait=False)
    api.router.add_event_handler('startup',start);api.router.add_event_handler('shutdown',stop)

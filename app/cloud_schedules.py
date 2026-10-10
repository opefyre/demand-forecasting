"""Private alarm descriptors reusing original scheduled workflows, never cron in scratch."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import uuid
from zoneinfo import ZoneInfo


def metadata(workspace):
    path=workspace.path('cloud-schedules.json')
    return json.loads(path.read_text()) if path.exists() else {}


def save_metadata(workspace,value):
    path=workspace.path('cloud-schedules.json')
    path.write_text(json.dumps(value));path.chmod(0o600)


def record_source_owner(workspace,who,method,path):
    if method!='PUT' or not path.startswith('/connections/external-sources/') or path.endswith(('/permission','/credential')):return
    from .company_context import personal_owner
    if who['role']!='admin' or who['auth_kind']!='session':return
    value=metadata(workspace)
    value.setdefault('sources',{})[path.rsplit('/',1)[1]]=personal_owner(who)
    save_metadata(workspace,value)


def event_hash(workspace):
    from .notifications import collect_events
    return hashlib.sha256(json.dumps(collect_events(workspace),sort_keys=True).encode()).hexdigest()


def descriptors(workspace):
    from .company_workflows import recurring
    from .sales_conventions import period_start,shift_month,local_today,month_label
    now=datetime.now(timezone.utc);result=[]
    def add(key,owner,due,path,**body):
        company,issuer,subject=json.loads(owner)
        if company!=workspace.company_id or issuer!='https://forecast.vrolen.com':raise ValueError('Invalid schedule owner.')
        result.append({'id':key,'subject':subject,'due':int(due*1000),'method':'POST','path':path,'body':body})
    for row in workspace.connections.list():
        schedule=row.get('schedule')
        if row['archived'] or not schedule or not schedule['enabled']:continue
        with workspace.connections.db() as db:
            value=json.loads(db.execute('SELECT payload FROM input_schedules WHERE connection_id=?',(row['id'],)).fetchone()[0])
        add('input:'+row['id'],value['owner'],value['next_due'],'/connections/inputs/'+row['id']+'/schedule/check')
    store=recurring(workspace,None,None)
    with store.db() as db:rows=db.execute('SELECT id,actor,payload FROM recurring_forecasts').fetchall()
    for key,owner,payload in rows:
        value=json.loads(payload)
        if not value['enabled']:continue
        today=local_today(workspace.site['timezone'],now);month=period_start(today,value['basis'])
        threshold=month.to_pydatetime().date()+timedelta(days=value['day']-1)
        cycle=uuid.uuid5(uuid.NAMESPACE_URL,'recurring-cycle:'+key+':'+month_label(today,value['basis'])).hex
        with store.db() as db:exists=db.execute('SELECT 1 FROM recurring_cycles WHERE id=?',(cycle,)).fetchone()
        if exists:threshold=shift_month(month,1,value['basis']).to_pydatetime().date()+timedelta(days=value['day']-1)
        due=datetime.combine(threshold,datetime.min.time(),ZoneInfo(workspace.site['timezone'])).timestamp()
        add('monthly:'+key,owner,max(now.timestamp(),due),'/recurring-forecasts/'+key+'/check')
    value=metadata(workspace)
    from .live_sources import SOURCES
    for key,owner in value.get('sources',{}).items():
        state=workspace.live_sources.state(key)
        if not state.get('enabled') or key=='iran_cpi' and not state.get('permission_confirmed') or key=='servix' and not state.get('credential_configured'):continue
        stamp=state.get('last_attempt') or state.get('last_success')
        due=datetime.fromisoformat(stamp).timestamp()+SOURCES[key]['hours']*3600 if stamp else now.timestamp()
        if state.get('cooldown_until'):due=max(due,datetime.fromisoformat(state['cooldown_until']).timestamp())
        add('source:'+key,owner,due,'/connections/external-sources/'+key+'/refresh')
    if workspace.notifications.list() and value.get('events')!=event_hash(workspace):
        owners={workspace.notifications.raw(row['id'])['owner'] for row in workspace.notifications.list() if row['enabled']}
        for owner in owners:add('notifications:'+hashlib.sha256(owner.encode()).hexdigest()[:32],owner,now.timestamp(),'/notifications/check')
    if len(result)>200:raise ValueError('Too many active company schedules.')
    return {'company_id':workspace.company_id,'schedules':result}

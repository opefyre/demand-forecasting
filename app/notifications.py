"""Company-owned, consent-bound notification outbox. Never sends business files."""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import re
import sqlite3
import time
from typing import Literal
from urllib.parse import parse_qs, urlsplit
import uuid

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool
from .business_connections import ConnectorVault, ConnectionError

EVENTS = ('forecast_ready', 'forecast_failed', 'forecast_approved', 'inputs_ready', 'import_failed')
Event = Literal['forecast_ready','forecast_failed','forecast_approved','inputs_ready','import_failed']
MESSAGES = {
    'test': ('Notification connection test.', 'آزمایش اتصال اعلان.'),
    'forecast_ready': ('A forecast is ready for review.', 'یک پیش‌بینی آمادهٔ بررسی است.'),
    'forecast_failed': ('A forecast needs attention.', 'یک پیش‌بینی نیاز به بررسی دارد.'),
    'forecast_approved': ('A sales forecast has been approved.', 'یک پیش‌بینی فروش تأیید شده است.'),
    'inputs_ready': ('New connected inputs are ready for review.', 'داده‌های جدیدِ متصل آمادهٔ بررسی هستند.'),
    'import_failed': ('An input connection needs attention.', 'یک اتصال داده نیاز به بررسی دارد.'),
}
PATHS = {'test':'/settings','forecast_ready':'/demand','forecast_failed':'/demand',
         'forecast_approved':'/approvals','inputs_ready':'/data','import_failed':'/data'}


class NotificationError(ValueError): pass
class NotificationConflict(NotificationError): pass


class DestinationInput(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)
    name: str = Field(min_length=1,max_length=120)
    provider: Literal['slack','teams','telegram','whatsapp']
    destination: str = Field(min_length=1,max_length=120)
    language: Literal['en','fa'] = 'en'
    events: list[Event] = Field(default_factory=list,max_length=5)
    enabled: StrictBool = False
    confirmed: StrictBool = False
    webhook: SecretStr | None = Field(default=None,max_length=3000)
    token: SecretStr | None = Field(default=None,max_length=2000)
    recipient: SecretStr | None = Field(default=None,max_length=100)
    sender_id: SecretStr | None = Field(default=None,max_length=40)
    template: str = Field(default='',max_length=100)
    template_language: str = Field(default='en_US',max_length=20)
    eligible: StrictBool = False

    def public(self):
        value=self.model_dump(exclude={'webhook','token','recipient','sender_id','confirmed'})
        value['events']=list(dict.fromkeys(value['events']))
        return value


def private_config(body, old=None):
    """No arbitrary Apprise URL, template path, proxy or TLS controls from users."""
    private=dict(old or {})
    for key in ('webhook','token','recipient','sender_id'):
        value=getattr(body,key)
        if value is not None: private[key]=value.get_secret_value().strip()
    for value in private.values():
        if any(ord(c)<32 for c in value): raise NotificationError('Check notification credentials.')
    provider=body.provider
    if provider in {'slack','teams'}:
        webhook=private.get('webhook','')
        try: parsed=urlsplit(webhook);port=parsed.port
        except ValueError: raise NotificationError('Use a valid provider webhook.') from None
        if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or
                port not in {None,443} or parsed.fragment or any(c.isspace() for c in webhook)):
            raise NotificationError('Use a valid provider webhook.')
        if provider=='slack':
            if parsed.hostname!='hooks.slack.com' or parsed.query or not re.fullmatch(r'/services/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+',parsed.path):
                raise NotificationError('Use a Slack incoming webhook.')
        else:
            host=parsed.hostname.lower()
            query=parse_qs(parsed.query,keep_blank_values=True)
            if (not (host.endswith('.api.powerplatform.com') or host.endswith('.logic.azure.com')) or
                not re.fullmatch(r'/(?:powerautomate/automations/direct/(?:cu/[A-Za-z0-9_-]+/)?)?workflows/[A-Za-z0-9_-]+/triggers/manual/paths/invoke/?',parsed.path) or
                set(query)-{'api-version','sp','sv','sig'} or any(len(v)!=1 for v in query.values()) or not query.get('sig',[''])[0]):
                raise NotificationError('Use a Teams Workflows webhook, not a retired connector.')
        return {'webhook':webhook}
    if provider=='telegram':
        if not re.fullmatch(r'\d{5,20}:[A-Za-z0-9_-]{20,200}',private.get('token','')) or not re.fullmatch(r'-?\d{1,20}',private.get('recipient','')):
            raise NotificationError('Enter a Telegram bot token and one chat ID.')
        return {k:private[k] for k in ('token','recipient')}
    if (not body.eligible or not re.fullmatch(r'[a-z0-9_]{1,100}',body.template) or
            not re.fullmatch(r'[a-z]{2,3}(?:_[A-Z]{2})?',body.template_language) or
            not re.fullmatch(r'\d{5,30}',private.get('sender_id','')) or
            not re.fullmatch(r'\+[1-9]\d{7,14}',private.get('recipient','')) or
            not re.fullmatch(r'[A-Za-z0-9]{20,2000}',private.get('token',''))):
        raise NotificationError('Confirm WhatsApp eligibility, recipient consent and an approved one-variable template.')
    return {k:private[k] for k in ('token','recipient','sender_id')}


class NotificationVault(ConnectorVault):
    def __init__(self, root):
        super().__init__(root)
        self.service=self.service.replace('business-connections','notifications')


class Notifications:
    def __init__(self,path,*,vault=None,sender=None):
        self.path=path
        self.vault=vault or NotificationVault(path.parent)
        if sender is None:
            from .notification_sender import IsolatedSender
            sender=IsolatedSender()
        self.sender=sender
        with self.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS destinations(id TEXT PRIMARY KEY,config TEXT NOT NULL,version INTEGER NOT NULL,
                archived INTEGER NOT NULL,owner TEXT NOT NULL,secret_id TEXT NOT NULL,since REAL NOT NULL);
              CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY,destination_id TEXT NOT NULL,event_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL,record TEXT NOT NULL,UNIQUE(destination_id,event_key));
            ''')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    def raw(self,key,db=None):
        if db is None:
            with self.db() as conn:return self.raw(key,conn)
        row=db.execute('SELECT * FROM destinations WHERE id=?',(key,)).fetchone()
        if row is None:raise NotificationError('Notification connection not found.')
        return dict(row)

    def get(self,key):
        row=self.raw(key)
        return {'id':key,**json.loads(row['config']),'version':row['version'],'archived':bool(row['archived']),
                'credential_configured':True}

    def list(self,archived=False):
        with self.db() as db:keys=[r[0] for r in db.execute('SELECT id FROM destinations WHERE archived=0 OR ? ORDER BY rowid DESC',(archived,))]
        return [self.get(key) for key in keys]

    def secret(self,row):
        try:
            value=self.vault.get(row['secret_id'])
            if not value:raise ValueError()
            return json.loads(value)
        except Exception:raise NotificationError('Secure notification credentials are unavailable.') from None

    def cancel_pending(self,db,key):
        for row in db.execute('SELECT id,record FROM deliveries WHERE destination_id=?',(key,)).fetchall():
            record=json.loads(row['record'])
            if record['state']=='queued':
                record.update(state='cancelled',message='Connection settings or access changed.',finished_at=time.time())
                db.execute('UPDATE deliveries SET record=? WHERE id=?',(json.dumps(record),row['id']))

    def save(self,body,owner,key=None,version=0):
        if not body.confirmed:raise NotificationError('Confirm the destination and outbound notification permission.')
        if body.enabled and not body.events:raise NotificationError('Select at least one notification event.')
        key=key or uuid.uuid4().hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM destinations WHERE id=?',(key,)).fetchone()
            if (old['version'] if old else 0)!=version:raise NotificationConflict('Notification connection changed. Reload it before editing.')
            if old and old['archived']:raise NotificationConflict('Restore this notification connection before editing.')
            prior=self.secret(old) if old and json.loads(old['config'])['provider']==body.provider else None
            secret=private_config(body,prior)
            secret_id=uuid.uuid4().hex # Credentials are never overwritten under an in-flight version.
            try:self.vault.set(secret_id,json.dumps(secret))
            except Exception:raise NotificationError('Secure notification credentials could not be saved.') from None
            now=time.time();config=body.public()
            db.execute('INSERT OR REPLACE INTO destinations VALUES (?,?,?,?,?,?,?)',
                (key,json.dumps(config),version+1,0,owner,secret_id,now))
            self.cancel_pending(db,key)
        return self.get(key)

    def archive(self,key,version,archived,owner):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE');row=self.raw(key,db)
            if row['version']!=version:raise NotificationConflict('Notification connection changed. Reload it before editing.')
            config=json.loads(row['config']);config['enabled']=False # Restore never renews outbound consent.
            db.execute('UPDATE destinations SET config=?,version=version+1,archived=?,owner=?,since=? WHERE id=?',
                (json.dumps(config),int(archived),owner,time.time(),key))
            self.cancel_pending(db,key)
        return self.get(key)

    def delivery(self,key):
        with self.db() as db:row=db.execute('SELECT record FROM deliveries WHERE id=?',(key,)).fetchone()
        if not row:raise NotificationError('Notification delivery not found.')
        value=json.loads(row[0]);return {k:v for k,v in value.items() if k not in {'owner','fingerprint'}}

    def history(self,limit=100,offset=0,destination_id=None):
        with self.db() as db:
            clause=' WHERE destination_id=?' if destination_id else '';params=(destination_id,) if destination_id else ()
            total=db.execute('SELECT COUNT(*) FROM deliveries'+clause,params).fetchone()[0]
            rows=db.execute('SELECT id FROM deliveries'+clause+' ORDER BY rowid DESC LIMIT ? OFFSET ?',params+(limit,offset)).fetchall()
        return {'deliveries':[self.delivery(r[0]) for r in rows],'total':total,'limit':limit,'offset':offset}

    def queue(self,key,event,event_key,owner,*,resource=None,created=None,version=None,retry_of=None):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE');row=self.raw(key,db);config=json.loads(row['config'])
            if version is not None and row['version']!=version:raise NotificationConflict('Notification connection changed. Review it before sending.')
            if row['archived'] or (event!='test' and (not config['enabled'] or event not in config['events'])):
                raise NotificationError('This notification connection is paused or archived.')
            if created is not None and created<row['since']:return None # No surprise historical replay.
            fingerprint=hashlib.sha256(json.dumps([event,resource,retry_of],sort_keys=True).encode()).hexdigest()
            old=db.execute('SELECT id,fingerprint FROM deliveries WHERE destination_id=? AND event_key=?',(key,event_key)).fetchone()
            if old:
                if old['fingerprint']!=fingerprint:raise NotificationConflict('This notification request was used for different content.')
                return self.delivery(old['id'])
            recent=db.execute('SELECT record FROM deliveries WHERE destination_id=? ORDER BY rowid DESC LIMIT 10',(key,)).fetchall()
            if sum(json.loads(r[0])['created_at']>time.time()-60 for r in recent)>=5:
                raise NotificationConflict('Wait a minute before sending more notifications.')
            text=MESSAGES[event][config['language']=='fa']
            record={'id':uuid.uuid4().hex,'destination_id':key,'connection_version':row['version'],
                'name':config['name'],'destination':config['destination'],'provider':config['provider'],
                'event':event,'resource':resource,'state':'queued','message':'Waiting to send.',
                'text':text,'path':PATHS[event],'created_at':time.time(),'started_at':None,'finished_at':None,
                'retry_of':retry_of,'owner':owner}
            db.execute('INSERT INTO deliveries VALUES (?,?,?,?,?)',(record['id'],key,event_key,fingerprint,json.dumps(record)))
        return self.delivery(record['id'])

    def retry(self,key,request_id,version,owner,duplicate_confirmed=False):
        old=self.delivery(key)
        if old['state'] not in {'rejected','unknown','cancelled'}:raise NotificationConflict('Only unsuccessful notifications can be retried.')
        if old['state']=='unknown' and not duplicate_confirmed:
            raise NotificationError('Delivery is uncertain. Confirm the destination was checked before retrying; a duplicate is possible.')
        return self.queue(old['destination_id'],old['event'],'retry:'+request_id,owner,resource=old['resource'],version=version,retry_of=key)

    def drain(self,authorized,origin,limit=10):
        results=[]
        with self.db() as db:keys=[r[0] for r in db.execute('SELECT id FROM deliveries ORDER BY rowid')]
        for key in keys:
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE');record=json.loads(db.execute('SELECT record FROM deliveries WHERE id=?',(key,)).fetchone()[0])
                if record['state']=='sending' and record['started_at']<time.time()-90:
                    record.update(state='unknown',message='Delivery is uncertain. Check the destination before retrying.',finished_at=time.time())
                    db.execute('UPDATE deliveries SET record=? WHERE id=?',(json.dumps(record),key));continue
                if record['state']!='queued':continue
                row=self.raw(record['destination_id'],db);config=json.loads(row['config'])
                try:allowed=authorized(record['owner']) is True
                except Exception:allowed=False
                if row['archived'] or row['version']!=record['connection_version'] or not allowed:
                    record.update(state='cancelled',message='Connection settings or access changed.',finished_at=time.time())
                    db.execute('UPDATE deliveries SET record=? WHERE id=?',(json.dumps(record),key));continue
                record.update(state='sending',started_at=time.time())
                db.execute('UPDATE deliveries SET record=? WHERE id=?',(json.dumps(record),key))
            try:
                secret=self.secret(row)
                # Recheck consent and live admin membership immediately before network I/O.
                latest=self.raw(row['id'])
                if latest['version']!=row['version'] or latest['archived'] or authorized(record['owner']) is not True:
                    status='cancelled'
                else:status=self.sender.send(config,secret,record['text'],origin+record['path'])
            except NotificationError:status='rejected'
            except Exception:status='unknown' # Never expose SDK exceptions, URLs or tokens.
            if status not in {'accepted','rejected','unknown','cancelled'}:status='unknown'
            message={'accepted':'Accepted by provider. Recipient delivery is not confirmed.',
                'rejected':'Not accepted. Check connection settings and provider access.',
                'unknown':'Delivery is uncertain. Check the destination before retrying.',
                'cancelled':'Connection settings or access changed.'}[status]
            record.update(state=status,message=message,finished_at=time.time())
            with self.db() as db:db.execute('UPDATE deliveries SET record=? WHERE id=?',(json.dumps(record),key))
            results.append(self.delivery(key))
            if len(results)>=limit:break
        return results


def timestamp(value):
    if isinstance(value,(int,float)):return float(value)
    return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()


def collect_events(workspace):
    """Observe existing ledgers, not new model calculations or hidden data exports."""
    events=[];jobs=workspace.jobs.list(limit=None)
    groups={g['id']:g for g in workspace.jobs.list_groups(limit=None)}
    grouped={}
    for job in jobs:
        group=job['payload'].get('forecast_group_id')
        if group in groups:grouped.setdefault(group,[]).append(job)
        else:grouped['job:'+job['id']]=[job]
    for key,rows in grouped.items():
        if any(r['state'] in {'queued','running','publishing'} for r in rows):continue
        # Retried methods supersede earlier failed attempts of that method.
        latest={}
        for row in sorted(rows,key=lambda r:r['created_at']):latest[row['payload'].get('method',row['id'])]=row
        current=list(latest.values());states={r['state'] for r in current}
        if states=={'succeeded'}:event='forecast_ready'
        elif states & {'failed','interrupted'}:event='forecast_failed'
        else:continue
        ended=max(r['updated_at'] for r in current)
        events.append(dict(event=event,key=key+':'+event+':'+','.join(sorted(r['id'] for r in current)),resource={'kind':'forecast','id':key},created=ended))
    for row in workspace.releases.list():
        if row['state']!='approved' or row.get('demo_only'):continue
        record=workspace.releases.get(row['id'])
        events.append(dict(event='forecast_approved',key='release:'+row['id'],resource={'kind':'release','id':row['id']},created=timestamp(record['approved_at'])))
    for row in workspace.connections.list(True):
        # Query the full receipt ledger rather than its 20-row display limit.
        with workspace.connections.db() as db:pulls=[dict(r) for r in db.execute('SELECT * FROM pulls WHERE connection_id=?',(row['id'],))]
        for pull in pulls:
            if pull['state']=='ready' and pull['candidate_id'] and pull['message']!='No changes':
                event='inputs_ready';key='capture:'+pull['candidate_id']
            elif pull['state']=='failed':event='import_failed';key='pull:'+pull['id']
            else:continue
            events.append(dict(event=event,key=key,resource={'kind':'input_connection','id':row['id']},created=pull['started']))
    return events


def tick(workspace,authorized,origin):
    store=workspace.notifications
    events=None
    for destination in store.list():
        if not destination['enabled']:continue
        row=store.raw(destination['id'])
        try:allowed=authorized(row['owner']) is True
        except Exception:allowed=False
        if not allowed:continue
        if events is None:events=collect_events(workspace)
        for event in events:
            if event['event'] not in destination['events']:continue
            try:store.queue(row['id'],event['event'],event['key'],row['owner'],resource=event['resource'],created=event['created'],version=row['version'])
            except NotificationError:continue
    return store.drain(authorized,origin)

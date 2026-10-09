"""Monthly draft orchestration. Reuses reviewed inputs, APScheduler and forecast jobs."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import sqlite3
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt
from persiantools.jdatetime import JalaliDate
from .monthly_refresh import StartUpdate, UpdateStep, principal_actor
from .input_refresh import history_groups, repeat_review
from .input_review import digest
from .sales_conventions import local_today, period_start, shift_month, month_label


class RecurringConfig(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    run_id:str=Field(min_length=1,max_length=80)
    request_id:str=Field(min_length=8,max_length=100)
    day:StrictInt=Field(ge=1,le=28)
    months:StrictInt=Field(ge=1,le=24)
    method:str=Field(default='recommended',min_length=1,max_length=100)
    enabled:StrictBool=False
    confirmed:StrictBool=False
    connection_id:str|None=None


class RecurringForecasts:
    def __init__(self,path,monthly,folders=None,authorized=None):
        self.path,self.monthly,self.folders=path,monthly,folders
        self.authorized=authorized or (lambda actor:True)
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS recurring_forecasts (id TEXT PRIMARY KEY, actor TEXT, payload TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS recurring_cycles (id TEXT PRIMARY KEY, schedule_id TEXT, payload TEXT)')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            with db:yield db
        finally:db.close()

    def config(self,key,actor=None):
        with self.db() as db:row=db.execute('SELECT actor,payload FROM recurring_forecasts WHERE id=?',(key,)).fetchone()
        if not row or actor is not None and actor!=row[0]:raise ValueError('This monthly schedule is not available to this user.')
        return row[0],json.loads(row[1])

    def save(self,actor,payload):
        if payload.confirmed is not True:raise ValueError('Confirm automatic draft calculation and the review steps first.')
        run,source=self.monthly.baseline(payload.run_id)
        if source['sources'].get('future'):
            raise ValueError('Use history-only baseline inputs. External factors need fresh, separately reviewed future assumptions.')
        from .sales_groups import series_column
        if not series_column(source['settings']) or not all(source['settings'].get(k) for k in ('customer_col','sku_col')):
            raise ValueError('Map customers and products before setting a monthly schedule.')
        from .forecast_engine import _model_specs
        if payload.method not in {'recommended','seasonal','trend','intermittent','driver'}|{'model:'+s.name for s in _model_specs('deep')}:
            raise ValueError('Choose an available forecasting method.')
        if payload.connection_id:
            folder=self.folders.get_config(payload.connection_id) if self.folders else None
            if not folder or folder['dataset_id']!=source['id'] or set(folder['files'])!={'history'}:
                raise ValueError('Choose a history-only connection for this baseline.')
        key=uuid.uuid5(uuid.NAMESPACE_URL,'recurring:'+actor+':'+payload.run_id).hex
        value={'id':key,'run_id':payload.run_id,'run_sha256':digest(run),'dataset_id':source['id'],
            'dataset_sha256':digest(source),'name':source['name'],'classification':source['classification'],
            'basis':source['settings'].get('month_basis','gregorian'),'day':payload.day,
            'months':payload.months,'method':payload.method,'enabled':payload.enabled,'connection_id':payload.connection_id,
            'request_id':payload.request_id,'confirmed_at':datetime.now(timezone.utc).isoformat()}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT payload FROM recurring_forecasts WHERE id=?',(key,)).fetchone()
            if old:
                previous=json.loads(old[0])
                if previous['request_id']==payload.request_id:
                    if any(previous.get(k)!=value[k] for k in value if k!='confirmed_at'):raise ValueError('Retry settings changed.')
                    return previous
            db.execute('INSERT OR REPLACE INTO recurring_forecasts VALUES (?,?,?)',(key,actor,json.dumps(value)))
        return value

    def listing(self,actor):
        with self.db() as db:
            rows=db.execute('SELECT payload FROM recurring_forecasts WHERE actor=? ORDER BY rowid DESC',(actor,)).fetchall()
            result=[]
            for (payload,) in rows:
                config=json.loads(payload)
                latest=db.execute('SELECT payload FROM recurring_cycles WHERE schedule_id=? ORDER BY rowid DESC LIMIT 1',(config['id'],)).fetchone()
                cycle=json.loads(latest[0]) if latest else None
                if cycle and cycle.get('update_id') and cycle['state']=='calculating':
                    try:
                        session=self.monthly.get(cycle['update_id'],actor)
                        if session['stage']!='calculating':cycle={**cycle,'state':'review'}
                        else:
                            job=self.monthly.jobs.get(session['job_id'])
                            if job['state']=='succeeded':cycle={**cycle,'state':'review'}
                            elif job['state'] in {'failed','cancelled','interrupted'}:
                                cycle={**cycle,'state':'attention','attention':'Calculation stopped. Open the update to review and retry.'}
                    except (ValueError,KeyError):
                        cycle={**cycle,'state':'attention','attention':'Saved update or calculation is unavailable. Review the saved inputs before retrying.'}
                result.append({**config,'cycle':cycle})
            return result

    def latest_history(self,config):
        original=self.monthly.datasets.get(config['dataset_id'])
        if digest(original)!=config['dataset_sha256']:raise ValueError('Original sales settings changed. Review the schedule again.')
        if config['connection_id']:
            self.folders.check(config['connection_id'])
            connection=next(c for c in self.folders.list() if c['id']==config['connection_id'])
            latest=connection['checks'][0]
            if latest['state']=='failed':raise ValueError('Sales connection needs attention. Review it in Data.')
            candidate=self.folders.candidate(latest.get('candidate_id') or latest['id'])
            if not candidate.get('accepted_dataset_id'):raise ValueError('New sales data needs review in Data before calculation.')
            chosen=self.monthly.datasets.get(candidate['accepted_dataset_id'])
        else:
            chosen=original
            for source in self.monthly.datasets.list():
                if source.get('scenario_provenance') or source['sources'].get('operations'):continue
                current,seen=source,set()
                while current['id']!=original['id'] and current.get('parent_dataset_id') and current['id'] not in seen:
                    seen.add(current['id']);current=self.monthly.datasets.get(current['parent_dataset_id'])
                if current['id']==original['id']:
                    chosen=source;break
        if chosen['sources'].get('future'):raise ValueError('New inputs include future factors. Review them manually before using this schedule.')
        return original,chosen

    def check(self,key,actor=None,now=None):
        owner,config=self.config(key,actor)
        if not config['enabled']:return {'state':'paused'}
        today=local_today('Asia/Tehran',now)
        day=JalaliDate(today).day if config['basis']=='jalali' else today.day
        period=month_label(today,config['basis'])
        if day<config['day']:return {'state':'not_due','period':period}
        cycle_id=uuid.uuid5(uuid.NAMESPACE_URL,'recurring-cycle:'+key+':'+period).hex
        with self.db() as db:
            # A persisted cycle makes retries/restarts and concurrent checks idempotent.
            db.execute('BEGIN IMMEDIATE')
            found=db.execute('SELECT payload FROM recurring_cycles WHERE id=?',(cycle_id,)).fetchone()
            value=json.loads(found[0]) if found else {'id':cycle_id,'period':period,'state':'checking'}
            if value.get('update_id'):
                try:
                    session=self.monthly.get(value['update_id'],owner)
                    value.update(state='calculating' if session['stage']=='calculating' else 'review',stage=session['stage'],attention=None)
                    if session['stage']=='calculating':
                        job=self.monthly.jobs.get(session['job_id'])
                        if job['state']=='succeeded':
                            session=self.monthly.step(session['id'],owner,UpdateStep(revision=session['revision'],action='calculated',request_id=cycle_id+':completed'))
                            value.update(state='review',stage=session['stage'])
                        elif job['state'] in {'failed','cancelled','interrupted'}:
                            value.update(state='attention',attention='Calculation stopped. Open the update to review and retry.')
                except (ValueError,KeyError):
                    value.update(state='attention',attention='Saved update or calculation is unavailable. Review the saved inputs before retrying.')
            else:
                try:
                    if not self.authorized(owner):raise ValueError('Schedule owner no longer has administrator access. Review authorization.')
                    run,_=self.monthly.baseline(config['run_id'])
                    if digest(run)!=config['run_sha256']:raise ValueError('Original forecast changed. Review the schedule again.')
                    original,source=self.latest_history(config)
                    groups,_,_=history_groups(self.monthly.datasets,source)
                    periods={k[-1] for k in groups}
                    expected=str(shift_month(period_start(today,config['basis']),-1,config['basis']).date())
                    if not periods or max(periods)!=expected:
                        raise ValueError('Sales history must finish at the latest completed planning month. Review missing or unfinished months in Data.')
                    scopes={k[:-1] for k in groups}
                    if any((*scope,expected) not in groups for scope in scopes):
                        raise ValueError('Some customer/products have no latest-month sales record. Review missing records or explicit zero sales in Data.')
                    changes=repeat_review(self.monthly.datasets,original['id'],source['sources'],source['settings'],source['classification'])
                    session=self.monthly.start(owner,StartUpdate(run_id=config['run_id'],request_id=cycle_id))
                    if session['stage']=='forecast' and session.get('dataset_id')!=source['id']:
                        raise ValueError('This update already chose different sales inputs. Open it before recalculating.')
                    if session['stage']=='history':
                        session=self.monthly.step(session['id'],owner,UpdateStep(revision=session['revision'],action='history',dataset_id=source['id'],reviewed=True,request_id=cycle_id+':history'))
                    if session['stage']=='forecast':
                        session=self.monthly.step(session['id'],owner,UpdateStep(revision=session['revision'],action='calculate',months=config['months'],method=config['method'],reviewed=True,request_id=cycle_id+':calculate'))
                    value.update(update_id=session['id'],dataset_id=session.get('dataset_id',source['id']),state='calculating',stage=session['stage'],
                        changes=changes,attention=None,note='Baseline draft only. Review external factors, current orders and changes before export.')
                except (ValueError,KeyError) as exc:value.update(state='attention',attention=str(exc))
                except Exception:value.update(state='attention',attention='Could not prepare this draft. Review the update or connection before retrying.')
            value['checked_at']=datetime.now(timezone.utc).isoformat()
            db.execute('INSERT OR REPLACE INTO recurring_cycles VALUES (?,?,?)',(cycle_id,key,json.dumps(value,allow_nan=False)))
        return value

    def tick(self):
        with self.db() as db:keys=[r[0] for r in db.execute('SELECT id FROM recurring_forecasts')]
        for key in keys:
            try:self.check(key)
            except Exception:pass # One unavailable schedule must not stop other owners' checks.


def install_recurring_forecasts(app,service,scheduler):
    router=APIRouter(prefix='/api/recurring-forecasts')
    def safe(work):
        try:return work()
        except (ValueError,KeyError) as exc:raise HTTPException(400,str(exc)) from exc
    @router.get('')
    def listing(request:Request):return {'schedules':service.listing(principal_actor(request))}
    @router.post('')
    def save(payload:RecurringConfig,request:Request):return safe(lambda:service.save(principal_actor(request),payload))
    @router.post('/{key}/check')
    def check(key:str,request:Request):return safe(lambda:service.check(key,principal_actor(request)))
    app.include_router(router)
    @app.on_event('startup')
    def restore():scheduler.add_job(service.tick,'interval',minutes=10,id='monthly-forecast-drafts',replace_existing=True,max_instances=1,coalesce=True)

"""Stage approved local factor exports; schedules never approve data or run models."""
from copy import deepcopy
import json
from pathlib import Path
import time
import uuid

from fastapi import APIRouter, HTTPException

from .folder_inputs import FolderInputs, EXTENSIONS
from .inventory import raw_table
from .factor_imports import review_import, save_import, freshness


class FactorFolders(FolderInputs):
    def __init__(self,path,datasets,roots,factors):
        super().__init__(path,datasets,roots)
        self.factors=factors

    def factor(self,snapshot_id):
        snapshot=self.factors.get(snapshot_id)
        if snapshot.get('kind')!='imported_observations':
            raise ValueError('Connect a reviewed imported factor, not a public-source snapshot.')
        return snapshot

    def latest(self,factor_id):
        return next((s for s in self.factors.list() if s['factor_id']==factor_id),None)

    def info(self,snapshot_id):
        snapshot=self.factor(snapshot_id)
        try: config=self.get_config(snapshot['factor_id'])
        except ValueError: config=None
        return {'connection':config,'approved_roots':[str(p) for p in self.roots]}

    def configure(self,snapshot_id,payload):
        if payload.get('confirmed_local_access') is not True:
            raise ValueError('Confirm permission to read this factor export.')
        snapshot=self.factor(snapshot_id)
        folder=self._folder(payload.get('path',''))
        name=payload.get('filename','')
        if (not isinstance(name,str) or Path(name).name!=name or any(c in name for c in '*?[]\\')
                or Path(name).suffix.lower() not in EXTENSIONS):
            raise ValueError('Choose one exact CSV, TSV, JSON or Excel filename.')
        minutes=payload.get('minutes',0)
        if type(minutes) is not int or minutes not in {0,15,60,360,1440}:
            raise ValueError('Choose a supported refresh interval.')
        source,content=self.datasets.source(snapshot['source']['id'])
        imported=snapshot['import_config']
        columns=raw_table(source['name'],content,imported.get('sheet'),imported.get('header_row') or 1)['columns']
        config={'id':snapshot['factor_id'],'snapshot_id':snapshot['id'],'path':str(folder),
                'files':{'factor_observations':name},'minutes':minutes,'enabled':minutes>0,
                'columns':columns,'created_at':time.time(),'configuration_id':uuid.uuid4().hex}
        with self.connect() as db,self.factors.lock:
            if self.latest(snapshot['factor_id'])['id']!=snapshot_id:
                raise ValueError('Connect the latest reviewed factor version.')
            db.execute('INSERT OR REPLACE INTO folder_inputs VALUES (?,?)',(config['id'],json.dumps(config)))
        return config

    def check(self,key):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT config FROM folder_inputs WHERE id=?',(key,)).fetchone()
            if not row: raise ValueError('Connect a factor export first.')
            config=json.loads(row[0]);detail={};state='failed'
            try:
                parent=self.factor(config['snapshot_id'])
                if self.latest(key)['id']!=parent['id']:
                    raise ValueError('The factor was updated elsewhere. Reconnect its latest reviewed version.')
                name,content,sha=self._read_files(config)['factor_observations']
                if len(content)>10*1024*1024:
                    raise ValueError('Use a factor export smaller than 10 MB.')
                imported=parent['import_config']
                columns=raw_table(name,content,imported.get('sheet'),imported.get('header_row') or 1)['columns']
                if columns!=config['columns']:
                    raise ValueError('Column headings changed. Import and review the new mapping before reconnecting.')
                previous=db.execute("SELECT id,detail FROM folder_checks WHERE connector_id=? AND state='ready' ORDER BY checked DESC,rowid DESC LIMIT 1",(key,)).fetchone()
                prior=json.loads(previous[1]) if previous else None
                if parent.get('sha256')==sha:
                    state='unchanged';detail={'message':'File matches the latest reviewed version.',
                        'accepted_snapshot_id':parent['id']}
                elif prior and prior['sha256']==sha and prior['configuration_id']==config['configuration_id']:
                    state='unchanged';detail={'message':'No new file contents.','candidate_id':previous[0]}
                else:
                    source=self.datasets.upload(name,content,'factor_observations')
                    payload={**deepcopy(imported),'header_row':imported.get('header_row') or 1,
                             'source_id':source['id'],'parent_id':parent['id']}
                    report=review_import(self.datasets,payload)
                    if report['issue_count']:
                        detail={'message':f"Fix {report['issue_count']} row errors before reviewing.",
                                'issues':report['issues'],'issue_count':report['issue_count']}
                    else:
                        state='ready';detail={'message':'New factor values need review.','sha256':sha,
                            'configuration_id':config['configuration_id'],'parent_id':parent['id'],
                            'payload':payload,'review_token':report['review_token']}
                config.update(status=state,message=detail['message'],checked_at=time.time())
            except (ValueError,OSError,KeyError,TypeError) as exc:
                detail={'message':str(exc)[:500]}
                config.update(status='failed',message=detail['message'],checked_at=time.time())
            identifier=uuid.uuid4().hex
            db.execute('INSERT INTO folder_checks VALUES (?,?,?,?,?)',
                (identifier,key,config['checked_at'],state,json.dumps(detail,allow_nan=False)))
            db.execute('UPDATE folder_inputs SET config=? WHERE id=?',(json.dumps(config),key))
        return {'id':identifier,'connector_id':key,'state':state,**detail}

    def scheduled_check(self,key):
        if not self.get_config(key)['enabled']:return None
        return self.check(key)

    def current_candidate(self,snapshot_id):
        key=self.factor(snapshot_id)['factor_id']
        checked=self.check(key)
        if checked['state']=='failed':raise ValueError(checked['message'])
        if checked.get('accepted_snapshot_id'):return checked
        return self.candidate(checked['candidate_id'] if checked['state']=='unchanged' else checked['id'])

    def review(self,snapshot_id):
        candidate=self.current_candidate(snapshot_id)
        if candidate.get('accepted_snapshot_id'):
            return {'saved':{k:v for k,v in self.factor(candidate['accepted_snapshot_id']).items() if k!='points'}}
        report=review_import(self.datasets,candidate['payload'])
        if report['issue_count']:raise ValueError('Fix row errors before reviewing.')
        parent=self.factor(candidate['parent_id'])
        old={(p['period'],p['available_at']):p['value'] for p in parent['points']}
        new={(p['period'],p['available_at']):p['value'] for p in report['points']}
        report['changes']={'new_releases':len(new.keys()-old.keys()),
            'removed_releases':len(old.keys()-new.keys()),
            'changed_values':sum(new[k]!=old[k] for k in old.keys()&new.keys())}
        report['freshness']=freshness({'summary':report['summary'],'frequency':report['config']['frequency']})
        changed=[p for p in report['points'] if old.get((p['period'],p['available_at']))!=p['value']]
        same=[p for p in report['points'] if old.get((p['period'],p['available_at']))==p['value']]
        removed=sorted(old.keys()-new.keys())
        shown=[{**p,'previous_value':old.get((p['period'],p['available_at']))} for p in (changed+same)[:30]]
        return {'candidate_id':candidate['id'],'review':{**report,'points':shown,
            'removed_releases':[{'period':p,'available_at':a} for p,a in removed[:30]]}}

    def accept(self,snapshot_id,payload):
        if payload.get('reviewed') is not True:
            raise ValueError('Review the factor values before saving.')
        key=self.factor(snapshot_id)['factor_id']
        # Exact retries recover the acknowledged immutable version even after later checks.
        candidate=self.candidate(payload.get('candidate_id',''))
        if candidate['connector_id']!=key or payload.get('review_token')!=candidate['review_token']:
            raise ValueError('Review these exact connected inputs again.')
        if candidate.get('accepted_snapshot_id'):
            return self.factor(candidate['accepted_snapshot_id'])
        request_id=str(uuid.uuid5(uuid.NAMESPACE_URL,'factor-folder:'+candidate['id']))
        identifier=uuid.uuid5(uuid.NAMESPACE_URL,'demand-factor-import:'+request_id).hex
        with self.factors.lock:
            latest=self.latest(key)
            published=latest['id']==identifier and latest.get('save_fingerprint')==candidate['review_token']
        # A crash after publication can leave the file connection unacknowledged.
        # Recover that exact saved version without treating it as an unrelated update.
        if not published:
            current=self.current_candidate(snapshot_id)
            if current['id']!=candidate['id']:
                raise ValueError('The export changed after review. Check and review its new values.')
        with self.connect() as db,self.factors.lock:
            db.execute('BEGIN IMMEDIATE')
            record=db.execute('SELECT config FROM folder_inputs WHERE id=?',(key,)).fetchone()
            config=json.loads(record[0]) if record else {}
            if config.get('configuration_id')!=candidate['configuration_id']:
                raise ValueError('The connection changed. Review its inputs again.')
            if self.latest(key)['id']!=candidate['parent_id']:
                # Recover publication-before-acknowledgment using its deterministic ID.
                latest=self.latest(key)
                if latest['id']!=identifier or latest.get('save_fingerprint')!=candidate['review_token']:
                    raise ValueError('The factor changed after review. Reconnect its latest version.')
                saved=latest
            else:
                # Re-read the actual file inside the acceptance transaction, not just cached state.
                if self._read_files(config)['factor_observations'][2]!=candidate['sha256']:
                    raise ValueError('The export changed after review. Review it again.')
                saved=save_import(self.datasets,self.factors,{**candidate['payload'],'reviewed':True,
                    'review_token':candidate['review_token'],
                    'request_id':request_id})
            detail={k:v for k,v in candidate.items() if k not in ('id','connector_id','checked')}
            detail['accepted_snapshot_id']=saved['id']
            db.execute('UPDATE folder_checks SET detail=? WHERE id=?',(json.dumps(detail),candidate['id']))
            config.update(snapshot_id=saved['id'],status='unchanged',message='Reviewed factor saved. Forecasts unchanged.')
            db.execute('UPDATE folder_inputs SET config=? WHERE id=?',(json.dumps(config),key))
        return saved


def install_factor_folders(app,store,scheduler, *, allow_schedule=lambda: True):
    router=APIRouter(prefix='/api/integrations/factor-folders')
    def schedule(config):
        key='factor-folder-'+config['id']
        if scheduler.get_job(key):scheduler.remove_job(key)
        if config['enabled'] and config['minutes']:
            scheduler.add_job(store.scheduled_check,'interval',minutes=config['minutes'],
                args=[config['id']],id=key,max_instances=1,coalesce=True)

    @app.on_event('startup')
    def restore():
        if not allow_schedule():return
        with store.connect() as db:
            configs=[json.loads(row[0]) for row in db.execute('SELECT config FROM folder_inputs')]
        for config in configs:schedule(config)

    @router.get('/{snapshot_id}')
    def info(snapshot_id:str):
        try:return store.info(snapshot_id)
        except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/{snapshot_id}')
    def configure(snapshot_id:str,payload:dict):
        try:
            config=store.configure(snapshot_id,payload);schedule(config);return config
        except (ValueError,OSError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/{snapshot_id}/enabled')
    def enabled(snapshot_id:str,payload:dict):
        if type(payload.get('enabled')) is not bool:raise HTTPException(400,'Choose pause or resume.')
        try:
            config=store.set_enabled(store.factor(snapshot_id)['factor_id'],payload['enabled']);schedule(config);return config
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/{snapshot_id}/review')
    def review(snapshot_id:str):
        try:return store.review(snapshot_id)
        except (ValueError,OSError,TypeError,KeyError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/{snapshot_id}/accept')
    def accept(snapshot_id:str,payload:dict):
        try:
            saved=store.accept(snapshot_id,payload)
            return {k:v for k,v in saved.items() if k!='points'}
        except (ValueError,OSError,TypeError,KeyError) as exc:raise HTTPException(400,str(exc)) from exc

    app.include_router(router)

"""Local order exports staged for human review, never silently accepted."""
import json
import time
from copy import deepcopy
from pathlib import Path
from fastapi import APIRouter, HTTPException
from .folder_inputs import FolderInputs, EXTENSIONS
from .sales_demand import import_rows
from .inventory import raw_table, inventory_preview
from .order_reuse import compatible
from .sales_api import run_hash


class OrderFolders(FolderInputs):
    def __init__(self, path, sources, roots, orders, load_run=None):
        super().__init__(path, sources, roots)
        self.orders = orders
        self.load_run = load_run

    def choices(self, run_id):
        if not self.load_run: return []
        target = self.load_run(run_id)
        with self.connect() as db:
            configs=[json.loads(r[0]) for r in db.execute('SELECT config FROM folder_inputs')]
        return [{'id':c['id'],'name':self.load_run(c['run_id']).get('name') or c['run_id'],
                 'filename':c['files']['orders']} for c in configs
                if c['run_id']!=run_id and self.orders.list(c['run_id'])
                and compatible(self.load_run(c['run_id']),target)]

    def reuse(self, run_id, source_id):
        if source_id not in {c['id'] for c in self.choices(run_id)}:
            raise ValueError('Choose a connection for the same customers, products, units and data type.')
        config=deepcopy(self.get_config(source_id))
        # Each forecast can pause/change its own connection independently.
        config.update(id=run_id,run_id=run_id,source_run_id=source_id,
                      minutes=0,enabled=False,created_at=time.time())
        for key in ('candidate','status','message','checked_at'):config.pop(key,None)
        with self.connect() as db:
            if db.execute('SELECT 1 FROM folder_inputs WHERE id=?',(run_id,)).fetchone():
                raise ValueError('This forecast already has a connection. Change it or use Refresh & review.')
            db.execute('INSERT INTO folder_inputs VALUES (?,?)',(run_id,json.dumps(config)))
        return config

    def configure(self, run_id, payload):
        if payload.get('confirmed_local_access') is not True:
            raise ValueError('Confirm permission to read this order export.')
        versions = self.orders.list(run_id)
        if not versions: raise ValueError('Import and review an order file first.')
        base = versions[0]
        proof = next((p for p in base['evidence'] if p.get('role') == 'orders'), None)
        if not proof: raise ValueError('Import and save an order file to establish its column mapping first.')
        folder = self._folder(payload.get('path', ''))
        name = payload.get('filename', '')
        if not isinstance(name,str) or Path(name).name != name or any(c in name for c in '*?[]\\') or Path(name).suffix.lower() not in EXTENSIONS:
            raise ValueError('Choose one exact CSV, TSV, JSON or Excel filename.')
        minutes = payload.get('minutes',0)
        if type(minutes) is not int or minutes not in {0,15,60,360,1440}:
            raise ValueError('Choose a supported refresh interval.')
        source, content = self.datasets.source(proof['source']['id'])
        columns = raw_table(source['name'],content,proof['sheet'],proof['header_row'])['columns']
        config = dict(id=run_id, run_id=run_id, path=str(folder), files={'orders':name},
            minutes=minutes, enabled=minutes>0, mapping=proof['mapping'], sheet=proof['sheet'],
            header_row=proof['header_row'], columns=columns, created_at=time.time())
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO folder_inputs VALUES (?,?)',(run_id,json.dumps(config)))
        return config

    def check(self, key):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record=db.execute('SELECT config FROM folder_inputs WHERE id=?',(key,)).fetchone()
            if not record: raise ValueError('Connect an order export first.')
            config=json.loads(record[0])
            try:
                name,content,digest=self._read_files(config)['orders']
                if len(content)>10*1024*1024: raise ValueError('Use an order export smaller than 10 MB.')
                columns=raw_table(name,content,config['sheet'],config['header_row'])['columns']
                if columns!=config['columns']:
                    raise ValueError('Column headings changed. Import and review the new mapping before reconnecting.')
                previous=config.get('candidate')
                if previous and previous['sha256']==digest:
                    candidate=previous
                else:
                    source=self.datasets.upload(name,content,'sales_orders')
                    mapping={k:config[k] for k in ('mapping','sheet','header_row')}
                    mapping['source_id']=source['id']
                    rows,_=import_rows(self.datasets,'orders',mapping)
                    if not rows: raise ValueError('Empty export: review an empty order book manually before replacing all orders.')
                    candidate={'sha256':digest,'import':mapping,'rows':len(rows)}
                config.update(candidate=candidate,status='ready',message='Order export ready for review.')
            except (ValueError,OSError,KeyError,TypeError) as exc:
                config.update(status='failed',message=str(exc))
            config['checked_at']=time.time()
            db.execute('UPDATE folder_inputs SET config=? WHERE id=?',(json.dumps(config),key))
        return config

    def review(self, key):
        config=self.check(key)
        if config['status']!='ready': raise ValueError(config['message'])
        versions=self.orders.list(key)
        source_id=config.get('source_run_id',key)
        source_versions=self.orders.list(source_id)
        if not source_versions: raise ValueError('Saved orders are unavailable.')
        origin=source_versions[0]
        if self.load_run:
            base_run=self.load_run(origin['inputs']['run_id'])
            if next((e.get('run_sha256') for e in origin['evidence'] if 'run_sha256' in e),None)!=run_hash(base_run):
                raise ValueError('The source forecast changed. Review its orders again.')
            if source_id!=key and not compatible(base_run,self.load_run(key)):
                raise ValueError('The forecast scope changed. Reconnect matching customers and products.')
        base=versions[0] if versions else origin
        mapping=dict(config['candidate']['import'])
        source,content=self.datasets.source(mapping['source_id'])
        mapping.update(_source=source,_preview=inventory_preview(source['name'],content,mapping['sheet'],mapping['header_row']))
        return {'base_snapshot_id':base['id'] if versions else None,
                'inputs':{**base['inputs'],'run_id':key,'reviewed':False,'note':''},
                'order_refresh_source':{'snapshot_id':origin['id'],'sha256':origin['sha256']},
                'imports':{'orders':mapping},'order_mode':'replace'}


def install_order_folders(app, store, scheduler, *, allow_schedule=lambda: True):
    router=APIRouter(prefix='/api/integrations/order-folders')

    def schedule(config):
        key='order-folder-'+config['id']
        if scheduler.get_job(key): scheduler.remove_job(key)
        if config['enabled'] and config['minutes']:
            scheduler.add_job(store.check,'interval',minutes=config['minutes'],args=[config['id']],
                id=key,max_instances=1,coalesce=True)

    @app.on_event('startup')
    def restore():
        if not allow_schedule():return
        with store.connect() as db:
            configs=[json.loads(row[0]) for row in db.execute('SELECT config FROM folder_inputs')]
        for config in configs: schedule(config)

    @router.get('/{run_id}')
    def info(run_id:str):
        try: config=store.get_config(run_id)
        except ValueError: config=None
        try:choices=store.choices(run_id)
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
        return {'connection':config,'approved_roots':[str(p) for p in store.roots],'choices':choices}

    @router.post('/{run_id}/reuse')
    def reuse(run_id:str,payload:dict):
        try:return store.reuse(run_id,payload.get('source_id',''))
        except (ValueError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/{run_id}')
    def configure(run_id:str,payload:dict):
        try:
            config=store.configure(run_id,payload); schedule(config); return config
        except (ValueError,OSError,TypeError) as exc: raise HTTPException(400,str(exc)) from exc

    @router.post('/{run_id}/enabled')
    def enabled(run_id:str,payload:dict):
        if type(payload.get('enabled')) is not bool: raise HTTPException(400,'Choose pause or resume.')
        try:
            config=store.set_enabled(run_id,payload['enabled']); schedule(config); return config
        except ValueError as exc: raise HTTPException(400,str(exc)) from exc

    @router.post('/{run_id}/review')
    def review(run_id:str):
        try:return store.review(run_id)
        except (ValueError,OSError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc

    app.include_router(router)

"""User-owned, version-pinned forecast presentation preferences."""
from contextlib import closing
import json
import sqlite3
import uuid
from typing import Literal
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field


class ViewSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer: str = Field(default='', max_length=200)
    sku: str = Field(default='', max_length=200)
    period: str = Field(default='', max_length=10)
    unit: str = Field(max_length=80)
    coverage: str = Field(default='', max_length=80)
    display: Literal['chart','trend','table','pivot','coverage'] = 'chart'
    view: Literal['detail','month','customer','sku'] = 'month'
    sort: Literal['name','largest','smallest'] = 'name'
    measure: Literal['total','baseline','booked','remaining','still_to_serve'] = 'total'


class SavedView(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str = Field(min_length=1,max_length=80)
    run_id: str = Field(min_length=1,max_length=100)
    snapshot_id: str = Field(min_length=1,max_length=100)
    settings: ViewSettings


class ViewStore:
    def __init__(self,path):
        self.path=path
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE IF NOT EXISTS forecast_views (id TEXT PRIMARY KEY, owner TEXT NOT NULL, payload TEXT NOT NULL)')
            db.commit()

    def list(self,owner,run_id):
        with closing(sqlite3.connect(self.path)) as db:
            rows=[dict(id=r[0],**json.loads(r[1])) for r in db.execute('SELECT id,payload FROM forecast_views WHERE owner=? ORDER BY rowid DESC',(owner,))]
        return [r for r in rows if r['run_id']==run_id]

    def save(self,owner,view):
        key=uuid.uuid4().hex
        with closing(sqlite3.connect(self.path,timeout=30)) as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM forecast_views WHERE owner=?',(owner,)).fetchone()[0]>=100:
                raise ValueError('You can save up to 100 views.')
            db.execute('INSERT INTO forecast_views VALUES (?,?,?)',(key,owner,view.model_dump_json()))
            db.commit()
        return dict(id=key,**view.model_dump())

    def get(self,owner,key):
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute('SELECT payload FROM forecast_views WHERE id=? AND owner=?',(key,owner)).fetchone()
        if not row:raise ValueError('Saved view not found.')
        return dict(id=key,**json.loads(row[0]))

    def update(self,owner,key,view):
        with closing(sqlite3.connect(self.path,timeout=30)) as db:
            changed=db.execute('UPDATE forecast_views SET payload=? WHERE id=? AND owner=?',(view.model_dump_json(),key,owner)).rowcount
            if not changed:raise ValueError('Saved view not found.')
            db.commit()
        return dict(id=key,**view.model_dump())

    def delete(self,owner,key):
        with closing(sqlite3.connect(self.path,timeout=30)) as db:
            changed=db.execute('DELETE FROM forecast_views WHERE id=? AND owner=?',(key,owner)).rowcount
            if not changed:raise ValueError('Saved view not found.')
            db.commit()
        return {'deleted':True,'id':key}


def install_view_routes(app,store,load_run,get_snapshot):
    def owner(request):
        p=request.state.principal or {}
        return json.dumps([p.get('issuer'),p.get('subject')]) if p else 'local'

    @app.get('/api/sales/views')
    def views(run_id: str,request: Request):
        load_run(run_id)
        return {'views':store.list(owner(request),run_id)}

    @app.post('/api/sales/views')
    def save_view(body: SavedView,request: Request):
        try:
            load_run(body.run_id)
            if get_snapshot(body.snapshot_id)['inputs']['run_id']!=body.run_id:
                raise ValueError('This order version belongs to another forecast.')
            return store.save(owner(request),body)
        except ValueError as exc:
            raise HTTPException(400,str(exc)) from exc

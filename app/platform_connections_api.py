"""Public read-only business input connections. No cross-company store fallback."""
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from .business_connections import ConnectionInput, ConnectionError, ConnectionConflict, ROLES
from .platform_identity import principal
from .platform_sales_api import DatasetInput, StrictInput


class ConnectionUpdate(ConnectionInput):
    version: int = Field(ge=1, strict=True)

class Revision(StrictInput):
    version: int = Field(ge=1, strict=True)

class Pull(StrictInput):
    request_id: str = Field(min_length=8,max_length=100)


def install_platform_connections(api,workspaces):
    router = APIRouter(prefix='',tags=['Business connections'])

    def ws(request,*scopes):
        who = principal(request)
        for scope in scopes: principal(request,scope)
        if workspaces is None: raise HTTPException(503,'Company storage is unavailable.')
        return workspaces.for_principal(who)

    def call(fn,missing=False):
        try: return fn()
        except ConnectionConflict as exc: raise HTTPException(409,str(exc)) from None
        except ConnectionError as exc: raise HTTPException(404 if missing else 400,str(exc)) from None
        except ValueError:
            raise HTTPException(400,'Check the captured inputs, mapping and review settings.') from None

    def connection(request,identifier,action='read'):
        w = ws(request,'connections:'+action)
        item = call(lambda:w.connections.get(identifier),True)
        principal(request,ROLES[item['role']]+':'+('read' if action=='read' else 'write'))
        return w,item

    def candidate(request,identifier,write=False):
        w = ws(request,'connections:sync' if write else 'connections:read')
        item = call(lambda:w.connections.candidate(identifier),True)
        principal(request,ROLES[item['role']]+':'+('write' if write else 'read'))
        # A future-factor receipt also contains historical sales references.
        if 'history' in item['sources']: principal(request,'inputs:write' if write else 'inputs:read')
        if 'future' in item['sources']: principal(request,'factors:write' if write else 'factors:read')
        return w,item

    @router.get('/connections/inputs')
    def listing(request:Request,include_archived:bool=False,limit:int=Query(default=100,ge=1,le=1000),offset:int=Query(default=0,ge=0)):
        w = ws(request,'connections:read')
        scopes = principal(request)['permissions']
        rows = [r for r in call(lambda:w.connections.list(include_archived)) if ROLES[r['role']]+':read' in scopes]
        return {'connections':rows[offset:offset+limit],'total':len(rows),'offset':offset,'limit':limit}

    @router.post('/connections/inputs',status_code=201)
    def create(body:ConnectionInput,request:Request):
        w = ws(request,'connections:manage',ROLES[body.role]+':write')
        if body.template_dataset_id: principal(request,'inputs:read')
        return call(lambda:w.connections.save(body))

    @router.get('/connections/inputs/{connection_id}')
    def get(connection_id:str,request:Request):
        return connection(request,connection_id)[1]

    @router.put('/connections/inputs/{connection_id}')
    def update(connection_id:str,body:ConnectionUpdate,request:Request):
        w,_ = connection(request,connection_id,'manage')
        principal(request,ROLES[body.role]+':write')
        if body.template_dataset_id: principal(request,'inputs:read')
        # Version is not persisted inside the provider configuration.
        config = ConnectionInput.model_validate(body.model_dump(exclude={'version'}))
        return call(lambda:w.connections.save(config,connection_id,body.version))

    @router.delete('/connections/inputs/{connection_id}',description='Archive a connection. Existing source captures and forecasts remain intact.')
    def archive(connection_id:str,body:Revision,request:Request):
        w,_ = connection(request,connection_id,'manage')
        return call(lambda:w.connections.archive(connection_id,body.version,True))

    @router.post('/connections/inputs/{connection_id}/restore')
    def restore(connection_id:str,body:Revision,request:Request):
        w,_ = connection(request,connection_id,'manage')
        return call(lambda:w.connections.archive(connection_id,body.version,False))

    @router.post('/connections/inputs/{connection_id}/fetch',description='Capture a full read-only export. Repeated request IDs and unchanged content do not create duplicate inputs. Does not calculate or publish a forecast.')
    def fetch(connection_id:str,body:Pull,request:Request):
        w,_ = connection(request,connection_id,'sync')
        return call(lambda:w.connections.pull(connection_id,body.request_id))

    @router.get('/connections/imports/{import_id}')
    def get_candidate(import_id:str,request:Request):
        return candidate(request,import_id)[1]

    @router.post('/connections/imports/{import_id}/accept',status_code=201,description='Validate and save the exact captured inputs as an immutable reviewed dataset revision.')
    def accept(import_id:str,body:DatasetInput,request:Request):
        w,_ = candidate(request,import_id,True)
        principal(request,'inputs:write')
        return call(lambda:w.connections.accept(import_id,body))

    api.include_router(router)

"""Versioned public platform API. Unscoped legacy routes are not exposed here."""
from typing import Literal
from fastapi import FastAPI, Request, HTTPException, Query, Body
from typing import Annotated
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, ConfigDict, Field
from .platform_identity import principal
from .customers import Customer, Product

Role = Literal['admin','planner','approver','viewer']

class KeyCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    kind: Literal['personal','company'] = 'personal'
    name: str = Field(min_length=1, max_length=80)
    role: Literal['planner','viewer'] | None = None
    scopes: list[str] = Field(min_length=1, max_length=40)
    days: int = Field(default=90, ge=1, le=365, strict=True)

class KeyRename(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)

class KeyRotate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    days: int = Field(default=90, ge=1, le=365, strict=True)

class Invitation(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    role: Role

class MemberUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Role | None = None
    suspended: bool | None = None


def create_platform_api(service, workspaces=None, dispatcher=None):
    api = FastAPI(title='DemandLab public API', version='1.0.0',
        description='Company-scoped sales and demand forecasting. API access uses a Bearer key. Access administration requires an interactive session.')

    async def operation(request, name, values=None, admin=False):
        who = principal(request, 'members:manage' if admin else None, interactive=True)
        if service is None:
            raise HTTPException(503, 'Company access is not configured.')
        return await service.call(name, {**(values or {}), 'cookie':request.headers.get('cookie',''), 'company_id':who['company_id']})

    @api.get('/me', tags=['Account'])
    def me(request: Request):
        who = principal(request)
        return {key:value for key,value in who.items() if key not in {'session_id','key_id'}}

    def customers(request, write=False):
        who = principal(request, 'customers:write' if write else 'customers:read')
        if workspaces is None:
            raise HTTPException(503, 'Company storage is not configured.')
        try:
            return workspaces.for_principal(who).customers
        except ValueError:
            raise HTTPException(503, 'Company storage is unavailable.') from None

    def customer(store, identifier):
        item = next((row for row in store.list() if row['id'] == identifier), None)
        if item is None:
            raise HTTPException(404, 'Customer not found.')
        return item

    def customer_values(item):
        return {k:v for k,v in item.items() if k not in {'id','updated_at'}}

    @api.get('/customers', tags=['Customers'])
    def list_customers(request: Request, limit: int = Query(default=100, ge=1, le=1000),
            offset: int = Query(default=0, ge=0), include_archived: bool = False):
        rows = customers(request).list()
        if not include_archived: rows = [row for row in rows if row['active']]
        return {'customers':rows[offset:offset+limit], 'total':len(rows), 'offset':offset, 'limit':limit}

    @api.post('/customers', status_code=201, tags=['Customers'])
    def create_customer(body: Customer, request: Request):
        store = customers(request, True)
        identifier = store.save([body])['ids'][0]
        return customer(store, identifier)

    @api.get('/customers/{customer_id}', tags=['Customers'])
    def get_customer(customer_id: str, request: Request):
        return customer(customers(request), customer_id)

    @api.put('/customers/{customer_id}', tags=['Customers'])
    def update_customer(customer_id: str, body: Customer, request: Request):
        store = customers(request, True)
        store.save([body], customer_id)
        return customer(store, customer_id)

    @api.delete('/customers/{customer_id}', tags=['Customers'], description='Archive the directory entry. Saved sales and forecast evidence are not deleted.')
    def archive_customer(customer_id: str, request: Request):
        store = customers(request, True)
        body = customer_values(customer(store, customer_id))
        body['active'] = False
        store.save([Customer(**body)], customer_id)
        return {'archived':True, 'id':customer_id}

    @api.get('/customers/{customer_id}/products', tags=['Customer products'])
    def list_products(customer_id: str, request: Request):
        return {'products':customer(customers(request), customer_id)['products']}

    @api.put('/customers/{customer_id}/products', tags=['Customer products'])
    def replace_products(customer_id: str, body: Annotated[list[Product], Body(max_length=2000)], request: Request):
        if len({(p.sku,p.unit) for p in body}) != len(body):
            raise HTTPException(422, 'Each product and unit should appear only once.')
        store = customers(request, True)
        values = customer_values(customer(store, customer_id))
        values['products'] = [p.model_dump() for p in body]
        store.save([Customer(**values)], customer_id)
        return {'products':values['products']}

    @api.get('/api-keys', tags=['API access'])
    async def list_keys(request: Request):
        return await operation(request, 'keys/list')

    @api.get('/access-options', tags=['API access'])
    async def access_options(request: Request):
        return await operation(request, 'policy')

    @api.post('/api-keys', status_code=201, tags=['API access'])
    async def create_key(body: KeyCreate, request: Request):
        return await operation(request, 'keys/create', body.model_dump(exclude_none=True))

    @api.patch('/api-keys/{key_id}', tags=['API access'])
    async def rename_key(key_id: str, body: KeyRename, request: Request):
        return await operation(request, 'keys/manage', {'id':key_id, 'operation':'rename', 'name':body.name})

    @api.delete('/api-keys/{key_id}', tags=['API access'])
    async def revoke_key(key_id: str, request: Request):
        return await operation(request, 'keys/manage', {'id':key_id, 'operation':'revoke'})

    @api.post('/api-keys/{key_id}/rotate', status_code=201, tags=['API access'])
    async def rotate_key(key_id: str, body: KeyRotate, request: Request):
        return await operation(request, 'keys/rotate', {'id':key_id, **body.model_dump()})

    @api.get('/members', tags=['People'])
    async def list_members(request: Request):
        return await operation(request, 'members/list', admin=True)

    @api.post('/invitations', status_code=201, tags=['People'])
    async def invite(body: Invitation, request: Request):
        return await operation(request, 'members/invite', body.model_dump(), admin=True)

    @api.delete('/invitations/{invitation_id}', tags=['People'])
    async def cancel_invitation(invitation_id: str, request: Request):
        return await operation(request, 'members/cancel-invitation', {'id':invitation_id}, admin=True)

    @api.patch('/members/{member_id}', tags=['People'])
    async def update_member(member_id: str, body: MemberUpdate, request: Request):
        # A single operation per request avoids partially applied mixed changes.
        if (body.role is None) == (body.suspended is None):
            raise HTTPException(422, 'Change either role or suspension in one request.')
        values = {'id':member_id, 'operation':'role', 'role':body.role} if body.role is not None else {
            'id':member_id, 'operation':'suspend' if body.suspended else 'resume'}
        return await operation(request, 'members/manage', values, admin=True)

    @api.delete('/members/{member_id}', tags=['People'])
    async def remove_member(member_id: str, request: Request):
        return await operation(request, 'members/manage', {'id':member_id,'operation':'remove'}, admin=True)

    @api.post('/members/{member_id}/revoke-sessions', tags=['People'])
    async def revoke_sessions(member_id: str, request: Request):
        return await operation(request, 'members/manage', {'id':member_id,'operation':'revoke_sessions'}, admin=True)

    @api.get('/audit-events', tags=['Administration'])
    async def audit(request: Request):
        return await operation(request, 'audit', admin=True)

    from .platform_sales_api import install_platform_sales
    install_platform_sales(api, workspaces, dispatcher)
    from .platform_workspace_api import install_platform_workspace
    install_platform_workspace(api, workspaces, dispatcher)
    from .platform_workflow_api import install_platform_workflows
    install_platform_workflows(api, workspaces, dispatcher, service)
    from .company_context import install_company_assistant
    install_company_assistant(api, workspaces, dispatcher)

    def schema():
        if api.openapi_schema is None:
            value = get_openapi(title=api.title, version=api.version, description=api.description,
                routes=api.routes, servers=[{'url':'/api/v1'}])
            secure_cookie = bool(service and service.config.origin.startswith('https://'))
            value.setdefault('components', {})['securitySchemes'] = {
                'ApiKey':{'type':'http','scheme':'bearer','description':'Company-bound API key. Cannot manage users or API keys.'},
                'BrowserSession':{'type':'apiKey','in':'cookie','name':('__Secure-' if secure_cookie else '')+'better-auth.session_token','description':'Verified interactive session; mutations also require X-DemandLab-CSRF.'}}
            for path, methods in value['paths'].items():
                for method, details in methods.items():
                    access_only = path.startswith(('/api-keys','/access-options','/members','/invitations','/audit-events')) or path == '/connections/external-sources/servix/credential'
                    details['security'] = [{'BrowserSession':[]}] if access_only else [{'ApiKey':[]},{'BrowserSession':[]}]
                    if method in {'post','put','patch','delete'}:
                        details.setdefault('parameters', []).append({'name':'X-DemandLab-CSRF','in':'header','required':False,
                            'schema':{'type':'string'},'description':'Required for browser-session changes, not Bearer-key requests.'})
            api.openapi_schema = value
        return api.openapi_schema
    api.openapi = schema
    return api

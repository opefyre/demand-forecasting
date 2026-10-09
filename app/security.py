"""Company OIDC sign-in with Authlib; application roles and revocable sessions."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, Request
from sqlalchemy import Column, Float, MetaData, String, Table, create_engine, insert, select, update
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool


ROLES = {'viewer', 'planner', 'reviewer', 'admin'}
UNSAFE = {'POST', 'PUT', 'PATCH', 'DELETE'}


@dataclass(frozen=True)
class SecurityConfig:
    mode: str = 'local'
    origin: str = 'http://127.0.0.1:8010'
    issuer: str = ''
    client_id: str = ''
    client_secret: str = ''
    session_secret: str = ''
    members_path: Path | None = None
    auth_service_url: str = ''
    auth_bridge_secret: str = ''

    @classmethod
    def from_env(cls):
        configured = any(key.startswith('DEMANDLAB_OIDC_') for key in os.environ)
        config = cls(mode=os.getenv('DEMANDLAB_AUTH_MODE', 'oidc' if configured else 'local'),
            origin=os.getenv('DEMANDLAB_PUBLIC_ORIGIN', 'http://127.0.0.1:8010').rstrip('/'),
            issuer=os.getenv('DEMANDLAB_OIDC_ISSUER', ''),
            client_id=os.getenv('DEMANDLAB_OIDC_CLIENT_ID', ''),
            client_secret=os.getenv('DEMANDLAB_OIDC_CLIENT_SECRET', ''),
            session_secret=os.getenv('DEMANDLAB_SESSION_SECRET', ''),
            members_path=Path(os.environ['DEMANDLAB_MEMBERS_FILE']) if os.getenv('DEMANDLAB_MEMBERS_FILE') else None,
            auth_service_url=os.getenv('DEMANDLAB_AUTH_SERVICE_URL', 'http://127.0.0.1:8011'),
            auth_bridge_secret=os.getenv('DEMANDLAB_AUTH_BRIDGE_SECRET', ''))
        config.validate()
        return config

    def validate(self):
        if self.mode not in {'local', 'oidc', 'better_auth'}:
            raise ValueError('DEMANDLAB_AUTH_MODE must be local, oidc or better_auth.')
        if self.mode == 'better_auth':
            from .platform_identity import IdentityServiceConfig
            IdentityServiceConfig(self.origin, self.auth_service_url, self.auth_bridge_secret).validate()
            return
        if self.mode == 'local':
            if self.issuer or self.client_id or self.client_secret:
                raise ValueError('OIDC settings cannot be silently ignored in local mode.')
            return
        for value in (self.origin, self.issuer):
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('Company sign-in requires explicit HTTPS origin and issuer URLs without credentials or query strings.')
        if urlsplit(self.origin).path not in ('', '/'):
            raise ValueError('The public origin must not contain a path.')
        if not self.client_id or not self.client_secret or len(self.session_secret) < 32 or not self.members_path:
            raise ValueError('Company sign-in needs client credentials, a random session secret (32+ characters) and a members file.')
        self.members()

    def members(self):
        # Re-read on requests: an operator's membership removal/reduction takes effect immediately.
        data = json.loads(self.members_path.read_text()) if self.members_path else {}
        if not isinstance(data, dict) or any(not isinstance(k,str) or not k or not isinstance(v,str) or v not in ROLES for k,v in data.items()):
            raise ValueError('Members must map exact OIDC subject identifiers to viewer, planner, reviewer or admin.')
        return data


class LoginStore:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f'sqlite:///{path}')
        metadata = MetaData()
        self.table = Table('login_sessions', metadata, Column('token_hash',String,primary_key=True),
            Column('issuer',String,nullable=False), Column('subject',String,nullable=False),
            Column('name',String,nullable=False), Column('expires',Float,nullable=False))
        metadata.create_all(self.engine)

    def create(self, identity):
        token = secrets.token_urlsafe(32)
        with self.engine.begin() as connection:
            connection.execute(insert(self.table).values(token_hash=hashlib.sha256(token.encode()).hexdigest(),
                issuer=identity['issuer'], subject=identity['subject'], name=identity['name'], expires=time.time()+3600))
        return token

    def get(self, token):
        if not isinstance(token,str) or len(token) > 200: return None
        with self.engine.connect() as connection:
            row = connection.execute(select(self.table).where(self.table.c.token_hash == hashlib.sha256(token.encode()).hexdigest(),
                                                             self.table.c.expires > time.time())).mappings().first()
            return {key:row[key] for key in ('issuer','subject','name')} if row else None

    def revoke(self, token):
        if not isinstance(token,str): return
        with self.engine.begin() as connection:
            connection.execute(update(self.table).where(self.table.c.token_hash == hashlib.sha256(token.encode()).hexdigest()).values(expires=0))


class AccessControl:
    def __init__(self, config, data_dir):
        config.validate()
        self.config = config
        self.data_dir = data_dir
        self.store = LoginStore(data_dir/'identity.sqlite3') if config.mode == 'oidc' else None
        self.oauth = OAuth()
        self.identity_service = None
        if config.mode == 'better_auth':
            from .platform_identity import IdentityService, IdentityServiceConfig
            self.identity_service = IdentityService(IdentityServiceConfig(config.origin, config.auth_service_url, config.auth_bridge_secret))
        if config.mode == 'oidc':
            self.oauth.register('company', client_id=config.client_id, client_secret=config.client_secret,
                server_metadata_url=config.issuer.rstrip('/')+'/.well-known/openid-configuration',
                client_kwargs={'scope':'openid profile', 'code_challenge_method':'S256', 'timeout':15},
                authorize_params={'prompt':'select_account'})

    def identity(self, session):
        if not self.store: return None
        identity = self.store.get(session.get('login'))
        if not identity or identity['issuer'] != self.config.issuer: return None
        role = self.config.members().get(identity['subject'])
        return {**identity,'role':role} if role else None

    def allowed(self, principal, method, path):
        role = principal['role']
        if method not in UNSAFE: return True
        if path in {'/api/assistant/query', '/api/ai/chat'}: return True
        if method=='POST' and path.startswith('/api/ai/conversations/') and path.rsplit('/',1)[-1] in {'rename','manage'}:return True
        if role == 'admin': return True
        if path == '/api/auth/logout': return True
        if path.startswith('/api/sales/releases/') and path.endswith('/approve'):
            return role == 'reviewer'
        if path.startswith('/api/plans/') and (path.endswith('/comments') or path.endswith('/status')):
            return role in {'planner','reviewer'}
        if role != 'planner': return False
        return not (path == '/api/site' or path.startswith('/api/integrations') or path.startswith('/api/live-sources') or path.startswith('/api/recurring-forecasts') or path == '/api/units'
                    or path.endswith('/refresh'))


class AccessMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, access):
        super().__init__(app)
        self.access = access

    async def dispatch(self, request, call_next):
        config = self.access.config
        path = request.url.path
        protected = path.startswith('/api/') or path in {'/docs','/redoc','/openapi.json'}
        request.state.principal = None
        if config.mode == 'better_auth':
            return await self.platform_dispatch(request, call_next, protected)
        if config.mode == 'local':
            # No authenticated identity is asserted in local evaluation mode.
            if protected and request.method in UNSAFE and request.headers.get('origin'):
                if request.headers['origin'] not in {config.origin, 'http://localhost:8010'}:
                    return JSONResponse({'detail':'Cross-site changes are not allowed.'},status_code=403)
            return await call_next(request)
        parsed = urlsplit(str(request.url))
        if f'{parsed.scheme}://{parsed.netloc}' != config.origin:
            return JSONResponse({'detail':'Use the configured secure application address.'},status_code=400)
        try:
            principal = await run_in_threadpool(self.access.identity, request.session)
        except (ValueError, OSError):
            return JSONResponse({'detail':'Access configuration is unavailable. Contact the administrator.'},status_code=503)
        request.state.principal = principal
        public = path in {'/api/auth/session','/api/auth/login','/api/auth/callback','/api/health'}
        if protected and not public:
            if not principal:
                return JSONResponse({'detail':'Sign in to continue.'},status_code=401)
            if not self.access.allowed(principal, request.method, path):
                return JSONResponse({'detail':'Your role does not allow this action.'},status_code=403)
            if request.method in UNSAFE:
                csrf = request.headers.get('x-demandlab-csrf','')
                if (request.headers.get('origin',config.origin) != config.origin or not csrf
                        or not secrets.compare_digest(csrf,request.session.get('csrf',''))):
                    return JSONResponse({'detail':'Refresh the page before making changes.'},status_code=403)
        response = await call_next(request)
        if protected: response.headers['Cache-Control'] = 'no-store'
        return response

    async def platform_dispatch(self, request, call_next, protected):
        service, config = self.access.identity_service, self.access.config
        parsed = urlsplit(str(request.url))
        if f'{parsed.scheme}://{parsed.netloc}' != config.origin:
            return JSONResponse({'detail':'Use the configured application address.'}, status_code=400)
        path = request.url.path
        public = path.startswith('/api/login/') or path in {'/api/auth/session','/api/auth/providers','/api/health'}
        if protected and not path.startswith('/api/login/'):
            try:
                request.state.principal = await service.identity(request)
            except HTTPException as error:
                if not public or error.status_code not in {401,403}:
                    return JSONResponse({'detail':error.detail}, status_code=error.status_code)
        if protected and not public:
            who = request.state.principal
            if who['mfa_required']:
                return JSONResponse({'detail':'Verify two-factor authentication first.'}, status_code=403)
            if request.method in UNSAFE and who['auth_kind'] == 'session':
                expected = service.csrf(who)
                received = request.headers.get('x-demandlab-csrf', '')
                if (request.headers.get('origin') != config.origin or not received or not secrets.compare_digest(received, expected)):
                    return JSONResponse({'detail':'Refresh the page before making changes.'}, status_code=403)
            # Legacy stores are global. Never expose them under new company
            # authentication until each route has been moved to scoped storage.
            if not path.startswith('/api/v1/'):
                return JSONResponse({'detail':'This route has not been migrated to company-scoped access.'}, status_code=503)
        response = await call_next(request)
        if protected: response.headers['Cache-Control'] = 'no-store'
        return response


def install_access(app, access):
    app.state.access = access
    app.add_middleware(AccessMiddleware, access=access)
    if access.config.mode == 'oidc':
        app.add_middleware(SessionMiddleware, secret_key=access.config.session_secret,
            session_cookie='demandlab_session', max_age=3600, same_site='lax', https_only=True)

    @app.get('/api/auth/session')
    def session(request: Request):
        if access.config.mode == 'better_auth':
            who = request.state.principal
            return {'mode':'better_auth', 'user':{k:v for k,v in who.items() if k not in {'session_id','key_id'}} if who else None,
                'csrf':access.identity_service.csrf(who) if who else None}
        return {'mode':access.config.mode, 'user':request.state.principal,
                'csrf':request.session.get('csrf') if request.state.principal else None}

    if access.config.mode == 'better_auth':
        from .platform_api import create_platform_api
        from .company_workspace import CompanyWorkspaces
        company_workspaces = CompanyWorkspaces(access.data_dir/'companies')
        app.mount('/api/v1', create_platform_api(access.identity_service, company_workspaces))

        @app.on_event('shutdown')
        def close_company_workspaces():
            company_workspaces.close()

        @app.api_route('/api/login/{path:path}', methods=['GET','POST'], include_in_schema=False)
        async def login_proxy(request: Request):
            return await access.identity_service.proxy(request)

        @app.get('/api/auth/providers')
        async def providers():
            return await access.identity_service.call('config', {})

    @app.get('/api/auth/login')
    async def login(request: Request):
        if access.config.mode != 'oidc': raise HTTPException(409,'Company sign-in is not configured.')
        try:
            return await access.oauth.company.authorize_redirect(request, access.config.origin+'/api/auth/callback')
        except Exception:
            raise HTTPException(503,'Company sign-in is unavailable. Try again or contact the administrator.') from None

    @app.get('/api/auth/callback')
    async def callback(request: Request):
        if access.config.mode != 'oidc': raise HTTPException(409,'Company sign-in is not configured.')
        try:
            token = await access.oauth.company.authorize_access_token(request,
                claims_options={'iss':{'essential':True,'value':access.config.issuer}, 'sub':{'essential':True}}, leeway=30)
            claims = token.get('userinfo')
            if not claims or not token.get('id_token') or claims.get('iss') != access.config.issuer:
                raise ValueError('Invalid identity')
            if claims.get('nonce_supported') is False:
                raise ValueError('This application requires nonce validation.')
            subject = claims.get('sub')
            if not isinstance(subject,str) or subject not in access.config.members():
                raise ValueError('No assigned role')
            identity = {'issuer':access.config.issuer,'subject':subject,'name':str(claims.get('name') or subject)[:120]}
            await run_in_threadpool(access.store.revoke, request.session.get('login'))
            login_id = await run_in_threadpool(access.store.create, identity)
            request.session.clear()
            request.session.update(login=login_id, csrf=secrets.token_urlsafe(32))
            return RedirectResponse('/today',status_code=303)
        except Exception:
            request.session.clear()
            return RedirectResponse('/?signin=failed',status_code=303)

    @app.post('/api/auth/logout')
    async def logout(request: Request):
        if access.store:
            await run_in_threadpool(access.store.revoke, request.session.get('login'))
            request.session.clear()
        return {'signed_out':True}


def identity_fields(request, supplied_name):
    principal = getattr(request.state,'principal',None)
    return {'actor':principal['name'] if principal else supplied_name, 'identity':principal}

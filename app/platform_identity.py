"""Private, fail-closed bridge to Better Auth. No password or OAuth implementation."""
from dataclasses import dataclass
import hashlib
import hmac
import re
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException, Request

ROLES = frozenset({'admin', 'planner', 'approver', 'viewer'})
COMPANY_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
INTERNAL_OPERATIONS = frozenset({'identity', 'config', 'policy', 'keys/list', 'keys/create', 'keys/manage',
    'keys/rotate', 'members/list', 'members/invite', 'members/manage', 'members/cancel-invitation', 'audit', 'schedules/authorize'})


@dataclass(frozen=True)
class IdentityServiceConfig:
    origin: str
    url: str
    secret: str

    def validate(self):
        public, private = urlsplit(self.origin), urlsplit(self.url)
        if (public.scheme not in {'http', 'https'} or not public.hostname or public.username or public.password
                or public.query or public.fragment or public.path not in {'', '/'}):
            raise ValueError('Use a valid public application origin.')
        if public.scheme != 'https' and public.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Public company access requires HTTPS.')
        # No redirects, proxy environment or arbitrary identity-service hosts.
        if (private.scheme != 'http' or private.hostname not in {'127.0.0.1', '::1'} or private.username
                or private.password or private.query or private.fragment or private.path not in {'', '/'}):
            raise ValueError('The authentication service must use a loopback HTTP address.')
        if len(self.secret) < 32:
            raise ValueError('Configure a separate random authentication bridge secret.')


class IdentityService:
    def __init__(self, config, transport=None):
        config.validate()
        self.config, self.transport = config, transport

    def client(self):
        return httpx.AsyncClient(base_url=self.config.url, timeout=10, follow_redirects=False,
            trust_env=False, transport=self.transport)

    async def call(self, operation, body):
        if operation not in INTERNAL_OPERATIONS:
            raise ValueError('Unknown identity operation.')
        try:
            async with self.client() as client:
                response = await client.post('/internal/'+operation, json=body,
                    headers={'x-demandlab-bridge-key': self.config.secret})
            if len(response.content) > 1024 * 1024:
                raise ValueError('Oversized identity response.')
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Invalid identity response.')
            if response.is_error:
                status = response.status_code if response.status_code in {400,401,403,404,409,429} else 503
                # The bridge supplies safe messages; never forward proxy/provider errors.
                message = data.get('detail') if isinstance(data.get('detail'), str) else None
                raise HTTPException(status, message[:200] if message and status != 503 else 'Sign-in service is unavailable.')
            return data
        except HTTPException:
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            raise HTTPException(503, 'Sign-in service is unavailable.') from None

    async def identity(self, request):
        authorization = request.headers.get('authorization', '')
        body = {'cookie': request.headers.get('cookie', '')}
        if authorization:
            parts = authorization.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer' or len(parts[1]) > 512:
                raise HTTPException(401, 'Use a valid Bearer API key.')
            body = {'key': parts[1]}
        company = request.headers.get('x-demandlab-company')
        if company:
            if not COMPANY_ID.fullmatch(company):
                raise HTTPException(400, 'Invalid company identifier.')
            body['company_id'] = company
        data = await self.call('identity', body)
        if (data.get('issuer') != self.config.origin or data.get('role') not in ROLES
                or not COMPANY_ID.fullmatch(str(data.get('company_id', '')))
                or not isinstance(data.get('subject'), str) or not data['subject']
                or not isinstance(data.get('permissions'), list)
                or any(not isinstance(value, str) for value in data['permissions'])
                or data.get('auth_kind') not in {'session', 'api_key'}
                or not isinstance(data.get('mfa_required'), bool)
                or (data['auth_kind'] == 'session' and not isinstance(data.get('session_id'), str))):
            raise HTTPException(503, 'Sign-in service returned an invalid identity.')
        if bool(authorization) != (data['auth_kind'] == 'api_key'):
            raise HTTPException(503, 'Sign-in service returned an invalid identity.')
        return data

    def csrf(self, principal):
        if principal.get('auth_kind') != 'session':
            return None
        # Standard synchronizer token, tied to the upstream validated session.
        return hmac.new(self.config.secret.encode(), ('csrf:'+principal['session_id']).encode(), hashlib.sha256).hexdigest()

    async def proxy(self, request):
        path = request.url.path
        if not path.startswith('/api/login/') or '\\' in path or '..' in path:
            raise HTTPException(404, 'Login endpoint not found.')
        if request.headers.get('authorization'):
            raise HTTPException(403, 'API keys cannot manage interactive sign-in.')
        if request.method not in {'GET','POST'}:
            raise HTTPException(405, 'Unsupported login action.')
        # Forward only an explicit header set. Never forward the private bridge key
        # or caller-provided forwarded-host headers to the authentication service.
        headers = {key:request.headers[key] for key in ('cookie','content-type','origin') if key in request.headers}
        if request.method == 'POST' and headers.get('origin') != self.config.origin:
            raise HTTPException(403, 'Cross-site sign-in changes are not allowed.')
        headers['x-forwarded-for'] = request.client.host if request.client else '127.0.0.1'
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 65536:
                raise HTTPException(413, 'Sign-in request is too large.')
        try:
            async with self.client() as client:
                response = await client.request(request.method, path, params=list(request.query_params.multi_items()),
                    headers=headers, content=bytes(content))
            if len(response.content) > 1024 * 1024:
                raise ValueError('Oversized sign-in response.')
            from starlette.responses import Response
            result = Response(response.content, status_code=response.status_code,
                media_type=response.headers.get('content-type', 'application/json'), headers={'Cache-Control':'no-store'})
            for value in response.headers.get_list('set-cookie'):
                result.headers.append('set-cookie', value)
            if response.headers.get('location'):
                result.headers['location'] = response.headers['location']
            if response.headers.get('retry-after'):
                result.headers['retry-after'] = response.headers['retry-after']
            return result
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, 'Sign-in service is unavailable.') from None


def principal(request: Request, scope=None, interactive=False):
    who = getattr(request.state, 'principal', None)
    if not who or not who.get('company_id'):
        raise HTTPException(401, 'Sign in to continue.')
    if who.get('mfa_required'):
        raise HTTPException(403, 'Verify two-factor authentication first.')
    if interactive and who.get('auth_kind') != 'session':
        raise HTTPException(403, 'Use an interactive sign-in to manage access.')
    if scope and scope not in who.get('permissions', []):
        raise HTTPException(403, 'Your access does not allow this action.')
    return who

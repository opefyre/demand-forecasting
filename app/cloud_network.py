"""Attempt-bound private relay. The engine itself still has no Internet access.

Existing httpx, Google-auth, Paramiko and Apprise adapters build requests. The
controller checks live access and exact destinations before any outside I/O.
No relay body or credential is logged or captured in company checkpoints.
"""
import asyncio
import base64
from contextvars import ContextVar
from contextlib import contextmanager
import json
import socket
from threading import Condition
import time
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
import uuid

import httpx

_current = ContextVar('forecast_network_bridge', default=None)
_bridges = {}
LIMIT = 20 * 1024 * 1024


def current_bridge():
    return _current.get()


class Bridge:
    def __init__(self, attempt, ai=None):
        self.attempt = attempt
        self.ai = ai or {'enabled':False,'configured':False}
        self.condition = Condition()
        self.pending = {}
        self.answers = {}
        self.closed = False
        self.calls = 0

    def exchange(self, value):
        encoded = json.dumps(value)
        if len(encoded) > 2 * 1024 * 1024:
            raise ValueError('Private request is too large.')
        key = uuid.uuid4().hex
        with self.condition:
            if self.closed or len(self.pending) >= 8 or self.calls >= 2000:
                raise ValueError('Private network operation is unavailable.')
            self.calls += 1
            self.pending[key] = {'id':key, **value}
            if not self.condition.wait_for(lambda:key in self.answers or self.closed, timeout=65):
                self.pending.pop(key, None)
                raise ValueError('Private network operation timed out.')
            self.pending.pop(key, None)
            answer = self.answers.pop(key, None)
        if not answer or answer.get('error'):
            raise ValueError('Private network operation failed. Review and retry.')
        return answer

    def next(self):
        with self.condition:
            # Delivery claims are never automatically replayed after interruption.
            for value in self.pending.values():
                if not value.get('_claimed'):
                    value['_claimed'] = True
                    return {k:v for k,v in value.items() if k != '_claimed'}
        return None

    def answer(self, key, value):
        with self.condition:
            if key not in self.pending or key in self.answers:
                raise ValueError('Private request is unavailable.')
            self.answers[key] = value
            self.condition.notify_all()

    def close(self):
        with self.condition:
            self.closed = True
            self.pending.clear()
            self.answers.clear()
            self.condition.notify_all()


@contextmanager
def bind_bridge(attempt, ai=None):
    bridge = Bridge(attempt, ai)
    if attempt in _bridges: raise ValueError('Private attempt already exists.')
    _bridges[attempt] = bridge
    token = _current.set(bridge)
    try: yield bridge
    finally:
        _current.reset(token)
        _bridges.pop(attempt, None)
        bridge.close()


def active_bridge(attempt):
    if attempt not in _bridges: raise ValueError('Private attempt is unavailable.')
    return _bridges[attempt]


class RelayPolicy:
    def resolve(self, host, port):
        # Placeholder only; no direct socket is ever opened to this address.
        # Public DNS/address checks are performed by the controller, not skipped.
        return (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('192.0.2.1', port))


class RelayTransport(httpx.BaseTransport):
    def __init__(self, bridge, category, config=None):
        self.bridge, self.category, self.config = bridge, category, config

    def handle_request(self, request):
        host = request.extensions.get('sni_hostname') or request.headers.get('host') or request.url.host
        if isinstance(host, bytes): host = host.decode()
        url = urlsplit(str(request.url))
        target = urlunsplit((url.scheme, host, url.path, url.query, ''))
        content = request.read()
        if len(content) > 1024 * 1024: raise httpx.RequestError('Private request limit exceeded.')
        try:
            result = self.bridge.exchange({'kind':'http', 'category':self.category, 'config':self.config,
                'url':target, 'method':request.method,
                'headers':{k:v for k,v in request.headers.items() if k.lower() not in {'host','content-length','connection','accept-encoding'}},
                'body':base64.b64encode(content).decode()})
            raw = base64.b64decode(result['body'], validate=True)
            if len(raw) > LIMIT: raise ValueError()
            return httpx.Response(result['status'], headers=result.get('headers', {}), content=raw, request=request)
        except (ValueError, KeyError): raise httpx.RequestError('Private provider request failed.') from None


class RelayAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(self, bridge): self.transport = RelayTransport(bridge, 'ai')
    async def handle_async_request(self, request):
        await request.aread()
        return await asyncio.to_thread(self.transport.handle_request, request)


class RelaySocket:
    def __init__(self, bridge, config):
        self.bridge, self.config, self.key, self.timeout = bridge, config, None, 10
    def connect(self, address):
        self.key = self.bridge.exchange({'kind':'tcp-open','config':self.config})['socket_id']
    def settimeout(self, value): self.timeout = value
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def setblocking(self, value): self.timeout = None if value else 0
    def gettimeout(self): return self.timeout
    def getpeername(self): return self.config['host'], self.config['port']
    def send(self, content):
        if not self.key: raise OSError('Private socket is closed.')
        self.bridge.exchange({'kind':'tcp-write','socket_id':self.key,'body':base64.b64encode(content).decode()})
        return len(content)
    def sendall(self, content): self.send(content)
    def recv(self, size):
        try:
            value=self.bridge.exchange({'kind':'tcp-read','socket_id':self.key,'size':min(size,65536),
                'timeout':max(1,min(self.timeout or 10,30))})
            if value.get('timeout'):raise ValueError()
            return base64.b64decode(value['body'],validate=True)
        except ValueError: raise socket.timeout('Private socket read failed.') from None
    def close(self):
        if self.key:
            try:self.bridge.exchange({'kind':'tcp-close','socket_id':self.key})
            except ValueError:pass
            self.key=None


class RelayFetcher:
    def __init__(self, bridge): self.bridge = bridge
    def fetch(self, config, credential):
        from .business_connections import InputFetcher
        fetcher=InputFetcher(policy=RelayPolicy(),transport=RelayTransport(self.bridge,'connection',config),
            socket_factory=lambda *args:RelaySocket(self.bridge,config))
        return fetcher.fetch(config,credential)


class CloudIdentityService:
    def __init__(self, bridge, company):
        self.bridge, self.company = bridge, company
        self.config = SimpleNamespace(origin='https://forecast.vrolen.com')
    async def call(self, operation, values):
        if operation != 'schedules/authorize' or values.get('company_id') != self.company:
            raise ValueError('Private identity operation is not allowed.')
        result=await asyncio.to_thread(self.bridge.exchange,{'kind':'identity','operation':operation,'body':values})
        return result['body']


class LoopbackBridge:
    """Only the single-use notification child uses this internal loopback route."""
    def __init__(self, attempt): self.attempt = attempt
    def exchange(self, value):
        with httpx.Client(trust_env=False,timeout=65) as client:
            response=client.post('http://127.0.0.1:8080/network/'+self.attempt+'/exchange',json=value)
            if response.status_code != 200: raise ValueError('Private notification request failed.')
            return response.json()

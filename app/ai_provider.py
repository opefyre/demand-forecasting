"""Existing SDK transports with local-only routing and durable call safeguards."""
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
import sqlite3
import uuid
from urllib.parse import urlsplit

import httpx
from openai import AsyncOpenAI
from agents import RunConfig
from agents.models.interface import Model, ModelProvider, ModelTracing
from agents.models.openai_provider import OpenAIProvider


class AILimitError(ValueError):
    pass


def setting(name, default, low, high):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        raise ValueError('AI limits are invalid. Ask the workspace administrator to check the server settings.') from None
    if not low <= value <= high:
        raise ValueError('AI limits are invalid. Ask the workspace administrator to check the server settings.')
    return value


@dataclass(frozen=True)
class Limits:
    daily_calls: int = 60
    actor_calls: int = 30
    request_calls: int = 6
    context_bytes: int = 100000
    output_tokens: int = 2500

    @classmethod
    def configured(cls):
        return cls(setting('DEMANDLAB_AI_DAILY_CALLS', 60, 1, 10000),
                   setting('DEMANDLAB_AI_USER_DAILY_CALLS', 30, 1, 10000),
                   setting('DEMANDLAB_AI_REQUEST_CALLS', 6, 1, 6),
                   setting('DEMANDLAB_AI_CONTEXT_BYTES', 100000, 1000, 200000),
                   setting('DEMANDLAB_AI_OUTPUT_TOKENS', 2500, 300, 4000))

    def public(self):
        return dict(daily_calls=self.daily_calls, user_daily_calls=self.actor_calls,
                    request_calls=self.request_calls, context_bytes=self.context_bytes,
                    output_tokens=self.output_tokens)


def local_endpoint(value):
    """No arbitrary hosts, URL credentials, proxies or redirects for local AI."""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
                or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment
                or parsed.path.rstrip('/') != '/v1' or not parsed.port or not 1024 <= parsed.port <= 65535):
            raise ValueError
        host = '[::1]' if parsed.hostname == '::1' else '127.0.0.1'
        return f'{parsed.scheme}://{host}:{parsed.port}/v1'
    except ValueError:
        raise ValueError('Local AI must use a loopback address, a port from 1024–65535, and /v1. Remote endpoints are not allowed.') from None


def provider_settings():
    from .cloud_network import current_bridge
    bridge = current_bridge()
    provider = os.getenv('DEMANDLAB_AI_PROVIDER', 'openai').strip().lower()
    if provider not in {'openai', 'local'}:
        raise ValueError('Choose openai or local in the AI server settings.')
    defaults = {'query': 'gpt-5.6-luna', 'review': 'gpt-5.6-terra', 'decision': 'gpt-6-astra'}
    models = {role: os.getenv(f'DEMANDLAB_AI_{role.upper()}_MODEL', default if provider == 'openai' else '').strip()
              for role, default in defaults.items()}
    if any(not model or len(model) > 200 for model in models.values()):
        raise ValueError('Configure a model for questions, data review and forecast decisions.')
    models['title']=os.getenv('DEMANDLAB_AI_TITLE_MODEL','gpt-4.1-nano' if provider=='openai' else models['query']).strip()
    if bridge:
        provider='openai'
        models.update(bridge.ai.get('models',{}))
    if not models['title'] or len(models['title'])>200:
        raise ValueError('Configure a short-title model.')
    endpoint = local_endpoint(os.getenv('DEMANDLAB_AI_LOCAL_URL', 'http://127.0.0.1:11434/v1')) if provider == 'local' else 'https://api.openai.com/v1'
    return provider, endpoint, models, Limits.configured()


def ai_status():
    from .cloud_network import current_bridge
    bridge = current_bridge()
    enabled = os.getenv('DEMANDLAB_AI_ENABLED', 'false').lower() == 'true'
    if bridge: enabled = bridge.ai.get('enabled') is True
    try:
        provider, endpoint, models, limits = provider_settings()
    except ValueError as exc:
        return {'configured': False, 'enabled': enabled, 'ready': False, 'message': str(exc), 'models': {}}
    key = os.getenv('OPENAI_API_KEY', '').strip()
    configured = provider == 'local' or (key.startswith('sk-') and len(key) > 30
        and not any(s in key.lower() for s in ('placeholder', 'replace', 'your_key')))
    if bridge: configured = bridge.ai.get('configured') is True
    label = 'OpenAI' if provider == 'openai' else 'Local AI on this computer'
    return {'configured': configured, 'enabled': enabled, 'ready': configured and enabled,
            'provider': provider, 'provider_label': label, 'models': models, 'limits': limits.public(),
            'consent_id': hashlib.sha256(f'{provider}|{endpoint}'.encode()).hexdigest(),
            'connection_verified': False,
            'message': 'Configured' if configured and enabled else (
                'Configure an OpenAI key and enable AI on the server. No AI calls are made while disabled.'
                if provider == 'openai' else 'Configure local models and enable AI on the server.')}


def validate_consent(payload, status):
    if not status['ready']:
        raise ValueError(status['message'])
    if not payload.consent:
        raise ValueError(f'Confirm sending your question and selected evidence to {status["provider_label"]}.')
    if (payload.provider_id or status.get('provider') == 'local') and payload.provider_id != status['consent_id']:
        raise ValueError('The AI provider changed. Review the sharing permission again; nothing was sent.')


class AICallLedger:
    def __init__(self, path):
        self.path = path
        with closing(sqlite3.connect(path)) as con:
            con.execute('''CREATE TABLE IF NOT EXISTS ai_calls (
                id TEXT PRIMARY KEY, day TEXT NOT NULL, actor TEXT NOT NULL,
                provider TEXT NOT NULL, model TEXT NOT NULL, state TEXT NOT NULL,
                input_tokens INTEGER, output_tokens INTEGER)''')
            con.execute('CREATE INDEX IF NOT EXISTS ai_calls_day ON ai_calls(day,actor)')
            con.commit()

    @staticmethod
    def day():
        return datetime.now(timezone.utc).date().isoformat()

    def reserve(self, actor, provider, model, limits):
        actor = hashlib.sha256(actor.encode()).hexdigest()
        key = uuid.uuid4().hex
        with closing(sqlite3.connect(self.path, timeout=30)) as con, con:
            con.execute('BEGIN IMMEDIATE')
            day = self.day()
            total, own = con.execute('SELECT COUNT(*),COALESCE(SUM(actor=?),0) FROM ai_calls WHERE day=?',
                                     (actor, day)).fetchone()
            if total >= limits.daily_calls or own >= limits.actor_calls:
                raise AILimitError('The daily AI call limit has been reached. Manual forecasts and exports still work. The limit resets at midnight UTC.')
            con.execute('INSERT INTO ai_calls(id,day,actor,provider,model,state) VALUES (?,?,?,?,?,?)',
                        (key, day, actor, provider, model, 'attempted'))
        return key

    def finish(self, key, usage):
        # Missing usage is unknown, never a confirmed zero. Failed/cancelled attempts
        # keep their call reservation, including across server restarts.
        values = [getattr(usage, name, None) for name in ('input_tokens', 'output_tokens')]
        known = all(isinstance(v, int) and v >= 0 for v in values) and sum(values) > 0
        with closing(sqlite3.connect(self.path)) as con, con:
            con.execute('UPDATE ai_calls SET state=?,input_tokens=?,output_tokens=? WHERE id=?',
                        ('reported' if known else 'usage_unknown', *(values if known else [None, None]), key))

    def summary(self, actor):
        with closing(sqlite3.connect(self.path)) as con:
            row = con.execute('''SELECT COUNT(*), COALESCE(SUM(actor=?),0),
                COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0),
                COALESCE(SUM(state!='reported'),0) FROM ai_calls WHERE day=?''',
                (hashlib.sha256(actor.encode()).hexdigest(), self.day())).fetchone()
        return dict(day=self.day(), workspace_calls=row[0], user_calls=row[1],
                    reported_input_tokens=row[2], reported_output_tokens=row[3], unreported_calls=row[4])


class LimitedModel(Model):
    def __init__(self, base, owner, name):
        self.base, self.owner, self.name = base, owner, name

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema,
                           handoffs, tracing, **kwargs):
        owner = self.owner
        # Count UTF-8 bytes, not guessed tokens; never silently truncate evidence.
        evidence = {'instructions': system_instructions, 'input': input,
                    'tools': [{'name': t.name, 'description': getattr(t, 'description', ''),
                               'schema': getattr(t, 'params_json_schema', {})} for t in tools],
                    'output': output_schema.json_schema() if output_schema else None}
        if len(json.dumps(evidence, ensure_ascii=False, default=str).encode()) > owner.limits.context_bytes:
            raise AILimitError('This AI request contains too much data. Start a new chat or narrow the customer selection. Nothing new was sent.')
        if owner.calls >= owner.limits.request_calls:
            raise AILimitError('The assistant reached its step limit. No proposed changes were applied. Ask a narrower question.')
        if handoffs or kwargs.get('prompt') or kwargs.get('conversation_id') or kwargs.get('previous_response_id'):
            raise ValueError('Stored provider context and handoffs are not supported in this workspace.')
        if owner.ledger is None:
            raise ValueError('AI call tracking must be configured before sending data.')
        key = owner.ledger.reserve(owner.actor, owner.provider, self.name, owner.limits)
        owner.calls += 1
        settings = replace(model_settings, max_tokens=min(model_settings.max_tokens or owner.limits.output_tokens,
                           owner.limits.output_tokens), store=False, retry=None)
        result = await self.base.get_response(system_instructions, input, settings, tools, output_schema,
                                              handoffs, ModelTracing.DISABLED, **kwargs)
        owner.ledger.finish(key, getattr(result, 'usage', None))
        return result

    async def stream_response(self, *args, **kwargs):
        raise ValueError('Streaming model calls are not enabled in this workspace.')
        yield  # Make the SDK interface an async iterator, without an unmetered path.


class LimitedProvider(ModelProvider):
    def __init__(self, base, ledger, actor, provider, models, limits):
        self.base, self.ledger, self.actor, self.provider = base, ledger, actor, provider
        self.models, self.limits, self.calls = models, limits, 0

    def get_model(self, model_name):
        if model_name not in self.models.values():
            raise ValueError('This AI model is not configured for the workspace.')
        return LimitedModel(self.base.get_model(model_name), self, model_name)


@asynccontextmanager
async def ai_run_config(ledger, actor, expected_status):
    status = ai_status()
    if not status['ready'] or status.get('consent_id') != expected_status.get('consent_id', status.get('consent_id')):
        raise ValueError('AI settings changed. Review the sharing permission again; nothing was sent.')
    provider, endpoint, models, limits = provider_settings()
    # Explicit destinations; ambient OPENAI_BASE_URL and proxy settings cannot
    # redirect a cloud credential or silently turn local mode into a cloud call.
    from .cloud_network import current_bridge, RelayAsyncTransport
    bridge = current_bridge()
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                **({'transport':RelayAsyncTransport(bridge)} if bridge else {})) as transport:
        async with AsyncOpenAI(api_key='sk-private-relay-placeholder-not-a-real-key' if bridge else os.environ['OPENAI_API_KEY'] if provider == 'openai' else 'local-no-key',  # pragma: allowlist secret - non-secret relay placeholder
                               base_url=endpoint, http_client=transport, timeout=60, max_retries=0,
                               **({'organization': '', 'project': ''} if provider == 'local' else {})) as client:
            base = OpenAIProvider(openai_client=client, use_responses=provider == 'openai', strict_feature_validation=True)
            bounded = LimitedProvider(base, ledger, actor, provider, models, limits)
            yield RunConfig(tracing_disabled=True, model_provider=bounded)

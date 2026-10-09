import asyncio
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import httpx
from agents import Agent, Runner, ModelSettings
from agents.models.interface import Model, ModelTracing
from app.ai_provider import (AICallLedger, AILimitError, Limits, LimitedProvider,
    ai_status, ai_run_config, local_endpoint, validate_consent)
from app.ai_workspace import ChatRequest, run_chat
from tests.test_sales_demand import fixture, demand_outlook


class FakeModel(Model):
    def __init__(self, error=None, usage=True):
        self.calls, self.error, self.usage = [], error, usage

    async def get_response(self, *args, **kw):
        self.calls.append((args, kw))
        if self.error:
            raise self.error
        return SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=4) if self.usage else None)

    async def stream_response(self, *args, **kw):
        raise AssertionError('Streaming must not escape limits')
        yield


class ProviderTests(unittest.TestCase):
    def test_local_urls_cannot_send_to_remote_hosts_or_include_credentials(self):
        for url in ('https://example.com/v1', 'http://192.168.1.2:11434/v1',
                    'http://0.0.0.0:11434/v1', 'http://user:secret@localhost:11434/v1',
                    'http://localhost:11434/v1?token=secret', 'http://localhost:11434/v1#secret',
                    'http://localhost:80/v1', 'http://localhost:invalid/v1', 'http://localhost:11434/api'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                local_endpoint(url)
        self.assertEqual(local_endpoint('http://localhost:11434/v1/'), 'http://127.0.0.1:11434/v1')
        self.assertEqual(local_endpoint('http://[::1]:11434/v1'), 'http://[::1]:11434/v1')

    def test_invalid_config_fails_closed_and_local_requires_explicit_models(self):
        with patch.dict(os.environ, {'DEMANDLAB_AI_PROVIDER': 'local', 'DEMANDLAB_AI_ENABLED': 'true',
                                    'DEMANDLAB_AI_QUERY_MODEL': '', 'DEMANDLAB_AI_REVIEW_MODEL': '',
                                    'DEMANDLAB_AI_DECISION_MODEL': ''}):
            self.assertFalse(ai_status()['ready'])
        for value in ('0', '-1', 'not-a-number', '10001'):
            with patch.dict(os.environ, {'DEMANDLAB_AI_DAILY_CALLS': value}):
                self.assertFalse(ai_status()['ready'])

    def test_consent_belongs_to_data_recipient_not_any_provider(self):
        status = {'ready': True, 'provider': 'local', 'provider_label': 'Local AI', 'consent_id': 'a'*64}
        payload = ChatRequest(question='Forecast', run_id='run', consent=True)
        with self.assertRaisesRegex(ValueError, 'provider changed'):
            validate_consent(payload, status)
        validate_consent(payload.model_copy(update={'provider_id': 'a'*64}), status)
        with self.assertRaisesRegex(ValueError, 'provider changed'):
            validate_consent(payload.model_copy(update={'provider_id': 'b'*64}), status)

    def test_durable_atomic_limits_across_users_providers_and_restarts(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'usage.sqlite3'
            limits = Limits(daily_calls=4, actor_calls=2)
            ledger = AICallLedger(path)
            ledger.reserve('alice','openai','query',limits)
            key = ledger.reserve('alice','local','decision',limits)
            ledger.finish(key, None)
            with self.assertRaises(AILimitError):
                AICallLedger(path).reserve('alice','openai','review',limits)
            ledger.reserve('bob','local','query',limits)
            ledger.reserve('bob','openai','review',limits)
            with self.assertRaises(AILimitError):
                ledger.reserve('charlie','openai','query',limits)
            summary = ledger.summary('alice')
            self.assertEqual((summary['workspace_calls'],summary['user_calls'],summary['unreported_calls']), (4,2,4))
            with patch.object(AICallLedger, 'day', return_value='2099-01-01'):
                self.assertEqual(ledger.summary('alice')['workspace_calls'],0)
                ledger.reserve('alice','openai','query',limits)

    def test_concurrent_connections_cannot_overrun_daily_limit(self):
        with tempfile.TemporaryDirectory() as root:
            ledger = AICallLedger(Path(root)/'usage.sqlite3')
            limits = Limits(daily_calls=3, actor_calls=30)
            def reserve(i):
                try:
                    ledger.reserve(str(i),'openai','query',limits)
                    return True
                except AILimitError:
                    return False
            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(reserve,range(16))),3)


class CallTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ledger = AICallLedger(Path(self.tmp.name)/'usage.sqlite3')

    def provider(self, base, limits=Limits()):
        return LimitedProvider(SimpleNamespace(get_model=lambda name: base), self.ledger, 'alice',
                               'local', {'query':'query-test'}, limits)

    async def call(self, model, text='hello'):
        return await model.get_response('Instructions',text,ModelSettings(max_tokens=9000,store=True), [],None,[],
            ModelTracing.ENABLED, previous_response_id=None, conversation_id=None, prompt=None)

    async def test_each_call_is_metered_and_response_capped_with_tracing_off(self):
        base = FakeModel(); provider = self.provider(base, replace(Limits(),request_calls=2))
        await self.call(provider.get_model('query-test'))
        await self.call(provider.get_model('query-test'))
        with self.assertRaises(AILimitError):
            await self.call(provider.get_model('query-test'))
        self.assertEqual(len(base.calls),2)
        settings = base.calls[0][0][2]
        self.assertEqual(settings.max_tokens,2500)
        self.assertFalse(settings.store)
        self.assertIsNone(settings.retry)
        self.assertEqual(base.calls[0][0][6],ModelTracing.DISABLED)
        self.assertEqual(self.ledger.summary('alice')['reported_input_tokens'],20)

    async def test_oversized_context_unknown_model_and_streaming_never_call_provider(self):
        base = FakeModel(); provider = self.provider(base)
        with self.assertRaises(AILimitError):
            await self.call(provider.get_model('query-test'),'الف'*50000)
        with self.assertRaises(ValueError):
            provider.get_model('not-configured')
        with self.assertRaises(ValueError):
            async for _ in provider.get_model('query-test').stream_response():
                pass
        self.assertEqual(base.calls,[])
        self.assertEqual(self.ledger.summary('alice')['workspace_calls'],0)

    async def test_errors_cancellation_and_missing_usage_do_not_reset_calls(self):
        for error in (RuntimeError('private provider detail'), asyncio.CancelledError(), None):
            with self.subTest(error=type(error).__name__):
                model = self.provider(FakeModel(error=error,usage=False)).get_model('query-test')
                if error:
                    with self.assertRaises(type(error)):
                        await self.call(model)
                else:
                    await self.call(model)
        summary = self.ledger.summary('alice')
        self.assertEqual((summary['workspace_calls'],summary['unreported_calls']), (3,3))
        self.assertEqual(summary['reported_input_tokens'],0)

    async def test_real_sdk_local_transport_uses_no_cloud_key_and_no_fallback(self):
        seen=[]
        def handler(request):
            seen.append(request)
            return httpx.Response(200,json={'id':'local-completion','object':'chat.completion','created':1,
                'model':'query-test','choices':[{'index':0,'finish_reason':'stop',
                    'message':{'role':'assistant','content':'Local response'}}],
                'usage':{'prompt_tokens':12,'completion_tokens':3,'total_tokens':15}})
        client_type = httpx.AsyncClient
        test = self
        class Transport(client_type):
            def __init__(self, **kwargs):
                test.assertFalse(kwargs['trust_env'])
                test.assertFalse(kwargs['follow_redirects'])
                super().__init__(transport=httpx.MockTransport(handler), **kwargs)
        env={'DEMANDLAB_AI_PROVIDER':'local','DEMANDLAB_AI_ENABLED':'true',
             'DEMANDLAB_AI_QUERY_MODEL':'query-test','DEMANDLAB_AI_REVIEW_MODEL':'review-test',
             'DEMANDLAB_AI_DECISION_MODEL':'decision-test','OPENAI_API_KEY':'sk-secret-never-send',
             'OPENAI_BASE_URL':'https://must-not-call.example/v1','DEMANDLAB_AI_LOCAL_URL':'http://localhost:11434/v1'}
        with patch.dict(os.environ,env), patch('app.ai_provider.httpx.AsyncClient',Transport):
            status=ai_status()
            self.assertTrue(status['ready']); self.assertFalse(status['connection_verified'])
            async with ai_run_config(self.ledger,'alice',status) as config:
                result=await Runner.run(Agent('Fixture',model='query-test',model_settings=ModelSettings(max_tokens=500)),
                                        'Hello',max_turns=1,run_config=config)
            self.assertEqual(result.final_output,'Local response')
        self.assertEqual(len(seen),1)
        self.assertEqual(str(seen[0].url),'http://127.0.0.1:11434/v1/chat/completions')
        self.assertEqual(seen[0].headers['authorization'],'Bearer local-no-key')
        self.assertEqual(self.ledger.summary('alice')['workspace_calls'],1)

    async def test_redirects_errors_and_disabled_ai_make_no_fallback_or_retry(self):
        seen=[]
        response=[307]
        def handler(request):
            seen.append(request)
            return httpx.Response(response[0],headers={'location':'https://must-not-call.example/v1/chat/completions'},
                                  json={'error':{'message':'Private provider failure'}})
        client_type=httpx.AsyncClient
        class Transport(client_type):
            def __init__(self, **kwargs):
                super().__init__(transport=httpx.MockTransport(handler),**kwargs)
        env={'DEMANDLAB_AI_PROVIDER':'local','DEMANDLAB_AI_ENABLED':'true',
             'DEMANDLAB_AI_QUERY_MODEL':'query-test','DEMANDLAB_AI_REVIEW_MODEL':'review-test',
             'DEMANDLAB_AI_DECISION_MODEL':'decision-test','DEMANDLAB_AI_LOCAL_URL':'http://127.0.0.1:11434/v1'}
        with patch.dict(os.environ,env), patch('app.ai_provider.httpx.AsyncClient',Transport):
            for code in (307,500):
                response[0]=code
                async with ai_run_config(self.ledger,'alice',ai_status()) as config:
                    with self.assertRaises(Exception):
                        await Runner.run(Agent('Fixture',model='query-test'), 'Hello',max_turns=1,run_config=config)
            os.environ['DEMANDLAB_AI_ENABLED']='false'
            with self.assertRaises(ValueError):
                async with ai_run_config(self.ledger,'alice',ai_status()):
                    self.fail('Disabled AI entered the provider context')
        self.assertEqual(len(seen),2)
        self.assertTrue(all(r.url.host=='127.0.0.1' for r in seen))
        self.assertEqual(self.ledger.summary('alice')['unreported_calls'],2)

    async def test_real_sdk_routes_then_reads_exact_saved_order_aware_demand(self):
        run,inputs=fixture()
        outlook={**demand_outlook(inputs,run),'snapshot_id':'snapshot'}
        seen=[]
        def handler(request):
            body=json.loads(request.content); seen.append(body)
            if len(seen)==1:
                self.assertEqual(body['model'],'query-test')
                self.assertEqual(body['response_format']['type'],'json_schema')
                message={'role':'assistant','content':'{"role":"decision"}'}; finish='stop'
            elif len(seen)==2:
                self.assertEqual(body['model'],'decision-test')
                self.assertIn('inspect_forecast',[t['function']['name'] for t in body['tools']])
                message={'role':'assistant','content':None,'tool_calls':[{'id':'call-fixture','type':'function',
                    'function':{'name':'inspect_forecast','arguments':'{"customer":"B"}'}}]}; finish='tool_calls'
            else:
                evidence=ast.literal_eval(next(m['content'] for m in body['messages'] if m['role']=='tool'))
                self.assertEqual(evidence['rows'][0]['customer'],'B')
                self.assertEqual(evidence['rows'][0]['total'],8)
                message={'role':'assistant','content':'Expected demand is 8 tonnes.'}; finish='stop'
            return httpx.Response(200,json={'id':f'completion-{len(seen)}','object':'chat.completion','created':1,
                'model':body['model'],'choices':[{'index':0,'finish_reason':finish,'message':message}],
                'usage':{'prompt_tokens':12,'completion_tokens':3,'total_tokens':15}})
        client_type=httpx.AsyncClient
        class Transport(client_type):
            def __init__(self, **kwargs):
                super().__init__(transport=httpx.MockTransport(handler),**kwargs)
        env={'DEMANDLAB_AI_PROVIDER':'local','DEMANDLAB_AI_ENABLED':'true',
             'DEMANDLAB_AI_QUERY_MODEL':'query-test','DEMANDLAB_AI_REVIEW_MODEL':'review-test',
             'DEMANDLAB_AI_DECISION_MODEL':'decision-test','DEMANDLAB_AI_LOCAL_URL':'http://127.0.0.1:11434/v1'}
        with patch.dict(os.environ,env),patch('app.ai_provider.httpx.AsyncClient',Transport):
            payload=ChatRequest(question='Demand for B?',run_id=run['run_id'],snapshot_id='snapshot',
                                consent=True,provider_id=ai_status()['consent_id'])
            result=await run_chat(payload,run,outlook,ledger=self.ledger,actor='alice')
        self.assertEqual(result['answer'],'Expected demand is 8 tonnes.')
        self.assertEqual(result['role'],'decision'); self.assertEqual(result['provider'],'local')
        self.assertEqual(result['usage']['requests'],3)
        self.assertEqual(self.ledger.summary('alice')['workspace_calls'],3)
        self.assertEqual(self.ledger.summary('alice')['unreported_calls'],0)

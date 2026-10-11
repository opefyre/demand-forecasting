"""No cached input contexts outside a single immutable company projection."""
import asyncio
from contextlib import nullcontext
import json
import time
import unittest
from unittest.mock import patch

from app import cloud_api, forecast_inputs
from tests import test_platform_sales as sales_fixture


class ProjectionInputTests(unittest.TestCase):
    def setUp(self):
        self.fixture = sales_fixture.PublicSalesTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        _, self.dataset, _ = self.fixture.history()

    def test_scoped_copies_no_cross_store_or_cross_request_reuse(self):
        store = self.fixture.ws.datasets
        with patch.object(forecast_inputs, '_input_context', wraps=forecast_inputs._input_context) as prepare:
            with forecast_inputs.projection_input_reads(store):
                first = forecast_inputs.input_context(store, self.dataset['id'])
                first['metadata'].clear()
                second = forecast_inputs.input_context(store, self.dataset['id'])
                self.assertTrue(second['metadata'])
                self.assertEqual(prepare.call_count, 1)
                # Plain history has identical context through either reader.
                forecast_inputs.input_context(store, self.dataset['id'], reviewed_scenario=True)
                self.assertEqual(prepare.call_count, 1)
                self.fixture.company = 'tehran_b'
                _, other, _ = self.fixture.history(2)
                forecast_inputs.input_context(self.fixture.ws.datasets, other['id'])
                self.assertEqual(prepare.call_count, 2)
            forecast_inputs.input_context(store, self.dataset['id'])
            self.assertEqual(prepare.call_count, 3)
            self.assertEqual(forecast_inputs._projection_context.get(), None)
            source = store.get(self.dataset['id'])['sources']['history']
            (store.root / (source + '.bin')).write_bytes(b'corrupted test source')
            with self.assertRaises(ValueError):
                forecast_inputs.input_context(store, self.dataset['id'])

    def test_projection_matches_uncached_permissions_and_values(self):
        fixture = self.fixture
        fixture.orders(self.dataset)
        measurements = {}
        payloads = []
        for cached in (False, True):
            context = forecast_inputs.projection_input_reads if cached else lambda store: nullcontext()
            with patch.object(forecast_inputs, 'projection_input_reads', context), \
                 patch.object(forecast_inputs, '_input_context', wraps=forecast_inputs._input_context) as prepare:
                started = time.perf_counter()
                result = json.loads(asyncio.run(cloud_api.projection(fixture.api, fixture.ws, fixture.company)))
                measurements['cached' if cached else 'uncached'] = {
                    'seconds': round(time.perf_counter() - started, 4), 'preparations': prepare.call_count}
            result.pop('checked_at')
            payloads.append(result)
        self.assertEqual(payloads[0], payloads[1])
        self.assertLess(measurements['cached']['preparations'], measurements['uncached']['preparations'])
        self.assertEqual(payloads[1]['report_views']['/runs']['runs'], [])
        print('Synthetic projection comparison: ' + json.dumps(measurements), flush=True)

    def test_scope_is_released_on_exception_and_nested_scope(self):
        store = self.fixture.ws.datasets
        with self.assertRaises(RuntimeError):
            with forecast_inputs.projection_input_reads(store):
                outer = forecast_inputs._projection_context.get()
                with forecast_inputs.projection_input_reads(store):
                    self.assertIsNot(forecast_inputs._projection_context.get(), outer)
                self.assertIs(forecast_inputs._projection_context.get(), outer)
                raise RuntimeError('Stop the projection')
        self.assertIsNone(forecast_inputs._projection_context.get())

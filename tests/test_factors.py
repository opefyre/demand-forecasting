from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import httpx

from app.factors import FactorStore, observations_available_at


class FactorTests(unittest.TestCase):
    def transport(self, country='IRN', value=32.5):
        return httpx.MockTransport(lambda request: httpx.Response(200, json=[{'lastupdated': '2026-09-01'}, [
            {'countryiso3code': country, 'indicator': {'id': 'FP.CPI.TOTL.ZG'}, 'date': '2025', 'value': value},
            {'countryiso3code': country, 'indicator': {'id': 'FP.CPI.TOTL.ZG'}, 'date': '2024', 'value': None},
        ]]))

    def test_refresh_persists_a_real_response_not_a_live_status_only(self):
        with TemporaryDirectory() as folder:
            store = FactorStore(Path(folder))
            snapshot = store.refresh('iran_inflation', transport=self.transport())
            stored = FactorStore(Path(folder)).get(snapshot['id'])
            self.assertEqual(stored['points'][0]['value'], 32.5)
            self.assertEqual(stored['use'], 'context_only')
            self.assertEqual(len(stored['sha256']), 64)
            self.assertTrue((store.root / stored['raw_response']).exists())
            self.assertTrue(observations_available_at(stored, '2025-12-31').empty)
            self.assertEqual(len(observations_available_at(stored, stored['captured_at'])), 1)

    def test_refresh_failure_preserves_prior_snapshots(self):
        with TemporaryDirectory() as folder:
            store = FactorStore(Path(folder))
            store.refresh('iran_inflation', transport=self.transport())
            with self.assertRaisesRegex(ValueError, 'country or indicator'):
                store.refresh('iran_inflation', transport=self.transport(country='USA'))
            self.assertEqual(len(store.list()), 1)

    def test_unsupported_source_and_path_are_rejected(self):
        with TemporaryDirectory() as folder:
            store = FactorStore(Path(folder))
            with self.assertRaises(ValueError): store.refresh('https://arbitrary.example/')
            with self.assertRaises(ValueError): store.get('../anything')


if __name__ == '__main__': unittest.main()

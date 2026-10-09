from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

import httpx

from app.factors import FactorStore, observations_available_at
from app.supply_pressure import DATA_URL, freshness, parse_supply_pressure


# Deliberately synthetic values and two revisions, not provider measurements.
CSV = b'Date,Jan-25,Feb-25\r\n31-Dec-2024,-0.5,-0.4\r\n31-Jan-2025,#N/A,0.2\r\n,,\r\n'
CAPTURED = '2025-02-20T12:00:00+00:00'


class SupplyPressureTests(unittest.TestCase):
    def test_latest_vintage_without_fabricated_release_day(self):
        parsed = parse_supply_pressure(CSV, CAPTURED)
        self.assertEqual(parsed['provider_vintage_month'], '2025-02')
        self.assertEqual(parsed['points'][0]['value'], -0.4)
        self.assertEqual(parsed['points'][0]['available_at'], CAPTURED)
        self.assertIsNone(parsed['provider_updated_at'])
        self.assertTrue(observations_available_at(parsed, '2025-02-01').empty)

    def test_invalid_schema_dates_values_and_duplicate_months(self):
        invalid = [CSV.replace(b'Date', b'Period'), CSV.replace(b'Jan-25,Feb-25', b'Feb-25,Feb-25'),
                   CSV.replace(b'31-Dec-2024', b'30-Dec-2024'), CSV.replace(b'0.2', b'nan'),
                   CSV.replace(b'0.2', b'#N/A'), CSV.replace(b'31-Jan-2025', b'31-Dec-2024'),
                   CSV.replace(b'#N/A', b'0.7'), CSV.replace(b'Feb-25', b'Feb-30'),
                   CSV.replace(b'31-Dec-2024', b'31-Oct-2024'), b'<html>maintenance</html>']
        for content in invalid:
            with self.subTest(content=content), self.assertRaises(ValueError):
                parse_supply_pressure(content, CAPTURED)

    def test_retains_exact_response_and_versions(self):
        requests = []
        def serve(request):
            requests.append(request)
            return httpx.Response(200, content=CSV)
        with TemporaryDirectory() as folder:
            store = FactorStore(Path(folder))
            one = store.refresh('global_supply_pressure', transport=httpx.MockTransport(serve))
            two = store.refresh('global_supply_pressure', transport=httpx.MockTransport(serve))
            self.assertNotEqual(one['id'], two['id'])
            self.assertEqual((Path(folder) / one['raw_response']).read_bytes(), CSV)
            self.assertEqual(one['sha256'], hashlib.sha256(CSV).hexdigest())
            self.assertEqual(one['use'], 'context_only')
            self.assertEqual(len(store.list()), 2)
            self.assertEqual(str(requests[0].url), DATA_URL)
            self.assertEqual(requests[0].content, b'')

    def test_failure_and_oversize_preserve_previous_snapshot(self):
        with TemporaryDirectory() as folder:
            store = FactorStore(Path(folder))
            good = httpx.MockTransport(lambda r: httpx.Response(200, content=CSV))
            before = store.refresh('global_supply_pressure', transport=good)
            for status, body in [(503, b'Unavailable'), (302, b''), (200, b'broken'), (200, b'x' * 2_000_001)]:
                with self.subTest(status=status, length=len(body)), self.assertRaises((ValueError, httpx.HTTPError)):
                    store.refresh('global_supply_pressure', transport=httpx.MockTransport(
                        lambda r: httpx.Response(status, content=body)))
            self.assertEqual(store.list(), [before])

    def test_freshness_is_about_observation_age_not_fetch_success(self):
        row = parse_supply_pressure(CSV, CAPTURED)
        self.assertEqual(freshness(row, '2025-03-31T00:00:00Z')['status'], 'recent')
        self.assertEqual(freshness(row, '2025-04-01T00:00:00Z')['status'], 'behind')


if __name__ == '__main__':
    unittest.main()

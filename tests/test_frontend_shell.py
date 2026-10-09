"""Entry routes never fall back to the obsolete, separately styled PoC."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
import app.main as main


class FrontendShellTests(unittest.TestCase):
    def test_both_entry_routes_use_the_current_shell(self):
        endpoints = {route.path: route.endpoint for route in main.app.routes if hasattr(route, 'endpoint')}
        self.assertIs(endpoints['/'], main.frontend)
        self.assertIs(endpoints['/index.html'], main.frontend)
        for page in ('today', 'demand', 'forecast', 'data', 'plans', 'settings', 'customers', 'help', 'new', 'assistant'):
            self.assertIs(endpoints['/' + page], main.frontend)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'client').mkdir()
            (root / 'client' / 'index.html').write_text('<main>Current shell</main>')
            with patch.object(main, 'STATIC_DIR', root):
                self.assertEqual(Path(main.frontend().path), root / 'client' / 'index.html')

    def test_missing_build_never_serves_old_poc(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'index.html').write_text('<main>Obsolete PoC</main>')
            with patch.object(main, 'STATIC_DIR', root):
                with self.assertRaises(HTTPException) as failure:
                    main.frontend()
            self.assertEqual(failure.exception.status_code, 503)
            self.assertIn('has not been built', failure.exception.detail)

    def test_direct_page_requests_use_current_shell_and_do_not_mask_other_paths(self):
        # No lifespan: do not start background refreshers during this routing test.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'client').mkdir()
            (root / 'client' / 'index.html').write_text('<main>Current shell</main>')
            with patch.object(main, 'STATIC_DIR', root):
                client = TestClient(main.app)
                try:
                    for page in ('today', 'demand', 'forecast', 'data', 'plans', 'settings', 'customers', 'help'):
                        response = client.get('/' + page)
                        self.assertEqual(response.status_code, 200, page)
                        self.assertIn('Current shell', response.text)
                    for path in ('/api/nonexistent-route', '/ui/missing-asset.js', '/unknown-page'):
                        self.assertEqual(client.get(path).status_code, 404, path)
                finally:
                    client.close()

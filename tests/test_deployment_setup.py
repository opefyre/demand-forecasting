"""Read-only contracts for deployment templates; no host or provider activation."""
from configparser import ConfigParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / 'deploy'


def unit(name):
    parsed = ConfigParser(interpolation=None)
    parsed.optionxform = str
    parsed.read(DEPLOY / 'linux' / name)
    return parsed


def settings(name):
    return dict(line.split('=', 1) for line in (DEPLOY / name).read_text().splitlines()
                if line.strip() and not line.startswith('#'))


class DeploymentSetupTests(unittest.TestCase):
    def test_company_settings_have_no_real_credentials_or_public_demo(self):
        env = settings('deployment.env.example')
        self.assertEqual(env['DEMANDLAB_AUTH_MODE'], 'better_auth')
        self.assertEqual(env['DEMANDLAB_PUBLIC_ORIGIN'], '')
        self.assertEqual(env['DEMANDLAB_AUTH_SERVICE_URL'], 'http://127.0.0.1:8011')
        self.assertEqual(env['DEMANDLAB_AI_ENABLED'], 'false')
        self.assertEqual(env['DEMANDLAB_AUTH_DEV_MAIL'], 'false')
        self.assertEqual(env['DEMANDLAB_CONNECTOR_PRIVATE_TARGETS'], '{}')
        for name in ('BETTER_AUTH_SECRET', 'DEMANDLAB_AUTH_BRIDGE_SECRET',
                     'DEMANDLAB_AUTH_DATABASE_URL', 'SMTP_HOST', 'SMTP_USER',
                     'SMTP_PASSWORD', 'SMTP_FROM', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET'):
            self.assertEqual(env[name], '', name)
        self.assertFalse(any(name.startswith('DEMANDLAB_BOOTSTRAP_') for name in env))
        self.assertNotIn('OPENAI_API_KEY', env)
        bootstrap = settings('bootstrap.env.example')
        self.assertEqual(len(bootstrap), 5)
        self.assertTrue(all(not value for value in bootstrap.values()))

    def test_services_share_private_configuration_and_non_root_hardening(self):
        for path in (DEPLOY / 'linux').glob('*.service'):
            if path.name == 'demandlab-bootstrap.service':
                continue  # Its repeated EnvironmentFile entries are checked below.
            with self.subTest(service=path.name):
                service = unit(path.name)['Service']
                self.assertEqual(service['User'], 'demandlab')
                self.assertEqual(service['Group'], 'demandlab')
                self.assertEqual(service['UMask'], '0077')
                self.assertEqual(service['ProtectSystem'], 'strict')
                self.assertEqual(service['ProtectHome'], 'yes')
                self.assertEqual(service['NoNewPrivileges'], 'yes')
                self.assertEqual(service['PrivateTmp'], 'yes')
                self.assertEqual(service['EnvironmentFile'], '/etc/demandlab/secrets/deployment.env')

    def test_api_uses_one_private_process_and_no_demo_worker_launcher(self):
        command = unit('demandlab-api.service')['Service']['ExecStart']
        self.assertIn('--host 127.0.0.1 --port 8020 --workers 1', command)
        self.assertIn('--forwarded-allow-ips 127.0.0.1', command)
        self.assertIn('--no-access-log', command)
        self.assertNotIn('8010', command)
        self.assertNotIn('run.py', command)
        self.assertEqual(unit('demandlab-worker.service')['Service']['ExecStart'],
                         '/opt/demandlab/.venv/bin/python -m app.worker')
        auth = unit('demandlab-auth.service')['Service']['ExecStart']
        self.assertIn('src/server.ts', auth)
        self.assertIn('127.0.0.1', (ROOT / 'auth-service/src/server.ts').read_text())

    def test_only_runtime_paths_are_writable(self):
        expected = {'/opt/demandlab/' + name for name in
                    ('data', 'runs', '.forecast-work', '.workspace.lock')}
        for name in ('api', 'worker'):
            actual = unit(f'demandlab-{name}.service')['Service']['ReadWritePaths']
            self.assertEqual(set(actual.split()), expected)
        for name in ('auth', 'check'):
            self.assertNotIn('ReadWritePaths', unit(f'demandlab-{name}.service')['Service'])

    def test_target_runs_configuration_check_and_stops_all_runtime_services(self):
        target = unit('demandlab.target')['Unit']
        self.assertEqual(target['Requires'], 'demandlab-check.service')
        wanted = {'demandlab-' + name + '.service' for name in ('auth', 'api', 'worker')}
        self.assertEqual(set(target['Wants'].split()), wanted)
        for name in ('check', 'auth', 'api', 'worker'):
            definition = unit(f'demandlab-{name}.service')
            self.assertEqual(definition['Unit']['PartOf'], 'demandlab.target')
            if name != 'check':
                self.assertIn('demandlab-check.service', definition['Unit']['Requires'])
                self.assertIn('demandlab-check.service', definition['Unit']['After'])
        check = unit('demandlab-check.service')['Service']
        self.assertIn('src/preflight.ts', check['ExecStart'])
        self.assertNotIn('--local', check['ExecStart'])
        self.assertEqual(check['Type'], 'oneshot')
        # A transient runtime failure must not stop the target and all siblings.
        # Each process restarts independently; authentication stays fail-closed.
        for name in ('api', 'worker'):
            definition = unit(f'demandlab-{name}.service')
            self.assertNotIn('demandlab-auth.service', definition['Unit']['Requires'])
            self.assertIn('demandlab-auth.service', definition['Unit']['Wants'])
            self.assertEqual(definition['Service']['Restart'], 'on-failure')

    def test_bootstrap_is_offline_manual_only_and_not_in_target(self):
        raw = (DEPLOY / 'linux/demandlab-bootstrap.service').read_text()
        self.assertNotIn('[Install]', raw)
        self.assertNotIn('Restart=', raw)
        self.assertIn('EnvironmentFile=/etc/demandlab/secrets/bootstrap.env', raw)
        self.assertEqual(re.findall(r'^EnvironmentFile=(.*)$', raw, re.M),
                         ['/etc/demandlab/secrets/deployment.env', '/etc/demandlab/secrets/bootstrap.env'])
        self.assertIn('User=demandlab', raw)
        self.assertIn('UMask=0077', raw)
        self.assertIn('src/bootstrap.ts', raw)
        self.assertNotIn('bootstrap', (DEPLOY / 'linux/demandlab.target').read_text())
        for name in ('check', 'auth', 'api', 'worker'):
            self.assertNotIn('bootstrap.env', (DEPLOY / f'linux/demandlab-{name}.service').read_text())

    def test_proxy_does_not_expose_identity_or_block_legitimate_data_page(self):
        raw = (DEPLOY / 'linux/Caddyfile.example').read_text()
        active = '\n'.join(line for line in raw.splitlines() if not line.strip().startswith('#'))
        self.assertEqual(re.findall(r'reverse_proxy\s+(\S+)', active), ['127.0.0.1:8020'])
        self.assertNotIn('8010', active)
        self.assertNotIn('8011', active)
        self.assertNotIn('file_server', active)
        self.assertNotIn('log {', active)
        paths = re.search(r'@private path ([^\n]+)', active).group(1).split()
        for path in ('/internal', '/internal/*', '/secrets', '/secrets/*', '/.git', '/.git/*',
                     '/.env', '/.env.*', '/RESTORE_INCOMPLETE'):
            self.assertIn(path, paths)
        self.assertNotIn('/data', paths)
        self.assertNotIn('/api/v1/*', paths)

    def test_runbook_exposes_real_gates_without_activating_demo(self):
        text = (ROOT / 'docs/DEPLOYMENT_SETUP.md').read_text()
        for phrase in ('macOS Keychain', 'AI stays off', 'systemd-analyze verify',
                       'caddy validate', 'http://127.0.0.1:8010', 'whole target',
                       'No packages installed', '/api/login/callback/google',
                       'password authentication', 'including dev dependencies'):
            self.assertIn(phrase, text)
        self.assertTrue((ROOT / 'docs/DEPLOYMENT_ACCEPTANCE.md').exists())


if __name__ == '__main__':
    unittest.main()

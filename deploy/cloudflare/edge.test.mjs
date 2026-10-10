import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import edge from './edge.mjs';

test('all app, identity, internal and secret routes stay closed', async () => {
  for (const path of ['/', '/demand', '/data', '/api', '/api/v1/customers',
    '/api/login/callback/google?code=private-code', '/internal', '/secrets', '/.env']) {
    for (const method of ['GET', 'POST', 'HEAD', 'OPTIONS']) {
      const response = await edge.fetch(new Request('https://forecast.vrolen.com' + path, { method }));
      assert.equal(response.status, 503);
      assert.equal(response.headers.get('cache-control'), 'no-store');
      assert.equal(response.headers.get('x-robots-tag'), 'noindex, nofollow');
      assert.equal(response.headers.get('access-control-allow-origin'), null);
      assert.equal(response.headers.get('set-cookie'), null);
      const body = await response.text();
      assert.ok(!body.includes('private-code'));
      assert.equal(method === 'HEAD', body === '');
    }
  }
});

test('API responds truthfully with an unavailable status, not a demo', async () => {
  const response = await edge.fetch(new Request('https://forecast.vrolen.com/api/v1/forecasts'));
  assert.equal((await response.json()).error, 'deployment_not_ready');
});

test('owner-only gateway has only the approved domain and private service bindings', async () => {
  const config = JSON.parse(await readFile(new URL('./wrangler.jsonc', import.meta.url), 'utf8'));
  assert.equal(config.name, 'demandlab-forecast-edge');
  assert.deepEqual(config.routes, [{ pattern: 'forecast.vrolen.com', custom_domain: true }]);
  assert.equal(config.workers_dev, false);
  assert.equal(config.preview_urls, false);
  assert.equal(config.observability.enabled, false);
  assert.equal(config.limits.cpu_ms, 50);
  assert.equal(config.vars.PRIVATE_ACCESS,'closed');assert.equal(config.vars.OWNER_ONLY_ACCEPTANCE,'true');
  assert.equal(config.assets.run_worker_first,true);
  assert.deepEqual(config.services.map(s=>s.service),['demandlab-forecast-identity','demandlab-forecast-storage','demandlab-forecast-engine']);
  for (const key of ['containers', 'r2_buckets', 'd1_databases', 'triggers']) {
    assert.ok(!(key in config), key);
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { randomBytes } from "node:crypto";
import { Miniflare, convertV4MiniflareOptions } from "miniflare";
type WorkerFetcher = { fetch(input: string, init?: RequestInit): Promise<Response> };

test("identity deployment has no public URL, routes, cron, engine or existing database bindings", async () => {
  const config = JSON.parse(await readFile(new URL("../../deploy/cloudflare/identity.wrangler.jsonc", import.meta.url), "utf8"));
  assert.equal(config.name, "demandlab-forecast-identity");
  assert.equal(config.workers_dev, false);
  assert.equal(config.preview_urls, false);
  assert.deepEqual(config.routes, []);
  assert.equal(config.observability.enabled, false);
  assert.equal(config.vars.PRIVATE_ACCESS, "closed");
  assert.equal(config.vars.NODE_ENV, "production");
  assert.deepEqual(config.d1_databases.map((binding: any) => binding.database_id),
    ["f0f8d4b4-ff3d-4bcc-90ac-c08ff97b64e7"]);
  for (const binding of ["assets", "containers", "r2_buckets", "triggers", "services"])
    assert.ok(!(binding in config), binding);
  for (const key of Object.keys(config.vars)) assert.ok(!/secret|key|password/i.test(key));
});

// Build first with Wrangler --dry-run. This caller exists only in disposable
// Miniflare memory; it is NEVER deployed or given real credentials.
test("built identity Worker denies every HTTP route while private RPC checks native D1",
  { timeout: 30000, skip: !process.env.DEMANDLAB_TEST_CLOUDFLARE_BUNDLE }, async () => {
  const runtime = new Miniflare(convertV4MiniflareOptions({ telemetry: { enabled: false }, workers: [
    { name: "identity", modules: true,
      script: await readFile(new URL("../../deploy/cloudflare/build/identity/cloudflare-worker.js", import.meta.url), "utf8"),
      compatibilityDate: "2026-10-09",
      bindings: { PRIVATE_ACCESS: "closed", NODE_ENV: "production", BETTER_AUTH_SECRET: randomBytes(32).toString("hex"),
        RESEND_API_KEY: "re_synthetic_not_a_real_key", GOOGLE_CLIENT_ID: "945632758521-baj6dsc8irl5qmcknbi0tgt4ui0skjl0.apps.googleusercontent.com",
        GOOGLE_CLIENT_SECRET: "synthetic-not-a-real-secret" }, d1Databases: ["IDENTITY_DB"] },
    { name: "test-only-caller", modules: true, compatibilityDate: "2026-10-09",
      script: "export default { async fetch(request, env) { return Response.json(await env.IDENTITY.readiness()); } };",
      serviceBindings: { IDENTITY: { name: "identity", entrypoint: "ForecastIdentity" } } },
  ] }));
  try {
    const worker = await runtime.getWorker("identity") as unknown as WorkerFetcher;
    for (const path of ["/", "/api/login/sign-up/email", "/api/login/sign-in/social", "/api/v1/customers", "/internal", "/secrets"])
      for (const method of ["GET", "POST", "HEAD", "OPTIONS"]) {
        const denied = await worker.fetch("https://forecast.vrolen.com" + path, { method });
        assert.equal(denied.status, 404);
        assert.equal(denied.headers.get("set-cookie"), null);
        assert.equal(denied.headers.get("cache-control"), "no-store");
        assert.equal(denied.headers.get("access-control-allow-origin"), null);
      }
    const caller = await runtime.getWorker("test-only-caller") as unknown as WorkerFetcher;
    assert.equal((await (await caller.fetch("https://local.test/")).json() as any).schema_ready, false);
    const db = await runtime.getD1Database("IDENTITY_DB", "identity");
    const sql = await readFile(new URL("../../deploy/cloudflare/migrations/0001_identity.sql", import.meta.url), "utf8");
    await db.batch(sql.replace(/^--.*$/gm, "").split(";").map(statement => statement.trim())
      .filter(Boolean).map(statement => db.prepare(statement)));
    const readiness = await (await caller.fetch("https://local.test/")).json();
    assert.deepEqual(readiness, { access: "closed", schema_ready: true, google_configured: true,
      mail_configured: true, sign_in_verified: false, delivery_verified: false });
    assert.equal((await db.prepare('SELECT count(*) AS n FROM "user"').first<{ n: number }>())!.n, 0);
  } finally { await runtime.dispose(); }
});

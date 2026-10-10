import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { randomBytes } from "node:crypto";
import { Miniflare, convertV4MiniflareOptions } from "miniflare";
import { createAuthCore } from "../src/auth-core.js";
import { FORECAST_ORIGIN } from "../src/cloudflare.js";
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
  assert.deepEqual(config.durable_objects.bindings, [{ name: "ACCESS", class_name: "ForecastAccess" }]);
  assert.deepEqual(config.d1_databases.map((binding: any) => binding.database_id),
    ["f0f8d4b4-ff3d-4bcc-90ac-c08ff97b64e7"]);
  for (const binding of ["assets", "containers", "r2_buckets", "triggers", "services"])
    assert.ok(!(binding in config), binding);
  for (const key of Object.keys(config.vars)) assert.ok(!/secret|key|password/i.test(key));
});

// Build first with Wrangler --dry-run. This caller exists only in disposable
// Miniflare memory; it is NEVER deployed or given real credentials.
test("built identity Worker denies every HTTP route while private RPC checks native D1",
  { timeout: 60000, skip: !process.env.DEMANDLAB_TEST_CLOUDFLARE_BUNDLE }, async () => {
  const secret = randomBytes(32).toString("hex");
  const runtime = new Miniflare(convertV4MiniflareOptions({ telemetry: { enabled: false }, workers: [
    { name: "identity", modules: true,
      script: await readFile(new URL("../../deploy/cloudflare/build/identity/cloudflare-worker.js", import.meta.url), "utf8"),
      compatibilityDate: "2026-10-09",
      durableObjects: { ACCESS: { className: "ForecastAccess", useSQLite: true } },
      bindings: { PRIVATE_ACCESS: "closed", NODE_ENV: "production", BETTER_AUTH_SECRET: secret,
        RESEND_API_KEY: "re_synthetic_not_a_real_key", GOOGLE_CLIENT_ID: "945632758521-baj6dsc8irl5qmcknbi0tgt4ui0skjl0.apps.googleusercontent.com",
        GOOGLE_CLIENT_SECRET: "synthetic-not-a-real-secret" }, d1Databases: ["IDENTITY_DB"] },
    { name: "test-only-caller", modules: true, compatibilityDate: "2026-10-09",
      script: "export default { async fetch(request, env) { if(request.method==='POST') { const {operation,body}=await request.json(); return Response.json(await env.IDENTITY.operation(operation,body)); } return Response.json(await env.IDENTITY.readiness()); } };",
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
    // Disposable operator fixture only. Never deployed and no real mail/keys.
    const fixture = createAuthCore({ origin: FORECAST_ORIGIN, secret, local: false }, db, {
      async invitationAllowed() { return true; }, async recordMfa() {}, async clearMfa() {},
    }, async () => {});
    const password = "Synthetic-" + randomBytes(24).toString("hex");
    const people: { user: string; cookie: string; session: string }[] = [];
    for (const name of ["one", "two", "viewer"]) {
      const user = await fixture.api.signUpEmail({ body: { name, email: name + "@example.test", password } });
      await db.prepare('UPDATE "user" SET "emailVerified"=1 WHERE id=?').bind(user.user.id).run();
      const response = await fixture.handler(new Request(FORECAST_ORIGIN + "/api/login/sign-in/email", {
        method: "POST", headers: { origin: FORECAST_ORIGIN, "content-type": "application/json" },
        body: JSON.stringify({ email: user.user.email, password }),
      }));
      assert.equal(response.status, 200);
      const cookie = response.headers.getSetCookie().map(value => value.split(";")[0]).join("; ");
      const session = await fixture.api.getSession({ headers: new Headers({ cookie }) });
      await db.prepare('UPDATE "user" SET "twoFactorEnabled"=1 WHERE id=?').bind(user.user.id).run();
      await db.prepare("INSERT INTO demandlab_session_mfa(session_id,user_id,verified_at) VALUES(?,?,?)")
        .bind(session!.session.id, user.user.id, Date.now()).run();
      people.push({ user: user.user.id, cookie, session: session!.session.id });
    }
    const company = await fixture.api.createOrganization({ body: { name: "Synthetic one", slug: "synthetic-one", userId: people[0].user } });
    const other = await fixture.api.createOrganization({ body: { name: "Synthetic two", slug: "synthetic-two", userId: people[0].user } });
    await fixture.api.addMember({ body: { organizationId: company.id, userId: people[1].user, role: "admin" } });
    await fixture.api.addMember({ body: { organizationId: company.id, userId: people[2].user, role: "viewer" } });
    const members: { id: string; user: string }[] = (await db.prepare('SELECT id,"userId" AS user FROM "member" WHERE "organizationId"=?').bind(company.id).all<{ id: string; user: string }>()).results;
    const call = async (operation: string, body: Record<string, unknown>) => (await (await caller.fetch("https://local.test/", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ operation, body }),
    })).json()) as { status: number; body: any };
    const adminBody = { company_id: company.id, cookie: people[0].cookie };
    const viewerBody = { company_id: company.id, cookie: people[2].cookie };
    const viewerIdentity=(await call('identity',viewerBody)).body;
    const staleRole=await call('work/authorize',{...viewerIdentity,role:'admin',required_scopes:['reports:read']});
    assert.equal(staleRole.body.allowed,true);assert.equal(staleRole.body.role,'viewer','Queued work uses the live role, not its saved role');
    assert.equal((await call("members/list", viewerBody)).status, 403);
    assert.equal((await call("keys/create", { ...viewerBody, kind: "company", name: "Invalid", scopes: ["reports:read"] })).status, 403);
    assert.equal((await call("keys/create", { ...viewerBody, kind: "personal", name: "Invalid", scopes: ["orders:write"] })).status, 400);
    const key = await call("keys/create", { ...adminBody, kind: "company", role: "planner", name: "Read orders", scopes: ["reports:read", "orders:write"] });
    assert.equal(key.status, 200);
    const keyPrincipal=(await call("identity", { key: key.body.key })).body;
    assert.equal(keyPrincipal.company_id, company.id);
    assert.equal((await call("work/authorize",keyPrincipal)).body.allowed,false); // Read/orders scopes cannot run forecasts.
    assert.equal((await call('work/authorize',{...keyPrincipal,required_scopes:['orders:write']})).body.allowed,true);
    assert.equal((await call('work/authorize',{...keyPrincipal,required_scopes:['orders:write','inputs:read']})).body.allowed,false);
    assert.equal((await call('work/authorize',{...keyPrincipal,required_scopes:[]})).body.allowed,false);
    assert.equal((await call('work/authorize',{...keyPrincipal,required_scopes:['invented:scope']})).body.allowed,false);
    assert.equal((await call("identity", { key: key.body.key, company_id: other.id })).status, 403);
    assert.equal((await call("members/list", { key: key.body.key })).status, 403);
    const listed = await call("keys/list", adminBody);
    assert.equal(listed.status, 200);
    assert.equal(listed.body.keys[0].key, undefined);
    const next = await call("keys/rotate", { ...adminBody, id: key.body.id });
    assert.equal(next.status, 200);
    assert.equal((await call("identity", { key: key.body.key })).status, 401);
    assert.equal((await call("identity", { key: next.body.key })).status, 200);
    assert.equal((await call("keys/manage", { ...adminBody, id: next.body.id, operation: "revoke" })).status, 200);
    assert.equal((await call("identity", { key: next.body.key })).status, 401);
    const runKey=await call('keys/create',{...adminBody,kind:'company',role:'planner',name:'Forecast automation',scopes:['forecasts:run']});
    const grant=(await call('identity',{key:runKey.body.key})).body;
    assert.equal((await call('work/authorize',grant)).body.allowed,true);
    await call('keys/manage',{...adminBody,id:runKey.body.id,operation:'revoke'});
    assert.equal((await call('work/authorize',grant)).body.allowed,false);
    const viewerMember = members.find(member => member.user === people[2].user)!;
    await call("identity", viewerBody); // record company use, without making it active
    assert.equal((await call("members/manage", { ...adminBody, id: viewerMember.id, operation: "suspend" })).status, 200);
    assert.equal((await call("identity", viewerBody)).status, 401);
    assert.equal((await db.prepare('SELECT count(*) AS n FROM "session" WHERE id=?').bind(people[0].session).first<{ n: number }>())!.n, 1);
    assert.equal((await call("members/invite", { ...adminBody, email: "outsider@example.test", role: "planner" })).status, 403);
    assert.equal((await call("schedules/authorize", { issuer: FORECAST_ORIGIN, company_id: other.id, subject: people[0].user })).body.allowed, true);
    assert.equal((await call("schedules/authorize", { issuer: FORECAST_ORIGIN, company_id: company.id, subject: "service:fake" })).body.allowed, false);
    // Real workerd Durable Object lock, not a test mutex. Simultaneous demotions
    // must leave one administrator; authorization is checked inside that lock.
    const demotions = await Promise.all(people.slice(0, 2).map(person => call("members/manage", {
      company_id: company.id, cookie: person.cookie, id: members.find(member => member.user === person.user)!.id,
      operation: "role", role: "viewer",
    })));
    assert.deepEqual(demotions.map(result => result.status).sort(), [200, 409]);
    assert.equal((await db.prepare('SELECT count(*) AS n FROM "member" WHERE "organizationId"=? AND role=?').bind(company.id, "admin").first<{ n: number }>())!.n, 1);
    assert.equal((await call("schedules/authorize", { issuer: FORECAST_ORIGIN, company_id: company.id,
      subject: people[demotions[0].status === 200 ? 0 : 1].user })).body.allowed, false);
    assert.equal((await call("not-an-operation", adminBody)).status, 404);
  } finally { await runtime.dispose(); }
});

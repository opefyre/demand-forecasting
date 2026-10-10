import test from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { Miniflare, convertV4MiniflareOptions } from "miniflare";
import { getMigrations } from "better-auth/db/migration";
import { createCloudflareIdentity, cloudflareConfiguration, D1_POLICY_SCHEMA,
  FORECAST_ORIGIN, FORECAST_OWNER, FORECAST_SENDER, FORECAST_GOOGLE_CLIENT } from "../src/cloudflare.js";
import { createAuthCore } from "../src/auth-core.js";
import { cloudflareMailer } from "../src/cloudflare-mail.js";
import { resolveD1Identity, PrivateIdentityError } from "../src/cloudflare-principal.js";
import { permissions } from "../src/policy.js";

test("Cloudflare identity uses native persistent D1, shared roles and closed registration", { timeout: 60000 }, async (t) => {
  const runtime = new Miniflare(convertV4MiniflareOptions({ modules: true,
    script: "export default { fetch() { return new Response(null, {status:404}); } };",
    compatibilityDate: "2026-10-09", d1Databases: ["IDENTITY_DB"], telemetry: { enabled: false } }));
  try {
    const db = await runtime.getD1Database("IDENTITY_DB");
    const env = { IDENTITY_DB: db, PRIVATE_ACCESS: "closed", BETTER_AUTH_SECRET: randomBytes(32).toString("hex") };
    let deliveries = 0;
    const identity = createCloudflareIdentity(env, async () => { deliveries++; });
    const migration = await getMigrations(identity.auth.options);
    assert.ok(migration.toBeCreated.some(table => table.table === "user"));
    await migration.runMigrations();
    await db.batch(D1_POLICY_SCHEMA.map(sql => db.prepare(sql)));
    const checked = await getMigrations(identity.auth.options);
    assert.equal(checked.toBeCreated.length, 0);
    assert.equal(checked.toBeAdded.length, 0);
    assert.equal(checked.schemaProblems.length, 0);
    const password = "Synthetic-test-" + randomBytes(20).toString("hex");
    await t.test("nobody, including the owner, can register through the closed auth policy", async () => {
      for (const email of [FORECAST_OWNER, "stranger@example.test"]) {
        await identity.auth.handler(new Request(FORECAST_ORIGIN + "/api/login/sign-up/email", {
          method: "POST", headers: { origin: FORECAST_ORIGIN, "content-type": "application/json" },
          body: JSON.stringify({ email, name: "Synthetic", password }),
        }));
      }
      assert.equal((await db.prepare('SELECT count(*) AS n FROM "user"').first<{ n: number }>())!.n, 0);
      assert.equal(deliveries, 0);
    });
    // Operator fixture is TEST ONLY; production has no bootstrap method/route.
    const fixture = createAuthCore(identity.config, db, {
      async invitationAllowed() { return true; },
      async recordMfa() {}, async clearMfa() {},
    }, async () => {});
    const user = await fixture.api.signUpEmail({ body: { name: "Synthetic owner", email: "owner@example.test", password } });
    await db.prepare('UPDATE "user" SET "emailVerified"=1 WHERE id=?').bind(user.user.id).run();
    const first = await fixture.api.createOrganization({ body: { name: "Company One", slug: "company-one", userId: user.user.id } });
    const second = await fixture.api.createOrganization({ body: { name: "Company Two", slug: "company-two", userId: user.user.id } });
    await t.test("real library organizations and sessions survive a new identity instance", async (sessions) => {
      const signIn = await identity.auth.handler(new Request(FORECAST_ORIGIN + "/api/login/sign-in/email", {
        method: "POST", headers: { origin: FORECAST_ORIGIN, "content-type": "application/json" },
        body: JSON.stringify({ email: user.user.email, password }),
      }));
      assert.equal(signIn.status, 200);
      const cookies = signIn.headers.getSetCookie();
      assert(cookies.some(cookie => /; Secure/i.test(cookie) && /; HttpOnly/i.test(cookie)));
      const cookie = cookies.map(value => value.split(";")[0]).join("; ");
      const restarted = createCloudflareIdentity(env, async () => { deliveries++; });
      const saved = await restarted.auth.api.getSession({ headers: new Headers({ cookie }) });
      assert.equal(saved?.user.id, user.user.id);
      const initial = await resolveD1Identity(restarted, db, { cookie, company_id: first.id });
      assert(initial.mfa_required);
      assert.equal(initial.company_id, first.id);
      const companies = await db.prepare('SELECT id FROM "organization" ORDER BY id').all<{ id: string }>();
      assert.deepEqual(new Set(companies.results.map((row: { id: string }) => row.id)), new Set([first.id, second.id]));
      await db.prepare("INSERT INTO demandlab_session_mfa(session_id,user_id,verified_at) VALUES(?,?,?)")
        .bind(saved!.session.id, user.user.id, Date.now()).run();
      await sessions.test("D1 roles, fresh MFA and company membership are enforced on every resolution", async () => {
        await db.prepare('UPDATE "user" SET "twoFactorEnabled"=1 WHERE id=?').bind(user.user.id).run();
        for (const role of ["admin", "planner", "approver", "viewer"] as const) {
          await db.prepare('UPDATE "member" SET role=? WHERE "organizationId"=? AND "userId"=?')
            .bind(role, first.id, user.user.id).run();
          const who = await resolveD1Identity(restarted, db, { cookie, company_id: first.id });
          assert.equal(who.role, role); assert.deepEqual(who.permissions, permissions[role]);
          assert.equal(who.mfa_required, false);
        }
        await assert.rejects(resolveD1Identity(restarted, db, { cookie, company_id: "not-a-member-company" }),
          error => error instanceof PrivateIdentityError && error.status === 403);
        await assert.rejects(resolveD1Identity(restarted, db, { cookie, company_id: "../other-company" }),
          error => error instanceof PrivateIdentityError && error.status === 400);
        await db.prepare("INSERT INTO demandlab_membership_status(company_id,user_id,suspended) VALUES(?,?,1)")
          .bind(first.id, user.user.id).run();
        await assert.rejects(resolveD1Identity(restarted, db, { cookie, company_id: first.id }),
          error => error instanceof PrivateIdentityError && error.status === 403);
        assert.equal((await resolveD1Identity(restarted, db, { cookie, company_id: second.id })).company_id, second.id);
        await db.prepare("DELETE FROM demandlab_membership_status WHERE company_id=? AND user_id=?")
          .bind(first.id, user.user.id).run();
        await db.prepare('UPDATE "member" SET role=? WHERE "organizationId"=? AND "userId"=?')
          .bind("admin", first.id, user.user.id).run();
        await db.prepare("UPDATE demandlab_session_mfa SET verified_at=? WHERE session_id=?")
          .bind(Date.now() - 3600001, saved!.session.id).run();
        assert((await resolveD1Identity(restarted, db, { cookie, company_id: first.id })).mfa_required);
        await db.prepare("UPDATE demandlab_session_mfa SET verified_at=? WHERE session_id=?")
          .bind(Date.now() + 3600000, saved!.session.id).run();
        assert((await resolveD1Identity(restarted, db, { cookie, company_id: first.id })).mfa_required);
      });
      await sessions.test("D1 hashed API keys stay company-bound, intersect live roles and honor revocation", async () => {
        const key = await fixture.api.createApiKey({ body: { configId: "company", name: "Synthetic read integration",
          userId: user.user.id, organizationId: first.id, permissions: { app: ["reports:read", "orders:write"] } } });
        await db.prepare("INSERT INTO demandlab_key_bindings(key_id,company_id,owner_id,service_role) VALUES(?,?,?,?)")
          .bind(key.id, first.id, user.user.id, "planner").run();
        const who = await resolveD1Identity(restarted, db, { key: key.key });
        assert.deepEqual(who.permissions, ["reports:read", "orders:write"]);
        await assert.rejects(resolveD1Identity(restarted, db, { key: key.key, company_id: second.id }),
          error => error instanceof PrivateIdentityError && error.status === 403);
        await db.prepare('UPDATE "member" SET role=? WHERE "organizationId"=? AND "userId"=?')
          .bind("viewer", first.id, user.user.id).run();
        assert.deepEqual((await resolveD1Identity(restarted, db, { key: key.key })).permissions, ["reports:read"]);
        await db.prepare("UPDATE demandlab_key_bindings SET revoked=1 WHERE key_id=?").bind(key.id).run();
        await assert.rejects(resolveD1Identity(restarted, db, { key: key.key }),
          error => error instanceof PrivateIdentityError && error.status === 401);
      });
      await restarted.auth.api.signOut({ headers: new Headers({ cookie }) });
      assert.equal(await restarted.auth.api.getSession({ headers: new Headers({ cookie }) }), null);
      assert.equal((await db.prepare("SELECT count(*) AS n FROM demandlab_session_mfa").first<{ n: number }>())!.n, 0);
    });
    await t.test("production configuration cannot be switched to open access", () => {
      for (const value of ["open", "owner", "", "true"])
        assert.throws(() => cloudflareConfiguration({ ...env, PRIVATE_ACCESS: value }));
      assert.throws(() => cloudflareConfiguration({ ...env, BETTER_AUTH_SECRET: "short" }));
      assert.throws(() => cloudflareConfiguration({ ...env, GOOGLE_CLIENT_ID: "other-client", GOOGLE_CLIENT_SECRET: "synthetic" }));
      assert.throws(() => cloudflareConfiguration({ ...env, GOOGLE_CLIENT_ID: FORECAST_GOOGLE_CLIENT }));
      assert.equal(cloudflareConfiguration({ ...env, GOOGLE_CLIENT_ID: FORECAST_GOOGLE_CLIENT,
        GOOGLE_CLIENT_SECRET: "synthetic" }).origin, FORECAST_ORIGIN);
    });
  } finally { await runtime.dispose(); }
});

test("maintained Resend SDK enforces owner-only mail, safe errors and repeat-safe request keys", async () => {
  const fetchBefore = globalThis.fetch, nodeEnvBefore = process.env.NODE_ENV;
  process.env.NODE_ENV = "production";
  const key = "re_" + randomBytes(24).toString("hex");
  const messages: { body: Record<string, any>; headers: Headers }[] = [];
  globalThis.fetch = async (url, options) => {
    assert.equal(String(url), "https://api.resend.com/emails");
    const headers = new Headers(options!.headers);
    assert.equal(headers.get("authorization"), "Bearer " + key);
    messages.push({ body: JSON.parse(String(options!.body)), headers });
    return Response.json({ id: "synthetic-message" });
  };
  try {
    const deliver = cloudflareMailer({ RESEND_API_KEY: key });
    for (const recipient of ["stranger@example.test", "opefyre@gmail.com,other@example.test", "OPEFYRE@gmail.com"])
      await assert.rejects(deliver(recipient, "Test", "Text"));
    await assert.rejects(deliver(FORECAST_OWNER, "Bad\nSubject", "Text"));
    assert.equal(messages.length, 0);
    await deliver(FORECAST_OWNER, "Setup test", "No private data");
    await deliver(FORECAST_OWNER, "Setup test", "No private data");
    assert.equal(messages.length, 2);
    assert.equal(messages[0].body.from, FORECAST_SENDER);
    assert.deepEqual(messages[0].body.to, [FORECAST_OWNER]);
    assert.equal(messages[0].headers.get("idempotency-key"), messages[1].headers.get("idempotency-key"));
    globalThis.fetch = async () => { throw new Error("Sensitive provider payload " + key); };
    await assert.rejects(deliver(FORECAST_OWNER, "Failure", "Text"), error =>
      error instanceof Error && error.message === "Forecast mail could not be sent" && !error.message.includes(key));
  } finally {
    globalThis.fetch = fetchBefore;
    if (nodeEnvBefore === undefined) delete process.env.NODE_ENV;
    else process.env.NODE_ENV = nodeEnvBefore;
  }
});

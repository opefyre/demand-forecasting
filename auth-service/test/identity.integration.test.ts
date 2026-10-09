import test from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { Pool } from "pg";
import { serve } from "@hono/node-server";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { base32 } from "@better-auth/utils/base32";
import { createIdentity } from "../src/auth.js";
import { createBridge } from "../src/bridge.js";
import { migrate } from "../src/migrate.js";

// Creates and removes ONE uniquely named test database. Never clears an existing
// application database. Opt-in connection needs permission to create databases.
test(
  "real PostgreSQL identity and access lifecycle",
  { skip: !process.env.DEMANDLAB_AUTH_TEST_POSTGRES },
  async (t) => {
    const database = `demandlab_auth_test_${randomBytes(8).toString("hex")}`;
    const admin = new Pool({
      connectionString: process.env.DEMANDLAB_AUTH_TEST_POSTGRES,
    });
    let fixture: ReturnType<typeof createIdentity> | undefined;
    let identity: ReturnType<typeof createIdentity> | undefined;
    const mail: { to: string; subject: string; text: string }[] = [];
    const deliver = async (to: string, subject: string, text: string) => {
      mail.push({ to, subject, text });
    };
    try {
      await admin.query(`CREATE DATABASE "${database}"`);
      const databaseURL = new URL(process.env.DEMANDLAB_AUTH_TEST_POSTGRES!);
      databaseURL.pathname = `/${database}`;
      const env = {
        DEMANDLAB_PUBLIC_ORIGIN: "http://127.0.0.1:8010",
        DEMANDLAB_AUTH_DEV_MAIL: "true",
        BETTER_AUTH_SECRET: randomBytes(32).toString("hex"),
        DEMANDLAB_AUTH_BRIDGE_SECRET: randomBytes(32).toString("hex"),
        DEMANDLAB_AUTH_DATABASE_URL: databaseURL.href,
      };
      fixture = createIdentity(env, true, deliver);
      await migrate(fixture);
      identity = createIdentity(env, false, deliver);
      const bridge = createBridge(identity);
      const password = `Test-password-${randomBytes(12).toString("hex")}`;
      const created = await fixture.auth.api.signUpEmail({
        body: {
          name: "Test administrator",
          email: "admin@example.test",
          password,
        },
      });
      // Fixtures only: actual bootstrap requires real email verification.
      await fixture.pool.query(
        'UPDATE "user" SET "emailVerified"=true WHERE id=$1',
        [created.user.id],
      );
      const company = await fixture.auth.api.createOrganization({
        body: {
          name: "Tehran test company",
          slug: "tehran-test",
          userId: created.user.id,
        },
      });
      const other = await fixture.auth.api.createOrganization({
        body: {
          name: "Other test company",
          slug: "other-test",
          userId: created.user.id,
        },
      });
      const jar = new Map<string, string>();
      let backupCodes: string[] = [];
      let ip = 1;
      async function http(
        path: string,
        body: Record<string, unknown>,
        cookieJar = jar,
      ) {
        const response = await bridge.request(
          `${env.DEMANDLAB_PUBLIC_ORIGIN}/api/login${path}`,
          {
            method: "POST",
            headers: {
              "content-type": "application/json",
              origin: env.DEMANDLAB_PUBLIC_ORIGIN,
              cookie: [...cookieJar].map(([k, v]) => `${k}=${v}`).join("; "),
              "x-forwarded-for": `192.0.2.${ip++}`,
            },
            body: JSON.stringify(body),
          },
        );
        for (const header of response.headers.getSetCookie()) {
          const [pair] = header.split(";");
          const at = pair.indexOf("=");
          if (/max-age=0/i.test(header)) cookieJar.delete(pair.slice(0, at));
          else cookieJar.set(pair.slice(0, at), pair.slice(at + 1));
        }
        const content = await response.text();
        return {
          status: response.status,
          body: content ? (JSON.parse(content) as any) : {},
        };
      }
      async function internal(
        path: string,
        values: Record<string, unknown> = {},
        cookieJar = jar,
        secret = env.DEMANDLAB_AUTH_BRIDGE_SECRET,
      ) {
        const response = await bridge.request(`/internal/${path}`, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "x-demandlab-bridge-key": secret,
          },
          body: JSON.stringify({
            cookie: [...cookieJar].map(([k, v]) => `${k}=${v}`).join("; "),
            company_id: company.id,
            ...values,
          }),
        });
        return {
          status: response.status,
          body: (await response.json()) as any,
        };
      }
      await t.test(
        "private bridge rejects missing and incorrect secret",
        async () => {
          assert.equal((await internal("identity", {}, jar, "")).status, 401);
          assert.equal(
            (
              await internal(
                "identity",
                {},
                jar,
                "x".repeat(env.DEMANDLAB_AUTH_BRIDGE_SECRET.length),
              )
            ).status,
            401,
          );
        },
      );
      await t.test(
        "signup is invitation-only and passwords are checked",
        async () => {
          // Better Auth deliberately gives a generic response to avoid exposing
          // which emails exist or are invited. Assert the actual database outcome.
          assert.equal(
            (
              await http("/sign-up/email", {
                name: "Stranger",
                email: "stranger@example.test",
                password,
              })
            ).status,
            200,
          );
          assert.equal(
            (
              await identity!.pool.query(
                'SELECT 1 FROM "user" WHERE email=$1',
                ["stranger@example.test"],
              )
            ).rowCount,
            0,
          );
          assert.equal(
            (
              await http("/sign-in/email", {
                email: created.user.email,
                password: "incorrect-password",
              })
            ).status,
            401,
          );
          assert.equal(
            (
              await http("/sign-in/email", {
                email: created.user.email,
                password,
              })
            ).status,
            200,
          );
        },
      );
      await t.test(
        "admin settings are blocked until this session passes two-factor",
        async () => {
          const current = await internal("identity");
          assert.equal(current.status, 200);
          assert.equal(current.body.mfa_required, true);
          assert.equal((await internal("members/list")).status, 403);
          const enabled = await http("/two-factor/enable", { password });
          assert.equal(enabled.status, 200);
          backupCodes = enabled.body.backupCodes;
          const secret = new TextDecoder().decode(
            base32.decode(
              new URL(enabled.body.totpURI).searchParams.get("secret")!,
            ),
          );
          const { code } = await identity!.auth.api.generateTOTP({
            body: { secret },
          });
          assert.equal(
            (await http("/two-factor/verify-totp", { code })).status,
            200,
          );
          assert.equal((await internal("identity")).body.mfa_required, false);
          assert.equal((await internal("members/list")).status, 200);
        },
      );
      await t.test(
        "public library routes cannot bypass access administration",
        async () => {
          assert.equal(
            (await http("/api-key/create", { name: "Bypass" })).status,
            403,
          );
          assert.equal(
            (
              await http("/organization/update", {
                organizationId: company.id,
                data: { name: "Bypass" },
              })
            ).status,
            403,
          );
          assert.equal(
            (
              await http("/organization/update-member-role", {
                organizationId: company.id,
                memberId: "missing",
                role: "viewer",
              })
            ).status,
            403,
          );
        },
      );
      const memberJar = new Map<string, string>();
      let planner: any, invitation: any, memberId: string;
      await t.test(
        "invite, verify email, accept and assign only the invited role",
        async () => {
          invitation = await internal("members/invite", {
            email: "planner@example.test",
            role: "planner",
          });
          assert.equal(invitation.status, 201);
          assert(
            mail.some(
              (item) =>
                item.subject.startsWith("Join") &&
                item.to === "planner@example.test",
            ),
          );
          const signup = await http(
            "/sign-up/email",
            { name: "Planner", email: "planner@example.test", password },
            memberJar,
          );
          assert.equal(signup.status, 200);
          planner = signup.body.user;
          const email = mail.findLast(
            (item) =>
              item.subject.startsWith("Verify") &&
              item.to === "planner@example.test",
          )!;
          const link = new URL(email.text);
          const verified = await bridge.request(link.href, {
            headers: { origin: env.DEMANDLAB_PUBLIC_ORIGIN },
            redirect: "manual",
          });
          assert([200, 302].includes(verified.status));
          assert.equal(
            (
              await http(
                "/sign-in/email",
                { email: planner.email, password },
                memberJar,
              )
            ).status,
            200,
          );
          assert.equal(
            (
              await http(
                "/organization/accept-invitation",
                { invitationId: invitation.body.id },
                memberJar,
              )
            ).status,
            200,
          );
          const current = await internal("identity", {}, memberJar);
          assert.equal(current.body.role, "planner");
          assert.equal(
            (await internal("members/list", {}, memberJar)).status,
            403,
          );
          memberId = (await internal("members/list")).body.members.find(
            (m: any) => m.user_id === planner.id,
          ).id;
          assert.equal(
            (await internal("identity", { company_id: other.id }, memberJar))
              .status,
            403,
          );
        },
      );
      let personal: any, service: any;
      await t.test(
        "personal keys are hashed, shown once and limited to current role",
        async () => {
          assert.equal(
            (
              await internal(
                "keys/create",
                {
                  kind: "personal",
                  name: "Forbidden",
                  scopes: ["members:manage"],
                },
                memberJar,
              )
            ).status,
            400,
          );
          personal = await internal(
            "keys/create",
            {
              kind: "personal",
              name: "ERP demand sync",
              scopes: ["orders:write", "reports:read"],
              days: 30,
            },
            memberJar,
          );
          assert.equal(personal.status, 201);
          assert(Math.abs(new Date(personal.body.expires_at).getTime() - Date.now() - 30 * 86400 * 1000) < 10000);
          const defaulted = await identity!.auth.api.createApiKey({body:{configId:"default",userId:created.user.id,name:"Default expiry fixture"}});
          assert(Math.abs(new Date(defaulted.expiresAt!).getTime() - Date.now() - 90 * 86400 * 1000) < 10000);
          const stored = (
            await identity!.pool.query('SELECT key FROM "apikey" WHERE id=$1', [
              personal.body.id,
            ])
          ).rows[0];
          assert.notEqual(stored.key, personal.body.key);
          const listed = await internal("keys/list", {}, memberJar);
          assert.equal(listed.status, 200);
          assert(!JSON.stringify(listed.body).includes(personal.body.key));
          const principal = await internal(
            "identity",
            { key: personal.body.key },
            new Map(),
          );
          assert.equal(principal.status, 200);
          assert(principal.body.permissions.includes("orders:write"));
          assert.equal(
            (
              await internal("identity", {
                key: personal.body.key,
                company_id: other.id,
              })
            ).status,
            403,
          );
          assert.equal(
            (
              await internal(
                "keys/create",
                {
                  key: personal.body.key,
                  kind: "personal",
                  name: "Nested",
                  scopes: ["reports:read"],
                },
                memberJar,
              )
            ).status,
            403,
          );
        },
      );
      await t.test(
        "company service keys require admin and cannot grant admin rights",
        async () => {
          assert.equal(
            (
              await internal(
                "keys/create",
                {
                  kind: "company",
                  name: "Denied",
                  role: "viewer",
                  scopes: ["reports:read"],
                },
                memberJar,
              )
            ).status,
            403,
          );
          assert.equal(
            (
              await internal("keys/create", {
                kind: "company",
                name: "Denied",
                role: "admin",
                scopes: ["reports:read"],
              })
            ).status,
            400,
          );
          service = await internal("keys/create", {
            kind: "company",
            name: "Reporting sync",
            role: "viewer",
            scopes: ["reports:read", "reports:export"],
          });
          assert.equal(service.status, 201);
          const principal = await internal("identity", {
            key: service.body.key,
          });
          assert.equal(principal.status, 200);
          assert.equal(principal.body.role, "viewer");
          assert(principal.body.subject.startsWith("service:"));
        },
      );
      await t.test(
        "role downgrade affects existing sessions and keys immediately",
        async () => {
          assert.equal(
            (
              await internal("members/manage", {
                id: memberId,
                operation: "role",
                role: "viewer",
              })
            ).status,
            200,
          );
          assert.equal(
            (await internal("identity", {}, memberJar)).body.role,
            "viewer",
          );
          const principal = await internal("identity", {
            key: personal.body.key,
          });
          assert.deepEqual(principal.body.permissions, ["reports:read"]);
        },
      );
      await t.test(
        "suspension and removal cannot expose another company's memberships",
        async () => {
          assert.equal(
            (
              await internal("members/manage", {
                id: memberId,
                operation: "suspend",
                company_id: other.id,
              })
            ).status,
            404,
          );
          assert.equal(
            (
              await internal("members/manage", {
                id: memberId,
                operation: "suspend",
              })
            ).status,
            200,
          );
          assert.equal(
            (await internal("identity", { key: personal.body.key })).status,
            403,
          );
          assert.equal((await internal("identity", {}, memberJar)).status, 401);
          assert.equal(
            (
              await internal("members/manage", {
                id: memberId,
                operation: "resume",
              })
            ).status,
            200,
          );
        },
      );
      await t.test(
        "last active administrator cannot be removed or demoted",
        async () => {
          const adminId = (await internal("members/list")).body.members.find(
            (m: any) => m.user_id === created.user.id,
          ).id;
          for (const operation of ["suspend", "remove", "role"])
            assert.equal(
              (
                await internal("members/manage", {
                  id: adminId,
                  operation,
                  role: "viewer",
                })
              ).status,
              409,
            );
        },
      );
      await t.test(
        "company sessions can be revoked without an upstream active-company field",
        async () => {
          assert.equal(
            (
              await http(
                "/sign-in/email",
                { email: planner.email, password },
                memberJar,
              )
            ).status,
            200,
          );
          const current = await internal("identity", {}, memberJar);
          assert.equal(current.status, 200);
          await identity!.pool.query(
            'UPDATE "session" SET "activeOrganizationId"=NULL WHERE id=$1',
            [current.body.session_id],
          );
          assert.equal(
            (
              await internal("members/manage", {
                id: memberId,
                operation: "revoke_sessions",
              })
            ).status,
            200,
          );
          assert.equal((await internal("identity", {}, memberJar)).status, 401);
        },
      );
      await t.test(
        "real Python application bridge accepts cookies and scoped keys",
        async () => {
          const server = serve({
            fetch: bridge.fetch,
            hostname: "127.0.0.1",
            port: 0,
          });
          try {
            if (!server.listening)
              await new Promise<void>((resolve) =>
                server.once("listening", resolve),
              );
            const address = server.address();
            if (!address || typeof address === "string")
              throw new Error("Test server address missing");
            const root = fileURLToPath(new URL("../../", import.meta.url));
            await promisify(execFile)(
              `${root}/.venv/bin/python`,
              ["-m", "unittest", "tests.test_platform_roundtrip"],
              {
                cwd: root,
                timeout: 30000,
                env: {
                  ...process.env,
                  ...env,
                  DEMANDLAB_PLATFORM_ROUNDTRIP: "true",
                  DEMANDLAB_AUTH_SERVICE_URL: `http://127.0.0.1:${address.port}`,
                  DEMANDLAB_PLATFORM_TEST_COOKIE: JSON.stringify(
                    Object.fromEntries(jar),
                  ),
                  DEMANDLAB_PLATFORM_TEST_COMPANY: company.id,
                  DEMANDLAB_PLATFORM_TEST_OTHER: other.id,
                },
              },
            );
          } finally {
            await new Promise<void>((resolve, reject) =>
              server.close((error) => (error ? reject(error) : resolve())),
            );
          }
        },
      );
      await t.test(
        "a fresh administrator login requires its own factor and recovery codes are single-use",
        async () => {
          const freshJar = new Map<string, string>();
          const login = await http(
            "/sign-in/email",
            { email: created.user.email, password },
            freshJar,
          );
          assert.equal(login.body.twoFactorRedirect, true);
          assert.equal((await internal("identity", {}, freshJar)).status, 401);
          assert.equal(
            (
              await http(
                "/two-factor/verify-backup-code",
                { code: backupCodes[0] },
                freshJar,
              )
            ).status,
            200,
          );
          assert.equal(
            (await internal("identity", {}, freshJar)).body.mfa_required,
            false,
          );
          assert.equal(
            (await internal("members/list", {}, freshJar)).status,
            200,
          );
          assert(
            (
              await http(
                "/two-factor/verify-backup-code",
                { code: backupCodes[0] },
                freshJar,
              )
            ).status >= 400,
          );
        },
      );
      await t.test(
        "rotation returns a replacement once and revokes the old key",
        async () => {
          const previous = service.body.key;
          const next = await internal("keys/rotate", { id: service.body.id });
          assert.equal(next.status, 201);
          assert.notEqual(next.body.key, previous);
          assert.equal(
            (await internal("identity", { key: previous })).status,
            401,
          );
          assert.equal(
            (await internal("identity", { key: next.body.key })).status,
            200,
          );
          assert.equal(
            (await internal("keys/rotate", { id: service.body.id })).status,
            404,
          );
          service = next;
        },
      );
      await t.test(
        "revocation, expiration and rate limits are enforced",
        async () => {
          await identity!.pool.query(
            'UPDATE "apikey" SET "rateLimitMax"=1 WHERE id=$1',
            [service.body.id],
          );
          assert.equal(
            (await internal("identity", { key: service.body.key })).status,
            429,
          );
          assert.equal(
            (
              await internal("keys/manage", {
                id: service.body.id,
                operation: "revoke",
              })
            ).status,
            200,
          );
          assert.equal(
            (await internal("identity", { key: service.body.key })).status,
            401,
          );
          await identity!.pool.query(
            'UPDATE "apikey" SET "expiresAt"=now()-interval \'1 day\' WHERE id=$1',
            [personal.body.id],
          );
          assert.equal(
            (await internal("identity", { key: personal.body.key })).status,
            401,
          );
        },
      );
      await t.test(
        "invitation cancellation and audit remain company-scoped",
        async () => {
          const pending = await internal("members/invite", {
            email: "cancel@example.test",
            role: "viewer",
          });
          assert.equal(pending.status, 201);
          assert.equal(
            (
              await internal("members/cancel-invitation", {
                id: pending.body.id,
                company_id: other.id,
              })
            ).status,
            404,
          );
          assert.equal(
            (
              await internal("members/cancel-invitation", {
                id: pending.body.id,
              })
            ).status,
            200,
          );
          assert.equal(
            (
              await http(
                "/sign-up/email",
                { name: "Cancelled", email: "cancel@example.test", password },
                new Map(),
              )
            ).status,
            200,
          );
          assert.equal(
            (
              await identity!.pool.query(
                'SELECT 1 FROM "user" WHERE email=$1',
                ["cancel@example.test"],
              )
            ).rowCount,
            0,
          );
          const audit = await internal("audit");
          assert.equal(audit.status, 200);
          assert(audit.body.events.length > 5);
          assert(!JSON.stringify(audit.body).includes(personal.body.key));
          assert.equal(
            (await internal("audit", { company_id: other.id })).body.events
              .length,
            0,
          );
        },
      );
      await t.test(
        "enrolled account alone is not proof for a new Google-like session",
        async () => {
          const raw = await (
            await identity!.auth.$context
          ).internalAdapter.createSession(created.user.id);
          const proof = (
            await identity!.pool.query(
              "SELECT 1 FROM demandlab_session_mfa WHERE session_id=$1",
              [raw!.id],
            )
          ).rowCount;
          assert.equal(proof, 0);
          // No proof can be minted through the bridge by specifying a session ID.
          const missing = await internal(
            "identity",
            { session_id: raw!.id },
            new Map(),
          );
          assert.equal(missing.status, 401);
          const current = (await internal("identity")).body;
          await identity!.pool.query(
            "DELETE FROM demandlab_session_mfa WHERE session_id=$1",
            [current.session_id],
          );
          assert.equal((await internal("identity")).body.mfa_enabled, true);
          assert.equal((await internal("identity")).body.mfa_required, true);
          assert.equal((await internal("members/list")).status, 403);
        },
      );
    } finally {
      await identity?.pool.end();
      await fixture?.pool.end();
      await admin.query(`DROP DATABASE IF EXISTS "${database}" WITH (FORCE)`);
      await admin.end();
    }
  },
);

import { timingSafeEqual } from "node:crypto";
import { Hono } from "hono";
import { bodyLimit } from "hono/body-limit";
import { APIError } from "better-auth/api";
import { createIdentity } from "./auth.js";
import {
  asRole,
  effectiveScopes,
  keyScopes,
  permissions,
  scopeLabels,
  roles,
  Role,
} from "./policy.js";

export function createBridge(identity: ReturnType<typeof createIdentity>) {
  const { auth, pool, config } = identity;
  const app = new Hono();
  app.use("*", bodyLimit({ maxSize: 65536 }));
  app.use("/internal/*", async (c, next) => {
    const value = c.req.header("x-demandlab-bridge-key") || "";
    if (
      Buffer.byteLength(value) !== Buffer.byteLength(config.bridgeSecret) ||
      !timingSafeEqual(Buffer.from(value), Buffer.from(config.bridgeSecret))
    )
      return c.json({ detail: "Unauthorized" }, 401);
    c.header("Cache-Control", "no-store");
    await next();
  });
  app.onError((error, c) => {
    // Provider/database exceptions can contain credentials; never forward them.
    if (error instanceof BridgeError)
      return c.json({ detail: error.message }, error.status);
    // Never return upstream messages: they may include a provider or connection URL.
    if (error instanceof APIError) {
      const status = error.statusCode;
      if ([400, 401, 403, 404, 409, 429].includes(status))
        return c.json(
          {
            detail:
              status === 429
                ? "Too many requests. Try again shortly."
                : "Authentication request could not be completed",
          },
          status as 400,
        );
    }
    return c.json({ detail: "Authentication operation unavailable" }, 503);
  });
  function headers(body: Record<string, any>) {
    const result = new Headers({ origin: config.origin });
    if (typeof body.cookie === "string") result.set("cookie", body.cookie);
    return result;
  }
  async function member(company: string, user: string) {
    const result = await pool.query(
      `SELECT m.*, coalesce(s.suspended,false) AS suspended,
      u.name, u.email, u."emailVerified", u."twoFactorEnabled",
      EXISTS(SELECT 1 FROM "account" a WHERE a."userId"=u.id AND a."providerId"='credential') AS has_password
      FROM "member" m JOIN "user" u ON u.id=m."userId"
      LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
      WHERE m."organizationId"=$1 AND m."userId"=$2`,
      [company, user],
    );
    const row = result.rows[0];
    if (!row || row.suspended || !row.emailVerified)
      throw new BridgeError(403, "Company access is unavailable");
    row.role = asRole(row.role);
    return row;
  }
  async function session(body: Record<string, any>) {
    const saved = await auth.api.getSession({
      headers: headers(body),
      query: { disableCookieCache: true },
    });
    if (!saved) throw new BridgeError(401, "Sign in to continue");
    const memberships = await pool.query(
      `SELECT m."organizationId" AS id,o.name,m.role,coalesce(s.suspended,false) AS suspended
      FROM "member" m JOIN "organization" o ON o.id=m."organizationId"
      LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
      WHERE m."userId"=$1 ORDER BY o.name`,
      [saved.user.id],
    );
    const active = memberships.rows.find(
      (r) => r.id === saved.session.activeOrganizationId && !r.suspended,
    );
    const company =
      body.company_id ||
      active?.id ||
      memberships.rows.find((r) => !r.suspended)?.id;
    if (!company)
      throw new BridgeError(403, "Accept a company invitation first");
    const current = await member(company, saved.user.id);
    await pool.query(
      "INSERT INTO demandlab_session_company(session_id,company_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
      [saved.session.id, company],
    );
    const proof = await pool.query(
      "SELECT 1 FROM demandlab_session_mfa WHERE session_id=$1 AND verified_at>now()-interval '1 hour'",
      [saved.session.id],
    );
    return {
      issuer: config.origin,
      subject: saved.user.id,
      name: saved.user.name,
      email: saved.user.email,
      company_id: company,
      role: current.role as Role,
      permissions: permissions[current.role as Role],
      mfa_required:
        current.role === "admin" &&
        (!current.twoFactorEnabled || !proof.rowCount),
      mfa_enabled: !!current.twoFactorEnabled,
      has_password: !!current.has_password,
      auth_kind: "session",
      session_id: saved.session.id,
      companies: memberships.rows
        .filter((r) => !r.suspended)
        .map(({ suspended, ...row }) => row),
    };
  }
  async function requireSession(body: Record<string, any>, admin = false) {
    if (body.key)
      throw new BridgeError(403, "Use an interactive sign-in to manage access");
    const principal = await session(body);
    if (principal.mfa_required)
      throw new BridgeError(403, "Enable two-factor authentication first");
    if (admin && principal.role !== "admin")
      throw new BridgeError(403, "Administrator access required");
    return principal;
  }
  function role(value: unknown) {
    try {
      return asRole(value);
    } catch {
      throw new BridgeError(400, "Choose Admin, Planner, Approver or Viewer");
    }
  }
  async function audit(
    company: string,
    actor: string,
    event: string,
    resource: string,
  ) {
    await pool.query(
      "INSERT INTO demandlab_audit(company_id,actor_id,event,resource_id) VALUES($1,$2,$3,$4)",
      [company, actor, event, resource],
    );
  }
  async function locked(company: string, work: () => Promise<unknown>) {
    const client = await pool.connect();
    try {
      await client.query("SELECT pg_advisory_lock(hashtext($1))", [company]);
      return await work();
    } finally {
      await client.query("SELECT pg_advisory_unlock(hashtext($1))", [company]);
      client.release();
    }
  }
  async function lastAdmin(company: string, target: string) {
    const result = await pool.query(
      `SELECT m.id FROM "member" m
      LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
      WHERE m."organizationId"=$1 AND m.role='admin' AND coalesce(s.suspended,false)=false`,
      [company],
    );
    if (result.rows.length === 1 && result.rows[0].id === target)
      throw new BridgeError(409, "Keep at least one active administrator");
  }
  app.get("/health", (c) => c.json({ status: "ok" }));
  app.post("/internal/config", (c) =>
    c.json({ password: true, google: !!auth.options.socialProviders?.google }),
  );
  app.post("/internal/policy", async (c) => {
    const who = await requireSession(await c.req.json());
    return c.json({
      roles,
      personal: permissions[who.role]
        .filter((scope) => scope !== "members:manage")
        .map((scope) => ({ scope, label: scopeLabels[scope] })),
      company:
        who.role === "admin"
          ? Object.fromEntries(
              ["planner", "viewer"].map((role) => [
                role,
                permissions[role as Role]
                  .filter(
                    (scope) => !["chats:own", "views:own"].includes(scope),
                  )
                  .map((scope) => ({ scope, label: scopeLabels[scope] })),
              ]),
            )
          : {},
    });
  });
  app.post("/internal/identity", async (c) => {
    const body = await c.req.json();
    if (!body.key) return c.json(await session(body));
    const result = await auth.api.verifyApiKey({ body: { key: body.key } });
    if (!result.valid || !result.key) {
      if (result.error?.code === "RATE_LIMITED")
        throw new BridgeError(429, "Too many requests. Try again shortly.");
      throw new BridgeError(401, "API key is invalid, expired or revoked");
    }
    const key = result.key;
    const binding = (
      await pool.query(
        "SELECT * FROM demandlab_key_bindings WHERE key_id=$1 AND NOT revoked",
        [key.id],
      )
    ).rows[0];
    if (!binding)
      throw new BridgeError(401, "API key is not bound to an active company");
    if (body.company_id && body.company_id !== binding.company_id)
      throw new BridgeError(403, "API key belongs to a different company");
    const current = await member(binding.company_id, binding.owner_id);
    if (current.role === "admin" && !current.twoFactorEnabled)
      throw new BridgeError(
        403,
        "Key owner must enable two-factor authentication",
      );
    const role = binding.service_role
      ? asRole(binding.service_role)
      : (current.role as Role);
    const available = effectiveScopes(
      current.role,
      effectiveScopes(role, key.permissions?.app || []),
    );
    return c.json({
      issuer: config.origin,
      subject: binding.service_role ? `service:${key.id}` : binding.owner_id,
      name: binding.service_role ? key.name : current.name,
      role,
      company_id: binding.company_id,
      permissions: available,
      key_id: key.id,
      auth_kind: "api_key",
      mfa_required: false,
    });
  });
  app.post("/internal/keys/list", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body);
    const result = await pool.query(
      `SELECT a.id,a.name,a.start,a.enabled,a."expiresAt",a."createdAt",a."lastRequest",a.permissions,
      b.service_role AS role,b.owner_id,b.revoked FROM "apikey" a JOIN demandlab_key_bindings b ON b.key_id=a.id
      WHERE b.company_id=$1 AND ($2::boolean OR b.owner_id=$3) ORDER BY a."createdAt" DESC`,
      [who.company_id, who.role === "admin", who.subject],
    );
    return c.json({ keys: result.rows });
  });
  async function createKey(
    body: Record<string, any>,
    who: Awaited<ReturnType<typeof session>>,
  ) {
    if (!["personal", "company"].includes(body.kind))
      throw new BridgeError(400, "Choose personal or company key");
    const keyRole =
      body.kind === "company" ? role(body.role || "viewer") : who.role;
    if (body.kind === "company" && !["planner", "viewer"].includes(keyRole))
      throw new BridgeError(
        400,
        "Company keys must use Viewer or Planner access",
      );
    let scopes: string[];
    try {
      scopes = keyScopes(keyRole, body.scopes, body.kind === "company");
    } catch {
      throw new BridgeError(
        400,
        "Choose API permissions within the allowed role",
      );
    }
    const name = typeof body.name === "string" ? body.name.trim() : "";
    if (!name || name.length > 80)
      throw new BridgeError(400, "Enter a key name of 1–80 characters");
    const days = body.days ?? 90;
    if (!Number.isInteger(days) || days < 1 || days > 365)
      throw new BridgeError(400, "Choose an expiry of 1–365 days");
    const key = await auth.api.createApiKey({
      body: {
        configId: body.kind === "company" ? "company" : "default",
        name,
        expiresIn: days * 86400,
        userId: who.subject,
        ...(body.kind === "company" ? { organizationId: who.company_id } : {}),
        permissions: { app: scopes },
        metadata: { company_id: who.company_id },
      },
    });
    try {
      await pool.query(
        "INSERT INTO demandlab_key_bindings(key_id,company_id,owner_id,service_role) VALUES($1,$2,$3,$4)",
        [
          key.id,
          who.company_id,
          who.subject,
          body.kind === "company" ? keyRole : null,
        ],
      );
      await audit(who.company_id, who.subject, "key.created", key.id);
    } catch (error) {
      await pool.query('UPDATE "apikey" SET enabled=false WHERE id=$1', [
        key.id,
      ]);
      throw error;
    }
    return {
      id: key.id,
      name: key.name,
      key: key.key,
      expires_at: key.expiresAt,
      scopes,
    };
  }
  app.post("/internal/keys/create", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body, body.kind === "company");
    return c.json(await createKey(body, who), 201);
  });
  app.post("/internal/keys/rotate", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body);
    return c.json(
      (await locked(who.company_id, async () => {
        const old = (
          await pool.query(
            `SELECT b.*,a.name,a.permissions FROM demandlab_key_bindings b
        JOIN "apikey" a ON a.id=b.key_id WHERE b.key_id=$1 AND b.company_id=$2 AND NOT b.revoked`,
            [body.id, who.company_id],
          )
        ).rows[0];
        if (
          !old ||
          (old.owner_id !== who.subject &&
            !(old.service_role && who.role === "admin"))
        )
          throw new BridgeError(404, "API key not found");
        if (old.service_role && who.role !== "admin")
          throw new BridgeError(403, "Administrator access required");
        const savedPermissions =
          typeof old.permissions === "string"
            ? JSON.parse(old.permissions)
            : old.permissions;
        const scopes = effectiveScopes(
          who.role,
          effectiveScopes(
            old.service_role || who.role,
            savedPermissions?.app || [],
          ),
        );
        const next = await createKey(
          {
            kind: old.service_role ? "company" : "personal",
            role: old.service_role,
            name: body.name || old.name,
            days: body.days ?? 90,
            scopes,
          },
          who,
        );
        const client = await pool.connect();
        try {
          await client.query("BEGIN");
          await client.query(
            "UPDATE demandlab_key_bindings SET revoked=true WHERE key_id=$1",
            [old.key_id],
          );
          await client.query('UPDATE "apikey" SET enabled=false WHERE id=$1', [
            old.key_id,
          ]);
          await client.query(
            "INSERT INTO demandlab_audit(company_id,actor_id,event,resource_id) VALUES($1,$2,'key.rotated',$3)",
            [who.company_id, who.subject, old.key_id],
          );
          await client.query("COMMIT");
        } catch (error) {
          await client.query("ROLLBACK");
          // A failed rotation never leaves an undisclosed usable replacement.
          await pool.query('UPDATE "apikey" SET enabled=false WHERE id=$1', [
            next.id,
          ]);
          await pool.query(
            "UPDATE demandlab_key_bindings SET revoked=true WHERE key_id=$1",
            [next.id],
          );
          throw error;
        } finally {
          client.release();
        }
        return next;
      })) as object,
      201,
    );
  });
  app.post("/internal/keys/manage", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body);
    const binding = (
      await pool.query(
        "SELECT * FROM demandlab_key_bindings WHERE key_id=$1 AND company_id=$2",
        [body.id, who.company_id],
      )
    ).rows[0];
    if (!binding || (who.role !== "admin" && binding.owner_id !== who.subject))
      throw new BridgeError(404, "API key not found");
    if (body.operation === "revoke") {
      await pool.query(
        "UPDATE demandlab_key_bindings SET revoked=true WHERE key_id=$1",
        [body.id],
      );
      await pool.query('UPDATE "apikey" SET enabled=false WHERE id=$1', [
        body.id,
      ]);
    } else if (
      body.operation === "rename" &&
      typeof body.name === "string" &&
      body.name.trim().length &&
      body.name.length <= 80
    ) {
      await pool.query('UPDATE "apikey" SET name=$1 WHERE id=$2', [
        body.name.trim(),
        body.id,
      ]);
    } else throw new BridgeError(400, "Choose rename or revoke");
    await audit(who.company_id, who.subject, `key.${body.operation}`, body.id);
    return c.json({ updated: true });
  });
  app.post("/internal/members/list", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body, true);
    const rows = await pool.query(
      `SELECT m.id,m."userId" AS user_id,m.role,u.name,u.email,coalesce(s.suspended,false) AS suspended
      FROM "member" m JOIN "user" u ON u.id=m."userId"
      LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
      WHERE m."organizationId"=$1 ORDER BY u.name`,
      [who.company_id],
    );
    const invitations = await pool.query(
      'SELECT id,email,role,status,"expiresAt" FROM "invitation" WHERE "organizationId"=$1 ORDER BY "expiresAt" DESC',
      [who.company_id],
    );
    return c.json({ members: rows.rows, invitations: invitations.rows });
  });
  app.post("/internal/members/invite", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body, true);
    const nextRole = role(body.role),
      email = String(body.email || "").trim();
    const invitation = await auth.api.createInvitation({
      headers: headers(body),
      body: { email, role: nextRole, organizationId: who.company_id },
    });
    await audit(who.company_id, who.subject, "member.invited", invitation.id);
    return c.json({ id: invitation.id, email, role: nextRole }, 201);
  });
  app.post("/internal/members/cancel-invitation", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body, true);
    const exists = await pool.query(
      'SELECT 1 FROM "invitation" WHERE id=$1 AND "organizationId"=$2',
      [body.id, who.company_id],
    );
    if (!exists.rowCount) throw new BridgeError(404, "Invitation not found");
    await auth.api.cancelInvitation({
      headers: headers(body),
      body: { invitationId: body.id },
    });
    await audit(who.company_id, who.subject, "invitation.cancelled", body.id);
    return c.json({ updated: true });
  });
  app.post("/internal/members/manage", async (c) => {
    const body = await c.req.json(),
      who = await requireSession(body, true);
    return c.json(
      await locked(who.company_id, async () => {
        const target = (
          await pool.query(
            'SELECT * FROM "member" WHERE id=$1 AND "organizationId"=$2',
            [body.id, who.company_id],
          )
        ).rows[0];
        if (!target) throw new BridgeError(404, "Member not found");
        const nextRole =
          body.operation === "role" ? role(body.role) : target.role;
        if (
          target.role === "admin" &&
          (nextRole !== "admin" ||
            ["suspend", "remove"].includes(body.operation))
        )
          await lastAdmin(who.company_id, target.id);
        if (body.operation === "role")
          await auth.api.updateMemberRole({
            headers: headers(body),
            body: {
              memberId: target.id,
              role: nextRole,
              organizationId: who.company_id,
            },
          });
        else if (body.operation === "remove")
          await auth.api.removeMember({
            headers: headers(body),
            body: {
              memberIdOrEmail: target.id,
              organizationId: who.company_id,
            },
          });
        else if (["suspend", "resume"].includes(body.operation))
          await pool.query(
            `INSERT INTO demandlab_membership_status(company_id,user_id,suspended)
        VALUES($1,$2,$3) ON CONFLICT(company_id,user_id) DO UPDATE SET suspended=excluded.suspended`,
            [who.company_id, target.userId, body.operation === "suspend"],
          );
        else if (body.operation !== "revoke_sessions")
          throw new BridgeError(400, "Unknown member action");
        if (["suspend", "remove", "revoke_sessions"].includes(body.operation))
          await pool.query(
            `DELETE FROM "session" WHERE "userId"=$1 AND
        ("activeOrganizationId"=$2 OR id IN (SELECT session_id FROM demandlab_session_company WHERE company_id=$2))`,
            [target.userId, who.company_id],
          );
        await audit(
          who.company_id,
          who.subject,
          `member.${body.operation}`,
          target.id,
        );
        return { updated: true };
      }),
    );
  });
  app.post("/internal/audit", async (c) => {
    const who = await requireSession(await c.req.json(), true);
    return c.json({
      events: (
        await pool.query(
          "SELECT id,actor_id,event,resource_id,created_at FROM demandlab_audit WHERE company_id=$1 ORDER BY id DESC LIMIT 100",
          [who.company_id],
        )
      ).rows,
    });
  });
  app.all("/api/login/*", (c) => auth.handler(c.req.raw));
  return app;
}

class BridgeError extends Error {
  constructor(
    public status: 400 | 401 | 403 | 404 | 409 | 429,
    message: string,
  ) {
    super(message);
  }
}

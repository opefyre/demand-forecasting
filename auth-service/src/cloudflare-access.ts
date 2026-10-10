import { APIError } from "better-auth/api";
import { createCloudflareIdentity, FORECAST_OWNER, type D1Binding } from "./cloudflare.js";
import { d1Membership, PrivateIdentityError as AccessError, resolveD1Identity } from "./cloudflare-principal.js";
import { asRole, effectiveScopes, keyScopes, permissions, roles, scopeLabels, type Role } from "./policy.js";

type Identity = ReturnType<typeof createCloudflareIdentity>;
type Body = Record<string, any>;
export const CLOUD_ACCESS_OPERATIONS = new Set([
  "config", "identity", "policy", "keys/list", "keys/create", "keys/rotate", "keys/manage",
  "members/list", "members/invite", "members/cancel-invitation", "members/manage", "audit", "schedules/authorize", "work/authorize",
]);

// Invoke ONLY within the private Access Durable Object's serialized operation.
// Authorization is deliberately inside the lock: an earlier request can revoke
// this actor while a later request waits. No cookies/keys are saved by the lock.
export async function cloudAccessOperation(identity: Identity, db: D1Binding, operation: string, body: Body) {
  if (!CLOUD_ACCESS_OPERATIONS.has(operation)) throw new AccessError(404, "Operation not found");
  if (!body || typeof body !== "object" || Array.isArray(body) || JSON.stringify(body).length > 65536)
    throw new AccessError(400, "Invalid request");
  const headers = new Headers({ origin: identity.config.origin, cookie: body.cookie || "" });
  const statement = (sql: string, ...values: (string | number | null)[]) => db.prepare(sql).bind(...values);
  const audit = (company: string, actor: string, event: string, resource: string) =>
    statement("INSERT INTO demandlab_audit(company_id,actor_id,event,resource_id,created_at) VALUES(?,?,?,?,?)",
      company, actor, event, resource, Date.now());
  const role = (value: unknown) => {
    try { return asRole(value); } catch { throw new AccessError(400, "Choose Admin, Planner, Approver or Viewer"); }
  };
  if (operation === "config") return { password: true, google: !!identity.auth.options.socialProviders?.google };
  if (operation === "identity") return resolveD1Identity(identity, db, body);
  if (operation === "work/authorize") {
    // Saved grants contain IDs only, never a cookie or raw API key. Recheck live
    // ownership, expiry, suspension, role and revocation before a queued job starts.
    if (body.issuer !== identity.config.origin || typeof body.company_id !== "string" ||
        !/^[A-Za-z0-9_-]{1,128}$/.test(body.company_id) || typeof body.subject !== "string" ||
        !Array.isArray(body.permissions)) return { allowed: false };
    try {
      let user = body.subject, available: string[], currentRole: Role;
      if (body.auth_kind === "api_key") {
        const key = await statement(`SELECT b.owner_id,b.service_role,a.permissions,a.enabled,a."expiresAt"
          FROM demandlab_key_bindings b JOIN "apikey" a ON a.id=b.key_id
          WHERE b.key_id=? AND b.company_id=? AND b.revoked=0`, body.key_id, body.company_id).first<Body>();
        if (!key || key.enabled !== 1 || (key.expiresAt !== null && key.expiresAt <= Date.now()) ||
            body.subject !== (key.service_role ? 'service:' + body.key_id : key.owner_id)) return { allowed: false };
        user = key.owner_id;
        const current = await d1Membership(db, body.company_id, user);
        currentRole = asRole(key.service_role || current.role);
        if (current.role === 'admin' && current.two_factor_enabled !== 1) return { allowed: false };
        const saved = typeof key.permissions === 'string' ? JSON.parse(key.permissions) : key.permissions;
        available = effectiveScopes(current.role, effectiveScopes(key.service_role || current.role, saved?.app || []));
      } else if (body.auth_kind === "session") {
        const session = await statement('SELECT 1 FROM "session" WHERE id=? AND "userId"=? AND "expiresAt">?',
          body.session_id, user, Date.now()).first();
        if (!session) return { allowed: false };
        const current = await d1Membership(db, body.company_id, user);
        currentRole = asRole(current.role);
        if (current.role === 'admin' && current.two_factor_enabled !== 1) return { allowed: false };
        available = permissions[current.role];
      } else return { allowed: false };
      const required = body.required_scopes ?? ['forecasts:run'];
      if (!Array.isArray(required) || !required.length || required.length > 40 ||
          required.some(scope => typeof scope !== 'string' || !(scope in scopeLabels))) return { allowed: false };
      return { allowed: required.every(scope => body.permissions.includes(scope) && available.includes(scope)),
        permissions: body.permissions.filter(scope => available.includes(scope)), role:currentRole };
    } catch (error) {
      if (error instanceof AccessError && error.status === 403) return { allowed: false };
      throw error;
    }
  }
  if (operation === "schedules/authorize") {
    if (body.issuer !== identity.config.origin || typeof body.company_id !== "string" ||
        !/^[A-Za-z0-9_-]{1,128}$/.test(body.company_id) || typeof body.subject !== "string" ||
        !body.subject || body.subject.startsWith("service:")) return { allowed: false };
    try {
      const current = await d1Membership(db, body.company_id, body.subject);
      return { allowed: current.role === "admin" && current.two_factor_enabled === 1,
        role:current.role, permissions:permissions[current.role] };
    } catch (error) {
      if (error instanceof AccessError && error.status === 403) return { allowed: false };
      throw error;
    }
  }
  if (body.key) throw new AccessError(403, "Use an interactive sign-in to manage access");
  const who = await resolveD1Identity(identity, db, body);
  if (who.auth_kind !== "session" || who.mfa_required)
    throw new AccessError(403, "Verify two-factor authentication first");
  const company = who.company_id, actor = who.subject;
  const admin = () => { if (who.role !== "admin") throw new AccessError(403, "Administrator access required"); };
  if (operation === "policy") return { roles,
    personal: permissions[who.role].filter(scope => scope !== "members:manage").map(scope => ({ scope, label: scopeLabels[scope] })),
    company: who.role === "admin" ? Object.fromEntries((["planner", "viewer"] as const).map(r => [r,
      permissions[r].filter(scope => !["chats:own", "views:own"].includes(scope)).map(scope => ({ scope, label: scopeLabels[scope] }))])) : {} };
  if (operation === "keys/list") return { keys: (await statement(`SELECT a.id,a.name,a.start,a.enabled,a."expiresAt",
      a."createdAt",a."lastRequest",a.permissions,b.service_role AS role,b.owner_id,b.revoked
      FROM "apikey" a JOIN demandlab_key_bindings b ON b.key_id=a.id
      WHERE b.company_id=? AND (?=1 OR b.owner_id=?) ORDER BY a."createdAt" DESC`, company, who.role === "admin" ? 1 : 0, actor).all()).results };
  async function createKey(input: Body) {
    if (!["personal", "company"].includes(input.kind)) throw new AccessError(400, "Choose personal or company key");
    const service = input.kind === "company";
    if (service) admin();
    const keyRole = service ? role(input.role || "viewer") : who.role;
    if (service && !["planner", "viewer"].includes(keyRole)) throw new AccessError(400, "Company keys must use Viewer or Planner access");
    let scopes: string[];
    try { scopes = keyScopes(keyRole, input.scopes, service); }
    catch { throw new AccessError(400, "Choose API permissions within the allowed role"); }
    const name = typeof input.name === "string" ? input.name.trim() : "", days = input.days ?? 90;
    if (!name || name.length > 80) throw new AccessError(400, "Enter a key name of 1–80 characters");
    if (!Number.isInteger(days) || days < 1 || days > 365) throw new AccessError(400, "Choose an expiry of 1–365 days");
    const key = await identity.auth.api.createApiKey({ body: { configId: service ? "company" : "default",
      name, expiresIn: days * 86400, userId: actor, ...(service ? { organizationId: company } : {}),
      permissions: { app: scopes }, metadata: { company_id: company } } });
    try {
      await db.batch([statement("INSERT INTO demandlab_key_bindings(key_id,company_id,owner_id,service_role) VALUES(?,?,?,?)",
        key.id, company, actor, service ? keyRole : null), audit(company, actor, "key.created", key.id)]);
    } catch (error) {
      // An unbound key never resolves, even if disabling it also fails.
      await statement('UPDATE "apikey" SET enabled=0 WHERE id=?', key.id).run();
      throw error;
    }
    return { id: key.id, name: key.name, key: key.key, expires_at: key.expiresAt, scopes };
  }
  if (operation === "keys/create") return createKey(body);
  if (operation === "keys/rotate") {
    const old = await statement(`SELECT b.*,a.name,a.permissions FROM demandlab_key_bindings b
      JOIN "apikey" a ON a.id=b.key_id WHERE b.key_id=? AND b.company_id=? AND b.revoked=0`, body.id, company).first<Body>();
    if (!old || (old.owner_id !== actor && !(old.service_role && who.role === "admin"))) throw new AccessError(404, "API key not found");
    if (old.service_role) admin();
    const saved = typeof old.permissions === "string" ? JSON.parse(old.permissions) : old.permissions;
    const scopes = effectiveScopes(who.role, effectiveScopes(old.service_role || who.role, saved?.app || []));
    const next = await createKey({ kind: old.service_role ? "company" : "personal", role: old.service_role,
      name: body.name || old.name, days: body.days ?? 90, scopes });
    try {
      await db.batch([statement("UPDATE demandlab_key_bindings SET revoked=1 WHERE key_id=?", old.key_id),
        statement('UPDATE "apikey" SET enabled=0 WHERE id=?', old.key_id), audit(company, actor, "key.rotated", old.key_id)]);
    } catch (error) {
      await db.batch([statement("UPDATE demandlab_key_bindings SET revoked=1 WHERE key_id=?", next.id),
        statement('UPDATE "apikey" SET enabled=0 WHERE id=?', next.id)]);
      throw error;
    }
    return next;
  }
  if (operation === "keys/manage") {
    const binding = await statement("SELECT * FROM demandlab_key_bindings WHERE key_id=? AND company_id=?", body.id, company).first<Body>();
    if (!binding || (who.role !== "admin" && binding.owner_id !== actor)) throw new AccessError(404, "API key not found");
    const changes = [];
    if (body.operation === "revoke") changes.push(statement("UPDATE demandlab_key_bindings SET revoked=1 WHERE key_id=?", body.id),
      statement('UPDATE "apikey" SET enabled=0 WHERE id=?', body.id));
    else if (body.operation === "rename" && typeof body.name === "string" && body.name.trim().length && body.name.trim().length <= 80)
      changes.push(statement('UPDATE "apikey" SET name=? WHERE id=?', body.name.trim(), body.id));
    else throw new AccessError(400, "Choose rename or revoke");
    await db.batch([...changes, audit(company, actor, `key.${body.operation}`, body.id)]);
    return { updated: true };
  }
  admin();
  if (operation === "members/list") return {
    members: (await statement(`SELECT m.id,m."userId" AS user_id,m.role,u.name,u.email,coalesce(s.suspended,0) AS suspended
      FROM "member" m JOIN "user" u ON u.id=m."userId"
      LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
      WHERE m."organizationId"=? ORDER BY u.name`, company).all()).results,
    invitations: (await statement('SELECT id,email,role,status,"expiresAt" FROM "invitation" WHERE "organizationId"=? ORDER BY "expiresAt" DESC', company).all()).results,
  };
  if (operation === "members/invite") {
    // Private deployment must never send invitations to anyone but the owner.
    const email = typeof body.email === "string" ? body.email.trim() : "";
    if (email !== FORECAST_OWNER) throw new AccessError(403, "Invitations remain private");
    const nextRole = role(body.role);
    const invite = await identity.auth.api.createInvitation({ headers, body: { email, role: nextRole, organizationId: company } });
    await audit(company, actor, "member.invited", invite.id).run();
    return { id: invite.id, email, role: nextRole };
  }
  if (operation === "members/cancel-invitation") {
    if (!await statement('SELECT 1 FROM "invitation" WHERE id=? AND "organizationId"=?', body.id, company).first())
      throw new AccessError(404, "Invitation not found");
    await identity.auth.api.cancelInvitation({ headers, body: { invitationId: body.id } });
    await audit(company, actor, "invitation.cancelled", body.id).run();
    return { updated: true };
  }
  if (operation === "members/manage") {
    const target = await statement('SELECT * FROM "member" WHERE id=? AND "organizationId"=?', body.id, company).first<Body>();
    if (!target) throw new AccessError(404, "Member not found");
    const nextRole = body.operation === "role" ? role(body.role) : target.role;
    if (target.role === "admin" && (nextRole !== "admin" || ["suspend", "remove"].includes(body.operation))) {
      const active = (await statement(`SELECT m.id FROM "member" m JOIN "user" u ON u.id=m."userId"
        LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
        WHERE m."organizationId"=? AND m.role='admin' AND u."emailVerified"=1 AND coalesce(s.suspended,0)=0`, company).all<{ id: string }>()).results;
      if (active.length <= 1 && active.some(row => row.id === target.id)) throw new AccessError(409, "Keep at least one active administrator");
    }
    if (body.operation === "role") await identity.auth.api.updateMemberRole({ headers,
      body: { memberId: target.id, role: nextRole, organizationId: company } });
    else if (body.operation === "remove") await identity.auth.api.removeMember({ headers,
      body: { memberIdOrEmail: target.id, organizationId: company } });
    else if (["suspend", "resume"].includes(body.operation)) await statement(`INSERT INTO demandlab_membership_status(company_id,user_id,suspended)
      VALUES(?,?,?) ON CONFLICT(company_id,user_id) DO UPDATE SET suspended=excluded.suspended`, company, target.userId, body.operation === "suspend" ? 1 : 0).run();
    else if (body.operation !== "revoke_sessions") throw new AccessError(400, "Unknown member action");
    const changes = [audit(company, actor, `member.${body.operation}`, target.id)];
    if (["suspend", "remove", "revoke_sessions"].includes(body.operation)) changes.unshift(statement(`DELETE FROM "session" WHERE "userId"=? AND
      ("activeOrganizationId"=? OR id IN (SELECT session_id FROM demandlab_session_company WHERE company_id=?))`, target.userId, company, company));
    await db.batch(changes);
    return { updated: true };
  }
  return { events: (await statement("SELECT id,actor_id,event,resource_id,created_at FROM demandlab_audit WHERE company_id=? ORDER BY id DESC LIMIT 100", company).all()).results };
}

export function safeCloudAccessError(error: unknown) {
  if (error instanceof AccessError) return { status: error.status, body: { detail: error.message } };
  if (error instanceof APIError && [400, 401, 403, 404, 409, 429].includes(error.statusCode))
    return { status: error.statusCode, body: { detail: "Authentication request could not be completed" } };
  return { status: 503, body: { detail: "Authentication operation unavailable" } };
}

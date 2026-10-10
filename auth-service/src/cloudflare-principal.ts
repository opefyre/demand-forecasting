import { asRole, effectiveScopes, permissions, type Role } from "./policy.js";
import type { createCloudflareIdentity, D1Binding } from "./cloudflare.js";

type Identity = ReturnType<typeof createCloudflareIdentity>;
const COMPANY_ID = /^[A-Za-z0-9_-]{1,128}$/;
export class PrivateIdentityError extends Error {
  constructor(public status: 400 | 401 | 403 | 404 | 409 | 429, message: string) { super(message); }
}
type Membership = { company_id: string; user_id: string; role: string; suspended: number;
  name: string; email: string; email_verified: number; two_factor_enabled: number; has_password: number };

export async function d1Membership(db: D1Binding, company: string, user: string) {
  const row = await db.prepare(`SELECT m."organizationId" AS company_id,m."userId" AS user_id,m.role,
    coalesce(s.suspended,0) AS suspended,u.name,u.email,u."emailVerified" AS email_verified,
    coalesce(u."twoFactorEnabled",0) AS two_factor_enabled,
    EXISTS(SELECT 1 FROM "account" a WHERE a."userId"=u.id AND a."providerId"='credential') AS has_password
    FROM "member" m JOIN "user" u ON u.id=m."userId"
    LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
    WHERE m."organizationId"=? AND m."userId"=?`).bind(company, user).first<Membership>();
  if (!row || row.suspended !== 0 || row.email_verified !== 1)
    throw new PrivateIdentityError(403, "Company access is unavailable");
  try { return { ...row, role: asRole(row.role) }; }
  catch { throw new PrivateIdentityError(403, "Company access is unavailable"); }
}

// Server-side bridge implementation only. There is deliberately no public route
// or Worker RPC exposing identity resolution in the closed deployment milestone.
export async function resolveD1Identity(identity: Identity, db: D1Binding,
  body: { cookie?: string; key?: string; company_id?: string }, now = Date.now()) {
  if (body.company_id !== undefined && !COMPANY_ID.test(body.company_id))
    throw new PrivateIdentityError(400, "Invalid company identifier");
  if (body.key !== undefined) {
    if (typeof body.key !== "string" || !body.key || body.key.length > 512)
      throw new PrivateIdentityError(401, "API key is invalid, expired or revoked");
    const verified = await identity.auth.api.verifyApiKey({ body: { key: body.key } });
    if (!verified.valid || !verified.key)
      throw new PrivateIdentityError(verified.error?.code === "RATE_LIMITED" ? 429 : 401,
        "API key is invalid, expired or revoked");
    const binding = await db.prepare(`SELECT company_id,owner_id,service_role
      FROM demandlab_key_bindings WHERE key_id=? AND revoked=0`).bind(verified.key.id)
      .first<{ company_id: string; owner_id: string; service_role: Role | null }>();
    if (!binding || !COMPANY_ID.test(binding.company_id))
      throw new PrivateIdentityError(401, "API key is not bound to an active company");
    if (body.company_id && body.company_id !== binding.company_id)
      throw new PrivateIdentityError(403, "API key belongs to a different company");
    const current = await d1Membership(db, binding.company_id, binding.owner_id);
    if (current.role === "admin" && !current.two_factor_enabled)
      throw new PrivateIdentityError(403, "Key owner must enable two-factor authentication");
    if (binding.service_role && !["planner", "viewer"].includes(binding.service_role))
      throw new PrivateIdentityError(403, "Company access is unavailable");
    const role = binding.service_role || current.role;
    return { issuer: identity.config.origin, company_id: binding.company_id, role,
      subject: binding.service_role ? `service:${verified.key.id}` : binding.owner_id,
      name: binding.service_role ? verified.key.name : current.name,
      permissions: effectiveScopes(current.role, effectiveScopes(role, verified.key.permissions?.app || [])),
      key_id: verified.key.id, auth_kind: "api_key", mfa_required: false };
  }
  if (body.cookie !== undefined && (typeof body.cookie !== "string" || body.cookie.length > 16384))
    throw new PrivateIdentityError(401, "Sign in to continue");
  const saved = await identity.auth.api.getSession({
    headers: new Headers({ cookie: body.cookie || "", origin: identity.config.origin }),
    query: { disableCookieCache: true },
  });
  if (!saved) throw new PrivateIdentityError(401, "Sign in to continue");
  const memberships = (await db.prepare(`SELECT m."organizationId" AS id,o.name,m.role,
    coalesce(s.suspended,0) AS suspended FROM "member" m
    JOIN "organization" o ON o.id=m."organizationId"
    LEFT JOIN demandlab_membership_status s ON s.company_id=m."organizationId" AND s.user_id=m."userId"
    WHERE m."userId"=? ORDER BY o.name`).bind(saved.user.id)
    .all<{ id: string; name: string; role: string; suspended: number }>()).results;
  const company = body.company_id || memberships.find(row => row.id === saved.session.activeOrganizationId && !row.suspended)?.id ||
    memberships.find(row => !row.suspended)?.id;
  if (!company || !COMPANY_ID.test(company))
    throw new PrivateIdentityError(403, "Accept a company invitation first");
  const current = await d1Membership(db, company, saved.user.id);
  await db.prepare("INSERT INTO demandlab_session_company(session_id,company_id) VALUES(?,?) ON CONFLICT DO NOTHING")
    .bind(saved.session.id, company).run();
  const proof = await db.prepare("SELECT 1 FROM demandlab_session_mfa WHERE session_id=? AND verified_at>? AND verified_at<=?")
    .bind(saved.session.id, now - 3600000, now).first();
  return { issuer: identity.config.origin, subject: saved.user.id, name: saved.user.name, email: saved.user.email,
    company_id: company, role: current.role, permissions: permissions[current.role],
    mfa_required: current.role === "admin" && (!current.two_factor_enabled || !proof),
    mfa_enabled: !!current.two_factor_enabled, has_password: !!current.has_password,
    auth_kind: "session", session_id: saved.session.id,
    companies: memberships.filter(row => row.suspended === 0).map(({ suspended, ...row }) => row) };
}

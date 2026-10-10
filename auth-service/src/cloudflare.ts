import type { BetterAuthOptions } from "better-auth";
import { createAuthCore, type MailDelivery } from "./auth-core.js";

export interface D1Binding {
  prepare(sql: string): {
    bind(...values: (string | number | null)[]): {
      first<T = Record<string, unknown>>(): Promise<T | null>;
      run(): Promise<unknown>;
      all<T = Record<string, unknown>>(): Promise<{ results: T[] }>;
    };
    run(): Promise<unknown>;
  };
  batch(statements: unknown[]): Promise<unknown[]>;
  exec(sql: string): Promise<unknown>;
}
export interface CloudflareIdentityEnv {
  IDENTITY_DB: D1Binding;
  PRIVATE_ACCESS: string;
  BETTER_AUTH_SECRET?: string;
  RESEND_API_KEY?: string;
  GOOGLE_CLIENT_ID?: string;
  GOOGLE_CLIENT_SECRET?: string;
}
export const FORECAST_ORIGIN = "https://forecast.vrolen.com";
export const FORECAST_OWNER = "opefyre@gmail.com";
export const FORECAST_GOOGLE_CLIENT = "945632758521-baj6dsc8irl5qmcknbi0tgt4ui0skjl0.apps.googleusercontent.com";
export const FORECAST_SENDER = "Vrolen Forecast <notifications@forecast.vrolen.com>";

export function cloudflareConfiguration(env: CloudflareIdentityEnv) {
  if (env.PRIVATE_ACCESS !== "closed") throw new Error("Private deployment must remain closed");
  if (!env.IDENTITY_DB || !env.IDENTITY_DB.prepare || !env.IDENTITY_DB.batch || !env.IDENTITY_DB.exec)
    throw new Error("An isolated D1 identity database is required");
  if (typeof env.BETTER_AUTH_SECRET !== "string" || env.BETTER_AUTH_SECRET.length < 64)
    throw new Error("Configure a dedicated production authentication secret");
  if (!!env.GOOGLE_CLIENT_ID !== !!env.GOOGLE_CLIENT_SECRET ||
      (env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_ID !== FORECAST_GOOGLE_CLIENT))
    throw new Error("Configure the separate forecast Google client");
  return { origin: FORECAST_ORIGIN, secret: env.BETTER_AUTH_SECRET, local: false };
}

export function createCloudflareIdentity(env: CloudflareIdentityEnv, deliver: MailDelivery) {
  const config = cloudflareConfiguration(env);
  const auth = createAuthCore(config, env.IDENTITY_DB as BetterAuthOptions["database"], {
    // No bootstrap, new invitations or registration while deployment is closed.
    // Future owner-only acceptance needs an explicit reviewed workflow.
    async invitationAllowed() { return false; },
    async recordMfa(sessionId, userId) {
      await env.IDENTITY_DB.prepare(
        `INSERT INTO demandlab_session_mfa(session_id,user_id,verified_at) VALUES(?,?,?)
         ON CONFLICT(session_id) DO UPDATE SET verified_at=excluded.verified_at`,
      ).bind(sessionId, userId, Date.now()).run();
    },
    async clearMfa(userId) {
      await env.IDENTITY_DB.prepare("DELETE FROM demandlab_session_mfa WHERE user_id=?").bind(userId).run();
    },
  }, deliver, env);
  return { auth, config };
}

// Supplement the maintained library's generated schema, not new auth tables.
export const D1_POLICY_SCHEMA = [
  `CREATE TABLE IF NOT EXISTS demandlab_membership_status (
    company_id TEXT NOT NULL, user_id TEXT NOT NULL,
    suspended INTEGER NOT NULL DEFAULT 0 CHECK(suspended IN (0,1)),
    PRIMARY KEY(company_id,user_id))`,
  `CREATE TABLE IF NOT EXISTS demandlab_key_bindings (
    key_id TEXT PRIMARY KEY, company_id TEXT NOT NULL, owner_id TEXT NOT NULL,
    service_role TEXT CHECK(service_role IN ('planner','viewer')),
    revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)))`,
  `CREATE TABLE IF NOT EXISTS demandlab_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, company_id TEXT NOT NULL, actor_id TEXT NOT NULL,
    event TEXT NOT NULL, resource_id TEXT, created_at INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS demandlab_session_mfa (
    session_id TEXT PRIMARY KEY REFERENCES "session"(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    verified_at INTEGER NOT NULL)`,
  `CREATE TABLE IF NOT EXISTS demandlab_session_company (
    session_id TEXT NOT NULL REFERENCES "session"(id) ON DELETE CASCADE,
    company_id TEXT NOT NULL, PRIMARY KEY(session_id,company_id))`,
  `CREATE INDEX IF NOT EXISTS demandlab_key_company ON demandlab_key_bindings(company_id,owner_id)`,
  `CREATE INDEX IF NOT EXISTS demandlab_audit_company ON demandlab_audit(company_id,created_at)`,
];

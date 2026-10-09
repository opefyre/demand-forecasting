import { getMigrations } from "better-auth/db/migration";
import { createIdentity } from "./auth.js";

export async function migrate(identity: ReturnType<typeof createIdentity>) {
  const migration = await getMigrations(identity.auth.options);
  await migration.runMigrations();
  await identity.pool.query(`
    CREATE TABLE IF NOT EXISTS demandlab_membership_status (
      company_id text NOT NULL, user_id text NOT NULL, suspended boolean NOT NULL DEFAULT false,
      PRIMARY KEY (company_id,user_id));
    CREATE TABLE IF NOT EXISTS demandlab_key_bindings (
      key_id text PRIMARY KEY, company_id text NOT NULL, owner_id text NOT NULL,
      service_role text, revoked boolean NOT NULL DEFAULT false);
    CREATE TABLE IF NOT EXISTS demandlab_audit (
      id bigserial PRIMARY KEY, company_id text NOT NULL, actor_id text NOT NULL,
      event text NOT NULL, resource_id text, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE IF NOT EXISTS demandlab_session_mfa (
      session_id text PRIMARY KEY REFERENCES "session"(id) ON DELETE CASCADE,
      user_id text NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
      verified_at timestamptz NOT NULL);
    CREATE TABLE IF NOT EXISTS demandlab_session_company (
      session_id text NOT NULL REFERENCES "session"(id) ON DELETE CASCADE,
      company_id text NOT NULL, PRIMARY KEY(session_id,company_id));
  `);
}

if (process.argv[1]?.endsWith("migrate.ts")) {
  const identity = createIdentity();
  try {
    await migrate(identity);
    console.log("Authentication schema migrated");
  } finally {
    await identity.pool.end();
  }
}

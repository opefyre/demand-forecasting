import { Pool } from "pg";
import nodemailer from "nodemailer";
import { mkdir, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { configuration } from "./env.js";
import { createAuthCore, type MailDelivery } from "./auth-core.js";

export function createIdentity(env: NodeJS.ProcessEnv = process.env, bootstrap = false, deliver?: MailDelivery) {
  const config = configuration(env);
  const pool = new Pool({ connectionString: config.databaseURL, max: 8 });
  const mailer = config.devMail ? null : nodemailer.createTransport({
    host: env.SMTP_HOST, port: Number(env.SMTP_PORT || 587), secure: env.SMTP_PORT === "465",
    requireTLS: true,
    auth: env.SMTP_USER ? { user: env.SMTP_USER, pass: env.SMTP_PASSWORD } : undefined,
    disableFileAccess: true, disableUrlAccess: true,
  });
  async function send(to: string, subject: string, text: string) {
    if (deliver) return deliver(to, subject, text);
    if (config.devMail) {
      const outbox = fileURLToPath(new URL("../../secrets/auth-mail/", import.meta.url));
      await mkdir(outbox, { recursive: true, mode: 0o700 });
      await writeFile(`${outbox}/${randomUUID()}.json`, JSON.stringify({ to, subject, text }), { mode: 0o600 });
    } else await mailer!.sendMail({ from: env.SMTP_FROM, to, subject, text });
  }
  const auth = createAuthCore(config, pool, {
    async invitationAllowed(email) {
      if (bootstrap) return true;
      return !!(await pool.query(
        'SELECT 1 FROM "invitation" WHERE lower(email)=lower($1) AND status=$2 AND "expiresAt">now() LIMIT 1',
        [email, "pending"],
      )).rowCount;
    },
    async recordMfa(sessionId, userId) {
      await pool.query(
        `INSERT INTO demandlab_session_mfa(session_id,user_id,verified_at) VALUES($1,$2,now())
        ON CONFLICT(session_id) DO UPDATE SET verified_at=excluded.verified_at`, [sessionId, userId],
      );
    },
    async clearMfa(userId) { await pool.query("DELETE FROM demandlab_session_mfa WHERE user_id=$1", [userId]); },
  }, send, env);
  return { auth, pool, config };
}

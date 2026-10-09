import { fileURLToPath } from "node:url";
import { lstatSync } from "node:fs";

export function validateEnvironmentFile(path: string) {
  const info = lstatSync(path);
  if (!info.isFile() || info.isSymbolicLink() ||
      (process.platform !== "win32" && ((info.mode & 0o077) !== 0 || info.uid !== process.getuid!())))
    throw new Error("The authentication secret file must be owner-only and not a link");
}

try {
  const path = fileURLToPath(new URL("../../secrets/.env.local", import.meta.url));
  validateEnvironmentFile(path);
  process.loadEnvFile(path);
} catch (error) {
  if ((error as NodeJS.ErrnoException).code !== "ENOENT")
    throw new Error("Cannot load authentication settings. Use an owner-only regular secrets/.env.local file, not a link");
}

export function configuration(env: NodeJS.ProcessEnv = process.env) {
  const origin = env.DEMANDLAB_PUBLIC_ORIGIN || "http://127.0.0.1:8010";
  let parsed: URL;
  try { parsed = new URL(origin); }
  catch { throw new Error("Use a valid application origin"); }
  const local = ["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname);
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    (!local && parsed.protocol !== "https:") ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    parsed.pathname !== "/" ||
    origin.replace(/\/$/, '') !== parsed.origin
  )
    throw new Error(
      "Use an HTTPS application origin, or a loopback development origin",
    );
  const secret = env.BETTER_AUTH_SECRET || "";
  const bridgeSecret = env.DEMANDLAB_AUTH_BRIDGE_SECRET || "";
  if (secret.length < 32 || bridgeSecret.length < 32 || secret === bridgeSecret)
    throw new Error(
      "Separate random authentication and bridge secrets of 32+ characters are required",
    );
  if (!env.DEMANDLAB_AUTH_DATABASE_URL)
    throw new Error(
      "An isolated PostgreSQL authentication database is required",
    );
  let database: URL;
  try { database = new URL(env.DEMANDLAB_AUTH_DATABASE_URL); }
  catch { throw new Error("Use a valid PostgreSQL authentication database URL"); }
  if (!['postgres:', 'postgresql:'].includes(database.protocol) || !database.hostname ||
      database.pathname.length < 2 || database.hash)
    throw new Error("Use a dedicated PostgreSQL authentication database URL");
  const devMail = env.DEMANDLAB_AUTH_DEV_MAIL === "true";
  if (devMail && !local)
    throw new Error("Development mail cannot be enabled on a public origin");
  if (!devMail && (!env.SMTP_HOST || !env.SMTP_FROM))
    throw new Error(
      "Configure SMTP for verification, invitations and recovery",
    );
  const smtpPort = env.SMTP_PORT || '587';
  if (!/^\d+$/.test(smtpPort) || Number(smtpPort) < 1 || Number(smtpPort) > 65535)
    throw new Error("Use a valid SMTP port");
  if (!!env.SMTP_USER !== !!env.SMTP_PASSWORD)
    throw new Error("Both SMTP credentials are required when using authenticated mail");
  if (!!env.GOOGLE_CLIENT_ID !== !!env.GOOGLE_CLIENT_SECRET)
    throw new Error("Both Google OAuth credentials are required");
  return {
    origin: parsed.origin,
    local,
    secret,
    bridgeSecret,
    devMail,
    databaseURL: env.DEMANDLAB_AUTH_DATABASE_URL,
  };
}

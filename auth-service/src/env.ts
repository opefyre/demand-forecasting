import { fileURLToPath } from "node:url";

try {
  process.loadEnvFile(
    fileURLToPath(new URL("../../secrets/.env.local", import.meta.url)),
  );
} catch (error) {
  if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
}

export function configuration(env: NodeJS.ProcessEnv = process.env) {
  const origin = env.DEMANDLAB_PUBLIC_ORIGIN || "http://127.0.0.1:8010";
  const parsed = new URL(origin);
  const local = ["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname);
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    (!local && parsed.protocol !== "https:") ||
    parsed.username ||
    parsed.password ||
    parsed.search ||
    parsed.hash ||
    parsed.pathname !== "/"
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
  const devMail = env.DEMANDLAB_AUTH_DEV_MAIL === "true";
  if (devMail && !local)
    throw new Error("Development mail cannot be enabled on a public origin");
  if (!devMail && (!env.SMTP_HOST || !env.SMTP_FROM))
    throw new Error(
      "Configure SMTP for verification, invitations and recovery",
    );
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

import { lstat, readFile, writeFile } from "node:fs/promises";
import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { FORECAST_GOOGLE_CLIENT, FORECAST_ORIGIN } from "../src/cloudflare.js";

// Only this new, closed Worker. Never accept a worker/account/path override, log
// values, reuse local auth/AI keys, or deploy the quarantined Google download.
const configPath = fileURLToPath(new URL("../../deploy/cloudflare/identity.wrangler.jsonc", import.meta.url));
const secretsDirectory = new URL("../../secrets/", import.meta.url);
async function privateFile(name: string) {
  const path = new URL(name, secretsDirectory);
  const stat = await lstat(path);
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o077))
    throw new Error("Forecast credential files must be private regular files");
  return readFile(path, "utf8");
}

try {
  const config = JSON.parse(await readFile(configPath, "utf8"));
  if (config.name !== "demandlab-forecast-identity" || config.account_id !== "b53df72f41f5135daf312100e73ff6a1" ||
    config.workers_dev !== false || config.preview_urls !== false || config.routes.length ||
    config.vars.PRIVATE_ACCESS !== "closed" || config.vars.NODE_ENV !== "production" ||
    config.d1_databases.length !== 1 || config.d1_databases[0].database_id !== "f0f8d4b4-ff3d-4bcc-90ac-c08ff97b64e7")
    throw new Error("Forecast identity deployment must remain isolated and closed");
  const google = JSON.parse(await privateFile("forecast-google-oauth.json")).web;
  if (!google || google.client_id !== FORECAST_GOOGLE_CLIENT || google.project_id !== "vrolen" ||
    google.javascript_origins?.length !== 1 || google.javascript_origins[0] !== FORECAST_ORIGIN ||
    google.redirect_uris?.length !== 1 || google.redirect_uris[0] !== FORECAST_ORIGIN + "/api/login/callback/google" ||
    typeof google.client_secret !== "string" || !google.client_secret.startsWith("GOCSPX-"))
    throw new Error("Forecast Google credential does not match the approved client");
  const mail = (await privateFile("forecast-resend-api.txt")).trim();
  if (!/^re_[A-Za-z0-9_-]{16,}$/.test(mail)) throw new Error("Invalid forecast mail credential");
  const secretPath = new URL("forecast-auth-secret.txt", secretsDirectory);
  try { await lstat(secretPath); }
  catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    // Cryptographic generation; never overwrite an existing deployment secret.
    await writeFile(secretPath, randomBytes(32).toString("hex"), { flag: "wx", mode: 0o600 });
  }
  const auth = (await privateFile("forecast-auth-secret.txt")).trim();
  if (!/^[a-f0-9]{64}$/.test(auth)) throw new Error("Invalid dedicated authentication secret");
  const values = { BETTER_AUTH_SECRET: auth, GOOGLE_CLIENT_ID: google.client_id,
    GOOGLE_CLIENT_SECRET: google.client_secret, RESEND_API_KEY: mail };
  if (!process.argv.includes("--install")) {
    console.log("Four dedicated forecast credentials validated; no values displayed or uploaded");
  } else {
    const child = spawn("npx", ["--yes", "wrangler@4.149.0", "secret", "bulk", "--config", configPath], {
      stdio: ["pipe", "ignore", "ignore"], env: { ...process.env, WRANGLER_LOG: "error", WRANGLER_SEND_METRICS: "false" },
    });
    child.stdin.on("error", () => {});
    const done = new Promise<void>((resolve, reject) => {
      child.once("error", () => reject(new Error("Forecast secret upload could not start")));
      child.once("close", code => code === 0 ? resolve() : reject(new Error("Forecast secret upload failed")));
    });
    child.stdin.end(JSON.stringify(values));
    await done;
    console.log("Four dedicated forecast credentials installed in the closed identity Worker");
  }
} catch {
  // Do not forward parser errors, provider output, file contents or values.
  console.error("Forecast credential setup failed; check the approved private files and closed deployment configuration");
  process.exitCode = 1;
}

/** Read-only configuration checks. No database, provider or mail requests. */
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { configuration } from './env.js';

export function deploymentChecks(env: NodeJS.ProcessEnv, allowLocal = false) {
  const blockers: string[] = [];
  const pending = [
    'Verify migrations, sign-in and all four roles against the deployment database.',
    'Verify mail delivery and recovery links with a test recipient.',
    'Verify HTTPS, private identity-service access and signed-in API documentation.',
    'Verify company-state and PostgreSQL backups, session/key revocation and secret-vault recovery.',
    'Verify enabled input and notification providers with their real accounts.',
  ];
  try {
    const config = configuration(env);
    if (!env.DEMANDLAB_PUBLIC_ORIGIN) blockers.push('Set the exact application origin explicitly.');
    if (config.local && !allowLocal) blockers.push('A loopback origin is for local testing, not deployment.');
    if (config.devMail) pending.push('Local mail files do not prove real mail delivery.');
  } catch {
    // Never echo a malformed URL, database password or raw library exception.
    blockers.push('Authentication configuration is incomplete or invalid. Check the protected settings against .env.example.');
  }
  if (env.DEMANDLAB_AUTH_MODE !== 'better_auth') blockers.push('Company mode must be better_auth in the target deployment. Do not change the existing demo.');
  try {
    const privateURL = new URL(env.DEMANDLAB_AUTH_SERVICE_URL || 'http://127.0.0.1:8011');
    // The supplied server binds IPv4 port 8011; require the matching target.
    if (privateURL.origin !== 'http://127.0.0.1:8011' || privateURL.pathname !== '/' ||
        privateURL.username || privateURL.password || privateURL.search || privateURL.hash)
      blockers.push('Use the private identity service at http://127.0.0.1:8011.');
  } catch { blockers.push('Use a valid private identity-service URL.'); }
  if (env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET)
    pending.push('Verify Google sign-in and its callback with an invited test account.');
  else pending.push('Google sign-in is not configured.');
  return { configuration_ok: blockers.length === 0, deployment_verified: false,
           mode: allowLocal ? 'local-check' : 'deployment-check', blockers, pending };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = deploymentChecks(process.env, process.argv.includes('--local'));
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = result.configuration_ok ? 0 : 1;
}

import { WorkerEntrypoint, DurableObject } from 'cloudflare:workers';
import { getMigrations } from 'better-auth/db/migration';
import { cloudflareConfiguration, createCloudflareIdentity } from './cloudflare.ts';
import { cloudflareMailer } from './cloudflare-mail.ts';
import { cloudAccessOperation, safeCloudAccessError } from './cloudflare-access.ts';

// One private serialized coordinator. Nothing can remove two final admins in
// concurrent requests; each actor is checked against D1 AFTER entering the lock.
export class ForecastAccess extends DurableObject {
  async operation(operation, body) {
    return this.ctx.blockConcurrencyWhile(async () => {
      try {
        const identity = createCloudflareIdentity(this.env, cloudflareMailer(this.env));
        return { status: 200, body: await cloudAccessOperation(identity, this.env.IDENTITY_DB, operation, body) };
      } catch (error) { return safeCloudAccessError(error); }
    });
  }
  fetch() { return new Response(null, { status: 404 }); }
}

// Only a future, explicitly bound private gateway can call this RPC entrypoint.
// No request handler forwards to Better Auth; signup/login/keys remain inaccessible.
export class ForecastIdentity extends WorkerEntrypoint {
  async operation(operation, body) {
    return this.env.ACCESS.get(this.env.ACCESS.idFromName('forecast-access-v1')).operation(operation, body);
  }
  async readiness() {
    try {
      cloudflareConfiguration(this.env);
      const { auth } = createCloudflareIdentity(this.env, cloudflareMailer(this.env));
      const schema = await getMigrations(auth.options);
      return {
        access: 'closed',
        schema_ready: !schema.toBeCreated.length && !schema.toBeAdded.length &&
          !schema.toBeAddedIndexes.length && !schema.unsafeChanges.length && !schema.schemaProblems.length,
        google_configured: !!this.env.GOOGLE_CLIENT_ID,
        mail_configured: !!this.env.RESEND_API_KEY,
        sign_in_verified: false,
        delivery_verified: false,
      };
    } catch {
      return { access: 'closed', schema_ready: false, sign_in_verified: false, delivery_verified: false };
    }
  }
}

export default {
  fetch(request) {
    return new Response(request.method === 'HEAD' ? null : 'Not found.\n', {
      status: 404,
      headers: { 'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
        'Content-Type': 'text/plain; charset=utf-8', 'X-Content-Type-Options': 'nosniff',
        'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; base-uri 'none'" },
    });
  },
};

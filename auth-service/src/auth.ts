import { betterAuth } from "better-auth";
import { APIError, createAuthMiddleware } from "better-auth/api";
import { organization, twoFactor } from "better-auth/plugins";
import { createAccessControl } from "better-auth/plugins/access";
import {
  defaultStatements,
  adminAc,
} from "better-auth/plugins/organization/access";
import { apiKey } from "@better-auth/api-key";
import { Pool } from "pg";
import nodemailer from "nodemailer";
import { mkdir, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { configuration } from "./env.js";
import { asRole } from "./policy.js";

export function createIdentity(
  env: NodeJS.ProcessEnv = process.env,
  bootstrap = false,
  deliver?: (to: string, subject: string, text: string) => Promise<void>,
) {
  const config = configuration(env);
  const pool = new Pool({ connectionString: config.databaseURL, max: 8 });
  const ac = createAccessControl(defaultStatements);
  const empty = ac.newRole({});
  const mailer = config.devMail
    ? null
    : nodemailer.createTransport({
        host: env.SMTP_HOST,
        port: Number(env.SMTP_PORT || 587),
        secure: env.SMTP_PORT === "465",
        requireTLS: true,
        auth: env.SMTP_USER
          ? { user: env.SMTP_USER, pass: env.SMTP_PASSWORD }
          : undefined,
        disableFileAccess: true,
        disableUrlAccess: true,
      });
  async function send(to: string, subject: string, text: string) {
    if (deliver) return deliver(to, subject, text);
    if (config.devMail) {
      const outbox = fileURLToPath(
        new URL("../../secrets/auth-mail/", import.meta.url),
      );
      await mkdir(outbox, { recursive: true, mode: 0o700 });
      await writeFile(
        `${outbox}/${randomUUID()}.json`,
        JSON.stringify({ to, subject, text }),
        { mode: 0o600 },
      );
    } else await mailer!.sendMail({ from: env.SMTP_FROM, to, subject, text });
  }
  const auth = betterAuth({
    database: pool,
    secret: config.secret,
    baseURL: config.origin,
    basePath: "/api/login",
    trustedOrigins: [config.origin],
    logger: { disabled: true },
    advanced: { useSecureCookies: !config.local },
    session: { expiresIn: 3600, cookieCache: { enabled: false } },
    rateLimit: {
      enabled: true,
      storage: "database",
      window: 60,
      max: 60,
      customRules: {
        "/sign-in/email": { window: 60, max: 5 },
        "/sign-up/email": { window: 60, max: 5 },
      },
    },
    emailAndPassword: {
      enabled: true,
      minPasswordLength: 12,
      maxPasswordLength: 128,
      requireEmailVerification: true,
      sendResetPassword: async ({ user, url }) =>
        send(user.email, "Reset your DemandLab password", url),
      revokeSessionsOnPasswordReset: true,
    },
    emailVerification: {
      sendOnSignUp: true,
      autoSignInAfterVerification: false,
      sendVerificationEmail: async ({ user, url }) =>
        send(user.email, "Verify your DemandLab email", url),
    },
    socialProviders: env.GOOGLE_CLIENT_ID
      ? {
          google: {
            clientId: env.GOOGLE_CLIENT_ID,
            clientSecret: env.GOOGLE_CLIENT_SECRET!,
          },
        }
      : {},
    account: { accountLinking: { enabled: false } },
    databaseHooks: {
      user: {
        create: {
          before: async (user) => {
            if (!bootstrap) {
              const eligible = await pool.query(
                'SELECT 1 FROM "invitation" WHERE lower(email)=lower($1) AND status=$2 AND "expiresAt">now() LIMIT 1',
                [user.email, "pending"],
              );
              if (!eligible.rowCount)
                throw new APIError("FORBIDDEN", {
                  message: "An invitation is required",
                });
            }
            return { data: user };
          },
        },
      },
    },
    hooks: {
      before: createAuthMiddleware(async (ctx) => {
        // Keys are managed through permission-checked backend endpoints only.
        if (ctx.request && ctx.path.startsWith("/api-key/"))
          throw new APIError("FORBIDDEN", {
            message: "Use Settings → API access",
          });
        const publicOrganization = [
          "/organization/list",
          "/organization/set-active",
          "/organization/get-invitation",
          "/organization/accept-invitation",
          "/organization/reject-invitation",
          "/organization/list-user-invitations",
        ];
        if (
          ctx.request &&
          ctx.path.startsWith("/organization/") &&
          !publicOrganization.includes(ctx.path)
        )
          throw new APIError("FORBIDDEN", { message: "Use Settings → People" });
      }),
      after: createAuthMiddleware(async (ctx) => {
        // Better Auth validates the factor. This evidence also gates Google sessions:
        // enabling 2FA on an account is not proof that a particular session passed it.
        if (
          [
            "/two-factor/verify-totp",
            "/two-factor/verify-backup-code",
          ].includes(ctx.path)
        ) {
          const result = ctx.context.returned as { token?: string } | undefined;
          const saved = ctx.context.newSession || ctx.context.session;
          // Enrollment rotates the cookie; the upstream response can still name
          // the previous session token. Use its validated new-session context.
          if (typeof result?.token === "string" && saved?.session.id)
            await pool.query(
              `INSERT INTO demandlab_session_mfa(session_id,user_id,verified_at) VALUES($1,$2,now())
            ON CONFLICT(session_id) DO UPDATE SET verified_at=excluded.verified_at`,
              [saved.session.id, saved.user.id],
            );
        }
        if (
          ctx.path === "/two-factor/disable" &&
          !(ctx.context.returned instanceof APIError) &&
          ctx.context.session
        )
          await pool.query(
            "DELETE FROM demandlab_session_mfa WHERE user_id=$1",
            [ctx.context.session.user.id],
          );
      }),
    },
    plugins: [
      organization({
        allowUserToCreateOrganization: false,
        creatorRole: "admin",
        ac,
        roles: {
          admin: adminAc,
          planner: empty,
          approver: empty,
          viewer: empty,
        },
        requireEmailVerificationOnInvitation: true,
        sendInvitationEmail: async (data) =>
          send(
            data.email,
            "Join your DemandLab company",
            `${config.origin}/?invitation=${encodeURIComponent(data.id)}`,
          ),
        organizationHooks: {
          beforeAddMember: async ({ member }) => {
            asRole(member.role);
          },
          beforeUpdateMemberRole: async ({ newRole }) => {
            asRole(newRole);
          },
          beforeDeleteOrganization: async () => {
            throw new APIError("FORBIDDEN", {
              message: "Archive company data through the application",
            });
          },
        },
      }),
      twoFactor({ issuer: "DemandLab", allowPasswordless: true }),
      apiKey([
        {
          configId: "default",
          references: "user",
          defaultPrefix: "dl_",
          enableMetadata: true,
          disableKeyHashing: false,
          enableSessionForAPIKeys: false,
          permissions: { defaultPermissions: {} },
          keyExpiration: {
            defaultExpiresIn: 90 * 86400,
            maxExpiresIn: 365,
            minExpiresIn: 1,
          },
          rateLimit: { enabled: true, timeWindow: 60000, maxRequests: 60 },
        },
        {
          configId: "company",
          references: "organization",
          defaultPrefix: "dl_",
          enableMetadata: true,
          disableKeyHashing: false,
          enableSessionForAPIKeys: false,
          permissions: { defaultPermissions: {} },
          keyExpiration: {
            defaultExpiresIn: 90 * 86400,
            maxExpiresIn: 365,
            minExpiresIn: 1,
          },
          rateLimit: { enabled: true, timeWindow: 60000, maxRequests: 60 },
        },
      ]),
    ],
  });
  return { auth, pool, config };
}

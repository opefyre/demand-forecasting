# Reused components

Install packages rather than copying unmaintained snippets. Preserve upstream
licences if code is vendored. Pin and audit dependencies before each release.

| Component | Upstream | Licence | Use |
|---|---|---|---|
| Better Auth | https://github.com/better-auth/better-auth | MIT | Passwords, Google, sessions, organizations, invitations, API keys, 2FA |
| Hono | https://github.com/honojs/hono | MIT | Small authentication service and request handling |
| node-postgres | https://github.com/brianc/node-postgres | MIT | Authentication database |
| Nodemailer | https://github.com/nodemailer/nodemailer | MIT | Verification, reset and invitation emails |
| detect-secrets | https://github.com/Yelp/detect-secrets | Apache-2.0 | Pre-push secret scanning |

Existing FastAPI, Pydantic, SQLAlchemy, Huey, APScheduler, Authlib, Radix, Phosphor,
i18next, forecasting and chart libraries remain in use. No custom password hashing,
OAuth protocol, API-key cryptography, email transport or UI primitive is implemented.

Next connector dependencies: Paramiko for SFTP; Google's official API/auth clients
for Sheets; official provider APIs/SDKs for notifications. Odoo-specific mappings
must respect the API version and installed modules; do not copy an AGPL framework
into the application without explicitly reviewing the distribution obligations.

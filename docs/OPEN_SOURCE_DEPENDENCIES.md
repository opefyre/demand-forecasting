# Reused components

Install packages rather than copying unmaintained snippets. Preserve upstream
licences if code is vendored. Pin and audit dependencies before each release.

| Component | Upstream | Licence | Use |
|---|---|---|---|
| Better Auth | https://github.com/better-auth/better-auth | MIT | Passwords, Google, sessions, organizations, invitations, API keys, 2FA |
| Hono | https://github.com/honojs/hono | MIT | Small authentication service and request handling |
| node-postgres | https://github.com/brianc/node-postgres | MIT | Authentication database |
| Nodemailer | https://github.com/nodemailer/nodemailer | MIT | Verification, reset and invitation emails |
| qrcode.react | https://github.com/zpao/qrcode.react | ISC | Authenticator enrollment QR code |
| detect-secrets | https://github.com/Yelp/detect-secrets | Apache-2.0 | Pre-push secret scanning |
| Paramiko 5.0.0 | https://github.com/paramiko/paramiko | LGPL-2.1 | SSH/SFTP client and host-key verification; installed dependency, not vendored |

Existing FastAPI, Pydantic, SQLAlchemy, Huey, APScheduler, Authlib, Radix, Phosphor,
i18next, forecasting and chart libraries remain in use. No custom password hashing,
OAuth protocol, API-key cryptography, email transport or UI primitive is implemented.

Access milestone lockfiles pin Better Auth/API-key plugin 1.7.7, Hono 4.13.13,
Nodemailer 10.0.16 and qrcode.react 4.2.0. Both Node dependency audits reported
zero known vulnerabilities on 9 October 2026. This is not a permanent guarantee;
re-audit before deployment. The small private bridge adds application-specific
company/role checks; authentication itself remains the upstream implementation.

SFTP uses Paramiko; HTTPS reuses httpx and credentials reuse macOS Keychain through
keyring. Standard-library SQLite and the existing dataset/import review services
provide company receipts. No custom SSH, TLS or credential encryption is built.
The runtime dependency is bounded to Paramiko 5.x; retain the package's bundled
licence when distributing the environment. Upstream references:
[SSH client](https://docs.paramiko.org/en/stable/api/client.html),
[release](https://pypi.org/project/paramiko/5.0.0/).

Next connector dependencies: Google's official API/auth clients
for Sheets; official provider APIs/SDKs for notifications. Odoo-specific mappings
must respect the API version and installed modules; do not copy an AGPL framework
into the application without explicitly reviewing the distribution obligations.

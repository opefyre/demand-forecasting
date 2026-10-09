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
| google-auth 2.61.0 | https://github.com/googleapis/google-auth-library-python | Apache-2.0 | Official service-account authentication for read-only Sheets; installed dependency, not vendored |
| Apprise 2.0.1 | https://github.com/caronc/apprise | BSD-2-Clause | Slack, Telegram, WhatsApp adapters and Teams Workflows card formatting; installed dependency, not vendored |

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

Sheets uses Google's maintained authentication library and documented values API,
through the existing bounded/pinned httpx transport. No custom JWT signing or OAuth
protocol is implemented. Odoo uses its documented read-only JSON-RPC (18) and JSON2
(19) APIs through httpx, with version-specific Sales fields; no Odoo server code is
copied. Existing APScheduler supplies recurring captures. No new scheduling engine.

Notifications reuse Apprise in a single-use child process and existing pinned
httpx transport. No SDK files are modified. Teams card formatting is reused with
the current webhook URL; no custom message/card format or scheduling engine.
See [notification delivery and limits](COMPANY_NOTIFICATIONS_DELIVERY.md).

Odoo-specific mappings
must respect the API version and installed modules; do not copy an AGPL framework
into the application without explicitly reviewing the distribution obligations.

# Company notifications — 9 October 2026

Implemented in the company platform. The existing local demo on port 8010 is
unchanged and is not switched to authenticated company mode. Real messaging
accounts have not been verified or enabled.

## Administrator workflow

Settings → Notifications has two shared-framework sections: Destinations and
Delivery history. Add a labelled destination, select events and message language,
authorize outbound messages, and explicitly enable automatic notifications.
New destinations start paused. Credential fields never display saved secrets.
Editing requires renewed consent; restoring an archived destination leaves it paused.

Available events: a grouped forecast is ready, a forecast needs attention, a
forecast is approved, new connected inputs await review, or an input fetch fails.
The observer checks existing company ledgers once a minute; it does not calculate
forecasts or modify input acceptance. It waits for all grouped methods, treats
interrupted jobs as needing attention, and ignores unchanged input captures.
Events predating the latest configuration/consent are not replayed.

History records each attempt and distinguishes queued, sending, provider-accepted,
rejected, uncertain and cancelled. Provider acceptance is **not** evidence the
recipient received/read the message. No delivery/read callback is implemented.
Tests and retries require explicit confirmation; an uncertain retry also requires
acknowledging possible duplication. Retries create linked attempts and retain the
original record. Details link back to the previous attempt. History is paginated.

## Providers and reuse

- Slack: incoming channel webhook.
- Teams: current Workflows webhook; retired Office 365 connectors are rejected.
- Telegram: bot token and one numeric user/group chat ID; the bot must have access.
- WhatsApp: eligible Business Cloud account, sender phone ID, consenting recipient
  and an approved template with exactly one body text variable. No free-form
  outbound marketing, inbound commands or group-chat support.

Apprise **2.0.1**, BSD-2-Clause, supplies the maintained provider adapters and Teams
card formatter. No provider SDK is copied or modified. SDK sending runs in a
single-use bounded child process; secrets go through standard input, not arguments,
files, inherited environment or application logs. A small transport adapter reuses
httpx and the existing DNS-pinning/public-target policy. Teams uses Apprise's card
builder but preserves the current Power Platform webhook URL, which the SDK's
legacy native URL parser does not fully cover.

Upstream setup: [Slack](https://appriseit.com/services/slack/),
[Teams Workflows](https://appriseit.com/services/workflows/),
[Telegram](https://appriseit.com/services/telegram/),
[WhatsApp](https://appriseit.com/services/whatsapp/),
[source/licence](https://github.com/caronc/apprise).

Open-source software does not mean all provider services are free. Check account
limits, WhatsApp template charges, supported country/account eligibility and
local availability before deployment. Iran access and WhatsApp account eligibility
are not certified by synthetic tests. The pinned SDK currently uses Graph v21.0;
verify its supported version and approved template against the real account at
deployment. The app does not bypass provider restrictions.

## Safety and API boundary

All 11 `/api/v1/notifications/*` operations require an interactive administrator
session and `connections:manage`; API keys, planners, approvers and viewers are
denied. Existing session CSRF and administrator two-factor checks remain in force.
The scheduler checks current administrator membership/2FA through the identity
bridge before queuing and again immediately before sending. Outages/revocation
stop sending; grants are never cached. A message already in flight cannot be recalled.

Destinations and delivery records live in each company's `notifications.sqlite3`.
Secrets use separately namespaced macOS Keychain storage, with no plaintext
fallback. API responses, SQLite records and sent messages omit credentials.
Messages contain only brief status text and a sign-in-required app-page link:
no customer names, SKU quantities, files, forecast tables or sensitive error detail.
Metadata retains private actor/connection-version evidence for safe execution.

Configuration uses optimistic versions, explicit outbound consent and archive/
restore. The outbox claims a record atomically to prevent concurrent workers
resending it. There is no automatic retry after an uncertain send. A crashed send
becomes uncertain after 90 seconds; automatic checks never replay it. Queueing is
limited to five new attempts per destination per minute; processing is bounded to
ten sends per check. HTTPS redirects, private addresses and uncontrolled Apprise
URLs are blocked; TLS verification and hostname/SNI pinning remain enabled.

Offline backup/restore keeps delivery history, pauses all company destinations,
cancels queued sends and marks in-flight sends uncertain. Keychain secrets are
not in the backup; deployment vault migration remains a separate gate.

## Verification

Synthetic tests exercise real Apprise request formatting for all four providers,
transport restrictions, safe error states, consent/version/retry guards, concurrent
claims, revoked administrator access, two-company API isolation, actual grouped
job/capture/approval ledgers and recovery. No real message or paid AI call was made.

Browser acceptance covers administrator edit/test, uncertain retry acknowledgement,
linked history, archive/restore staying paused, another company, restricted roles,
Persian labels and a 390px internally scrolling dialog. Shared collection, menu,
table, form and dialog components are used; no inline or notification-specific CSS.

Verification: full backend suite 821 checks (820 passed, one optional identity
integration skipped); 54 focused checks passed after the final recovery and route
permission safeguards. All 264 frontend checks and the production build passed.
Dependency consistency and staged secret checks passed; the bundle's only known
non-secret finding retained its existing hash under the new generated filename.

## Next

Deployment acceptance: verify Google and production email, client connection and
messaging credentials, the deployment secret vault, company backup/restore and
the four-role walkthrough before activating authenticated company mode. Publish
the deployed OpenAPI URL and validate the client's export/receiving contract.

# Company context and screens — 9 October 2026

Core migration delivered. **Not activated on the existing local demo.**
Advanced scenario/monthly automation and deployment acceptance remain open.

## Delivered

- Request-bound assistant services: company datasets/results/AI usage ledger,
  personal chat history, cheap parallel chat naming and confirmed actions. The
  existing OpenAI Agents SDK and role-based models are reused, not replaced.
- Chats and saved views are private to company + identity issuer + user. Company
  integration keys cannot read private chats/views. Changing access rechecks saved
  text and context, not just new queries. Viewer AI sees fresh approved reports;
  draft access, input edits and calculations are not offered to viewers.
- Company actual-vs-forecast comparisons and exports reuse the existing closed-month,
  unit/calendar, missing-value and coverage checks. No production plans are involved.
- Company site/unit settings, customer imports/profiles, source inspection/revisions,
  order updates/templates and live-source configuration/refresh use scoped stores.
- Primary screens, the combined forecast wizard and download links use explicit
  `/api/v1` routes. One request creates a named multi-method forecast; review tokens
  and immutable order/factor versions remain required. Unknown legacy calls fail
  closed; no company screen can fall back to the shared demo stores.
- Browser preferences/drafts are separated by company and user. Company changes
  and role/permission changes remount the app context, discarding stale visible
  report/chat state. Local mode retains its existing keys and workflows.
- Existing global page/collection/dialog components are reused. No new stylesheet,
  inline appearance rules, UI framework or mathematical forecasting engine.
- Company external-source refresh has a root-application lifecycle. Legacy folder,
  recurring and live-source restore handlers cannot start shared-data jobs in
  company-auth mode. Existing provider freshness/permission checks are preserved.

Public API coverage: **105 v1 operations**, including personal chats/views,
actual results, settings and external factor connection operations. This count is
not a claim that all planned APIs/connectors are delivered.

## Verification

- Full backend suite: **725 checks; 724 passed, one optional real-identity
  integration skipped**. All **249 frontend tests passed** and production build
  passed. The earlier actual PostgreSQL identity roundtrip is recorded separately
  in the access milestone; it was not rerun with live credentials here.
- Temporary real company stores/API calls: personal ownership, company separation,
  permission changes, approved-only readers, restricted tools/actions, settings,
  factor connection state, view CRUD, actual-result checks and export snapshots.
- Additional regression for mounted source-refresh startup/shutdown. Existing
  legacy order/factor startup and assistant tests remain covered.
- Browser fixture: two companies, four customers, two SKUs and 36 sales months;
  real calculation engine and company APIs, mocked identity and AI transport.
  The wizard reused current orders, calculated two methods under one name, opened
  combined results and compared methods. Export links selected the exact reviewed
  snapshot. Chat consent/reply/parallel title/rename worked; changing company hid
  the prior chat and showed distinct quantities. Site changes stayed in company B.
- English/Persian screens and 390px Persian results checked, with no horizontal
  page overflow or browser console errors observed. Existing Data collection and
  Settings structures remain shared; no new parallel style system.

Fixture entry point: `tests/company_ui_fixture.py`, loopback-only and disposable.
It is never a production identity service or proof of live provider readiness.
No real client data, identity accounts, credentials or OpenAI calls were changed.
The existing listener on port 8010 was not restarted or switched to company mode.

## Still open / next build

1. Company-scoped advanced assistant factor/scenario/batch actions, guided monthly
   updates and recurring schedules. They are deliberately unavailable in company
   mode today; the existing local-mode implementation is preserved.
2. Remaining useful archive/revision lifecycle plus SFTP, Odoo 18/19, Google Sheets
   and safe HTTP ingestion, using maintained packages and the same review pipeline.
3. Slack/Teams/Telegram/eligible WhatsApp notifications with admin-managed access,
   delivery history and explicit outbound consent.
4. Google/mail and real source-provider acceptance, authenticated multi-company
   browser/worker pilot, backup/restore and deployment activation.

This is not whole-product completion or a new accuracy benchmark.

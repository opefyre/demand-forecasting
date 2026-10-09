# Public platform delivery

Approved scope: sales/demand forecasting only. Reuse maintained open-source
packages; retain licences and attribution. No SAML or messaging commands in v1.

## Milestones

- [x] Review and publish a secret-scanned checkpoint of existing app code.
      Baseline verification: 679 backend tests and 238 interface tests passed.
- [ ] Better Auth service: email/password, Google, invitation-only organizations,
      four roles, admin two-factor authentication, session revocation.
- [ ] Company-scoped persistence, files, jobs, schedules and assistant context.
- [ ] Public `/api/v1` and route-by-route permission/coverage inventory.
- [ ] Scoped personal and company API keys; revocation, rotation and expiry.
- [ ] Useful CRUD for customers/products, inputs/orders, forecast lifecycle,
      views/conversations, settings, connections and schedules.
- [ ] SFTP pull, Odoo 18/19, Google Sheets and generic HTTP ingestion.
- [ ] Slack, Teams Workflows, Telegram and eligible WhatsApp notifications.
- [ ] Unified English/Persian management UI using the existing design framework.
- [ ] Cross-company, role, key, ingestion, migration and end-to-end acceptance.
- [ ] Publish tested commits to the existing GitHub repository.

## Agreed access

Admin manages users/settings/connections and forecasting. Planner manages inputs
and drafts. Approver reviews/releases without editing inputs or calculating.
Viewer sees approved reports and read-only AI only. Own chats/views are personal.
Users issue keys within their current rights; admins issue restricted company keys.

## Safety and delivery

Keep current local evaluation usable while the new authenticated platform is built.
Do not enable authenticated multi-company mode until isolation is tested end to end.
Preserve existing immutable evidence and quantities. New snapshots are revisions,
not silent replacements. Credentials/client files/private outputs are never pushed.
Provider adapters are not called live-verified without a real ingestion/account test.

Commit each verified milestone on `codex/public-platform`. Never force-push.

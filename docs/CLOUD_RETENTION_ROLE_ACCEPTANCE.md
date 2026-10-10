# Private retention, roles and design acceptance — 10 October 2026

## Delivered

- Verified private cloud restore; three saved forecasts and 18 exports preserve
  the original values. See [rehearsal evidence](CLOUD_DISASTER_RECOVERY_REHEARSAL.md).
- Automatic ledger replication after checkpoint publication and job completion.
  Jobs lose session/API-key authority in the backup, without changing live grants.
  Replica failure is recorded privately, not misreported as failed forecast work
  or automatically replayed. It retries on the next publication/operator capture.
- Four-role permission matrix across the 169-route inventory in the compiled native
  identity worker: Admin, Planner, Approver and Viewer. Foreign-company access,
  non-admin user management, revoked grants and last-admin protection are tested.
  This uses disposable local native-runtime accounts, not new live users.

## Retention in the forecast backup bucket only

| Data | Retention |
| --- | --- |
| Latest ledger, `companies/<company>/recovery/latest.json` | No expiry |
| Published company archives and referenced forecast/input revisions | No expiry |
| Redundant ledger snapshots, `_ledger-history/` | 30 days |
| Incomplete multipart uploads | Existing 7-day rule unchanged |

The exact-prefix R2 rule was applied and read back from
`demandlab-forecast-backups`. No other bucket is modified. Keeping the latest copy
without expiry allows an idle company to recover after 30 days; preserving archives
keeps historical revision navigation usable. Native D1/SQLite recovery remains
separate. This is not an off-Cloudflare backup or a contractual recovery SLA.

The private initial capture was downloaded and SHA-256 verified:
`65e6714f76a92872f2704b4a0fbeb5b99d7d1cb9c927a20b7870ef1cfab6bb0e`.
It contains the committed revision, 20 revisions and 41 jobs, including 36 successes;
no restored session/API-key authority. Private payloads remain Git-ignored.
The temporary operator is disabled again, with no secrets, public URL or schedules.

## Design corrections

Sign-in, password reset and MFA now use shared `EntrySurface`, `Panel`, `Stack`,
fields, button sizes and Vrolen colour tokens. Removed dedicated login overrides;
People/API-key menus use the common `ActionMenu`. Sign-out and text actions now
use the shared text-button style. RTL account-header spacing uses logical margins.
Recovery-code mode now shows the correct heading.

The existing open-source Instrument Sans and Vazirmatn fonts are bundled by Vite,
not requested from an unavailable root path. No new UI dependency or inline style.
English/Persian sign-in and recovery/MFA forms were checked at desktop and 390px;
mobile panel width 358px, control buttons 40px, no horizontal overflow. Actual
People/API-access components and role dialog/menu were inspected in isolated
fixtures. After refresh, the existing owner session loaded successfully and the
published Workspace/People/API-access screens and People menu were checked live.
No live account was added, no permission was changed and MFA was not bypassed.

Verification: 274 frontend checks and production build pass; 46 cloud controller
checks, 27 authentication checks, six compiled native identity/storage/recovery
checks, 13 Python recovery checks and identity type checking pass. Four optional
auth-suite checks are skipped; native cloud checks are run separately.
The font asset fix adds a regression check; both cloud font requests return 200.
Private edge deployment: `91167740-1dc0-4e87-8d67-7b642036a544`.
Live identity policy is unchanged.

## Next acceptance chunk

Owner-only bilingual cloud sales journey: input import/correction, customers and
partial orders, factors, multiple models in one forecast, review, independent
approval and filtered exports. Include reload/error/mobile/keyboard paths using
fictional data. A true multi-person live approval pilot needs explicit permission
to add users; client accuracy needs real historical demand/order reconciliation.
No production/inventory scope, public access or automatic provider/AI consent.

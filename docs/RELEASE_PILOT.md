# Sales forecast pilot and operation — 7 October 2026

Ready within this checked local synthetic workflow, not whole-product/company
acceptance. No package, provider call, account, key or UI page was added.

## Delivered

- Restore pauses history/order/factor folder schedules, live sources, monthly
  forecasts and automatic history drafts. Completed forecasts, reviewed orders,
  views, source dates, permissions, quotas and cycle history remain unchanged.
  Restored active jobs need review/retry; original state is untouched.
- Stopped monthly calculations show needs-attention, not endless calculation.
  Missing updates/jobs do not break the schedule list or start another calculation.
- Customer/product validation uses set membership rather than scanning the entire
  directory for every order. Quantity rules are unchanged.
- A repeatable pilot covers real import/mapping/review, numerical models, durable
  jobs, partial orders, six demand exports and isolated backup/restore.
- README now describes the current sales-only product, replacing obsolete
  production/inventory and old integration instructions.
- Chart legend labels use dark theme text independently of the series fill;
  light-gray fulfilled/expected series remain legible without changing quantities.
  Both chart views retain the first and last month on narrow screens.

## Repeat the tests

From the project root, using the existing environment:

```sh
.venv/bin/python scripts/verify_release_pilot.py --destination outputs/new-volume-pilot
.venv/bin/python scripts/verify_release_pilot.py --destination outputs/new-persian-pilot --customers 3 --skus 2 --orders-per-series 24 --months 48 --horizon 10 --calendar jalali
```

Always choose a new output directory. Generated inputs, six exports, synthetic
archive and evidence remain there; the isolated calculation workspace is temporary.
Failed runs retain PILOT_INCOMPLETE. The script does not change client records,
make OpenAI/provider requests, or invoke application startup schedules. Importing
the app module initializes its existing local stores as usual.

Seed 7419 generates varying customer/product demand, trend, seasonal swings,
spring dips, intermittent zero demand, noise and recent shocks. These are artificial,
not observed Iranian effects or client demand. Orders cover no confirmed orders,
partial/above-forecast orders, current fulfillment, cancellations and unconfirmed
lines. Persian history uses true Persian monthly totals, not relabelled Gregorian
months.

Every weighted-average prediction is independently calculated from original sales:
`(oldest + 2 × middle + 3 × newest) / 6`. The normal engine still compares models.
Independent Decimal accounting checks every customer/SKU/month's orders and remaining
expectation. CSV/JSON and independently read-back Excel rows must match those values;
agreement between shared application helpers alone is not treated as proof.

## Measured results

| Run | History rows / series | Order lines | Forecast rows | Calculation | Demand matching | Peak memory |
| --- | --- | --- | --- | --- | --- | --- |
| Gregorian volume | 7,200 / 120; 60 months | 24,000 | 1,440; 12 months | 96.929 s | 0.447 s | 664.1 MiB |
| Persian months | 288 / 6; 48 months | 144 | 60; 10 months | 13.451 s | 0.003 s | 371.2 MiB |
| Small Gregorian | 144 / 4; 36 months | 48 | 24; 6 months | 4.544 s | See evidence | 364.3 MiB |

Evidence: outputs/release-pilot-volume/evidence.json,
outputs/release-pilot-persian/evidence.json and
outputs/release-pilot-small-fixed/evidence.json. These are single runs on this Mac,
with other tests running alongside some pilots: not speed guarantees, certified
capacity or multi-user benchmarks. Peak memory is the entire process high-water
mark, not only the model allocation. Synthetic correctness is not client accuracy.

All six exports reconcile. The volume run produces 82,688.167451 tonnes combined
open orders plus remaining expectation, or 43,318.4235 tonnes remaining expectation.
These artificial multi-customer annual totals are not the client's forecast.
Unknown/expired order books, a new customer without history and overdue open orders
block planning exports. No unknown quantities become zero.

Reopened job ledger and duplicate delivery do not re-execute the calculation.
Restore preserves result/export bytes, order snapshot and saved view; an active
restored job becomes interrupted while the original remains unchanged. This is
not an OS power-loss or live multi-process crash drill. Existing job tests separately
cover publication recovery.

A boundary test independently reconciles 10,000 customer/product relationships,
50,000 order lines and 10,000 demand rows. A 50,001st order line is rejected.
This uses a constructed baseline, not fitting 10,000 forecasting models.

An initial small pilot failed on a test-script Excel-reader typo. It stayed marked
incomplete; corrected small, volume and Persian runs passed. Existing dependency,
deprecation and database-cleanup warnings remain.

Final regression run: 606 backend checks / 111 interface checks pass, and frontend
build passes. Eight new backend checks cover complete schedule sanitization,
malformed recovery, stopped/missing monthly jobs, reproducible samples, Persian
boundaries, maximum order-book accounting and independent format read-back.
The existing large frontend bundle advisory remains; no UI asset-size fix is
claimed by this backend/operations delivery.

After restarting the local server, the existing synthetic demo opened correctly.
Customer filtering changed totals and clearing filters restored 4,100.31 tonnes.
Chart/trend views retained October 2026–March 2027 at 390px; legend labels remained
readable. Desktop layout was restored and the final browser error log was empty.
Screenshots: outputs/release-pilot-demo.png and outputs/release-pilot-demo-mobile.png.
This is a bounded results-page check, not whole-product UX acceptance.

## Local operation

1. Start ./scripts/start_mac.sh; keep the listener at 127.0.0.1:8010.
2. Home shows the next step. Explore a sample or review actual data in Data.
   Confirm units, calendar and whether quantities mean demand, shipments or invoices.
3. Run one representative dataset before scaling. Calculation happens in the
   background; taking minutes is not a frozen interface.
4. Review current orders, coverage and dates. Export remaining expectation if the
   receiving ERP already has those orders; otherwise use combined demand.
5. Leave monthly schedules paused unless reviewed inputs will arrive on time.
   Closing the server stops automation. Provider quotas/availability still apply.

Current validation bounds: 50 MiB upload, 1–24 forecast periods, 10,000 customer/
product relationships, 50,000 orders, 10,000 commitments. Customer/order table
imports also have 1,000,000-cell / 500-column limits. These are validation limits,
not performance promises. The launcher runs one forecast worker. No arbitrary
series capacity is inferred from this 120-series sample. No user data is automatically
deleted by this delivery.

## Backup and restore

Use scripts/workspace_backup.py and WORKSPACE_RECOVERY.md. Stop all app/worker
processes first; cooperative locks refuse live maintenance. Choose a new archive
outside data/runs. Restore only into a new staging directory. Check restore-report.json
and never launch a directory containing RESTORE_INCOMPLETE.

Archives contain confidential business records and are not encrypted. Keep them
on encrypted, access-controlled storage with an off-device copy and retention policy.
Preserve matching app source, built UI, Python and dependency versions separately;
requirement ranges are not a reproducible release. Environment/key files and external
folders are excluded; review integration configuration for embedded credentials
before off-device handling. No client backup was uploaded or workspace replaced here.

Before restarting restored state, configure secrets privately, review source paths,
sign in again, test one calculation/export, and explicitly confirm any schedule to
re-enable. Never run two installations on the same state.

## Company release gates — still open

- Do not expose local evaluation mode. Configure Authlib/OIDC, exact HTTPS origin,
  private listener, trusted proxy, members and secrets; see ACCESS_CONTROL.md.
  Test actual roles and independent demand-release approval before rollout.
- Confirm source rights, complete/fresh history, factory FX settlement basis and
  CPI permission. Missing history cannot be filled by AI. Future factor values
  remain explicit assumptions; unsupported accuracy claims stay suppressed.
- Measure benefit on longer actual history and future received actuals. Seven
  client actual months cannot establish annual seasonality or economic effects.
- Reconcile customer/SKU IDs, units, calendar, order handling and exports with the
  receiver. Draft/demo approval is not company approval; do not count ERP orders twice.
- Size the intended host and test concurrent users, worker restart and off-device
  recovery. This is one company workspace, not tenant isolation/high availability.

## Next major chunk

Full product acceptance across first-time setup → history → factors → current orders
→ assistant → filtered dashboard → reviewed planning exports. Exercise realistic
synthetic role, empty/error, reload and mobile states; fix workflow gaps together
without adding more settings/status cards. External rights/history, client accuracy
and receiving-system acceptance remain dependencies that dummy data cannot close.

The validation skill guided independent raw-input arithmetic, per-row checks,
separate export read-back and bounded capacity/accuracy claims.

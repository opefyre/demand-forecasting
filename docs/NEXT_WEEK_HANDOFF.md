# Next-week handoff — demo freeze, 21 September 2026

## Superseding scope decision — 22 September 2026

The user has narrowed the product to **sales/demand forecasting only**, including
current customer orders AND calculated demand for customers without orders. Use
the revised PRODUCT_REDESIGN.md, IMPLEMENTATION_CHECKLIST.md and DELIVERY_PLAN.md
as the authoritative requirements and next-work order. This was documentation
only; no implementation was authorized and development remains paused.

The older backlog below is preserved as history, not an instruction to complete
production, inventory, material, warehouse or purchasing features. Those are now
out of scope. Existing code/data and the demo remain unchanged. Do not reuse the
earlier full-scope completion estimates. New priorities are customer/order inputs,
per-customer order/forecast matching, sales-only views, safe demand handoff and
the permission-controlled AI assistant. The full customer list is essential;
customers with no current orders must not disappear from the forecast.

## Historical handoff follows

The user requested a demo of the current work and deferral of remaining work to
next week to preserve credits. Finish this checkpoint, then pause the broad goal.
Do not restart development, add optional models or schedule an automation without
the user's next instruction. The approved scope remains in PRODUCT_REDESIGN.md;
IMPLEMENTATION_CHECKLIST.md and UX_REBUILD.md retain the detailed open gates.

## Resume here

Start with DEMO_GUIDE.md and this note, not a fresh redesign or workbook audit.
Choose one bounded acceptance gap with the user. Existing work is a large dirty
working tree: preserve it, including generated assets, saved data and all unrelated
changes. No commit or cleanup was requested.

The final in-progress feature, delivery-file import, is implemented and browser
verified. It reuses the file preview, inventory validation, SQLite, React/Radix and
Pint foundations. CSV/TSV/JSON/Excel sources retain hashes, mapping and source-cell
evidence; the server reparses source bytes rather than trusting submitted rows.
Imported schedules are reviewed, immutable replacements, not additive versions.

## Remaining work, in priority order

1. **Workflow acceptance:** complete the full import → forecast → review → supply
   → export → later-actuals journey with real roles, empty/error/retry states,
   session expiry, keyboard and assistive technology. Receipt-import draft
   recovery and reusable mapping selection are still missing. Existing general
   demand-import recovery does not imply receipt-import recovery.
2. **Real input automation:** ERP/API/database ingestion, credentials management,
   freshness and point-in-time source provenance. Local-folder refresh already
   exists; connection checks alone are not integrations.
3. **Operational supply:** received/cancelled order reconciliation, warehouse
   flows, service/days-cover targets, replenishment policies and feasible
   production sequencing. Current receipt netting is period-end accounting;
   production completions are supplied inputs, not guaranteed feasible output.
4. **Forecast governance:** reviewed stockout/lost-sales corrections, unseen
   client holdout evaluation, closed-period locks, drift and retraining controls.
   Keep model selection separate from final accuracy evaluation.
5. **Iran factors:** approve FX market and rial/toman convention; handle inflation
   revision dates and precise weather coordinates where needed. War, outages and
   logistics disruptions need dated, reviewable assumptions, not invented causal
   coefficients or claims of automatically known future events.
6. **Remaining approved breadth:** hierarchical reconciliation, lifecycle/analogs,
   substitutions/promotions, Persian/RTL/Jalali workflows and a genuinely validated
   AI assistant. Existing deterministic helpers are not that assistant. Do not
   expand this breadth before core acceptance without an explicit priority choice.
7. **Deployment:** real OIDC/HTTPS and role acceptance, tenant isolation,
   multi-user/load tests, migrations/retention, encrypted off-device recovery and
   relocated deployment. Local authentication/recovery foundations are not
   production certification.
8. **Client pilot:** obtain missing inputs below, reconcile definitions with the
   client, and agree acceptance criteria before promising accuracy or readiness.

## Client inputs still needed

- Preferably 24–36+ months of actual history, with orders, returns and stockout
  definitions: observed sales and unconstrained demand are not interchangeable.
- Stock snapshot date/status meanings; product units and conversions; BOM,
  routing/capacity; outstanding purchase and production quantities/dates.
- Tehran is confirmed. Precise coordinates only if weather is relevant; approved
  external sources, FX market/currency conventions and service objectives.
- Deployment location, identity provider, users and reviewer responsibilities.

## Current evidence and stable demo records

- Full Python suite: **222 passed**, 21 September; JavaScript: **16 passed**;
  production frontend build passed. Python deprecation/resource warnings and
  frontend bundle-size warnings remain; they are not hidden test failures.
- Browser verified actual receipt file upload → mapping → explicit source-status
  meanings → review → save. Laptop 1280×850 and phone 390×844 affected views checked.
- Forecast `431fed798551`, dataset `cf685f57887d4ebeaa8fcb6d5ea3b324`:
  **Synthetic range verification - 6 months**, 12 items, 60 historical months.
  The 4.6% later-period error is synthetic-only evidence.
- Stock `65dddb08a3c64cf7a791c47d164b74ca`; receipt version
  `821ad3776d465f419c08378221ebcc93`, **Demo · imported deliveries**;
  source `b40561521cbf4d6cb99e69b3cdd56e16`.
  PKG-KRAFT-120 September: 50 + 200 − 183.7 = 66.3 tonnes displayed;
  50-tonne unconfirmed production is excluded. Original precision is retained.
- Published plan `e2379cd021`, **Synthetic workflow verification**, must remain
  immutable; draft child `51f34a7686`, **Synthetic revised plan**, demonstrates
  version comparison. Exports/supply use the shared effective-quantity resolver.
- Client diagnostic run `0ea4f6f71c21` is not the primary demo or evidence of
  independently validated client accuracy. Only seven actual months are present.
- Existing offline state archive `.recovery/state-20260921.zip` and restore drill
  `.recovery/drill-20260921` passed earlier. The archive predates the final receipt
  import and excludes source code; it is not a current complete project backup.
  It contains private data and is not encrypted. See WORKSPACE_RECOVERY.md.
- Original client workbooks in Downloads remain unchanged. No new external data
  transmission, deployment, commit or automatic next-week reminder was requested.

## Relevant implementation entry points

Receipt import: `app/receipt_imports.py`, `app/inventory.py`, receipt endpoints in
`app/main.py`, `frontend/src/receipt-import.jsx`, `tests/test_receipt_imports.py`.
Shared form accessibility: `frontend/src/form-field.mjs` and its component tests.
Recovery: `app/recovery.py`, `app/workspace_lock.py`,
`scripts/workspace_backup.py`, `tests/test_recovery.py`.

Local app is left running at http://127.0.0.1:8010/#forecast. If stopped, launch
`.venv/bin/python run.py` from the repo. Do not start a duplicate server. The
broad goal is paused, not complete; the demo does not reduce the approved scope.

# Assistant-guided orders and factor scenarios

Delivery: 3 October 2026. Sales/demand only; not whole-product acceptance.

## What is built

- Ask to add or update customer orders. The assistant prepares an **Open order upload** button bound to the exact forecast and selected order version. Clicking opens the same file/mapping/calendar/coverage/demand review used by Forecast, not a second import system.
- Original orders are loaded for updates; changes preserve other lines unless the user explicitly selects a full replacement. No upload or order save is performed by the model. Cancelling returns to chat. Saving an explicitly reviewed version opens the demand dashboard.
- Ask about connected factors. The assistant can list retained live/public snapshots and exact factor-aware methods, check an explicit scenario, and prepare a review card for calculation. It cannot revive manually imported factors through these new tools.
- Exact customer/SKU scope, source locations/units, earlier-observation timing, monthly assumptions and warnings are visible before a human confirms. Missing history blocks a proposal; future values are not invented. Other customer/product combinations keep the baseline.
- Confirmation reuses factor alignment, immutable input versions and the existing forecast queue. The saved scenario owns its method. Repeated confirmation reuses the same input/job identity.
- Orders are **not** automatically copied to a factor forecast. Existing order-scenario/reuse tools require a separate reviewed handoff; no cross-customer consumption or automatic publication.
- Downloaded historical factors remain what-if evidence, never proof of improved accuracy. Source calendar and publication-time limitations remain explicit.

## Confirmed facts, not assumptions

Existing Python Agents SDK, task-specific OpenAI models, consent/call limits, retained inputs, local calculations, React/Radix/Phosphor and reviewed import services are reused. No new forecasting formula, second wizard, shell/SQL tool, production or inventory capability was added.

The first live synthetic order request reached the new tool and its button opened the correct review. It did not read a new file or save orders. The model initially described a prepared button as an opened workflow; tool state and instructions now explicitly distinguish those stages. This wording correction is covered by the tool contract, not a claimed live re-test of the first request.

Browser review found and fixed an undefined calendar variable, missing required-note guidance, and the omission of fulfilled demand from the preview table. The review now exposes calculated estimate, open orders, already fulfilled, still expected and total demand separately. Empty review notes cannot progress.

A second live synthetic request inspected connected Aluminum data, checked coverage and prepared the requested factor comparison. No calculation was submitted. The final review was checked at 1280px and 390px: no page-width overflow; calculation stays disabled until review is checked. Long explanations are collapsed behind “Why this scenario?” while the full response remains available. Desktop and mobile screenshots are saved under `outputs/assistant-guided-scenario*.jpg`.

## Verification

- Full backend suite: 510 tests passed; final targeted assistant tests also passed after final safeguards.
- Frontend: 84 tests passed; production build passed. Existing dependency/resource and bundle-size warnings remain.
- Nine new backend tests invoke the actual SDK function tools and local services, checking exact source/scope selection, strict dated assumptions, missing observations, stale/corrupt evidence, user ownership, expiry, confirmation and retry identities.
- A temporary-workspace scenario runs the actual forecast engine, not AI-generated quantities; unselected customer predictions remain identical to the baseline.
- Six new rendered-card tests cover approval gating, Persian month labels, source assumptions, queued/expired outcomes, viewer restrictions and collapsed explanations. Required-note readiness has a separate regression test.
- Automated tests make no paid provider calls. Two live assistant smoke requests used explicitly labelled synthetic data; no client sales were transmitted or changed. The original synthetic orders and all six exports still reconcile.

## Still open

This is not automatic order-column matching or AI cell repair. The user still chooses files and reviews uncertain meanings, dates, units and coverage. Larger/ambiguous files, wider language coverage and business validation remain acceptance work. IMF monthly CPI permission/full capture and adequate client history remain external gates.

## Next major chunk

AI-assisted input repair and repeat-import review: bounded, explicit corrections in a new version; clear before/after evidence; preserve originals and order references; detect stale/changed inputs and route a monthly refresh through forecast, order coverage and exports. Reuse existing import and queue services. Do not invent missing demand or silently repair quantities. Real ERP connectivity remains deferred.

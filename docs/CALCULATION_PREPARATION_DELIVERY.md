# Forecast preparation reuse — 10 October 2026

This finishes a bounded calculation-speed slice, not the whole product.

## Change and safeguards

Historical lag, rolling and smoothing values are now prepared once per observed
origin and copied into each horizon row. Future calendar/driver values, step and
time index are still applied separately. Future prediction uses the same observed
origin across steps; it does not feed predictions back into later inputs.

Full-history fitting reuses each distinct factor-feature frame across models.
All reuse is local to the function call: no company, request, series or historical
validation window shares a persistent cache. Copies prevent driver-name collisions
from mutating another horizon's values. Existing NumPy, pandas, scikit-learn and
StatsForecast mathematics remain unchanged.

No candidate, historical validation window, method comparison, model failure,
per-customer/product selection, driver explanation or planning range was removed.
Pruning unused future models was rejected because those results are also exposed
as method comparisons. Model selection, order reconciliation and existing evidence
restrictions remain unchanged.

## Measured host comparison

`scripts/benchmark_automatic.py --reference-ref 3492520` reads only the four
preparation functions from the explicit local Git commit, runs both versions with
the same current libraries and profiling, and compares their complete results.
Temporary fictional inputs/results are removed on exit; no saved app data,
provider refresh, AI call or secret is used.

804 fictional Tehran observations, 18 customer/product series, six future months,
17 catalog candidates including unavailable monthly MSTL:

| Work | Reference seconds | Updated seconds |
| --- | ---: | ---: |
| Complete Automatic calculation | 24.187 | 22.221 |
| Training-feature preparation | 2.9115 | 1.8360 |

Complete output is exactly equal except generated run IDs and measured model
timings; forecast CSV bytes are exactly equal. This covers quantities, all method
curves, weights, selection/confirmation evidence, ranges and failures. The fixture
has no uploaded external factors; separate tests cover factor variants and exact
driver explanations.

This is one sequential profiled host comparison (reference first), not a cloud
latency guarantee or statistical speed claim. Statistical searches/fitting remain
the largest cost; startup, transport and company projection are not measured here.

## Interface and design check

No interface source, appearance rules, inline styling, page, banner or control was
added. Existing translated calculation progress and navigation locks are retained.
The private forecast page and new-forecast dialog were opened without saving.

Desktop dialog: 960×680, 24px padding, 16px radius. Persian mobile: RTL, 358×680,
20px padding, 390px page/viewport, no page overflow. Shared controls and five-step
flow remain; backdrop stays behind the dialog. The title's repeated accessibility
description is visually hidden (1×1), not a duplicate visible heading. One inline
`pointer-events` attribute is produced by the picker library, not authored styles.
Existing English saved names are not rewritten. Language/viewport restored.

Notification destinations/form were also opened without saving or sending.
The form uses the same 960×680 dialog, 24px padding, 16px radius, 44px controls
and 16px input text. Its 568px body scrolls internally for 851px of content.
No webhook, destination, authorization or account setting was changed.

These checks do not establish that every legacy page follows the framework.
The broader design migration remains open, as recorded in UI_FRAMEWORK.md.

## Verification and delivery

- Host: 102 engine/factor/calendar/range/input/company-cloud tests pass, including
  five new preparation checks. The five were rerun after extending formula checks.
- Interface: all 288 tests pass; no interface bundle changed.
- Exact Linux image: seven checks pass offline under 0.25 CPU / 1 GiB, including
  real grouped methods/partial orders and live-factor what-if exports. 209.081
  seconds under x86 emulation; its jemalloc warning is expected.
- Dedicated engine published as `3d627b21-5f74-4ac4-9350-c3883b7f3a50`, image
  `sha256:02c515fffe74ddb2ea27d0e0b0af96f94f991fd690fddf07d64d7c55ba8906c6`.
  This is the same manifest tested offline. Edge/identity/storage configuration,
  credentials, domain, owner-only access and five-minute sleep policy unchanged.
- Local demo declared health route returns 200; anonymous cloud customer API
  returns 401. `/health` is not the local health route and returns 404 normally.
- Temporary forecast registry login removed; dedicated build VM confirmed stopped
  and default Docker context unchanged. Private post-deployment reload opens the
  existing grouped forecast: 4,070.56 tonnes, with the original order breakdown
  and what-if warning intact. No new cloud calculation/data mutation was requested.
  This verifies restored reads, not a cloud end-to-end speed comparison.
- Existing dependency, emulation, frontend test socket/Radix and bundle warnings
  remain. No new interface build was needed; its sources/assets are unchanged.

## Next substantial task

Complete the corrected-input → revised grouped forecast → independent approval →
approved export journey, including Persian/mobile error recovery, reload and
revision navigation. Repair any design/workflow gaps through shared components,
not page overrides. Preserve original records and demonstrate orders from some
customers alongside calculated demand for customers without orders.
Use isolated company/role fixtures for independent approval while live access is
owner-only. Do not invite another account or widen live access for a test.

Still open: raw capture-receipt inspection, broader legacy-screen consistency,
real-client accuracy/data definitions, receiving MRP acceptance, multi-person pilot
and provider/AI eligibility. None is represented as finished by synthetic tests.

# Factor review latency and input navigation — 10 October 2026

Bounded performance/workflow delivery, not whole-product completion.

## Measured change

`scripts/benchmark_factor_review.py` creates disposable fictional Tehran history:
804 observations, 18 customer/product series, six future months and one dated
fictional monthly factor. No app records, provider, AI or secret are used. Package
and calendar imports are warmed before cProfile measures each operation.

| Operation | Before (seconds) | After (seconds) | Context preparations before → after |
| --- | ---: | ---: | ---: |
| Factor choices | 0.3961 | 0.3842 | 1 → 1 |
| Preview | 1.1271 | 0.8811 | 2 → 1 |
| Save | 2.6027 | 1.1326 | 3 → 1 |

These are single profiled host runs, not a statistical speed guarantee or remote
Cloudflare end-to-end measurements. Cold starts, checkpoint transfer, company
projection rebuilding and network/queue waits are outside these timings.

Preview/save now prepare their context once per request. Saving no longer performs
an extra preview: the existing save operation already recomputes alignment and
checks the exact approval token. Source digests, publication/capture gates, latest
source readiness, assumptions and idempotent saves remain checked. No cache spans
requests or companies. No forecasting formula, model selection, orders or export
calculation changed.

New regressions compare the full preview/alignment record, count one context
preparation, reject a source becoming stale after preview and reject edited source
bytes. Existing review-token/idempotency, live what-if, order reconciliation,
company isolation and cold-checkpoint tests also run.

## Design / workflow

Opening a saved input previously left its Review data button unchanged while
source reads were pending. The chosen row now shows the existing translated
Loading… label with `aria-busy`; competing review/import/menu/tab actions are
disabled. A synchronous guard prevents duplicate opening requests and always
releases after success/failure. This is read handling, not an automatic write retry.

Uses the existing shared Button, ResourceMenu and PageTabs, with no added CSS,
inline styles, new banner or new page. The original table/toolbar structure,
brand colour, spacing, responsive behavior and motion tokens are retained.

The private cloud's original input can be opened for review and returned from
without saving. The revisions dialog lists original/derived inputs and source
metadata through the existing permission-checked routes. Desktop measurement:
960×680, 24px padding, 16px radius, internal vertical scrolling and zero authored
inline styles. This read-only walkthrough is not acceptance of a full corrected
input → new forecast → independent approval → receiver export journey.

Persian mobile versions: 358×680 within 390×844, x16–374, RTL, internal scrolling,
page width 390. The viewport/language were restored. Original inputs and forecasts
were not changed. Live cloud review displayed Loading… on the selected input and
disabled competing review/import/menu controls; a dropped prop in the legacy tab
wrapper was caught during this walkthrough and corrected in the shared adapter.

## Verification

- Host: 65 factor-input/live-alignment/cloud API/cloud workflow checks pass.
- Company factor-link routes: seven checks pass.
- Interface: 288 checks and production build pass.
- Exact Linux image: four checks pass offline, under 0.25 CPU / 1 GiB, including
  grouped-model/partial-order cold checkpoints; 169.998 seconds under emulation.
- Local demo health: 200; anonymous cloud company API: 401.
- Existing dependency, bundle-size and database-resource warnings remain.
- Dedicated deployment: edge `7ab7ae6d-bf53-43fa-8d2b-ba9e334fed86`; private
  engine `422c453a-0284-477d-8962-fd5b4215435f`, image
  `sha256:5c78d299913a910e8ade958f3d95bb01b8aa6b3fd0346ec08f8b93ac81fd3a73`.
  Closed owner-only access and five-minute inactivity shutdown are retained.
  Temporary registry login was removed after upload; build VM stopped afterward.
- Numerical formulas, identity, storage configuration, credentials, domain and
  other services remain unchanged. No provider refresh or OpenAI call was made.

## Calculation profiling / next substantial work

The unchanged Automatic benchmark on the same 804-row history took 28.95 seconds
on the host under profiling: historical model tests accounted for 18.06 seconds,
full-history model fitting/prediction for 8.42 seconds. These are not cloud timings.
The engine currently fits the full catalog again for future prediction even when
only some methods carry weights. Reducing that work requires equivalence tests
for per-series choices, factor explanations and failure evidence; it was **not**
silently changed in this delivery.

Next: reduce verified calculation/projection work with unchanged results, then
complete corrected-input/revision and grouped-factor mobile/error/reload journeys.
Raw cloud capture receipt inspection, other provider/AI eligibility, client
accuracy and an explicitly authorised multi-person pilot remain separate gates.

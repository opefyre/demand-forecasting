# Live-source preparation — 7 October 2026

## Delivered

In a factor scenario, **Find relevant live factors** asks about currency exposure,
overseas supply, the Hormuz route and relevant materials. It checks the existing
Iran FX, monthly Iran CPI, global supply-pressure, shipping and commodity adapters.
It does not infer exposure from customer names or product codes, search arbitrary
websites, or claim that a suggested source improves accuracy.

Each suggestion shows usable historical coverage, missing future observations and
source limitations. Old/overdue data, incomplete history, corrupted retained evidence
and missing commercial permission cannot be prepared. A recent download does not
renew old observations. Annual inflation/industry data remain background only.

Selected sources enter the existing factor-review workflow. Future assumptions stay
blank, the proposed two-month timing needs review, and no timing/calendar approval
is preselected. Retrospective live history remains a fixed-method what-if comparison,
without historical accuracy or range claims. Eligible archived sources can use the
existing automatic factor test, still subject to its historical evidence checks.

Source/exposure evidence is rechecked before preview and save. The new scenario
records the declared exposure and selected versions. Original history, orders and
forecasts are unchanged. Profiles are saved with that scenario, not yet as shared
customer/product defaults. Recommendation checks are read-only; refresh remains
in Data → Factors. No new dependency, credential or paid AI call was needed.

The centered dialog has clearer checkbox spacing, fewer empty gaps, a title/close
control retained while scrolling, collapsed source explanations and a direct handoff
to connections. The manual source picker remains available. A brief false
"add orders" screen while saved demand was loading was also removed.

## Verification

- 556 backend tests passed, including 11 preparation tests. Existing dependency,
  SQLite-resource and frontend bundle-size warnings remain.
- 98 interface tests and production build passed.
- Isolated synthetic provider/history fixtures test relevance rules, strict inputs,
  missing/stale/corrupt data, changed evidence, permissions and canonical method names.
- A real existing-engine test prepares a source, saves reviewed assumptions,
  calculates two customer/product series over two months, applies partial orders
  and parses all six CSV/Excel/JSON planning exports. Four rows per export;
  independent order-consumption checks and totals reconcile. No OpenAI call.
- Synthetic captures simulate a source adapter; they do not prove a live endpoint
  works or that client forecasts will be accurate.
- Browser: source selection/recheck, material picker, unavailable-source blocks,
  manual fallback and connections handoff verified. 390px/320px dialogs have no
  horizontal overflow; title remains visible while scrolling. Desktop checked too.
- The retained live-data check correctly blocks all five current suggestions:
  monthly CPI permission is missing; FX/supply/shipping/commodity captures need
  refresh. A public commodity refresh attempt returned the existing cooldown;
  no limit was bypassed and old data were retained. This is not a live-refresh pass.

Evidence: `outputs/source-preparation-evidence.json`, source-preparation desktop,
mobile and 320px screenshots; `tests/test_factor_preparation.py` and
`frontend/src/factor-preparation.test.mjs`. Recheck retained sources without fetching:

```
.venv/bin/python scripts/verify_source_preparation.py --run-id 27bafe7c16d5 --output outputs/source-preparation-evidence.json
```

## Next major build

Reusable customer/product exposure profiles and assistant-guided monthly source
preparation: reuse declared relevance, propose exact sources and future assumptions,
then open the same review/calculation/order/export services. No silent approval or
AI-generated forecast quantities. Include ambiguous requests and failure recovery.

Whole-product acceptance still needs permitted/live source history, sufficient client
actuals and independent benefit testing, wider assistant/UI acceptance and deployment
checks. These cannot be marked complete using synthetic tests alone.

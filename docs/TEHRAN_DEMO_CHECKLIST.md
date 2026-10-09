# Tehran sales demo

Scope: fictional packaging-paper sales, not production or inventory planning.
Live market observations remain authentic; future conditions are assumptions.

- [x] Checksummed backup of previous application state; originals archived, keys retained.
- [x] Five customers, four products, 18 customer/product relationships.
- [x] 48 months of established history; 18 months for the new customer.
- [x] Gregorian and Persian-month inputs with correct calendar boundaries.
- [x] Confirmed, partial, fulfilled, cancelled, tentative and absent customer orders.
- [x] Four confirmed full-month customer/product commitments in a separate contract scenario.
- [x] Inflation, exchange-rate, price, promotion, payment, delay and disruption assumptions.
- [x] Refresh configured live feeds without bypassing permission or cooldown rules.
- [x] Feed actual live Brent prices and NY Fed supply pressure into model inputs.
- [x] Fresh Servix reference quote used as an explicit future hold in a what-if model.
- [x] Group several methods under each named forecast, rather than duplicate names.
- [x] Currency/freight stress scenario with frozen order reuse.
- [x] Customer, product, month, table, chart, pivot and order-coverage views.
- [x] Forecast ranges, method tests, factor relevance and model workbooks where supported.
- [x] Combined demand and remaining forecast exports in CSV, JSON and Excel.
- [x] Approval/handoff examples, explicitly local demo sign-off only.
- [x] Closed-period evaluation using a retrospective forecast, never fake prospective accuracy.
- [x] Connected local business-input pipeline and live source details populated.
- [x] Three genuine assistant conversations, including Persian; monthly quantities independently verified.
- [x] Independently reconcile orders, customer/product/month totals and all 96 demand exports.
- [x] Test missing/expired input safeguards outside the clean default demo.
- [x] Browser-check populated pages, filters, method comparisons and Persian display.
- [x] Unified forecast wizard loads saved customer orders and discards obsolete source drafts.

Verification: 679 backend tests pass; 31 targeted assistant tests pass after the final
quantity clarification; 238 frontend tests pass and the frontend build succeeds.
All 16 model workbooks open with the expected row counts.
The separate retrospective example compares 54 closed customer/product/month results.

The demo caught and fixed issues with explicit method selection for short-history
customers, and assistant totals/interpretation when detailed rows exceed the response limit.
The assistant now receives complete monthly totals and explicit net-order definitions.
The wizard also rejects saved drafts whose input data no longer exists.

Limitations are deliberately visible in the evidence, not filled with fake readings:
monthly Iranian CPI still needs source reuse permission; future inflation and disruption
are assumptions. Annual Iran data, Hormuz traffic and NASA Tehran weather are context,
not unsupported demand multipliers. Portfolio uncertainty is withheld where the new
customer lacks joint historical errors. Synthetic tests do not establish client accuracy.

Evidence: `outputs/tehran-sales-demo/manifest.json`. Reproduce with
`scripts/prepare_tehran_demo.py`; reset is one-shot and requires a stopped server.
Original customer workbooks and secrets are never removed.

Demo walkthrough: `docs/TEHRAN_DEMO.md`.

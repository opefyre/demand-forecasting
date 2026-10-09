# Persian/English interface — 7 October 2026

Delivered locally as a bounded interface slice, not whole-product acceptance.
Sales/demand remains the only product scope. No forecast engine, source data,
order snapshot, export contract, external feed or AI credential changed.

## Delivered

- Compact language switch in the existing header, available to every signed-in
  role; the browser remembers the preference. Also available in Settings.
- Open-source i18next 26.4.2 and react-i18next 17.0.16, not a custom translation
  engine. Uses the existing locally bundled Vazirmatn font for Persian.
- Right-to-left navigation, page layout, controls, tables and centered dialogs.
  Time-series charts intentionally keep increasing dates from left to right.
- Authored Persian labels for Home, primary navigation, history import/review,
  customer management, order review, demand filters/views and draft exports.
  Twenty Persian help topics explain inputs, calendars, order consumption,
  mathematical methods, factors, assistant, refresh, review and exports.
- Calendar choice stays independent from language. Real Gregorian/Persian month
  contracts remain unchanged. Numeric/date inputs keep their original conventions.
- Customer names, SKU codes, original column names, notes, filenames, saved view
  names and external source content are not translated. Exact matching and exports
  cannot depend on interface language. Machine order-status tokens stay English.

## Verification

- 121 interface checks pass, including seven new localization checks; build passes.
- Tests verify explicit preferences, blocked preference storage, document direction,
  interpolation, nonempty/unique catalogue entries and authored Persian help.
- Identical bytes for demand, monthly and coverage CSVs before/after switching.
  Customer name `Home` and SKU `0001` remain unchanged even when UI words translate.
  Both calendar labels and original row values are identical across languages.
- Mechanical migration only touches known authored labels, not routes, event
  payloads, input values, source identifiers or customer data; idempotence tested.
- Existing demo run `13dce80f9573`, orders
  `38dd9f7b9940d5e393fe5dc924b3465d`, reused without a new calculation or save.
  Persian and English show 93 open-order tonnes, 1,199.06 expected tonnes and
  1,304.06 total tonnes. Selecting Demo customer 001 preserves the selection and
  monthly table during a language switch: 90 / 461.08 / 563.08 tonnes.
- Draft Excel/CSV/JSON links use exactly the same snapshot and mode in both
  languages. Language does not alter the receiving-system order choice.
- Persian preference survives reload. Desktop dashboard/right-hand navigation,
  Persian help/mobile menu, 390px export and 320px customer dialog/import checked.
  Export bounds are x=15..375 at 390px; customer dialog x=15..305 at 320px.
  No page-level horizontal overflow in those checked states. Wide tables remain
  intentionally scrollable. Unsaved import/customer forms cancelled; viewport reset.
- npm audit reports zero known vulnerabilities after a scoped compatible patch to
  the existing source-map-js dependency. This is not a security certification.
  The existing large-bundle build warning remains.

The previous backend regression evidence remains in SALES_JOURNEY_ACCEPTANCE.md;
backend tests were not rerun for this display-only slice. No paid AI/provider call,
secret access, client-data replacement or new navigation destination.

Screenshots: `screenshots/persian-dashboard.png`,
`screenshots/persian-export-desktop.png`, `screenshots/persian-export-mobile.png`,
`screenshots/persian-customer-mobile.png`.

## Remaining / next substantial chunk

This is **not complete Persian coverage**. Finish advanced live-source/factor,
scenario/method-detail, assistant, saved-review/admin and authentication screens;
translate structured errors with explicit codes rather than translating arbitrary
provider or customer strings. Some dynamic metadata still uses English.

Then run the complete bilingual first-use-to-export journey across administrator,
planner and reader roles, keyboard-only use, failed inputs, recovery and narrow
screens. Keep the same sales-only workflow and repair real obstacles found there.

Client accuracy, permitted live-source history/rights, wider live AI acceptance,
receiving-system reconciliation and secure company deployment remain open gates.
Synthetic tests cannot establish Tehran demand accuracy or close these gates.

Implementation reference: [react-i18next documentation](https://react.i18next.com/latest/usetranslation-hook)
and [i18next interpolation](https://www.i18next.com/translation-function/interpolation).

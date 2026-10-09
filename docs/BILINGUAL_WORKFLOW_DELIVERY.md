# Persian/English advanced workflow delivery

7 October 2026. Bounded interface delivery, not whole-product acceptance.

## Delivered

- Persian assistant input, source picker, sharing consent and reviewed action
  cards. Original chat replies, customer names, identifiers and model names remain
  unchanged. Switching languages preserves an unsent message.
- Persian factor preparation, profile/exposure selection, testing, scenario and
  batch review controls. Existing confirmation and role restrictions remain.
- Persian live-source captions, status, permission and retry controls, saved-review
  navigation, authentication labels and AI settings labels.
- A shared, tested source-status presentation helper. A recent successful check
  does not hide old observations; cooldown and missing permission remain visible.
- Safer label migration: conditional routes, values and CSS classes are not
  translated; inline spacing and arbitrary business text are preserved.
- Reused existing i18next/react-i18next, components, models and provider services.
  No new package, numerical method, backend change or credential change.

## Verification performed this delivery

- 129 interface tests pass; frontend build passes. Existing large-bundle warning
  remains a performance follow-up, not a failed build.
- 39 focused backend tests pass: security, AI workspace, normal sales import
  journey and reviewed demand releases. These are isolated tests with mocked AI;
  this delivery did not rerun the entire backend suite.
- Actual rendered component tests verify Persian labels with exact source/model
  identifiers, reader-disabled mutations, expired proposals and explicit scenario
  confirmation. Catalogue tests reject duplicate keys and unsafe label migration.
- Source-status tests cover freshness, exact cooldown boundary, permissions and
  unchanged input records, including unrecognized source names.
- Browser: Persian desktop assistant, live factors and saved-review empty state;
  390px assistant and centered source details; no horizontal page overflow in
  these mobile views. Escape closes source details and returns focus to Details.
- Original saved synthetic forecast still displays 93 tonnes open orders,
  1,199.06 tonnes unbooked demand and 1,304.06 tonnes total including fulfilled
  quantities, for October 2026–July 2027. No new client calculation or record write.
- Browser console returned no errors after the latest build. No message submitted
  to OpenAI, no deliberate external-source refresh and no source permission changed.

Screenshots: `screenshots/persian-assistant-workflow.png`,
`screenshots/persian-live-factors.png`,
`screenshots/persian-live-factor-mobile.png`.

## Still open

- Full language coverage: deep administrator forms, weather setup, order-reuse/
  comparison and some assumptions/scenario details. Structured backend errors and
  provider-authored descriptions are not fully localized. Do not broadly translate
  arbitrary error text, source records or customer data to conceal this gap.
- Complete bilingual first-use-to-export acceptance across permissions, missing/
  invalid data, stale sources, calculation failures, reloads and keyboard use.
- Real-client accuracy requires representative history and actual outcomes.
  Synthetic testing proves specified behavior, not real market accuracy.
- Provider permission/history, wider live AI acceptance, receiving-system acceptance,
  intended-host load, off-device recovery and secure deployment remain separate gates.

## Next substantial chunk

Finish guided exception handling across the sales journey: show exactly what needs
attention, where to fix it and how to resume, for incomplete history, problematic
orders, stale/unavailable factors and failed calculations. Finish remaining user-facing
language within that workflow and test a complete import → orders/factors → forecast
→ filtered review → export journey for planner and reader roles in both languages.
Use isolated realistic synthetic cases, existing services and a single maintained
acceptance checklist. No production/inventory expansion or new navigation clutter.

# Bilingual management and connected-input acceptance — 11 October 2026

## Delivered

- Notifications and sales connections use the shared saved-data recovery control.
  Recovery only reads saved state; it never repeats a send, save or import.
- Failed first reads no longer claim that notifications, connections, people or
  API keys are empty. Creation stays disabled until the required data loads.
- Notification and connection dialogs cannot dismiss during pending operations.
  Connected-input mapping, dates and confirmation are locked during review/save.
- Notification message-language options are translated in Persian.
- Report-only users no longer see the unavailable Customers & orders shortcut.
  All changes reuse global components; no CSS, inline styles or dependencies added.

## Verification

335 interface tests, 46 connected-input/notification backend tests, 64 cloud
controller/edge tests and the production build pass. These are bounded suites,
not a fresh run of every backend test. Existing bundle-size and dependency
directive warnings remain; tests also log the sandboxed development-socket warning.

Browser checks used a disposable, loopback-only two-company fixture with real
application stores and mocked identity, connector transport, AI and notification
sender. No real keys, invitations, external notifications or paid AI calls.

- Injected one failed saved-data GET each for notifications, connections and
  people. Shared recovery restores the lists, with no false empty-state message.
  Notification delivery history remains exactly three entries after recovery.
- Four connected customers and four orders are reviewed and saved. Product codes,
  source/valid-until dates, confirmed/unconfirmed status and quantities survive;
  View orders opens the related dataset, not an unrelated first input.
- Uncertain notification resend requires both send consent and duplicate-risk
  acknowledgement. The synthetic sender adds a linked receipt only after both.
- Keyboard menus open edit dialogs, focus the first field and return focus to the
  original menu on Escape. On an actual 390 × 844 browser viewport, the Persian
  notification dialog is 358 × 680; its body scrolls internally with no page
  horizontal overflow. This verifies that dialog, not every mobile workflow.
- Persian chat rename, archive, restore and two-sided alignment pass. The user
  stays on the right and the assistant on the left. Stored/mock English content
  is not evidence of live AI translation quality.
- Switching to the second company as Viewer removes first-company chats and
  administrator navigation; Home exposes View forecasts, not the Data shortcut.

## Remaining acceptance

The shared interface is published to the existing private forecast edge, version
`c1e41a1c-45db-4150-aab2-1810574cc313`. Owner-only/closed access settings remain.
Anonymous company API access returns 401; the sign-in shell returns 200. No signed-
in cloud browser tab was available for this run, so the above interactive checks
are local acceptance, not a fresh signed-in cloud walkthrough. Engine, identity,
storage configuration and other services were not deployed or changed.

Finish bilingual history correction → revised grouped forecast → independent
approval → filtered export, including failure/reload and narrow-screen keyboard
paths. Larger-history timing, real connector receivers, live AI eligibility and
client accuracy remain separate gates. No whole-app acceptance claim.

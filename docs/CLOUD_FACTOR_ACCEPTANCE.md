# Private factor connection and design checkpoint — 10 October 2026

This is a partial acceptance checkpoint, not completion of live cloud factors.
Only the dedicated forecast edge/controller were deployed. Identity, storage,
other services, original sales/orders and existing numerical forecasts were not
changed. The local demo entry page still returns 200.

## Delivered

- The wizard factor step and shared selected-factor editor use global Stack,
  Grid, Panel/PanelHeader, FieldGroup, DefinitionList, Actions and Disclosure.
  Five obsolete wizard CSS rules and five selected-factor CSS rules were removed.
  There are no new inline styles or page-specific appearance rules.
- Shared panel headings now have a semantic minimum-width token: on narrow
  screens their actions wrap below the title rather than squeezing the words.
  This applies to all users of the shared panel, not just factors.
- Connect sends the first refresh before enabling the daily schedule. Previously,
  enabling first could install an immediately-due alarm and race the manual
  refresh against the current company revision. Failed requests are not replayed.
- Private administrator diagnostics keep only controlled failure codes, HTTP
  status, format category and timestamp. No URLs, bodies, credentials, exception
  messages or headers are retained. The existing owner/fresh-MFA gates remain.
- A fixed-host DNS probe uses only api.worldbank.org; it does not read company
  inputs, fetch a provider API, spend a provider quota, wake the container or
  write company state. Other queries and non-admin probes are denied.
- Default Worker fetch is wrapped rather than invoked with the broker as its
  receiver. A regression checks receiver semantics. This change alone did not
  resolve the observed cloud DNS-request failure.

## Verified versus unresolved

Actual World Bank commodity and NY Fed parsers worked from the host: 15 commodity
series and one supply-pressure series, both through September 2026. This proves
the upstream endpoints/parsers worked from that location, not the cloud path.

Actual cloud refreshes for commodities, supply pressure, Hormuz and annual Iran
context failed. The latest controlled failure was `dns_request`, recorded at
18:01:53 UTC before provider I/O. Its precise runtime exception is deliberately
not retained. Do not describe this as exhausted provider quota or a proven timeout.
Existing cooldowns were respected; none were reset, forced or bypassed.
No successful cloud monthly factor snapshot or factor-aware forecast is claimed.
The fixed DNS probe's browser navigation was blocked by Chrome
(`ERR_BLOCKED_BY_CLIENT`); no browser warning/protection was bypassed.

World Bank commodities and NY Fed history are monthly global reference data,
not Tehran measurements. Annual Iran series remain background context, not
invented monthly values. Servix cloud credential setup and IMF commercial-use
permission remain separate gates. No local key was copied or permission invented.
Cloud AI remains disabled pending its existing provider-eligibility gate.

## UI acceptance

The disposable loopback fixture now optionally supplies synthetic factor snapshots
(`--factors`). It contains two isolated companies, four customers, orders and real
API/model workflows; it never seeds production or contacts a provider.

At 1512×736, the factor editor uses shared title/actions, metadata and forms.
At 390×844, the dialog remains 358×680 with internal scrolling and page width 390;
the selected-factor title stays on one line and actions wrap below it. Viewport
overrides were reset. Persian wizard labels and navigation were inspected; this
is not a claim that every external dataset name or every app screen is translated.
The incomplete synthetic factor history correctly blocked confirmation and
continuing until missing observations are resolved; no historical values were
invented. A visual fixture check is not live cloud factor acceptance.

## Checks and deployment

- 280 interface tests pass; production build passes.
- 51 controller/edge/security tests pass.
- 53 focused backend tests pass.
- New successful monthly download/restore regression passes in the exact deployed
  offline Linux image, with no network and only synthetic test data mounted.
- Existing build warnings (large bundle/Radix directives) and dependency warnings
  remain; they are not hidden or claimed resolved.
- Dedicated forecast build VM was stopped after the offline check; the disposable
  UI fixture is stopped after browser checks. No registry credential was created.
- Edge: `053dd22c-a0e2-4039-a024-42d026dac51c`.
- Controller: `354937a6-55e2-44d5-91a9-8c844fb1b406`.
- Numerical image unchanged:
  `sha256:bb84d6cc0a7d2ee07edaaff2390daa1c9fc844beb715f009a6341990d176d45f`.
- Offline container, five-minute idle shutdown, no warm pool and closed access
  remain unchanged. No client data, AI, email or notification was sent externally.

## Next substantial task

Resolve the native cloud DNS-request failure without weakening public-address,
route, permission, revision or offline-container guards. Verify the public monthly
feeds with actual cloud receipts after cooldown, then complete one reviewed
factor-aware grouped forecast with orders, customer/product/month filters,
revision changes and matching exports. Continue the branded desktop/mobile/error
walkthrough. Real client accuracy and authorised multi-person acceptance remain
separate; do not open public access automatically.

# Assisted factor review and private cloud follow-up — 11 October 2026

## Delivered

Complete AI single-factor and customer/product batch proposals now save reviewed
factor inputs, then open the existing fixed forecast wizard. They do not start a
calculation directly or copy orders silently. Customer/order review, coverage,
forecast naming, recorded methods and results remain in one workflow.

Closing/reopening a confirmed proposal resumes its isolated wizard. Confirmation
is repeat-safe; repeated clicks cannot dispatch concurrent actions. Existing
queued receipts remain readable, without rewriting previous forecasts. Exact
company/actor, baseline, factor version, source timing, expiry and approval gates
remain enforced. Run-time validation rejects changed or stale sources.

Both cards reuse global Panel, DefinitionList, Disclosure, Actions, Button and
Table components. No CSS overrides or authored inline styles were introduced.
The cards now say “Review forecast factors” / “Continue”, not that calculation
starts at proposal confirmation. Missing Persian scope/geography labels were
translated; customer names and provider-supplied factor names remain source data.

## Cloud processing

A read-only cloud projection can reuse the validated dates/identities context of
one dataset within its immutable scratch checkpoint. The cache is restricted to
the exact dataset-store instance, held only for that projection, copied before
returning, and released on completion/error. Approved report reads still pass
through the original Viewer permissions. No cache is retained between companies,
requests, writes or checkpoints. Source readiness and approval proofs are not
cached; ordinary input reads continue checking source contents.

An unchanged saved-data review now closes directly. Previously “Done” briefly
displayed “Saving dataset…” and refreshed the whole cloud workspace, despite
not saving a new dataset. Changed inputs and explicit forecast requests retain
their existing save/validation paths. The final deployed “Done” returned to Data
in 38 ms in the owner browser check, with no saving state or record changes.

## Verification

- 57 backend tests: complete AI scenarios/batches, company workflows, cloud
  API/workflows and projection reuse. All pass.
- 327 interface tests and production build pass. 57 cloud controller tests pass.
- Exact cached/uncached projection equality, including approved-only report
  views, passes. Four-customer synthetic test: 134.3 ms uncached versus 75.0 ms
  cached, two preparations reduced to one. This excludes network and wake time.
- A separate prediction-frame optimization was tested against the prior commit:
  forecast numbers/CSV were identical, but total calculation time did not improve.
  That optimization was removed rather than claiming a speed gain.
- Disposable loopback browser: complete single-factor proposal → factor review →
  saved-order reuse → explicit order confirmation → named calculation → results.
  Four customers remain present, including customers without orders.
- Complete two-group proposal: original methods/scopes and two untouched products
  remain visible; Persian 390px wizard, resume, order review and calculation pass.
  The fixed dialog measured 358 × 680 px at a 390 × 844 viewport, with internal
  scrolling. No OpenAI or live source request was made in these tests.
- Deployed private saved-data review: 1,428 ms from click to “Saved data”, compared
  with 2,228 ms before deployment. These single observations are not controlled
  cold-start measurements and do not establish causality or a speed guarantee.
- Anonymous cloud customer reads remain 401. Local demo health is 200 after the
  explicitly approved restart; existing local/client data is unchanged.

## Dedicated deployments and limits

Engine: `24a0c9f9-218a-419d-ba49-27f386c8ebf2`; image
`sha256:c44ab3e1b9e818ebd5b79f704ae1d005bd23c4c8eaf10ab37c818160df870837`.
Edge: `ecef5a3d-f022-4e1d-997c-57408c2aa871`.
Only the dedicated forecast engine and edge were updated. Owner-only access,
closed private listeners, five-minute idle policy and provider eligibility gates
remain unchanged. Temporary registry credentials were removed; the dedicated
build VM is stopped. No other services or credentials were edited.

Cloud AI remains disabled pending the existing provider eligibility gate. Local
mock workflow acceptance does not certify real cloud AI/provider behavior.
Older standalone advanced-factor calculations and previously queued receipts
were preserved, not silently migrated. Full bilingual product/design acceptance,
real client accuracy and controlled cold/warm automatic forecast timings remain
open. This is not whole-app acceptance.

Next: measure complete cold/warm cloud forecast jobs and checkpoint rebuilding on
the larger synthetic Tehran case; then finish legacy advanced calculation/revision
navigation and the full bilingual input → forecast → approval → export journey.

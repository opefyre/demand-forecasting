# Assisted input review — updated 24 September 2026

## Delivered scope

Confirmed product purpose: sales/demand forecasting only. Reuse the existing
OpenAI Agents SDK, Pydantic, pandas and DatasetStore validators. Keep the user's
placeholder key: no live provider call or synthetic answer in the demo journal.

The assistant has two additional typed, local tools:

- `inspect_inputs`: inspect the active forecast's saved historical sales and future
  factor files; return columns, source hashes, mapped fields, validation errors,
  warnings, prepared-history summary, factor coverage and a small prepared preview.
  It also reads existing order warnings/issues without modifying orders. Order
  issue lists are bounded and explicitly marked when truncated.
- `prepare_input_mapping`: propose 1–7 supported column-mapping changes using exact
  column names in those files. It validates the resulting inputs and returns a
  reviewable proposal; it cannot apply it.

Supported mapping fields: sales date/quantity, customer–SKU series ID, customer,
SKU, future-factor date and future-factor series ID. No cell edits, row deletion,
unit conversion, altered classification, factor-value invention, order changes or
relaxation of missing-value policy is exposed through this tool.

## Review and application

The chat proposal shows mappings before/after, source quantity totals, totals of
the prepared history after period grouping/gap treatment, and validation warnings.
“Approve & save new input version” is the explicit application step. Existing
action ownership, one-hour expiry, role and CSRF controls still apply.

Application rechecks the dataset fingerprint, source byte hashes and the complete
computed preview. A changed/tampered proposal must be recreated. DatasetStore saves
an idempotent child version with actor/proposal provenance. Original bytes, parent
dataset, forecasts and customer-order snapshots are not modified. No calculation
is automatically queued. The result links to Data, where the new input version can
be selected for calculation; the old version remains available for recovery.

Warnings are not automatic repairs. Identical raw rows are flagged as possible
duplicates, not deleted: they could be legitimate transactions. Invalid quantities,
missing required factor values, missing mapped identifiers and an item mapping
that combines multiple customers/SKUs block the proposed mapping save.

## Verification and limits

284 backend tests / 37 frontend tests passed; production build passed. Tests cover
actual mapping impact (21 → 210 tonnes), immutable originals, idempotent application,
altered previews/source bytes, invalid fields/columns, ambiguous customer grouping,
factor gaps, duplicate warnings, actor isolation, and SDK read/propose tools with no
writes before approval. UI component checks cover visible changes/warnings and the
approval-to-saved state. Existing build/deprecation/resource warnings remain.

Live model judgment and provider-to-browser acceptance remain unverified without
the user's API key. This is not a claim of automatic data cleaning or full quality
assurance. Update, 7 October: bounded formatting-only cell overlays and repeat
history comparisons are delivered in INPUT_CORRECTION_DELIVERY.md. Arbitrary
value repairs remain pending; missing demand is never invented.
No new ERP connector or live Iran factor feed was added.

## First-upload review — implemented 24 September

The existing Match columns step now has one optional **Suggest mappings** button.
A centered consent dialog explains that column names and up to three sample rows
per history/future file are shared with OpenAI. No readiness banner, new navigation
page, automatic AI request or forecast dependency was introduced.

`POST /api/ai/import-mapping` accepts uploaded source IDs and draft settings. It
loads/hash-checks files server-side, verifies source roles, and never accepts
browser-supplied samples. The existing SDK review model returns structured mappings
in a single bounded call with tracing/storage disabled and no provider retries.
Up to 40 columns/file, 300 characters/heading and 120 characters/sample cell are
allowed. Wider inputs remain manually importable. Unrelated settings, filenames,
paths and whole workbooks are not sent. Samples can still contain private data;
client approval of the provider/data-sharing policy is a release dependency.

The response contains exact-column before/after changes, source quantity totals,
questions, and full-file deterministic validation issues. **Use suggestions** only
updates the draft mappings. Source values, unit, factors, classification and orders
cannot be changed by the model. Incomplete settings may still have errors: users
can apply the mapping subset, then resolve those errors before saving. This does
not certify mappings as semantically correct; the planner must review them.

Changed files/settings remount and invalidate the pending review; closing a dialog
discards late responses. Closing does not cancel a provider request already sent.
Manual import works without a key and has the same validation/save boundary.
The shared save validator rejects mixed customer/SKU series, reports possible
duplicates without deleting them, and preserves warnings in the saved dataset.
Existing immutable versions and idempotent save requests are reused.

Verification: **298 backend / 40 frontend tests**, production build passed. Added
tests cover first-upload/no-run operation, consent/disabled-provider guards, bounded
server-owned samples, typed fields, wrong-role/invented/repeated mappings, source
corruption, factor gaps, draft-only changes, stale mappings, save validation bypass,
warning acknowledgement/persistence and retry. Provider responses were mocked;
no live provider judgment was tested. Existing runtime/build warnings remain.

Browser verification: synthetic 720-row / 12-series history progressed from upload
through mappings/settings/review to successful save as “First-upload review · sample”.
Disabled-AI error is shown only after requesting suggestions; manual continuation
retains selections. Centered dialog inspected at laptop size; at 390×844 its bounds
were x=15, width=360 with page width=390 (no horizontal overflow). Existing forecast
demo remained at 966.24 open orders + 7,640.19 expected = 8,606.44 tonnes.

## Next task

Review the dated factor-to-scenario pipeline described in DELIVERY_PLAN.md. Reuse
existing connectors and scenario services, distinguish Iran national/Tehran/local
and global coverage, and test usefulness rather than automatically adding factors.

# History correction → revised forecast → approved export

11 October 2026. Bounded workflow acceptance, not whole-app or client-accuracy certification.

## Delivered fixes

- Monthly updates offer only history versions with the same data classification,
  quantity unit/meaning, frequency, calendars, row meaning and returns policy.
  An incompatible new upload is saved in Data, but stopped immediately with a
  clear instruction to start a separate forecast; the backend safety check remains.
- Persian column-picker labels, frequency options, forecast units and saved-input
  feedback use the shared translation system. Customer names and product IDs are
  never translated or converted.
- Saved-order reuse is disabled during reads/validation and for read-only users.
- Closing an approval refreshes its list in the background without removing the
  button that receives keyboard focus after the dialog closes.
- No dedicated styling, inline styles, new widgets or changes to model mathematics.

## Combined automated evidence

`tests/test_revision_journey.py` runs the real company APIs, stores and forecasting
engine in disposable stores for both Gregorian and Persian planning months:

1. 36 months, four customers and two product codes (`001`, `002`). Preserve the
   original history, two-method forecast and order snapshots.
2. Correct one history quantity from 20 to 26. Preview reports one changed group
   and a +6 total; saving without review acknowledgement is rejected.
3. Create an immutable corrected input and one grouped monthly revision with
   Last observed and Recent average. Repeating the request resumes the same group.
4. Review current orders. Each method produces 12 customer/product/month rows;
   the customer without orders still has positive expected demand.
5. A filtered customer/product JSON export has exactly three monthly rows and
   retains the leading-zero product code.
6. The preparer cannot approve their own release. A different company administrator
   approves; approved Excel, CSV and JSON are read back and quantities match.
   Planning totals exclude fulfilled quantities and equal remaining demand to serve.
7. Another company cannot read the release or forecast. A viewer can download an
   approved report but cannot create a revision. Original inputs/results stay identical.

Passing checks: **340 interface tests, 31 focused backend tests, 64 cloud-controller
tests**, production build and clean whitespace check. The combined test is one
test with two calendar subtests; it is included in the 31, not counted separately.
The build still warns about the large main JavaScript bundle; page-load optimization
is not closed by these checks.

## Actual browser evidence

Chrome against a loopback-only disposable company fixture. Identity/providers are
mocked; inputs/results are genuinely saved and calculated, not mocked screen output.

- Uploaded correction: mappings and `001` retained, review showed 144 → 144 rows
  and 1548 → 1554 tonnes. Review acknowledgement gates saving. Reload restores the
  draft and requires a fresh validation. Original and corrected rows remain in Data.
- The first fixture exposed a classification mismatch only at calculation. The
  backend correctly rejected it, but the workflow was confusing; the early
  compatibility guard above now prevents that late rejection.
- A second fixture with compatible imported-history classifications completed the
  corrected monthly revision with two methods under **Tehran revised demand · October**.
  Existing reviewed orders were reused and re-acknowledged before calculating.
- Recent average showed 141 tonnes; Last period showed 153 tonnes including two
  already fulfilled. The latter planning release exported 53, 49 and 49 tonnes
  (151 still to serve), not 153. All four customers and 12 detail rows were retained.
- Planner submission required review. The independent administrator approved.
  The approved Excel download completed; the Approvals list then showed Approved.
- Persian history settings showed translated month frequency and units. Persian
  approved reports showed translated statuses, labels, quantities and units.
- At **390 × 844**, the Persian dialog measured 358 × 680 with a 16px side inset;
  document width remained 390. Tables scroll inside their containers. Keyboard
  traversal reached the download links by scrolling the 576px dialog body internally.
  Escape closed the dialog. After the background-refresh fix, keyboard focus
  returned to the Review button. Temporary viewport override was reset.
- An unavailable update ID returned a recovery action back to Forecast rather
  than an empty or partially active wizard.

Screenshots are temporary local proof, not production records. No live customer
data, notifications, integrations or OpenAI calls were created by this test.

## Private publication

Only the existing `demandlab-forecast-edge` interface was deployed, version
`9c87457f-af0b-42d7-863a-75fe79e49dc5`. The live HTML references the tested
`index-DDzE7eqQ.js` bundle. Login responds 200; anonymous company dataset access
responds 401. `PRIVATE_ACCESS=closed`, owner-only acceptance, disabled Workers.dev
and preview URLs remain unchanged. No identity, engine, storage or unrelated
service was deployed. A signed-in cloud journey is not claimed by these probes.

## Remaining acceptance boundary

Next: repeat this complete correction/revision/approval/export path on the private
cloud interface with controlled fictional records, including cold/warm timings and
failure/reload recovery. Then finish the broader bilingual/mobile entry-to-result
acceptance matrix. Real client reconciliation, provider eligibility and forecast
accuracy require their own evidence; synthetic checks cannot prove those.

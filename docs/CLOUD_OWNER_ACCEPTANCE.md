# Private owner acceptance — 10 October 2026

## Live and verified

- `https://forecast.vrolen.com` serves the existing compiled interface. The sign-in
  screen is public; company data and actions are not. Only the verified
  `opefyre@gmail.com` account can enter, with fresh session-specific MFA.
- Real Google sign-in completed in the owner's Chrome profile. The owner personally
  enrolled their authenticator, saved recovery codes and verified the code. No real
  authenticator seed, recovery code, Google token or session cookie was exported.
- Aggregate checks in the dedicated D1 database show one user, one verified
  MFA-enabled user, one company, one owner and one session MFA record.
- One password-recovery email was sent from the forecast identity service to the
  owner. Resend shows **Delivered**, receipt `01a1261f-9a63-769e-8206-1124761adcfd`.
  No password was changed. Invitation acceptance and actual recovery completion
  are not certified by this mail-delivery check.
- Anonymous company reads/writes return 401; outsider email sign-in returns 403;
  public registration and secret-file routes return 404. Bearer/API-key access is
  deliberately refused during private owner acceptance, including issued keys.
- Google requires verified email. Only the authenticated Google owner can initialize
  an empty installation through the private serialized coordinator. No public
  bootstrap token or password-based bootstrap exists.
- Mutations require same-origin requests and a session-derived synchronizer token.
  Browser-supplied company, role and identity headers do not establish identity.
- Private identity/storage/engine HTTP listeners remain closed. The domain binds
  only those dedicated forecast services; no other Vrolen/Finkavo service changed.

## Remote calculation, export and sleep/wake verified

The owner workspace has accepted and validated the existing **fictional** Tehran
history: 804 monthly rows, five customers, four products, 18 customer/product
series, October 2022–September 2026. The configured forecast is October
2026–March 2027, tonnes, Gregorian monthly totals, customer-demand meaning and
Iran holiday calendar. All 79 rows of the existing fictional order file were
uploaded and reviewed as a complete snapshot, including fulfilled, cancelled and
tentative lines. Uploaded orders are now correctly labelled "All known orders"
before the snapshot is saved; they no longer misleadingly say "No current orders".
These are synthetic acceptance inputs, not client data or evidence of accuracy.
No local client workspace or local provider credential was copied.

The first cloud dataset upload, preview and save have completed. The private
`/api/auth/runtime` diagnostic reports the real singleton engine running and idle
with a 300,000 ms inactivity policy. It requires owner identity and fresh MFA;
status inspection never starts a stopped engine. Do not use the legacy
`wrangler containers list` instance count as proof for the image-based runtime:
it reported zero while the actual Durable Object reported a running container.

The real remote **Automatic** calculation completed: six planning months and
3,982.8 tonnes of combined demand. Automatic model comparison on this smallest
cold engine took roughly nine minutes; this is functional evidence, not acceptable
interactive performance or a promise of accuracy. The saved dashboard reports
2,099.36 tonnes of confirmed outstanding orders, 1,837.77 tonnes of expected demand
not yet ordered and 3,982.84 tonnes total including fulfilled quantities.

Run `19ade25fd9d6`, order snapshot `78fcdfbc0a98e3df628b3cc344484c2a`.
The real CSV download completed with 108 customer/product/month rows plus its
header. CSV sums match the dashboard: booked 2,099.36, fulfilled 45.71,
remaining 1,837.77 and total 3,982.84 tonnes. It includes separate baseline,
booked, fulfilled, remaining and total
columns, units, calendar, period boundaries and draft status. Aftab Printing has
positive calculated demand despite zero confirmed orders. The default export
excludes confirmed orders for receiving systems that already hold them; it is
not an approved planning release. Corrected idle shutdown, cold saved-report
reading and a second cold export are verified below. No additional source or
AI calls are enabled. No forecast was approved for real operational planning.
The separate port-8010 demo health remains 200 and its data is unchanged.

### Idle-cost issue found and repaired

The initial native inactivity setting did not produce a five-minute wall-clock
shutdown during status inspection. Cloudflare's timer starts after the Durable
Object becomes inactive, and another request can extend it; see its
[native lifecycle API](https://developers.cloudflare.com/containers/api/durable-object-container/#setinactivitytimeout).
Completed work now records a separate `idle_until` deadline and native durable
alarm, five minutes after completion. Status checks cannot change that deadline.
New work supersedes the idle alarm with its bounded active-work deadline; stale
alarms preserve a current active attempt. The platform timer remains a fallback.
The constructor preserves the recorded deadline after an object restart and
initializes it for an already-running pre-migration idle instance.

Only the engine controller was redeployed, version
`da414374-732f-478b-a25c-d3ae18250f97`, using the exact existing numerical image.
No Docker VM was started, image rebuilt, data migrated or other service edited.
At 14:52 UTC the live owner diagnostic reported `running:false,busy:false`.
An intervening status read had not extended the durable shutdown deadline.
Reloading the interface exposed another cost issue: bootstrap eagerly fetched
the checkpoint-backed monthly-update list. The engine woke, restored the saved
company data and showed the identical report, proving cold wake/durability but
not a compute-free read. The interface now fetches that list only on the explicit
"Update forecast" action, preserving resume-existing-update behaviour. Local
transport keeps its existing eager behaviour.

Final live sequence, 14:58–15:00 UTC:

1. Native owner runtime reported `running:false,busy:false` after the durable
   five-minute idle deadline, even with an intervening status inspection.
2. Reloaded the current compiled interface and waited for the complete saved
   demand dashboard. Its total remained 3,982.84 tonnes. A subsequent native
   status inspection still reported `running:false,busy:false`: this same-day
   saved report read did not wake computation. It is not a promise that expired
   report checks or every workflow can be served without computation.
3. Explicitly requested CSV export. The engine woke from stopped to running,
   restored the durable company checkpoint and completed the download.
4. Both downloaded files contain the same 108 rows and are byte-identical:
   SHA-256 `c48d83c56d2765fece604f8c11c988308f327bfdf4583386322361fc7d159fdd`.
   The engine was idle after export; its durable shutdown alarm was reset by this
   completed operation. No further computation was requested. No manual stop,
   warm ping or local-server tunnel was used to manufacture this result.

## Tests and deployment

- Identity type check and production UI build pass.
- Shared identity tests: 20 pass, three optional checks skipped.
- Disposable native D1 browser test verifies actual synthetic TOTP enrollment,
  bad-code denial, proof expiry, CSRF, single-owner bootstrap and outsider denial.
- Native compiled identity Worker: two checks pass, including OAuth state cookies
  across private RPC and the exact Google callback URL.
- Cloud controllers/gateway: 39 checks pass, including non-extending idle status,
  active-work protection and preserved deadlines after object eviction.
- Interface suite: all 270 checks pass, including uploaded-order coverage wording
  and lazy cloud monthly-workflow loading.
- Identity version: `04ea7aa7-943b-4b18-9e4a-46b58ead19e5`.
- Edge version: `1abf1151-a3b9-4bc9-b4d1-b0d323881da3`.
- Storage and numerical image are unchanged from CLOUD_WORKFLOWS_DELIVERY.md;
  the controller-only engine version is recorded above.

## Remaining gates

The requested owner interface, Google/MFA/mail, remote forecast/export and
sleep/wake slice is complete, with the performance limitation above. Next:
reduce cold Automatic calculation time and improve truthful progress; then verify
full sign-out/revocation, recovery and off-device restore.
Live client connectors need dedicated read-only test configurations. External
source credentials are not silently borrowed from the local demo. AI remains
disabled pending provider eligibility for the Iran client. Multi-company/role
tests have disposable-runtime evidence, not a live multi-user browser acceptance.
Opening access to anyone else requires a separate explicit decision.

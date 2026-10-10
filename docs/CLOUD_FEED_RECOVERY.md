# Private cloud connection and access recovery — 10 October 2026

## Delivered

The DNS broker's `redirect: 'error'` option worked in Node mocks but was rejected
by native Cloudflare workerd with a TypeError. Native Miniflare regression tests
reproduce that incompatibility and exercise the real broker. Requests now use
`manual`; all redirect responses are explicitly rejected. Public-IP checks,
timeouts, company isolation and revision guards remain unchanged.

The deployed private runtime diagnostic reports `source_probe.ready: true`,
`running: false`, and `busy: false`. The historical failure timestamp remains
visible as historical evidence, not a new failure. This verifies DNS recovery,
**not successful provider data refresh or factor-aware forecasting**. Existing
provider cooldowns were neither reset nor bypassed. The earliest monthly-source
retry times were 18:41 UTC (World Bank commodities) and 18:43 UTC (NY Fed).

At the owner's request, private development sessions and session-bound MFA proof
last up to 48 hours. This applies only while access is closed and owner acceptance
is enabled. The temporary policy ends at **17 October 2026, 00:00 UTC**; normal
one-hour checks then return. Other identities retain normal MFA checks and cannot
enter the owner-only workspace. No additional account or disabled authentication.

Better Auth manages cookie renewal. The owner session endpoint forwards only the
managed Secure/HttpOnly session cookie, never its value in JSON. Renewal cannot
outlive the validated database session. Cookie caching remains disabled;
revocation and password-reset protections remain. A metadata-only database read
confirmed owner session expiry **12 October 2026, 18:22:23 UTC**, and the actual
signed-in workspace loaded after the final deployment. This is not a two-day
elapsed-duration test.

An older open tab also exposed a lazy sign-in bundle loading failure. The sign-in
boundary now offers one explicit Reload action using the existing EntrySurface,
brand fonts and global button styles. No automatic reload or write replay, new
stylesheet, or inline styles. A disposable browser fixture deliberately rejects
the lazy module: English desktop and Persian 390px layouts render the recovery
screen without horizontal overflow, and Reload works. This bounded check does
not establish that every screen has passed a full design audit.

## Verification

- Interface: 281 tests passed; production build passed.
- Cloud controller/edge: 53 tests passed.
- Identity: 30 passed, four optional tests skipped; type checking passed.
- Compiled native cloud identity: two tests passed, including the existing
  169-route inventory test.
- Native DNS regressions are included in the identity suite.
- Local demo responds HTTP 200 and its data was not changed.
- Existing build bundle-size/Radix warnings and concurrent test-server port
  warnings remain; they are not presented as resolved.

Only these dedicated forecast deployments changed:

- Controller: `fc63b37e-5d51-4462-902e-7747bd6171c4`.
- Identity: `b3151a26-1691-48ae-8ba9-0d918661bf45`.
- Edge/interface: `ab2dacc8-82c7-426f-8ce7-0442bc42b927`.

The numerical image, five-minute idle shutdown, lack of warm pool, storage,
domains, credentials and other services are unchanged. No provider refresh,
OpenAI call, email delivery or client-data replacement was performed in this slice.

## Next substantial acceptance slice

1. Refresh monthly sources after their normal cooldowns and inspect durable
   snapshots, timestamps and capture receipts.
2. Review geography, historical coverage and explicit future assumptions; never
   invent missing source history or future values.
3. Run one grouped forecast with current customer orders and reviewed factors;
   compare models and reconcile customer/product/month views with exports.
4. Check correction/revision, mobile, error and reload paths against the shared
   design framework.

Servix cloud credentials, IMF commercial-use permission, cloud AI/provider
eligibility, real-client accuracy and an authorised multi-person pilot remain
separate acceptance gates. The app is not declared fully finished by this slice.

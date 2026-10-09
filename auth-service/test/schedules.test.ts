import assert from "node:assert/strict";
import test from "node:test";
import { createBridge } from "../src/bridge.js";
import { createIdentity } from "../src/auth.js";

test("background draft grants use live, verified, MFA-enabled company membership", async () => {
  const secret = "synthetic-bridge-proof-for-test-only"; // pragma: allowlist secret -- noncredential test fixture
  let row: Record<string, unknown> = { role: "admin", suspended: false, emailVerified: true, twoFactorEnabled: true };
  let unavailable = false;
  const requests: unknown[][] = [];
  const bridge = createBridge({
    auth: {}, config: { origin: "https://company.test", bridgeSecret: secret },
    pool: { query: async (_sql: string, args: unknown[]) => {
      requests.push(args);
      if (unavailable) throw new Error("Database unavailable");
      return { rows: [row] };
    } },
  } as unknown as ReturnType<typeof createIdentity>);
  const body = { company_id: "tehran_a", issuer: "https://company.test", subject: "alice" };
  const check = (values = body, key = secret) => bridge.request("/internal/schedules/authorize", {
    method: "POST", headers: { "content-type": "application/json", "x-demandlab-bridge-key": key }, body: JSON.stringify(values),
  });
  assert.equal((await (await check()).json()).allowed, true);
  assert.deepEqual(requests[0], ["tehran_a", "alice"]);
  for (const changes of [{ role: "planner" }, { suspended: true }, { emailVerified: false }, { twoFactorEnabled: false }]) {
    const old = row;
    row = { ...old, ...changes };
    assert.equal((await (await check()).json()).allowed, false);
    row = old;
  }
  for (const changes of [{ issuer: "https://other.test" }, { subject: "service:key" }, { company_id: "../tehran_a" }])
    assert.equal((await (await check({ ...body, ...changes })).json()).allowed, false);
  assert.equal((await check(body, "wrong-proof")).status, 401);
  unavailable = true;
  const result = await check();
  assert.equal(result.status, 503);
  assert.equal((await result.json()).detail, "Authentication operation unavailable");
});

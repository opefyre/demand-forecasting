import test from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { configuration } from "../src/env.js";
import {
  asRole,
  keyScopes,
  effectiveScopes,
  permissions,
} from "../src/policy.js";

test("roles do not grant write or draft access to viewers", () => {
  assert.throws(() => asRole("owner"));
  assert.throws(() => asRole("viewer,admin"));
  assert(!permissions.viewer.includes("drafts:read"));
  assert(!permissions.approver.includes("forecasts:run"));
  assert(!permissions.planner.includes("members:manage"));
});
test("keys cannot exceed current role or automate access administration", () => {
  assert.throws(() => keyScopes("viewer", ["forecasts:run"]));
  assert.throws(() => keyScopes("admin", ["members:manage"], true));
  assert.throws(() => keyScopes("admin", ["members:manage"]));
  assert.throws(() => keyScopes("admin", ["chats:own"], true));
  assert.throws(() => keyScopes("viewer", []));
  assert.deepEqual(keyScopes("viewer", ["reports:read", "reports:read"]), [
    "reports:read",
  ]);
  assert.deepEqual(
    effectiveScopes("viewer", ["reports:read", "forecasts:run", "unknown"]),
    ["reports:read"],
  );
});
test("unsafe or incomplete deployment settings fail closed", () => {
  const env = {
    BETTER_AUTH_SECRET: randomBytes(32).toString("hex"),
    DEMANDLAB_AUTH_BRIDGE_SECRET: randomBytes(32).toString("hex"),
    DEMANDLAB_AUTH_DATABASE_URL: "postgresql://localhost/test",
    DEMANDLAB_AUTH_DEV_MAIL: "true",
  };
  assert(configuration(env).local);
  assert.throws(() =>
    configuration({ ...env, DEMANDLAB_PUBLIC_ORIGIN: "http://example.com" }),
  );
  assert.throws(() =>
    configuration({ ...env, DEMANDLAB_PUBLIC_ORIGIN: "https://example.com" }),
  );
  assert.throws(() =>
    configuration({ ...env, GOOGLE_CLIENT_ID: "configured" }),
  );
  assert.throws(() =>
    configuration({
      ...env,
      DEMANDLAB_AUTH_BRIDGE_SECRET: env.BETTER_AUTH_SECRET,
    }),
  );
  assert.throws(() =>
    configuration({
      ...env,
      DEMANDLAB_PUBLIC_ORIGIN: "http://127.0.0.1:8010/path",
    }),
  );
  assert.throws(() =>
    configuration({ ...env, DEMANDLAB_PUBLIC_ORIGIN: "ftp://localhost" }),
  );
});

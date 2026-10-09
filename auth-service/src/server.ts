import { serve } from "@hono/node-server";
import { createIdentity } from "./auth.js";
import { createBridge } from "./bridge.js";

const identity = createIdentity();
const server = serve({
  fetch: createBridge(identity).fetch,
  hostname: "127.0.0.1",
  port: 8011,
});
async function close() {
  server.close();
  await identity.pool.end();
}
process.on("SIGTERM", close);
process.on("SIGINT", close);
console.log("DemandLab authentication listening on loopback port 8011");

import { createIdentity } from "./auth.js";
import { migrate } from "./migrate.js";

// Operator-only CLI. No HTTP endpoint can enable the bootstrap exception.
// Supply the password through the environment, not arguments or a committed file.
const identity = createIdentity(process.env, true);
try {
  const email = process.env.DEMANDLAB_BOOTSTRAP_EMAIL;
  const password = process.env.DEMANDLAB_BOOTSTRAP_PASSWORD;
  const name = process.env.DEMANDLAB_BOOTSTRAP_NAME;
  const company = process.env.DEMANDLAB_BOOTSTRAP_COMPANY;
  const slug = process.env.DEMANDLAB_BOOTSTRAP_SLUG;
  if (
    !email ||
    !password ||
    !name ||
    !company ||
    !slug ||
    !/^[a-z0-9-]{1,80}$/.test(slug)
  )
    throw new Error(
      "Supply bootstrap email, password, name, company and a lowercase company slug",
    );
  await migrate(identity);
  if (
    (await identity.pool.query('SELECT 1 FROM "organization" LIMIT 1')).rowCount
  )
    throw new Error(
      "A company already exists. Bootstrap only initializes an empty installation",
    );
  const user = await identity.auth.api.signUpEmail({
    body: { email, password, name },
  });
  await identity.auth.api.createOrganization({
    body: { name: company, slug, userId: user.user.id },
  });
  // Deliberately do not mark the account verified. The owner must verify their
  // email and enroll a second factor through the normal library flows.
  console.log(
    "Initial company created. Verify the administrator email, then enable two-factor authentication.",
  );
} catch {
  console.error(
    "Bootstrap was not completed. Check the supplied settings and isolated database; no credentials are shown.",
  );
  process.exitCode = 1;
} finally {
  delete process.env.DEMANDLAB_BOOTSTRAP_PASSWORD;
  await identity.pool.end();
}

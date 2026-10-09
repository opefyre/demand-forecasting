import { createAuthClient } from "better-auth/react";
import {
  organizationClient,
  twoFactorClient,
} from "better-auth/client/plugins";

// The official client manages cookies, Google redirects and 2FA challenges.
// Credentials and API keys are never stored in localStorage.
export const identityClient = createAuthClient({
  basePath: "/api/login",
  plugins: [organizationClient(), twoFactorClient()],
});

export function identityResult(result) {
  if (result.error)
    throw new Error(
      {
        INVALID_EMAIL_OR_PASSWORD: "Email or password is incorrect.",
        EMAIL_NOT_VERIFIED: "Verify your email before signing in.",
        INVALID_CODE: "The authentication code is incorrect.",
        TOO_MANY_REQUESTS: "Too many attempts. Try again shortly.",
      }[result.error.code] || "Sign-in was not completed. Try again.",
    );
  return result.data;
}

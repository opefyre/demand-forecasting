import { Resend } from "resend";
import { FORECAST_OWNER, FORECAST_SENDER, type CloudflareIdentityEnv } from "./cloudflare.js";

// Sending is deliberately limited to the owner until private deployment acceptance.
// Resend's maintained SDK, fixed endpoint/sender, no attachments or tracking.
export function cloudflareMailer(env: Pick<CloudflareIdentityEnv, "RESEND_API_KEY">) {
  if (!env.RESEND_API_KEY || !/^re_[A-Za-z0-9_-]{16,}$/.test(env.RESEND_API_KEY))
    throw new Error("Configure the restricted forecast mail credential");
  const client = new Resend(env.RESEND_API_KEY);
  return async (to: string, subject: string, text: string) => {
    if (to !== FORECAST_OWNER || typeof subject !== "string" || !subject || subject.length > 100 ||
        /[\r\n]/.test(subject) || typeof text !== "string" || !text || text.length > 16384)
      throw new Error("Private deployment mail is restricted to the owner");
    // The hash makes retries of the identical verification/reset email safe.
    // Provider idempotency is time-limited; durable delivery state remains a gate.
    const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(JSON.stringify([to, subject, text])));
    const idempotencyKey = "forecast-" + Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
    try {
      const result = await client.emails.send({ from: FORECAST_SENDER, to: [to], subject, text }, { idempotencyKey });
      if (result.error || !result.data?.id) throw new Error("Mail unavailable");
    } catch {
      // No provider response, recipient, URL/token or credential enters a log.
      throw new Error("Forecast mail could not be sent");
    }
  };
}

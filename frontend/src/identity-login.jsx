import React, { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { identityClient, identityResult } from "./identity-client.mjs";
import { t } from "./localization.mjs";
import { Stack, Actions } from "./ui-layout.jsx";
import { FormField } from "./form-field.mjs";

export function IdentityLogin({ user, api, onSignedIn }) {
  const query =
    typeof location === "undefined"
      ? new URLSearchParams()
      : new URLSearchParams(location.search);
  const invitation = query.get("invitation"),
    token = query.get("reset") ? query.get("token") : null;
  const [step, setStep] = useState(
    user?.mfa_required
      ? "factor"
      : user && invitation
        ? "invitation"
        : token
          ? "reset"
          : "signin",
  );
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [name, setName] = useState(""),
    [code, setCode] = useState("");
  const [providers, setProviders] = useState({}),
    [setup, setSetup] = useState(null),
    [savedCodes, setSavedCodes] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const [recoveryCode, setRecoveryCode] = useState(false);
  useEffect(() => {
    let active = true;
    api("/api/auth/providers")
      .then((value) => {
        if (active) setProviders(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [api]);
  async function done() {
    if (invitation) {
      identityResult(
        await identityClient.organization.acceptInvitation({
          invitationId: invitation,
        }),
      );
      const next = new URL(location.href);
      next.searchParams.delete("invitation");
      history.replaceState(null, "", next.pathname + next.search);
    }
    setPassword("");
    setCode("");
    onSignedIn();
  }
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (step === "invitation") await done();
      else if (step === "signup") {
        identityResult(
          await identityClient.signUp.email({ name, email, password }),
        );
        setPassword("");
        setStep("signin");
        setMessage(t("Check your email to verify your account."));
      } else if (step === "recover") {
        identityResult(
          await identityClient.requestPasswordReset({
            email,
            redirectTo: location.origin + "/?reset=1",
          }),
        );
        setMessage(t("If this account exists, a reset link has been sent."));
      } else if (step === "reset") {
        identityResult(
          await identityClient.resetPassword({ newPassword: password, token }),
        );
        setPassword("");
        setStep("signin");
        history.replaceState(null, "", "/");
        setMessage(t("Password updated. Sign in to continue."));
      } else if (step === "factor") {
        if (user?.mfa_required && !user.mfa_enabled && !setup) {
          const result = identityResult(
            await identityClient.twoFactor.enable(password ? { password } : {}),
          );
          setSetup(result);
          setPassword("");
        } else {
          identityResult(
            recoveryCode
              ? await identityClient.twoFactor.verifyBackupCode({
                  code,
                  trustDevice: false,
                })
              : await identityClient.twoFactor.verifyTotp({
                  code,
                  trustDevice: false,
                }),
          );
          await done();
        }
      } else {
        const result = identityResult(
          await identityClient.signIn.email({ email, password }),
        );
        setPassword("");
        if (result?.twoFactorRedirect) setStep("factor");
        else await done();
      }
    } catch (e) {
      setError(t(e.message));
    } finally {
      setBusy(false);
    }
  }
  const enrolling =
    step === "factor" && user?.mfa_required && !user.mfa_enabled;
  const title =
    step === "factor"
      ? t(
          enrolling
            ? "Set up two-factor authentication"
            : "Enter your authentication code",
        )
      : step === "recover"
        ? t("Reset your password")
        : step === "reset"
          ? t("Choose a new password")
          : ["signup", "invitation"].includes(step)
            ? t("Accept your invitation")
            : t("Sign in");
  return (
    <Stack as="form" onSubmit={submit}>
      <h1>{title}</h1>
      {error && <p role="alert">{error}</p>}
      {message && <p role="status">{message}</p>}
      {step === "signup" && (
        <FormField title={t("Your name")}>
          <input
            required
            autoComplete="name"
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </FormField>
      )}
      {["signin", "signup", "recover"].includes(step) && (
        <FormField title={t("Email address")}>
          <input
            required
            type="email"
            autoComplete="email"
            maxLength={254}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </FormField>
      )}
      {(["signin", "signup", "reset"].includes(step) ||
        (enrolling && !setup && user?.has_password)) && (
        <FormField
          title={t("Password")}
          help={
            ["signup", "reset"].includes(step)
              ? t("Use at least 12 characters.")
              : null
          }
        >
          <input
            required
            type="password"
            minLength={["signup", "reset"].includes(step) ? 12 : 1}
            maxLength={128}
            autoComplete={
              ["signup", "reset"].includes(step)
                ? "new-password"
                : "current-password"
            }
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </FormField>
      )}
      {setup && (
        <>
          <Actions>
            <QRCodeSVG
              value={setup.totpURI}
              title={t("Scan with your authenticator app")}
            />
          </Actions>
          <FormField title={t("Setup link")}>
            <input
              readOnly
              value={setup.totpURI}
              onFocus={(e) => e.target.select()}
            />
          </FormField>
          <FormField title={t("Recovery codes")}>
            <textarea readOnly rows={4} value={setup.backupCodes.join("\n")} />
          </FormField>
          <label className="ui-check">
            <input
              type="checkbox"
              checked={savedCodes}
              onChange={(e) => setSavedCodes(e.target.checked)}
            />
            {t("I saved my recovery codes securely.")}
          </label>
        </>
      )}
      {step === "factor" && (!enrolling || setup) && (
        <FormField
          title={t(recoveryCode ? "Recovery code" : "Authentication code")}
        >
          <input
            required
            inputMode={recoveryCode ? "text" : "numeric"}
            autoComplete="one-time-code"
            pattern={recoveryCode ? undefined : "[0-9]{6}"}
            maxLength={recoveryCode ? 128 : 6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </FormField>
      )}
      <button
        className="btn primary"
        disabled={busy || (setup && !savedCodes)}
        type="submit"
      >
        {busy
          ? t("Please wait…")
          : step === "factor"
            ? t(enrolling && !setup ? "Set up authenticator" : "Verify")
            : step === "recover"
              ? t("Send reset link")
              : step === "signup"
                ? t("Create account")
                : step === "reset"
                  ? t("Save password")
                  : step === "invitation"
                    ? t("Accept invitation")
                    : t("Sign in")}
      </button>
      {step === "signin" && providers.google && (
        <button
          className="btn secondary"
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              identityResult(
                await identityClient.signIn.social({
                  provider: "google",
                  callbackURL:
                    location.origin +
                    (invitation
                      ? "/?invitation=" + encodeURIComponent(invitation)
                      : "/"),
                }),
              );
            } catch (e) {
              setError(t(e.message));
              setBusy(false);
            }
          }}
        >
          {t("Continue with Google")}
        </button>
      )}
      <Actions>
        {step === "factor" && !enrolling && (
          <button
            className="text-button"
            type="button"
            disabled={busy}
            onClick={() => {
              setRecoveryCode((value) => !value);
              setCode("");
              setError("");
            }}
          >
            {t(recoveryCode ? "Use authenticator" : "Use recovery code")}
          </button>
        )}
        {step === "signin" && (
          <button
            className="text-button"
            type="button"
            disabled={busy}
            onClick={() => {
              setStep("recover");
              setError("");
              setMessage("");
            }}
          >
            {t("Forgot password?")}
          </button>
        )}
        {step === "signin" && invitation && (
          <button
            className="text-button"
            type="button"
            disabled={busy}
            onClick={() => {
              setStep("signup");
              setError("");
              setMessage("");
            }}
          >
            {t("Create invited account")}
          </button>
        )}
        {!["signin", "factor", "invitation"].includes(step) && (
          <button
            className="text-button"
            type="button"
            disabled={busy}
            onClick={() => {
              setStep("signin");
              setPassword("");
              setError("");
              setMessage("");
            }}
          >
            {t("Back to sign in")}
          </button>
        )}
      </Actions>
    </Stack>
  );
}

import { t as uiText } from "./localization.mjs";
import React, { useEffect, useState, lazy, Suspense } from "react";
import { ChartLineUp, ArrowRight } from "@phosphor-icons/react";
import { useInterfaceLanguage } from "./language-settings.jsx";
import {EntrySurface} from './ui-layout.jsx';
const IdentityLogin = lazy(() =>
  import("./identity-login.jsx").then((module) => ({
    default: module.IdentityLogin,
  })),
);

export function AccessGate({ api, onSession, children }) {
  useInterfaceLanguage();
  const [session, setSession] = useState(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    api("/api/auth/session")
      .then((value) => {
        if (active) {
          onSession(value);
          setSession(value);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    const expired = () => {
      onSession(null);
      setSession((value) => ({
        ...value,
        mode: value?.mode || "oidc",
        user: null,
      }));
    };
    const changed = () => setRevision((value) => value + 1);
    window.addEventListener("demandlab:session-expired", expired);
    window.addEventListener("demandlab:access-updated", changed);
    return () => {
      active = false;
      window.removeEventListener("demandlab:session-expired", expired);
      window.removeEventListener("demandlab:access-updated", changed);
    };
  }, [revision]);
  const invited =
    session?.mode === "better_auth" &&
    new URLSearchParams(location.search).has("invitation");
  if (
    session &&
    (session.mode === "local" ||
      (session.user && !session.user.mfa_required && !invited))
  )
    return children(session);
  const failed =
    new URLSearchParams(location.search).get("signin") === "failed";
  return (
    <EntrySurface brand="DemandLab" icon={ChartLineUp}>
        {session?.mode !== "better_auth" && (
          <h1>
            {session ? uiText("Welcome back") : uiText("Opening workspace")}
          </h1>
        )}
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button
              className="btn primary"
              onClick={() => setRevision((v) => v + 1)}
            >
              {uiText("Try again")}
            </button>
          </>
        ) : session?.mode === "better_auth" ? (
          <Suspense
            fallback={<p role="status">{uiText("Checking access…")}</p>}
          >
            <IdentityLogin
              key={session.user?.mfa_enabled || "signin"}
              user={session.user}
              api={api}
              onSignedIn={() => setRevision((value) => value + 1)}
            />
          </Suspense>
        ) : session ? (
          <>
            <p>{uiText("Sign in with your company account.")}</p>
            {failed && (
              <p role="alert">
                {uiText(
                  "Sign-in was not completed. Try again, or ask your administrator to check your access.",
                )}
              </p>
            )}
            <a className="btn primary" href="/api/auth/login">
              {uiText("Company sign-in")}
              <ArrowRight size={18} />
            </a>
          </>
        ) : (
          <p role="status">{uiText("Checking access…")}</p>
        )}
    </EntrySurface>
  );
}

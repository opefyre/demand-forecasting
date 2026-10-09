import {t as uiText} from './localization.mjs';
import React, { useEffect, useState } from "react";
import { ChartLineUp, ArrowRight } from "@phosphor-icons/react";
import {useInterfaceLanguage} from './language-settings.jsx';

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
      setSession({ mode: "oidc", user: null });
    };
    window.addEventListener("demandlab:session-expired", expired);
    return () => {
      active = false;
      window.removeEventListener("demandlab:session-expired", expired);
    };
  }, [revision]);
  if (session && (session.mode === "local" || session.user))
    return children(session);
  const failed =
    new URLSearchParams(location.search).get("signin") === "failed";
  return (
    <main className="access-screen">
      <section className="access-card">
        <div className="access-brand">
          <ChartLineUp size={28} weight="bold" /> DemandLab
        </div>
        <h1>{session ? uiText("Welcome back") : uiText("Opening workspace")}</h1>
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button
              className="btn primary"
              onClick={() => setRevision((v) => v + 1)}
            >{uiText("Try again")}</button>
          </>
        ) : session ? (
          <>
            <p>{uiText("Sign in with your company account.")}</p>
            {failed && (
              <p role="alert">{uiText("Sign-in was not completed. Try again, or ask your administrator to check your access.")}</p>
            )}
            <a className="btn primary" href="/api/auth/login">{uiText("Company sign-in")}<ArrowRight size={18} />
            </a>
          </>
        ) : (
          <p role="status">{uiText("Checking access…")}</p>
        )}
      </section>
    </main>
  );
}

import React, { useState } from "react";
import { useSmoothState } from "./ui-motion.jsx";
import { t as uiText } from "./localization.mjs";
import { LanguageSettings } from "./language-settings.jsx";
import { UnitSettings } from "./units.jsx";
import { AISettings } from "./ai-settings.jsx";
import { RecurringForecasts } from "./recurring-forecasts.jsx";
import { Page, PageTabs, Panel, Stack, Grid, Actions } from "./ui-layout.jsx";
import { PeopleSettings, ApiAccessSettings } from "./access-management.jsx";

export function SettingsWorkspace({
  workspace,
  refresh,
  notify,
  access,
  api,
  ui,
  fmt,
  date,
  runs = [],
  run,
  datasets = [],
  canAdmin = access.mode === "local" || access.user?.role === "admin",
  resumeUpdate,
  navigate,
}) {
  const { Button, Field, ErrorBox, Pick } = ui;
  const companyAccess = access.mode === "better_auth";
  const sections = [
    ...(canAdmin
      ? [
          ["workspace", "Workspace"],
          ["units", "Product units"],
          ["ai", "AI settings"],
          ["schedules", "Schedules"],
          ...(companyAccess ? [["people", "People"]] : [["access", "Access"]]),
        ]
      : []),
    ...(companyAccess ? [["api-access", "API access"]] : []),
  ];
  const [section, setSection] = useSmoothState(
    canAdmin ? "workspace" : "api-access",
  );
  const [site, setSite] = useState(workspace?.site || {}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(null);
  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api(
        "/api/site",
        { name: site.name, province: site.province, timezone: site.timezone },
        "PUT",
      );
      await refresh();
      notify(uiText("Site settings saved"));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Page
      title={uiText("Settings")}
      controls={
        <PageTabs
          label={uiText("Settings sections")}
          value={section}
          items={sections}
          onChange={(id) => {
            setSection(id);
            setError(null);
          }}
        />
      }
    >
      <div className="ui-content-column">
        <Stack>
          {section === "people" && canAdmin && (
            <PeopleSettings api={api} ui={ui} access={access} />
          )}
          {section === "api-access" && companyAccess && (
            <ApiAccessSettings
              api={api}
              ui={ui}
              canAdmin={canAdmin}
              date={date}
              access={access}
            />
          )}
          {section === "workspace" && (
            <>
              <Panel title={uiText("Workspace")}>
                <Stack as="form" onSubmit={save}>
                  <ErrorBox error={error} />
                  <Field title={uiText("Site name")}>
                    <input
                      aria-label={uiText("Site name")}
                      required
                      minLength={2}
                      maxLength={120}
                      value={site.name || ""}
                      onChange={(e) =>
                        setSite({ ...site, name: e.target.value })
                      }
                    />
                  </Field>
                  <Grid>
                    <Field title={uiText("Province in Iran")}>
                      <input
                        aria-label={uiText("Province in Iran")}
                        required
                        minLength={2}
                        maxLength={100}
                        value={site.province || ""}
                        onChange={(e) =>
                          setSite({ ...site, province: e.target.value })
                        }
                      />
                    </Field>
                    <Field title={uiText("Time zone")}>
                      <input
                        aria-label={uiText("Time zone")}
                        required
                        value={site.timezone || ""}
                        onChange={(e) =>
                          setSite({ ...site, timezone: e.target.value })
                        }
                      />
                    </Field>
                  </Grid>
                  <Actions>
                    <Button kind="primary" disabled={busy}>
                      {uiText(busy ? "Saving…" : "Save settings")}
                    </Button>
                  </Actions>
                </Stack>
              </Panel>
              <LanguageSettings ui={ui} />
            </>
          )}
          {section === "units" && (
            <UnitSettings api={api} ui={ui} fmt={fmt} date={date} />
          )}
          {section === "ai" && <AISettings api={api} ui={ui} expanded />}
          {section === "schedules" && (
            <RecurringForecasts
              api={api}
              ui={ui}
              runs={runs}
              run={run}
              datasets={datasets}
              canAdmin={canAdmin}
              resumeUpdate={resumeUpdate}
              refresh={refresh}
              navigate={navigate}
              settings
            />
          )}
          {section === "access" && (
            <Panel title={uiText("Access")}>
              <p>
                {uiText(
                  access.mode === "oidc"
                    ? "Company sign-in is enabled. Roles are assigned by your administrator."
                    : "Local workspace. Company sign-in is configured on the server.",
                )}
              </p>
            </Panel>
          )}
        </Stack>
      </div>
    </Page>
  );
}

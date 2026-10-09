// Isolated browser fixture. No accounts, mail, keys or provider calls are real.
// Not included in the production entry point. Appearance uses the app framework.
import React, { useState, useMemo, useRef } from "react";
import { createRoot } from "react-dom/client";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "@phosphor-icons/react";
import { PeopleSettings, ApiAccessSettings } from "./access-management.jsx";
import { Page, PageTabs, Stack } from "./ui-layout.jsx";
import { FormField } from "./form-field.mjs";
import {
  changeInterfaceLanguage,
  applyInterfaceLanguage,
  t,
} from "./localization.mjs";
import "./design-system.css";
const ui = {
  Button: ({ kind = "secondary", children, ...props }) => (
    <button className={"btn " + kind} {...props}>
      {children}
    </button>
  ),
  Field: FormField,
  Pick: ({ label, options, value, onChange, disabled }) => (
    <select
      aria-label={label}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {options.map(([v, l]) => (
        <option key={v} value={v}>
          {l}
        </option>
      ))}
    </select>
  ),
  ErrorBox: ({ error }) =>
    error ? (
      <p role="alert">{typeof error === "string" ? error : error.message}</p>
    ) : null,
  Table: ({ headers, children, empty }) => (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {headers.map((h, i) => (
              <th key={i}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {empty ? (
            <tr>
              <td colSpan={headers.length} className="table-empty">
                {empty}
              </td>
            </tr>
          ) : (
            children
          )}
        </tbody>
      </table>
    </div>
  ),
  Modal: ({ open, onClose, title, children, dismissible = true }) => (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => !v && dismissible && onClose()}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className="modal">
          <div className="modal-heading">
            <Dialog.Title>{title}</Dialog.Title>
            {dismissible && (
              <Dialog.Close asChild>
                <button className="icon-btn" aria-label={t("Close dialog")}>
                  <X />
                </button>
              </Dialog.Close>
            )}
          </div>
          <Dialog.Description className="sr-only">{title}</Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  ),
};
function Fixture() {
  const [section, setSection] = useState("people"),
    [language, setLanguage] = useState("en");
  const data = useRef({
    members: ["admin", "planner", "approver", "viewer"].map((role, i) => ({
      id: "m" + i,
      user_id: "u" + i,
      name: ["Admin Demo", "Planner Demo", "Approver Demo", "Viewer Demo"][i],
      email: role + "@example.test",
      role,
      suspended: false,
    })),
    invitations: [],
    keys: [],
  });
  const api = useMemo(
    () =>
      async (url, body, method = body ? "POST" : "GET") => {
        const saved = data.current;
        if (url === "/api/v1/access-options")
          return {
            personal: [
              { scope: "reports:read", label: "Read approved forecasts" },
              { scope: "customers:write", label: "Update customers" },
            ],
            company: {
              viewer: [
                { scope: "reports:read", label: "Read approved forecasts" },
              ],
              planner: [
                { scope: "reports:read", label: "Read approved forecasts" },
                { scope: "orders:write", label: "Update orders" },
              ],
            },
          };
        if (url === "/api/v1/members")
          return structuredClone({
            members: saved.members,
            invitations: saved.invitations,
          });
        if (url === "/api/v1/invitations") {
          const row = {
            id: "i" + saved.invitations.length,
            ...body,
            status: "pending",
          };
          saved.invitations.push(row);
          return row;
        }
        if (url.startsWith("/api/v1/invitations/")) {
          saved.invitations = saved.invitations.filter(
            (v) => v.id !== url.split("/").at(-1),
          );
          return { updated: true };
        }
        if (url.startsWith("/api/v1/members/")) {
          const id = url.split("/")[4],
            row = saved.members.find((v) => v.id === id);
          if (method === "DELETE")
            saved.members = saved.members.filter((v) => v.id !== id);
          else if (body) Object.assign(row, body);
          return { updated: true };
        }
        if (url === "/api/v1/api-keys" && method === "GET")
          return structuredClone({ keys: saved.keys });
        if (url === "/api/v1/api-keys") {
          const row = {
            id: "k" + saved.keys.length,
            name: body.name,
            role: body.role,
            owner_id: "u0",
            enabled: true,
            start: "NONSECRET",
            expiresAt: "2027-01-01T00:00:00Z",
          };
          saved.keys.push(row);
          return { ...row, key: "NONSECRET-FIXTURE-ONLY" };
        }
        if (url.startsWith("/api/v1/api-keys/")) {
          const row = saved.keys.find((v) => v.id === url.split("/")[4]);
          if (method === "DELETE") row.revoked = true;
          else if (body?.name) row.name = body.name;
          return { updated: true };
        }
        throw Error("Unexpected fixture operation");
      },
    [],
  );
  const access = {
    mode: "better_auth",
    user: { subject: "u0", role: "admin" },
  };
  return (
    <div className="main">
      <header className="topbar">
        <span>Isolated access UI test</span>
        <button
          className="text-btn"
          onClick={async () => {
            const next = language === "en" ? "fa" : "en";
            await changeInterfaceLanguage(next);
            applyInterfaceLanguage(document, next);
            setLanguage(next);
          }}
        >
          English / فارسی
        </button>
      </header>
      <main id="workspace">
        <Page
          title={t("Settings")}
          controls={
            <PageTabs
              value={section}
              onChange={setSection}
              items={[
                ["people", "People"],
                ["keys", "API access"],
              ]}
            />
          }
        >
          <div className="ui-content-column">
            <Stack>
              {section === "people" ? (
                <PeopleSettings api={api} ui={ui} access={access} />
              ) : (
                <ApiAccessSettings
                  api={api}
                  ui={ui}
                  access={access}
                  canAdmin
                  date={(v) => v?.slice(0, 10) || "—"}
                />
              )}
            </Stack>
          </div>
        </Page>
      </main>
    </div>
  );
}
applyInterfaceLanguage(document, "en");
createRoot(document.getElementById("root")).render(<Fixture />);

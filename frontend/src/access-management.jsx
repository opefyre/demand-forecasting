import React, { useEffect, useState, useRef } from "react";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { DotsThree, Plus, Copy } from "@phosphor-icons/react";
import { t } from "./localization.mjs";
import {
  Panel,
  Stack,
  Grid,
  Actions,
  FieldGroup,
  useMenuHandoff,
} from "./ui-layout.jsx";

const roles = {
  admin: "Admin",
  planner: "Planner",
  approver: "Approver",
  viewer: "Viewer",
};
const roleLabel = (role) => t(roles[role] || role);

function RowMenu({ name, options, busy }) {
  const handoff = useMenuHandoff();
  const trigger = useRef(null);
  return (
    <Dropdown.Root>
      <Dropdown.Trigger
        ref={trigger}
        className="btn secondary"
        aria-label={t("Actions for {{name}}", { name })}
        disabled={busy}
      >
        <DotsThree />
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content
          className="select-menu"
          sideOffset={5}
          onCloseAutoFocus={handoff.close}
        >
          {options.map(([label, action]) => (
            <Dropdown.Item
              className="select-option"
              key={label}
              onSelect={() => handoff.select(trigger.current, action)}
            >
              {t(label)}
            </Dropdown.Item>
          ))}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

export function PeopleSettings({ api, ui, access }) {
  const { Button, Field, Pick, Table, ErrorBox, Modal } = ui;
  const [data, setData] = useState({ members: [], invitations: [] }),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  const [editing, setEditing] = useState(null),
    [email, setEmail] = useState(""),
    [role, setRole] = useState("planner");
  const [loaded, setLoaded] = useState(false);
  async function load() {
    const value = await api("/api/v1/members");
    setData(value);
    setLoaded(true);
    setError(null);
  }
  useEffect(() => {
    let active = true;
    api("/api/v1/members")
      .then((value) => {
        if (active) {
          setData(value);
          setLoaded(true);
        }
      })
      .catch((e) => {
        if (active) setError(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);
  const open = (operation, row) => {
    setError("");
    setEditing({ operation, row });
    setRole(row?.role || "planner");
    setEmail("");
  };
  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const op = editing.operation,
        row = editing.row;
      if (op === "invite") await api("/api/v1/invitations", { email, role });
      else if (op === "role")
        await api("/api/v1/members/" + row.id, { role }, "PATCH");
      else if (op === "suspend" || op === "resume")
        await api(
          "/api/v1/members/" + row.id,
          { suspended: op === "suspend" },
          "PATCH",
        );
      else if (op === "remove")
        await api("/api/v1/members/" + row.id, null, "DELETE");
      else if (op === "revoke")
        await api("/api/v1/members/" + row.id + "/revoke-sessions", {});
      else if (op === "cancel")
        await api("/api/v1/invitations/" + row.id, null, "DELETE");
      if (row?.user_id === access.user.subject) {
        setEditing(null);
        window.dispatchEvent(new Event("demandlab:access-updated"));
        return;
      }
      await load();
      setEditing(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const titles = {
    invite: "Invite person",
    role: "Change role",
    suspend: "Suspend access",
    resume: "Restore access",
    remove: "Remove person",
    revoke: "Sign out this person",
    cancel: "Cancel invitation",
  };
  return (
    <>
      <Panel
        title={t("People")}
        actions={
          <Button
            onClick={() => open("invite")}
            disabled={busy || loading || !loaded}
          >
            <Plus />
            {t("Invite person")}
          </Button>
        }
      >
        {!editing && (
          <ErrorBox error={error} onReload={() => load().catch(setError)} />
        )}
        <Table
          headers={[t("Name"), t("Email address"), t("Role"), t("Status"), ""]}
          empty={
            loading
              ? t("Loading…")
              : data.members.length
                ? null
                : t("No people yet.")
          }
        >
          {data.members.map((row) => (
            <tr key={row.id}>
              <td>
                {row.name}
                {row.user_id === access.user.subject && (
                  <span className="ui-record-meta">{t("You")}</span>
                )}
              </td>
              <td>{row.email}</td>
              <td>{roleLabel(row.role)}</td>
              <td>{t(row.suspended ? "Suspended" : "Active")}</td>
              <td>
                <div className="ui-record-actions">
                  <RowMenu
                    name={row.name}
                    busy={busy}
                    options={[
                      ["Change role", () => open("role", row)],
                      [
                        row.suspended ? "Restore access" : "Suspend access",
                        () => open(row.suspended ? "resume" : "suspend", row),
                      ],
                      ["Sign out this person", () => open("revoke", row)],
                      ["Remove person", () => open("remove", row)],
                    ]}
                  />
                </div>
              </td>
            </tr>
          ))}
        </Table>
      </Panel>
      {data.invitations.some((row) => row.status === "pending") && (
        <Panel title={t("Pending invitations")}>
          <Table headers={[t("Email address"), t("Role"), ""]}>
            {data.invitations
              .filter((row) => row.status === "pending")
              .map((row) => (
                <tr key={row.id}>
                  <td>{row.email}</td>
                  <td>{roleLabel(row.role)}</td>
                  <td>
                    <div className="ui-record-actions">
                      <Button
                        disabled={busy}
                        onClick={() => open("cancel", row)}
                      >
                        {t("Cancel invitation")}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
          </Table>
        </Panel>
      )}
      <Modal
        title={t(titles[editing?.operation] || "People")}
        open={!!editing}
        onClose={() => !busy && setEditing(null)}
        dismissible={!busy}
      >
        {editing && (
          <Stack as="form" onSubmit={save}>
            <ErrorBox error={error} />
            {editing.operation === "invite" && (
              <Field title={t("Email address")}>
                <input
                  required
                  type="email"
                  autoComplete="email"
                  maxLength={254}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </Field>
            )}
            {["invite", "role"].includes(editing.operation) ? (
              <Field
                title={t("Role")}
                help={t(
                  "Admin manages the app. Planner prepares forecasts. Approver approves them. Viewer reads approved results.",
                )}
              >
                <Pick
                  label={t("Role")}
                  value={role}
                  onChange={setRole}
                  options={Object.keys(roles).map((value) => [
                    value,
                    roleLabel(value),
                  ])}
                />
              </Field>
            ) : (
              <p>{editing.row?.name || editing.row?.email}</p>
            )}
            <Actions>
              <Button
                type="button"
                disabled={busy}
                onClick={() => setEditing(null)}
              >
                {t("Cancel")}
              </Button>
              <Button kind="primary" type="submit" disabled={busy}>
                {busy ? t("Saving…") : t(titles[editing.operation])}
              </Button>
            </Actions>
          </Stack>
        )}
      </Modal>
    </>
  );
}

export function ApiAccessSettings({ api, ui, canAdmin, date, access }) {
  const { Button, Field, Pick, Table, ErrorBox, Modal } = ui;
  const [keys, setKeys] = useState([]),
    [policy, setPolicy] = useState(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [editing, setEditing] = useState(null),
    [shownKey, setShownKey] = useState(null),
    [copied, setCopied] = useState(false);
  const [name, setName] = useState(""),
    [kind, setKind] = useState("personal"),
    [role, setRole] = useState("viewer"),
    [days, setDays] = useState(90),
    [scopes, setScopes] = useState(["reports:read"]);
  async function load() {
    const [items, options] = await Promise.all([
      api("/api/v1/api-keys"),
      api("/api/v1/access-options"),
    ]);
    setKeys(items.keys);
    setPolicy(options);
    setError(null);
  }
  useEffect(() => {
    let active = true;
    Promise.all([api("/api/v1/api-keys"), api("/api/v1/access-options")])
      .then(([items, options]) => {
        if (active) {
          setKeys(items.keys);
          setPolicy(options);
        }
      })
      .catch((e) => {
        if (active) setError(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [api]);
  const open = (operation, row) => {
    setError("");
    setName(row?.name || "");
    setEditing({ operation, row });
    setKind("personal");
    setRole("viewer");
    setDays(90);
    setScopes(["reports:read"]);
  };
  const choices =
    kind === "company" ? policy?.company[role] || [] : policy?.personal || [];
  async function save(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      let value;
      const row = editing.row,
        op = editing.operation;
      if (op === "create")
        value = await api("/api/v1/api-keys", {
          name,
          kind,
          ...(kind === "company" ? { role } : {}),
          days: Number(days),
          scopes,
        });
      if (op === "rename")
        await api("/api/v1/api-keys/" + row.id, { name }, "PATCH");
      if (op === "revoke")
        await api("/api/v1/api-keys/" + row.id, null, "DELETE");
      if (op === "rotate")
        value = await api("/api/v1/api-keys/" + row.id + "/rotate", {
          days: Number(days),
        });
      // Keep the returned secret even if refreshing the list fails. Never resend
      // creation automatically or put a key in a toast, URL or browser storage.
      setEditing(null);
      if (value?.key) {
        setShownKey(value);
        setCopied(false);
      }
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const titles = {
    create: "Create API key",
    rename: "Rename API key",
    revoke: "Revoke API key",
    rotate: "Replace API key",
  };
  return (
    <>
      <Panel
        title={t("API access")}
        actions={
          <Button
            onClick={() => open("create")}
            disabled={busy || loading || !policy}
          >
            <Plus />
            {t("Create API key")}
          </Button>
        }
      >
        {!editing && (
          <ErrorBox error={error} onReload={() => load().catch(setError)} />
        )}
        <Table
          headers={[t("Name"), t("Access"), t("Expires"), t("Status"), ""]}
          empty={
            loading ? t("Loading…") : keys.length ? null : t("No API keys yet.")
          }
        >
          {keys.map((row) => (
            <tr key={row.id}>
              <td>
                <strong>{row.name}</strong>
                <span className="ui-record-meta">{row.start}</span>
              </td>
              <td>{row.role ? roleLabel(row.role) : t("Personal")}</td>
              <td>{date(row.expiresAt, true)}</td>
              <td>
                {t(
                  row.revoked || !row.enabled
                    ? "Revoked"
                    : row.expiresAt && new Date(row.expiresAt) < new Date()
                      ? "Expired"
                      : "Active",
                )}
              </td>
              <td>
                <div className="ui-record-actions">
                  <RowMenu
                    name={row.name}
                    busy={busy}
                    options={[
                      ["Rename API key", () => open("rename", row)],
                      ...(!row.revoked && row.enabled
                        ? [
                            ...(row.role ||
                            row.owner_id === access?.user?.subject
                              ? [["Replace API key", () => open("rotate", row)]]
                              : []),
                            ["Revoke API key", () => open("revoke", row)],
                          ]
                        : []),
                    ]}
                  />
                </div>
              </td>
            </tr>
          ))}
        </Table>
      </Panel>
      <Modal
        title={t(titles[editing?.operation] || "API access")}
        open={!!editing}
        onClose={() => !busy && setEditing(null)}
        dismissible={!busy}
      >
        {editing && (
          <Stack as="form" onSubmit={save}>
            <ErrorBox error={error} />
            {["create", "rename"].includes(editing.operation) && (
              <Field title={t("Name")}>
                <input
                  required
                  maxLength={80}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </Field>
            )}
            {editing.operation === "create" && canAdmin && (
              <Grid>
                <Field title={t("Key owner")}>
                  <Pick
                    label={t("Key owner")}
                    value={kind}
                    onChange={(value) => {
                      setKind(value);
                      setScopes(["reports:read"]);
                    }}
                    options={[
                      ["personal", t("Personal")],
                      ["company", t("Company connection")],
                    ]}
                  />
                </Field>
                {kind === "company" && (
                  <Field title={t("Access")}>
                    <Pick
                      label={t("Access")}
                      value={role}
                      onChange={(value) => {
                        setRole(value);
                        setScopes(["reports:read"]);
                      }}
                      options={Object.keys(policy.company).map((value) => [
                        value,
                        roleLabel(value),
                      ])}
                    />
                  </Field>
                )}
              </Grid>
            )}
            {["create", "rotate"].includes(editing.operation) && (
              <Field title={t("Expires after (days)")}>
                <input
                  required
                  type="number"
                  min={1}
                  max={365}
                  step={1}
                  value={days}
                  onChange={(e) => setDays(e.target.value)}
                />
              </Field>
            )}
            {editing.operation === "create" && (
              <FieldGroup title={t("Allow this connection to")}>
                {choices.map((item) => (
                  <label key={item.scope} className="ui-check">
                    <input
                      type="checkbox"
                      checked={scopes.includes(item.scope)}
                      onChange={(e) =>
                        setScopes((values) =>
                          e.target.checked
                            ? [...values, item.scope]
                            : values.filter((value) => value !== item.scope),
                        )
                      }
                    />
                    {t(item.label)}
                  </label>
                ))}
              </FieldGroup>
            )}
            {editing.operation === "revoke" && (
              <p>{t("Apps using this key will stop working immediately.")}</p>
            )}
            {editing.operation === "rotate" && (
              <p>
                {t(
                  "The old key will stop working. Update connected apps with the replacement.",
                )}
              </p>
            )}
            <Actions>
              <Button
                type="button"
                disabled={busy}
                onClick={() => setEditing(null)}
              >
                {t("Cancel")}
              </Button>
              <Button
                kind="primary"
                type="submit"
                disabled={
                  busy || (editing.operation === "create" && !scopes.length)
                }
              >
                {busy ? t("Saving…") : t(titles[editing.operation])}
              </Button>
            </Actions>
          </Stack>
        )}
      </Modal>
      <Modal
        title={t("Save your API key")}
        open={!!shownKey}
        onClose={() => setShownKey(null)}
      >
        {shownKey && (
          <Stack>
            <p>
              {t(
                "Shown only once. Store it securely; do not share it in chat.",
              )}
            </p>
            <Field title={t("API key")}>
              <textarea
                readOnly
                rows={3}
                value={shownKey.key}
                onFocus={(e) => e.target.select()}
              />
            </Field>
            <Actions>
              <Button
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(shownKey.key);
                    setCopied(true);
                  } catch {
                    setError(
                      t(
                        "Copy was unavailable. Select the key and copy it manually.",
                      ),
                    );
                  }
                }}
              >
                <Copy />
                {copied ? t("Copied") : t("Copy key")}
              </Button>
              <Button kind="primary" onClick={() => setShownKey(null)}>
                {t("Done")}
              </Button>
            </Actions>
            <ErrorBox error={error} />
          </Stack>
        )}
      </Modal>
    </>
  );
}

import { before, after, test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";
import { fa } from "./locales/fa.mjs";

let server,
  IdentityLogin,
  PeopleSettings,
  ApiAccessSettings,
  SettingsWorkspace,
  locale,
  identityResult;
before(async () => {
  server = await createServer({
    server: { middlewareMode: true, hmr: false, watch: null },
    appType: "custom",
  });
  ({ IdentityLogin } = await server.ssrLoadModule("/src/identity-login.jsx"));
  ({ PeopleSettings, ApiAccessSettings } = await server.ssrLoadModule(
    "/src/access-management.jsx",
  ));
  ({ SettingsWorkspace } = await server.ssrLoadModule(
    "/src/settings-workspace.jsx",
  ));
  locale = await server.ssrLoadModule("/src/localization.mjs");
  ({ identityResult } = await server.ssrLoadModule("/src/identity-client.mjs"));
});
after(async () => {
  await server?.close();
});
const ui = {
  Button: ({ children, kind, ...props }) =>
    React.createElement("button", props, children),
  Field: ({ title, children }) =>
    React.createElement("div", { className: "field" }, title, children),
  Pick: ({ label }) => React.createElement("select", { "aria-label": label }),
  ErrorBox: () => null,
  Table: () => React.createElement("div", { className: "table-wrap" }),
  Modal: () => null,
};
const common = {
  api: async () => ({}),
  ui,
  canAdmin: true,
  date: String,
  access: { mode: "better_auth", user: { subject: "u1", role: "admin" } },
};
test("new access screens reuse global panels and forms without inline styles", () => {
  for (const Component of [PeopleSettings, ApiAccessSettings]) {
    const html = renderToStaticMarkup(React.createElement(Component, common));
    assert.match(html, /class="ui-panel"/);
    assert.match(html, /class="ui-panel-header"/);
    assert.match(html, /class="ui-panel-title"/);
    assert.doesNotMatch(html, /style=/);
  }
  const html = renderToStaticMarkup(
    React.createElement(IdentityLogin, { api: common.api }),
  );
  assert.match(html, /class="ui-stack"/);
  assert.match(html, /type="email"/);
  assert.match(html, /type="password"/);
  assert.match(html, /autoComplete="current-password"/);
  assert.doesNotMatch(html, /style=/);
});
test('sign-in uses the shared entry surface and action-menu contract',async()=>{
  const {EntrySurface}=await server.ssrLoadModule('/src/ui-layout.jsx');
  const html=renderToStaticMarkup(React.createElement(EntrySurface,{brand:'DemandLab',icon:()=>null},React.createElement(IdentityLogin,{api:common.api})));
  assert.match(html,/class="ui-entry"/);assert.match(html,/class="ui-panel ui-entry-surface"/);
  assert.doesNotMatch(html,/style=|access-card|access-screen/);
  const source=await readFile(new URL('access-management.jsx',import.meta.url),'utf8');
  assert.match(source,/<ActionMenu name=/);assert.doesNotMatch(source,/select-menu|select-option|Dropdown\.Content/);
});
test('shared brand fonts are bundled assets, not missing cloud root paths',async()=>{
  const css=await readFile(new URL('workspace.css',import.meta.url),'utf8');
  assert.match(css,/\.\.\/\.\.\/app\/static\/fonts\/instrument-sans/);
  assert.match(css,/\.\.\/\.\.\/app\/static\/fonts\/vazirmatn/);
  assert.doesNotMatch(css,/url\(["']\/fonts\//);
});
test("Google-only administrator can start enrollment without an invented password", () => {
  const html = renderToStaticMarkup(
    React.createElement(IdentityLogin, {
      api: common.api,
      user: { mfa_required: true, mfa_enabled: false, has_password: false },
    }),
  );
  assert.match(html, /Set up two-factor authentication/);
  assert.doesNotMatch(html, /type="password"/);
  assert.match(html, /Set up authenticator/);
});
test("viewer settings expose personal API access without admin pages", () => {
  const html = renderToStaticMarkup(
    React.createElement(SettingsWorkspace, {
      ...common,
      canAdmin: false,
      access: { mode: "better_auth", user: { subject: "u1", role: "viewer" } },
    }),
  );
  assert.match(html, /API access/);
  assert.doesNotMatch(html, />People</);
  assert.doesNotMatch(html, />Workspace</);
});
test("login and access-management authored labels have Persian translations", async () => {
  for (const file of [
    "identity-login.jsx",
    "access-management.jsx",
    "identity-client.mjs",
  ]) {
    const source = await readFile(new URL(file, import.meta.url), "utf8");
    for (const item of source.matchAll(/\bt\((["'])([^"']+)\1/g))
      assert(Object.hasOwn(fa, item[2]), item[2]);
    assert.doesNotMatch(
      source,
      /\bstyle\s*=|localStorage\.setItem|sessionStorage\.setItem/,
    );
  }
  await locale.changeInterfaceLanguage("fa");
  const html = renderToStaticMarkup(
    React.createElement(IdentityLogin, { api: common.api }),
  );
  assert.match(html, /نشانی ایمیل/);
  assert.match(html, /رمز عبور/);
  await locale.changeInterfaceLanguage("en");
});
test("identity errors are safe user-facing messages, not raw provider details", () => {
  assert.throws(
    () =>
      identityResult({
        error: {
          code: "DATABASE_ERROR",
          message: "private URL with credentials",
        },
      }),
    /Sign-in was not completed/,
  );
  assert.throws(
    () => identityResult({ error: { code: "INVALID_EMAIL_OR_PASSWORD" } }),
    /Email or password is incorrect/,
  );
  assert.deepEqual(identityResult({ data: { ok: true } }), { ok: true });
});

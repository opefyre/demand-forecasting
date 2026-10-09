import test from "node:test";
import assert from "node:assert/strict";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FormField, FIELD_CONTROL } from "./form-field.mjs";

const h = React.createElement;
const render = (children, props = {}) =>
  renderToStaticMarkup(h(FormField, { title: "Quantity", ...props }, children));
const attribute = (tag, name) =>
  tag.match(new RegExp(` ${name}="([^"]+)"`))?.[1];

test("native input caption targets a stable unique control and supplies its name", () => {
  const html = render(h("input", { type: "number", defaultValue: 0 }));
  const input = html.match(/<input[^>]+>/)[0];
  const label = html.match(/<label[^>]+>/)[0];
  assert.equal(attribute(label, "for"), attribute(input, "id"));
  assert.equal(attribute(label, "id"), attribute(input, "aria-labelledby"));
});

test("suffix wrappers and fragments retain controls, exact names and help", () => {
  const html = render(
    h(
      React.Fragment,
      null,
      h(
        "div",
        { className: "input-suffix" },
        h("input", {
          id: "horizon",
          "aria-label": "Forecast horizon",
          "aria-describedby": "existing",
        }),
        h("span", null, "months"),
      ),
    ),
    { help: "Choose a period." },
  );
  const input = html.match(/<input[^>]+>/)[0];
  assert.equal(attribute(input, "aria-label"), "Forecast horizon");
  assert.equal(attribute(input, "aria-labelledby"), undefined);
  assert.equal(attribute(input, "id"), "horizon");
  assert.match(html, /for="horizon"/);
  const helpId = html.match(/class="sr-only" id="([^"]+)"/)[1];
  assert.equal(attribute(input, "aria-describedby"), `existing ${helpId}`);
});

test("opted-in select forwards caption and description to its trigger", () => {
  function Control(props) {
    return h("button", { ...props, role: "combobox" });
  }
  Control[FIELD_CONTROL] = true;
  const html = render(h(Control), { help: "Choose a unit." });
  const trigger = html.match(/<button[^>]+>/)[0];
  const label = html.match(/<label[^>]+>/)[0];
  assert.equal(attribute(label, "for"), attribute(trigger, "id"));
  assert.ok(attribute(trigger, "aria-describedby"));
});

test("multiple controls form a named group without duplicating ids", () => {
  const html = render([
    h("input", { key: "a", "aria-label": "Minimum" }),
    h("input", { key: "b", "aria-label": "Maximum" }),
  ]);
  assert.match(html, /role="group"/);
  assert.doesNotMatch(html, /<label/);
  const controls = html.match(/<input[^>]+>/g);
  assert.notEqual(attribute(controls[0], "id"), attribute(controls[1], "id"));
  assert.equal(attribute(controls[1], "aria-label"), "Maximum");
});

test("nested fields keep their own labels; hidden inputs are not labelled", () => {
  const html = render([
    h("input", { key: "hidden", type: "hidden" }),
    h(FormField, { key: "inner", title: "Inner" }, h("textarea")),
  ]);
  assert.match(html, /<input type="hidden"\/>/);
  assert.equal((html.match(/<label/g) || []).length, 1);
  assert.match(html, />Inner<\/label>/);
});

test("existing labelledby wins and separate field ids do not collide", () => {
  const html = renderToStaticMarkup(
    h(
      React.Fragment,
      null,
      h(
        FormField,
        { title: "First" },
        h("input", { "aria-labelledby": "explicit" }),
      ),
      h(FormField, { title: "Second" }, h("input")),
    ),
  );
  const controls = html.match(/<input[^>]+>/g);
  assert.equal(attribute(controls[0], "aria-labelledby"), "explicit");
  assert.notEqual(attribute(controls[0], "id"), attribute(controls[1], "id"));
});

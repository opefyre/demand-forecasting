import React, { useId } from "react";

// Explicit opt-in: do not inject DOM props into arbitrary nested components.
export const FIELD_CONTROL = Symbol.for("demandlab.field-control");

export function FormField({ title, help, children, Help }) {
  const key = useId();
  const captionId = `${key}-caption`;
  const helpId = help ? `${key}-help` : undefined;
  const controls = [];
  function bind(nodes) {
    return React.Children.map(nodes, (child) => {
      if (!React.isValidElement(child)) return child;
      const native = ["input", "textarea", "select"].includes(child.type);
      const custom = child.type?.[FIELD_CONTROL];
      if ((native || custom) && child.props.type !== "hidden") {
        const id = child.props.id || `${key}-control-${controls.length}`;
        controls.push(id);
        const describedBy =
          [child.props["aria-describedby"], helpId].filter(Boolean).join(" ") ||
          undefined;
        return React.cloneElement(child, {
          id,
          "aria-describedby": describedBy,
          // Existing precise names (e.g. Forecast horizon) remain authoritative.
          ...(child.props["aria-label"] ||
          child.props["aria-labelledby"] ||
          child.props.label
            ? {}
            : { "aria-labelledby": captionId }),
        });
      }
      // Traverse structural markup only. A nested Field owns its own labels.
      if (typeof child.type === "string" || child.type === React.Fragment) {
        return React.cloneElement(child, {}, bind(child.props.children));
      }
      return child;
    });
  }
  const bound = bind(children);
  const single = controls.length === 1;
  return React.createElement(
    "div",
    {
      className: "field",
      ...(!single ? { role: "group", "aria-labelledby": captionId } : {}),
    },
    React.createElement(
      "div",
      { className: "field-label" },
      React.createElement(
        single ? "label" : "span",
        {
          id: captionId,
          ...(single ? { htmlFor: controls[0] } : {}),
        },
        title,
      ),
      help && Help ? React.createElement(Help, { text: help }) : null,
    ),
    help
      ? React.createElement("span", { className: "sr-only", id: helpId }, help)
      : null,
    bound,
  );
}

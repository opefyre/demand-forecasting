import {t as uiText} from './localization.mjs';
import React, { useEffect, useState } from "react";
import { Plus, ArrowLeft } from "@phosphor-icons/react";
import {Panel,Stack,Grid,Actions,FieldGroup,Disclosure} from './ui-layout.jsx';

const blankRule = () => ({
  sku: "",
  from_unit: "",
  to_unit: "",
  factor: "",
  valid_from: "",
  valid_to: "",
  source: "",
});
const draftKey = "demandlab.unitDefinitionsDraft";
function readDraft() {
  try {
    const value = JSON.parse(localStorage.getItem(draftKey) || "null");
    return Array.isArray(value?.rules) ? { ...value, reviewed: false } : null;
  } catch {
    return null;
  }
}
export function UnitSettings({ ui, api, fmt, date }) {
  const { Button, Field, Pick, Table, ErrorBox } = ui;
  const [versions, setVersions] = useState([]),
    [standard, setStandard] = useState([]),
    [selected, setSelected] = useState(""),
    [form, setForm] = useState(readDraft),
    [busy, setBusy] = useState(true),
    [error, setError] = useState("");
  useEffect(() => {
    try {
      if (form) localStorage.setItem(draftKey, JSON.stringify(form));
      else localStorage.removeItem(draftKey);
    } catch {}
  }, [form]);
  useEffect(() => {
    api("/api/units")
      .then((r) => {
        setVersions(r.versions);
        setStandard(r.standard_labels);
      })
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }, []);
  const version = versions.find((v) => v.id === selected);
  const change = (key, value) =>
    setForm((f) => ({ ...f, [key]: value, reviewed: false }));
  const editRule = (i, key, value) =>
    change(
      "rules",
      form.rules.map((r, j) => (j === i ? { ...r, [key]: value } : r)),
    );
  const start = (base) => {
    setError("");
    setForm({
      name: base?.name || "",
      classification: base?.classification || "user_provided",
      parent_id: base?.id || null,
      reviewer: "",
      reviewed: false,
      rules: base ? base.rules.map((r) => ({ ...r })) : [blankRule()],
    });
  };
  return (
    <Panel title={uiText("Product units")} description={uiText("Convert input quantities to your forecast unit.")} actions={!form && (
          <Button onClick={() => start()} disabled={busy}>
            <Plus size={18} />{uiText("Add definitions")}</Button>
        )}>
      <ErrorBox error={error} />
      {busy && <p role="status">{uiText("Loading…")}</p>}
      {!form && (
        <>
          {versions.length > 0 && (
            <Field title={uiText("Saved version")}>
              <Pick
                label={uiText("Unit definition version")}
                value={selected}
                onChange={setSelected}
                options={[
                  ["", uiText("Choose a version")],
                  ...versions.map((v) => [
                    v.id,
                    `${v.name} · ${date(v.created_at, true)}`,
                  ]),
                ]}
              />
            </Field>
          )}
          {version && (
            <>
              <Table
                headers={[uiText("Product"), uiText("Conversion"), uiText("Valid from"), uiText("Definition reference")]}
              >
                {version.rules.map((r, i) => (
                  <tr key={i}>
                    <td>{r.sku}</td>
                    <td>
                      1 {r.from_unit} = {fmt(r.factor, 6)} {r.to_unit}
                    </td>
                    <td>
                      {date(r.valid_from, true)} –{" "}
                      {r.valid_to ? date(r.valid_to, true) : uiText("No end date")}
                    </td>
                    <td className="ui-table-note">{r.source}</td>
                  </tr>
                ))}
              </Table>
              <Actions>
                <span className="ui-panel-description">{uiText("Reviewed by")}{' '}{version.reviewer}{uiText(". Saved versions never change.")}</span>
                <Button onClick={() => start(version)}>{uiText("Create revised version")}</Button>
              </Actions>
            </>
          )}
          <Disclosure title={uiText("Which units convert automatically?")}>
            <p className="ui-panel-description">{uiText("Compatible physical units use Pint:")}{' '}{standard.join(", ")}{uiText(". Other labels need an exact product definition. No translations or packaging sizes are assumed.")}</p>
          </Disclosure>
        </>
      )}
      {form && (
        <Stack as="form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const saved = await api("/api/units", form);
              setVersions((v) => [saved, ...v]);
              setSelected(saved.id);
              setForm(null);
            } catch (e) {
              setError(e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <Grid>
            <Field title={uiText("Definition set name")}>
              <input
                aria-label={uiText("Definition set name")}
                required
                value={form.name}
                onChange={(e) => change("name", e.target.value)}
              />
            </Field>
            <Field title={uiText("Data type")}>
              <Pick
                label={uiText("Unit definition data type")}
                value={form.classification}
                disabled={!!form.parent_id}
                onChange={(v) => change("classification", v)}
                options={[
                  ["user_provided", uiText("Real product definitions")],
                  ["synthetic_sample", uiText("Sample definitions")],
                ]}
              />
            </Field>
          </Grid>
          {form.rules.map((r, i) => (
            <FieldGroup title={`${uiText("Definition")} ${i + 1}`} key={i}>
              <Grid>
                <Field
                  title={uiText("Product code")}
                  help={uiText("Use the exact product code from your sales data.")}
                >
                  <input
                    aria-label={`Product code ${i + 1}`}
                    required
                    value={r.sku}
                    onChange={(e) => editRule(i, "sku", e.target.value)}
                  />
                </Field>
                <Field
                  title={uiText("Definition reference")}
                  help={uiText("For example: a dated product specification or confirmed packing standard.")}
                >
                  <input
                    aria-label={`Reference ${i + 1}`}
                    required
                    value={r.source}
                    onChange={(e) => editRule(i, "source", e.target.value)}
                  />
                </Field>
              </Grid>
              <Grid columns={3}>
                <Field title={uiText("One input unit")}>
                  <input
                    aria-label={`${uiText("One input unit")} ${i + 1}`}
                    required
                    value={r.from_unit}
                    onChange={(e) => editRule(i, "from_unit", e.target.value)}
                  />
                </Field>
                <Field title={uiText("Quantity")}>
                  <input
                    aria-label={`Conversion quantity ${i + 1}`}
                    type="number"
                    min="0"
                    step="any"
                    required
                    value={r.factor}
                    onChange={(e) => editRule(i, "factor", e.target.value)}
                  />
                </Field>
                <Field title={uiText("Demand unit")}>
                  <input
                    aria-label={`Demand unit ${i + 1}`}
                    required
                    value={r.to_unit}
                    onChange={(e) => editRule(i, "to_unit", e.target.value)}
                  />
                </Field>
              </Grid>
              <Grid>
                <Field title={uiText("Valid from")}>
                  <input
                    aria-label={`Valid from ${i + 1}`}
                    type="date"
                    required
                    value={r.valid_from}
                    onInput={(e) => editRule(i, "valid_from", e.target.value)}
                    onChange={(e) => editRule(i, "valid_from", e.target.value)}
                  />
                </Field>
                <Field title={uiText("Through (optional)")}>
                  <input
                    aria-label={`Valid through ${i + 1}`}
                    type="date"
                    value={r.valid_to}
                    onInput={(e) => editRule(i, "valid_to", e.target.value)}
                    onChange={(e) => editRule(i, "valid_to", e.target.value)}
                  />
                </Field>
              </Grid>
              {form.rules.length > 1 && (
                <Button
                  type="button"
                  onClick={() =>
                    change(
                      "rules",
                      form.rules.filter((_, j) => i !== j),
                    )
                  }
                >{uiText("Remove definition")}{i + 1}
                </Button>
              )}
            </FieldGroup>
          ))}
          <Button
            type="button"
            onClick={() => change("rules", [...form.rules, blankRule()])}
          >
            <Plus size={18} />{uiText("Add another product")}</Button>
          <Field title={uiText("Reviewed by")}>
            <input
              aria-label={uiText("Unit definitions reviewed by")}
              required
              value={form.reviewer}
              onChange={(e) => change("reviewer", e.target.value)}
            />
          </Field>
          <label className="ui-check">
            <input
              type="checkbox"
              checked={form.reviewed}
              onChange={(e) => setForm({ ...form, reviewed: e.target.checked })}
            />{uiText("I checked the product codes, conversion direction, quantities and dates.")}</label>
          <Actions>
            <Button
              type="button"
              disabled={busy}
              onClick={() => {
                setForm(null);
                setError("");
              }}
            >
              <ArrowLeft size={18} />{uiText("Cancel")}</Button>
            <Button kind="primary" disabled={busy || !form.reviewed}>
              {busy ? uiText("Saving…") : uiText("Save new version")}
            </Button>
          </Actions>
        </Stack>
      )}
    </Panel>
  );
}

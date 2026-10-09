import {localState} from './workspace-storage.mjs';
import {t as uiText} from './localization.mjs';
import React, { useEffect, useRef, useState } from "react";

const keyOf = (factor, item, period) => JSON.stringify([factor, item, period]);
const nameOf = (value) => value.replace(/_synthetic$/, "").replaceAll("_", " ");

export function AssumptionEditor({
  run,
  api,
  ui,
  onCancel,
  onSave,
  fmt,
  date,
}) {
  const { Button, Field, Pick, Table, ErrorBox } = ui;
  const draftKey = `demandlab.assumptions.${run.run_id}`;
  const [draft] = useState(() => {
    try {
      return JSON.parse(localState.getItem(draftKey) || "{}");
    } catch {
      return {};
    }
  });
  const [preview, setPreview] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [factor, setFactor] = useState(""),
    [item, setItem] = useState("all");
  const [changes, setChanges] = useState(draft.changes || {}),
    [definitions, setDefinitions] = useState(draft.definitions || {});
  const [form, setForm] = useState({
    name: "",
    owner: "",
    reason: "",
    ...draft.form,
    reviewed: false,
  });
  const request = useRef(draft.request_id || null);
  useEffect(() => {
    localState.setItem(
      draftKey,
      JSON.stringify({
        changes,
        definitions,
        form,
        request_id: request.current,
      }),
    );
  }, [changes, definitions, form]);
  useEffect(() => {
    let live = true;
    api(`/api/runs/${run.run_id}/assumptions`)
      .then((data) => {
        if (live) {
          setPreview(data);
          setFactor(data.factors[0] || "");
        }
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [run.run_id]);
  function invalidate() {
    request.current = null;
    setForm((previous) => ({ ...previous, reviewed: false }));
  }
  function edit(period, value) {
    invalidate();
    setChanges((previous) => {
      const next = { ...previous };
      for (const row of preview.rows.filter(
        (r) => r.timestamp === period && (item === "all" || r.item_id === item),
      )) {
        const key = keyOf(factor, row.item_id, period);
        if (value === "") delete next[key];
        else next[key] = value;
      }
      return next;
    });
  }
  function describe(field, value) {
    invalidate();
    setDefinitions((previous) => ({
      ...previous,
      [factor]: { ...previous[factor], [field]: value },
    }));
  }
  const rows = (preview?.rows || []).filter(
    (row) => item === "all" || row.item_id === item,
  );
  const periods = [...new Set(rows.map((row) => row.timestamp))].sort();
  const edited = Object.entries(changes).filter(([key, value]) => {
    const [f, i, p] = JSON.parse(key);
    return (
      Number(value) !==
      Number(
        preview?.rows.find((r) => r.item_id === i && r.timestamp === p)?.[f],
      )
    );
  });
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const values = edited.map(([key, value]) => {
        const [factor, item_id, period] = JSON.parse(key);
        if (!value.trim() || !Number.isFinite(Number(value)))
          throw new Error("Enter a valid number for every changed value.");
        return { factor, item_id, period, value: Number(value) };
      });
      const factors = [...new Set(values.map((row) => row.factor))];
      if (!factors.length) throw new Error("Change at least one future value.");
      const payload = {
        ...form,
        changes: values,
        definitions: factors.map((factor) => ({
          factor,
          ...definitions[factor],
        })),
        request_id: request.current || crypto.randomUUID(),
      };
      request.current = payload.request_id;
      localState.setItem(
        draftKey,
        JSON.stringify({
          changes,
          definitions,
          form,
          request_id: request.current,
        }),
      );
      const saved = await api(`/api/runs/${run.run_id}/assumptions`, payload);
      await onSave(saved);
      localState.removeItem(draftKey);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="surface assumption-editor">
      <div className="section-heading">
        <div>
          <h2>{uiText("Change future inputs")}</h2>
          <p>{uiText("Keep the history and method. Change only the assumptions you want to test.")}</p>
        </div>
        <Button onClick={onCancel} disabled={busy}>{uiText("Back to scenarios")}</Button>
      </div>
      <ErrorBox error={error} />
      {!preview && !error && <p>{uiText("Loading baseline inputs…")}</p>}
      {preview && factor && (
        <form onSubmit={submit}>
          <div className="form-grid">
            <Field title={uiText("Factor")}>
              <Pick
                label={uiText("Scenario factor")}
                value={factor}
                options={preview.factors.map((f) => [f, nameOf(f)])}
                onChange={setFactor}
              />
            </Field>
            <Field title={uiText("Applies to")}>
              <Pick
                label={uiText("Assumption items")}
                value={item}
                options={[
                  ["all", uiText("All forecast items")],
                  ...preview.items.map((i) => [i, i]),
                ]}
                onChange={setItem}
              />
            </Field>
          </div>
          <div className="form-grid">
            <Field
              title={uiText("Unit")}
              help={uiText("Use exactly the unit of the original factor. This does not convert values. For exchange rates, specify the currency direction and rial or toman.")}
            >
              <input
                aria-label={uiText("Assumption unit")}
                value={definitions[factor]?.unit || ""}
                onChange={(e) => describe("unit", e.target.value)}
              />
            </Field>
            <Field
              title={uiText("Location or market")}
              help={uiText("State where this assumption applies: the plant, Tehran, Iran, a named exchange-rate market, a trade corridor or a global market.")}
            >
              <input
                aria-label={uiText("Assumption location")}
                value={definitions[factor]?.geography || ""}
                onChange={(e) => describe("geography", e.target.value)}
              />
            </Field>
          </div>
          <Field
            title={uiText("Source")}
            help={uiText("A source URL, supplier quote, internal plan or explicit planning assumption. A typed source is not independently verified by the app.")}
          >
            <input
              aria-label={uiText("Assumption source")}
              value={definitions[factor]?.source || ""}
              onChange={(e) => describe("source", e.target.value)}
            />
          </Field>
          <Table headers={[uiText("Period"), uiText("Baseline"), uiText("Your assumption")]}>
            {periods.map((period) => {
              const group = rows.filter((r) => r.timestamp === period);
              const baseline = group.map((r) => Number(r[factor]));
              const current = group.map(
                (r) => changes[keyOf(factor, r.item_id, period)] ?? "",
              );
              const common = current.every((v) => v === current[0]);
              return (
                <tr key={period}>
                  <td>{date(period)}</td>
                  <td>
                    {Math.min(...baseline) === Math.max(...baseline)
                      ? fmt(baseline[0], 2)
                      : `${fmt(Math.min(...baseline), 2)} – ${fmt(Math.max(...baseline), 2)}`}
                  </td>
                  <td>
                    <input
                      className="assumption-number"
                      aria-label={`Assumption for ${period}`}
                      type="number"
                      step="any"
                      value={common ? current[0] : ""}
                      placeholder={
                        common ? uiText("Unchanged") : uiText("Different item values")
                      }
                      onChange={(e) => edit(period, e.target.value)}
                    />
                  </td>
                </tr>
              );
            })}
          </Table>
          <p className="muted">{uiText("Blank means unchanged.")}{" "}
            {item === "all"
              ? uiText("A number here applies to every selected item for that period.")
              : ""}
          </p>
          {edited.length > 0 && (
            <details className="help-details">
              <summary>
                {edited.length}{' '}{uiText("changed values across")}{" "}
                {[...new Set(edited.map(([key]) => JSON.parse(key)[0]))].length}{" "}{uiText("factors")}</summary>
              <p>
                {[...new Set(edited.map(([key]) => JSON.parse(key)[0]))]
                  .map(nameOf)
                  .join(", ")}
              </p>
            </details>
          )}
          <div className="form-grid">
            <Field title={uiText("Scenario name")}>
              <input
                aria-label={uiText("Factor scenario name")}
                required
                minLength={2}
                maxLength={120}
                value={form.name}
                onChange={(e) => {
                  invalidate();
                  setForm((p) => ({ ...p, name: e.target.value }));
                }}
              />
            </Field>
            <Field title={uiText("Owner")}>
              <input
                aria-label={uiText("Factor scenario owner")}
                required
                minLength={2}
                value={form.owner}
                onChange={(e) => {
                  invalidate();
                  setForm((p) => ({ ...p, owner: e.target.value }));
                }}
              />
            </Field>
          </div>
          <Field title={uiText("Why are these values changing?")}>
            <textarea
              aria-label={uiText("Assumption reason")}
              required
              minLength={2}
              maxLength={500}
              value={form.reason}
              onChange={(e) => {
                invalidate();
                setForm((p) => ({ ...p, reason: e.target.value }));
              }}
            />
          </Field>
          <label className="check-line">
            <input
              type="checkbox"
              checked={form.reviewed}
              onChange={(e) => {
                setForm((p) => ({ ...p, reviewed: e.target.checked }));
              }}
            />{uiText("I checked the values, units, locations and sources. These are assumptions, not confirmed future observations.")}</label>
          {!!preview.warnings.length && (
            <details className="help-details">
              <summary>{uiText("Assumptions already used in the baseline")}</summary>
              {preview.warnings.map((warning, i) => (
                <p key={i}>{warning}</p>
              ))}
            </details>
          )}
          <p className="muted">{uiText("The chosen method may ignore a factor. A changed input does not guarantee a changed forecast, and the result does not prove cause and effect.")}</p>
          <div className="dialog-actions">
            <Button
              type="submit"
              kind="primary"
              disabled={busy || !form.reviewed || !edited.length}
            >
              {busy ? uiText("Saving and starting…") : uiText("Calculate comparison")}
            </Button>
          </div>
        </form>
      )}
      {preview && !factor && (
        <p>{uiText("No numeric factors are available to change. Add them to the saved data and create a baseline first.")}</p>
      )}
    </section>
  );
}

export function AssumptionEvidence({ scenario, ui, fmt, date }) {
  const { Table } = ui;
  if (scenario?.type !== "factor_assumptions") return null;
  return (
    <details className="surface disclosure">
      <summary>{uiText("Assumptions used in this scenario")}</summary>
      <div className="detail-body">
        <p>{scenario.reason}</p>
        <p className="muted">{uiText("Recorded by")}{scenario.owner} · {date(scenario.recorded_at)}{uiText(". Owner is self-declared.")}</p>
        <Table headers={[uiText("Factor"), uiText("Unit"), uiText("Location / market"), uiText("Source")]}>
          {scenario.definitions.map((d) => (
            <tr key={d.factor}>
              <td>{nameOf(d.factor)}</td>
              <td>{d.unit}</td>
              <td>{d.geography}</td>
              <td>{d.source}</td>
            </tr>
          ))}
        </Table>
        <Table headers={[uiText("Item"), uiText("Period"), uiText("Factor"), uiText("Baseline"), uiText("Assumption")]}>
          {scenario.changes.slice(0, 100).map((c, i) => (
            <tr key={i}>
              <td>{c.item_id}</td>
              <td>{date(c.period)}</td>
              <td>{nameOf(c.factor)}</td>
              <td>{fmt(c.baseline_value, 2)}</td>
              <td>{fmt(c.value, 2)}</td>
            </tr>
          ))}
        </Table>
        {scenario.changes.length > 100 && (
          <p>{uiText("Showing 100 of")}{scenario.changes.length}{uiText("changes. The export includes every change.")}</p>
        )}
      </div>
    </details>
  );
}

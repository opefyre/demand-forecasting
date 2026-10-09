import {t as uiText} from './localization.mjs';
import React, { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, UploadSimple } from "@phosphor-icons/react";

export function ActualResults({ ui, api, run, plans, fmt, date, importNew }) {
  const { Button, Pick, Field, Table, ErrorBox, Help } = ui;
  const [saved, setSaved] = useState([]),
    [result, setResult] = useState(null),
    [editing, setEditing] = useState(false),
    [step, setStep] = useState(0),
    [source, setSource] = useState(null),
    [preview, setPreview] = useState(null),
    [form, setForm] = useState({
      mapping: {},
      unit: "",
      closed_through: "",
      classification: run.source_classification || "user_provided",
      owner: "",
      plan_id: "",
      reviewed: false,
      accept_partial: false,
      header_row: 1,
      calendar: 'gregorian',
    }),
    [review, setReview] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(true),
    [dimension, setDimension] = useState("item_id");
  const file = useRef(),
    top = useRef();
  const draftKey = `demandlab.actuals.${run.run_id}`;
  const restored = useRef(false);
  const load = () =>
    api(`/api/actuals/${run.run_id}`).then((r) => {
      setSaved(r.evaluations);
      return r.evaluations;
    });
  useEffect(() => {
    let live = true;
    load()
      .then(
        (rows) =>
          rows[0] &&
          api(`/api/actual-results/${rows[0].id}`).then((r) => {
            if (live) setResult(r);
          }),
      )
      .catch((e) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setBusy(false);
      });
    try {
      const draft = JSON.parse(localStorage.getItem(draftKey) || "null");
      if (draft) {
        setSource(draft.source);
        setPreview(draft.preview);
        setForm(draft.form);
      }
    } catch {}
    restored.current = true;
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    if (restored.current && source)
      localStorage.setItem(draftKey, JSON.stringify({ source, preview, form }));
  }, [source, preview, form]);
  useEffect(() => {
    if (editing || result) top.current?.scrollIntoView({ block: "start" });
  }, [step, error, result?.id]);
  const change = (key, value) => {
    setForm((f) => ({
      ...f,
      [key]: value,
      reviewed: false,
      accept_partial: false,
      request_id: crypto.randomUUID(),
    }));
    setReview(null);
  };
  async function upload(e) {
    const incoming = e.target.files?.[0];
    if (!incoming) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", incoming);
      const s = await api("/api/actuals/sources", body);
      setSource(s);
      setPreview(s.preview);
      setForm((f) => ({
        ...f,
        source_id: s.id,
        request_id: crypto.randomUUID(),
        sheet: s.preview.sheet || "",
        header_row: 1,
        mapping: {},
        reviewed: false,
        accept_partial: false,
      }));
      setReview(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }
  async function next() {
    setBusy(true);
    setError("");
    try {
      if (step === 0) {
        const p = await api(`/api/actuals/sources/${source.id}/preview`, {
          sheet: form.sheet,
          header_row: form.header_row,
        });
        if (!p.columns.length)
          throw new Error("Choose the row containing the column names.");
        const choose = (regex) =>
          p.columns.find((c) => regex.test(c.label))?.id || "";
        if (
          !Object.keys(form.mapping).length ||
          p.sheet !== preview.sheet ||
          p.header_row !== preview.header_row
        )
          change("mapping", {
            item_id: choose(/^item_id$|^item$|series/i),
            timestamp: choose(/^timestamp$|^date$|period|month/i),
            actual: choose(/^actual$|quantity|sales|demand/i),
          });
        setPreview(p);
        setStep(1);
      } else {
        setReview(await api(`/api/actuals/${run.run_id}/review`, form));
        setStep(2);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    setBusy(true);
    setError("");
    try {
      const r = await api(`/api/actuals/${run.run_id}`, form);
      setResult(r);
      await load();
      setEditing(false);
      setSource(null);
      setReview(null);
      localStorage.removeItem(draftKey);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const percent = (n) => (n == null ? "Not available" : `${fmt(n)}%`);
  const planOptions = [
    ["", "Forecast only"],
    ...plans
      .filter(
        (p) =>
          p.run_id === run.run_id &&
          ["approved", "published"].includes(p.status),
      )
      .map((p) => [p.id, p.name]),
  ];
  const options = [
    ["", "Choose column"],
    ...(preview?.columns || []).map((c) => [c.id, `${c.id} · ${c.label}`]),
  ];
  const example = (key) =>
    (preview?.rows || [])
      .slice(0, 3)
      .map((r) => r.values[form.mapping[key]])
      .filter((v) => v !== undefined && v !== "")
      .join(" · ");
  if (editing)
    return (
      <section className="actual-import" ref={top}>
        <button
          className="back-link"
          onClick={() => {
            setEditing(false);
            setError("");
          }}
        >
          <ArrowLeft size={16} />{uiText("Actual results")}</button>
        <div className="section-heading">
          <h2>{uiText("Compare with actuals")}</h2>
          <span className="muted">
            {step + 1}{' '}{uiText("of 3 ·")}{" "}
            {["Choose file", "Match and confirm", "Review results"][step]}
          </span>
        </div>
        <ErrorBox error={error} />
        <section className="surface inventory-form">
          {step === 0 ? (
            <>
              <input
                ref={file}
                type="file"
                hidden
                accept=".csv,.tsv,.xlsx,.xlsm,.json"
                onChange={upload}
              />
              <div className="section-heading">
                <div>
                  <strong>{source?.name || "Actual sales or demand"}</strong>
                  <p className="muted">{uiText("One total per forecast item and period.")}</p>
                </div>
                <Button disabled={busy} onClick={() => file.current.click()}>
                  <UploadSimple size={18} />
                  {source ? uiText("Replace file") : uiText("Choose actuals file")}
                </Button>
              </div>
              {source && (
                <div className="field-grid">
                  {source.preview.sheets.length > 0 && (
                    <Field title={uiText("Worksheet")}>
                      <Pick
                        label={uiText("Actuals worksheet")}
                        value={form.sheet}
                        options={source.preview.sheets.map((s) => [s, s])}
                        onChange={(v) => change("sheet", v)}
                      />
                    </Field>
                  )}
                  <Field title={uiText("Heading row")}>
                    <input
                      aria-label={uiText("Actuals heading row")}
                      type="number"
                      min="1"
                      max="200"
                      value={form.header_row}
                      onChange={(e) =>
                        change("header_row", Number(e.target.value))
                      }
                    />
                  </Field>
                </div>
              )}
            </>
          ) : step === 1 ? (
            <>
              <div className="field-grid">
                <Field title={uiText("Dates in the file")} help={uiText("Match the file’s calendar. The forecast’s planning months stay unchanged.")}>
                  <Pick label={uiText("Actual-results date calendar")} value={form.calendar||'gregorian'} options={[["gregorian",uiText("Gregorian")],["jalali",uiText("Persian (Jalali)")]]} onChange={v=>change('calendar',v)}/>
                </Field>
                {[
                  ["item_id", "Forecast item"],
                  ["timestamp", "Period start"],
                  ["actual", "Actual quantity"],
                ].map(([key, title]) => (
                  <Field
                    key={key}
                    title={title}
                    help={
                      key === "item_id"
                        ? uiText("Use the exact item IDs from your forecast export, including customer or location where present.")
                        : key === "timestamp"
                          ? uiText("Use YYYY-MM-DD in the selected calendar. Supply the exact start date shown in the forecast export; dates are not automatically shifted.")
                          : undefined
                    }
                  >
                    <Pick
                      label={title}
                      value={form.mapping[key] || ""}
                      options={options}
                      onChange={(v) =>
                        change("mapping", { ...form.mapping, [key]: v })
                      }
                    />
                    <small className="mapping-example">
                      {example(key) || "No example selected"}
                    </small>
                  </Field>
                ))}
                <Field
                  title={uiText("Confirmed quantity unit")}
                  help={`This forecast uses ${run.unit}. Actuals must use the same unit; there is no automatic conversion.`}
                >
                  <input
                    aria-label={uiText("Actuals quantity unit")}
                    value={form.unit}
                    placeholder={run.unit}
                    onChange={(e) => change("unit", e.target.value)}
                  />
                </Field>
                <Field
                  title={uiText("Closed through (Gregorian date)")}
                  help={uiText("The last fully completed period end. Missing item totals will be listed before saving.")}
                >
                  <input
                    aria-label={uiText("Actuals closed through")}
                    type="date"
                    value={form.closed_through}
                    onInput={(e) =>
                      change("closed_through", e.currentTarget.value)
                    }
                    onChange={(e) => change("closed_through", e.target.value)}
                  />
                </Field>
                <Field title={uiText("Compare plan")}>
                  <Pick
                    label={uiText("Plan for actual comparison")}
                    value={form.plan_id}
                    options={planOptions}
                    onChange={(v) => change("plan_id", v)}
                  />
                </Field>
                <Field title={uiText("Reviewed by")}>
                  <input
                    aria-label={uiText("Actuals reviewer")}
                    value={form.owner}
                    onChange={(e) => change("owner", e.target.value)}
                    placeholder={uiText("Your name")}
                  />
                </Field>
              </div>
              <details className="help-details">
                <summary>{uiText("Exact item IDs")}</summary>
                <p className="muted">{run.items?.slice(0, 10).join(" · ")}</p>
                <a className="text-link" href={`/api/export/${run.run_id}/csv`}>{uiText("Download forecast with item IDs")}</a>
              </details>
            </>
          ) : (
            review && (
              <>
                <h3>
                  {review.coverage.matched}{' '}{uiText("of")}{' '}{review.coverage.expected}{" "}{uiText("expected results supplied")}</h3>
                {review.warnings.map((w, i) => (
                  <p className="muted" key={i}>
                    {w}
                  </p>
                ))}
                {review.issue_count > 0 && (
                  <>
                    <h3>{review.issue_count}{' '}{uiText("issues to resolve")}</h3>
                    <Table headers={[uiText("Source cell"), uiText("What needs attention")]}>
                      {review.issues.map((r, i) => (
                        <tr key={i}>
                          <td>{r.cell}</td>
                          <td>{r.message}</td>
                        </tr>
                      ))}
                    </Table>
                  </>
                )}
                <Table headers={[uiText("Item"), uiText("Period"), uiText("Actual"), uiText("Forecast")]}>
                  {review.rows.slice(0, 10).map((r) => (
                    <tr key={`${r.item_id}/${r.period}`}>
                      <td>{r.item_id}</td>
                      <td>{date(r.period)}</td>
                      <td>{fmt(r.actual)}</td>
                      <td>{fmt(r.forecast)}</td>
                    </tr>
                  ))}
                </Table>
                {review.coverage.matched > 10 && (
                  <p className="footnote">{uiText("Showing the first 10 matched rows. All")}{" "}
                    {review.coverage.matched}{uiText("will be saved.")}</p>
                )}
                {review.coverage.missing > 0 && (
                  <>
                    <details className="help-details">
                      <summary>{uiText("Missing results")}</summary>
                      <Table headers={[uiText("Item"), uiText("Period")]}>
                        {review.coverage.missing_keys.map((r) => (
                          <tr key={`${r.item_id}/${r.period}`}>
                            <td>{r.item_id}</td>
                            <td>{date(r.period)}</td>
                          </tr>
                        ))}
                      </Table>
                    </details>
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={form.accept_partial}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            accept_partial: e.target.checked,
                          }))
                        }
                      />{uiText("Save a partial comparison; missing results remain unknown.")}</label>
                  </>
                )}
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={form.reviewed}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, reviewed: e.target.checked }))
                    }
                  />{uiText("These are reviewed actual totals for fully closed periods, in the stated units.")}</label>
              </>
            )
          )}
          <div className="inventory-actions">
            {step > 0 && (
              <Button disabled={busy} onClick={() => setStep(step - 1)}>{uiText("Back")}</Button>
            )}
            {step < 2 ? (
              <Button kind="primary" disabled={busy || !source} onClick={next}>
                {busy
                  ? uiText("Reading…")
                  : step === 0
                    ? uiText("Match columns")
                    : uiText("Review results")}
                <ArrowRight size={16} />
              </Button>
            ) : (
              <Button
                kind="primary"
                disabled={
                  busy ||
                  !form.reviewed ||
                  !form.owner.trim() ||
                  review?.issue_count > 0 ||
                  (review?.coverage.missing > 0 && !form.accept_partial)
                }
                onClick={save}
              >
                {busy ? uiText("Saving…") : uiText("Save comparison")}
              </Button>
            )}
          </div>
        </section>
      </section>
    );
  return (
    <section className="actual-results" ref={top}>
      <div className="section-heading">
        <div>
          <h2>{uiText("Actual results")}</h2>
          <p>{uiText("Compare this forecast with completed sales or demand.")}</p>
        </div>
        <Button
          kind="primary"
          disabled={busy}
          onClick={() => {
            setEditing(true);
            setStep(0);
            setError("");
          }}
        >
          {source ? uiText("Resume actuals import") : uiText("Add actual results")}
          <ArrowRight size={16} />
        </Button>
      </div>
      <ErrorBox error={error} />
      {saved.length > 0 && (
        <div className="view-toolbar">
          <Pick
            label={uiText("Saved actual comparison")}
            disabled={busy}
            value={result?.id || ""}
            options={saved.map((s) => [
              s.id,
              `${date(s.closed_through, true)} · ${s.plan?.name || "Forecast only"} · ${date(s.created_at, true)}`,
            ])}
            onChange={(id) => {
              setBusy(true);
              setError("");
              api(`/api/actual-results/${id}`)
                .then(setResult)
                .catch((e) => setError(e.message))
                .finally(() => setBusy(false));
            }}
          />
        </div>
      )}
      {busy && <p role="status">{uiText("Loading comparison…")}</p>}
      {busy ? null : !result ? (
        <section className="surface actual-empty">
          <h3>{uiText("No actual results yet")}</h3>
          <p className="muted">{uiText("Historical tests help choose a method. Actual results show what happened after a forecast was made.")}</p>
        </section>
      ) : (
        <>
          <div className="accuracy-summary surface">
            <div>
              <span>{uiText("Recorded forecast error")}<Help text={uiText("Total absolute error divided by total actual demand, across supplied records only. Undefined when actual demand totals zero. Timing checks below distinguish prospective evidence from diagnostics.")} />
              </span>
              <strong>{percent(result.diagnostic.wape_pct)}</strong>
            </div>
            <div>
              <span>{uiText("Bias")}<Help text={uiText("Forecast total minus actual total, divided by actual total. Positive means the forecast was too high.")} />
              </span>
              <strong>{percent(result.diagnostic.bias_pct)}</strong>
            </div>
            <div>
              <span>{uiText("Results supplied")}</span>
              <strong>
                {result.coverage.matched} / {result.coverage.expected}
              </strong>
            </div>
          </div>
          <section className="surface actual-evidence">
            <h3>
              {result.classification === "synthetic_sample"
                ? uiText("Sample comparison")
                : result.prospective.observations ===
                    result.diagnostic.observations
                  ? uiText("Forward-looking check")
                  : uiText("Timing needs attention")}
            </h3>
            {result.diagnostic.observations >
              result.prospective.observations && (
              <p className="muted">
                {result.diagnostic.observations -
                  result.prospective.observations}{" "}{uiText("results have late or undated forecasts. Their errors are diagnostic only.")}</p>
            )}
            {result.coverage.missing > 0 && (
              <p className="muted">
                {result.coverage.missing}{uiText("missing results are excluded, not counted as zero.")}</p>
            )}
            <p>
              {result.prospective.observations}{uiText("results have a forecast issued before their period started.")}{result.prospective.observations > 0 && (
                <>
                  {" "}{uiText("Error on those results:")}{percent(result.prospective.wape_pct)}
                  .
                </>
              )}
            </p>
            {result.plan && (
              <p>{uiText("Plan:")}<strong>{result.plan.name}</strong>.{" "}
                {result.paired_baseline.observations}{' '}{uiText("eligible paired results.")}{" "}
                {result.improvement_points == null ? (
                  uiText("Not enough dated evidence to measure whether adjustments helped.")
                ) : (
                  <>{uiText("Adjustments")}{" "}
                    {result.improvement_points >= 0 ? uiText("reduced") : uiText("increased")}{" "}{uiText("error by")}{fmt(Math.abs(result.improvement_points))}{" "}{uiText("percentage points (")}{percent(result.paired_baseline.wape_pct)} →{" "}
                    {percent(result.paired_approved.wape_pct)}).
                  </>
                )}
              </p>
            )}
          </section>
          <div className="view-toolbar">
            <Pick
              label={uiText("Group actual results by")}
              value={dimension}
              options={[
                ["item_id", uiText("By item")],
                ["period", uiText("By period")],
                ["horizon_step", uiText("By forecast month / step")],
                ["category", uiText("By product family")],
                ["customer", uiText("By customer")],
              ]}
              onChange={setDimension}
            />
          </div>
          <section className="surface">
            <Table
              headers={[
                uiText("Group"),
                `Actual (${result.unit})`,
                uiText("Forecast"),
                uiText("Absolute error"),
                uiText("Error %"),
              ]}
            >
              {[...(result.breakdowns[dimension] || [])]
                .sort((a, b) =>
                  dimension === "period"
                    ? String(a.key).localeCompare(String(b.key))
                    : dimension === "horizon_step"
                      ? a.key - b.key
                      : b.absolute_error - a.absolute_error,
                )
                .map((r) => (
                  <tr key={r.key}>
                    <td>
                      {dimension === "period"
                        ? date(r.key)
                        : dimension === "horizon_step"
                          ? `Step ${r.key}`
                          : r.key}
                    </td>
                    <td>{fmt(r.actual_total)}</td>
                    <td>{fmt(r.predicted_total)}</td>
                    <td>{fmt(r.absolute_error)}</td>
                    <td>{percent(r.wape_pct)}</td>
                  </tr>
                ))}
            </Table>
          </section>
          <details className="help-details">
            <summary>{uiText("Source and review")}</summary>
            {result.warnings.map((w, i) => (
              <p className="muted" key={i}>
                {w}
              </p>
            ))}
            <a
              className="text-link"
              href={`/api/actual-results/${result.id}/export`}
            >{uiText("Download compared rows")}</a>
            <p>
              {result.source.name} · {result.source.sheet || "Table"}{uiText("· closed through")}{date(result.closed_through, true)}{' '}{uiText("· reviewed by")}{" "}
              {result.config?.owner}.
            </p>
            <p className="muted">{uiText("Saved comparisons do not change when another file or plan is edited. Corrections are saved as a new comparison. Uploaded actuals are not automatically added to training data.")}</p>
          </details>
          <Button onClick={importNew}>{uiText("Update forecast inputs")}<ArrowRight size={16} />
          </Button>
        </>
      )}
    </section>
  );
}

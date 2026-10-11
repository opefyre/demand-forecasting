import {apiLink} from './company-api.mjs';
import {localState} from './workspace-storage.mjs';
import {t as uiText,unitLabel} from './localization.mjs';
import {Stack,Panel,Grid,Actions,FieldGroup,Disclosure,DefinitionList,Steps} from './ui-layout.jsx';
import {DownloadLink} from './download-link.jsx';
import {salesSeriesLabel} from './demand-view.mjs';
import React, { useEffect, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, UploadSimple } from "@phosphor-icons/react";

export function ActualResults({ ui, api, run, plans=[], fmt, date, importNew, canEdit=true, embedded=false,onWorkingChange }) {
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
    [dimension, setDimension] = useState("item_id"),[readRevision,setReadRevision]=useState(0);
  const file = useRef(),submitting=useRef(false);
  useEffect(()=>{onWorkingChange?.(busy);return()=>onWorkingChange?.(false);},[busy,onWorkingChange]);
  const draftKey = `demandlab.actuals.${run.run_id}`;
  const restored = useRef(false);
  const load = () =>
    api(`/api/actuals/${run.run_id}`).then((r) => {
      return r.evaluations;
    });
  useEffect(() => {
    let live = true;setBusy(true);setError('');
    load()
      .then(
        (rows) => {
          if(!live)return;setSaved(rows);
          return rows[0] &&
          api(`/api/actual-results/${rows[0].id}`).then((r) => {
            if (live) setResult(r);
          });},
      )
      .catch((e) => {
        if (live) setError(e);
      })
      .finally(() => {
        if (live) setBusy(false);
      });
    try {
      const draft = JSON.parse(localState.getItem(draftKey) || "null");
      if (draft&&!restored.current) {
        setSource(draft.source);
        setPreview(draft.preview);
        setForm({...draft.form,reviewed:false,accept_partial:false});
      }
    } catch {}
    restored.current = true;
    return () => {
      live = false;
    };
  }, [run.run_id,readRevision]);
  useEffect(() => {
    if (restored.current && source)try{
      localState.setItem(draftKey, JSON.stringify({ source, preview, form:{...form,reviewed:false,accept_partial:false} }));
    }catch{/* A blocked preference store must not prevent review. */}
  }, [source, preview, form]);
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
    if (!incoming||busy||!canEdit) return;
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
    if(busy||!canEdit||!source)return;
    setBusy(true);
    setError("");
    try {
      if (step === 0) {
        const p = await api(`/api/actuals/sources/${source.id}/preview`, {
          sheet: form.sheet,
          header_row: form.header_row,
        });
        if (!p.columns.length)
          throw new Error(uiText("Choose the row containing the column names."));
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
    if(submitting.current||busy||!canEdit||!review||!form.reviewed||!form.owner.trim()||review.issue_count>0||(review.coverage.missing>0&&!form.accept_partial))return;
    submitting.current=true;
    setBusy(true);
    setError("");
    try {
      const r = await api(`/api/actuals/${run.run_id}`, form);
      setResult(r);
      setEditing(false);
      setSource(null);
      setReview(null);
      localState.removeItem(draftKey);
      setSaved(await load());
    } catch (e) {
      setError(e.message);
    } finally {
      submitting.current=false;
      setBusy(false);
    }
  }
  const percent = (n) => (n == null ? uiText("Not available") : `${fmt(n)}%`);
  const planOptions = [
    ["", uiText("Forecast only")],
    ...plans
      .filter(
        (p) =>
          p.run_id === run.run_id &&
          ["approved", "published"].includes(p.status),
      )
      .map((p) => [p.id, p.name]),
  ];
  const options = [
    ["", uiText("Choose column")],
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
      <Stack step={step}>
        <Actions><Button disabled={busy}
          onClick={() => {
            setEditing(false);
            setError("");
          }}
        >
          <ArrowLeft size={16} />{uiText("Actual results")}</Button></Actions>
        <Steps current={step} label={uiText('Actual-results progress')} items={['Choose file','Match and confirm','Review results']}/>
        <ErrorBox error={error} />
        <Panel title={uiText('Compare with actuals')}><FieldGroup disabled={busy||!canEdit}>
          {step === 0 ? (
            <>
              <input
                ref={file}
                type="file"
                hidden
                accept=".csv,.tsv,.xlsx,.xlsm,.json"
                onChange={upload}
              />
              <Actions>
                <div>
                  <strong>{source?.name || uiText("Actual sales or demand")}</strong>
                  <p className="muted">{uiText("One total per forecast item and period.")}</p>
                </div>
                <Button disabled={busy} onClick={() => file.current.click()}>
                  <UploadSimple size={18} />
                  {source ? uiText("Replace file") : uiText("Choose actuals file")}
                </Button>
              </Actions>
              {source && (
                <Grid>
                  {source.preview.sheets.length > 0 && (
                    <Field title={uiText("Worksheet")}>
                      <Pick
                        disabled={busy}
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
                </Grid>
              )}
            </>
          ) : step === 1 ? (
            <>
              <Grid>
                <Field title={uiText("Dates in the file")} help={uiText("Match the file’s calendar. The forecast’s planning months stay unchanged.")}>
                  <Pick disabled={busy} label={uiText("Actual-results date calendar")} value={form.calendar||'gregorian'} options={[["gregorian",uiText("Gregorian")],["jalali",uiText("Persian (Jalali)")]]} onChange={v=>change('calendar',v)}/>
                </Field>
                {[
                  ["item_id", "Forecast item"],
                  ["timestamp", "Period start"],
                  ["actual", "Actual quantity"],
                ].map(([key, title]) => (
                  <Field
                    key={key}
                    title={uiText(title)}
                    help={
                      key === "item_id"
                        ? uiText("Use the exact item IDs from your forecast export, including customer or location where present.")
                        : key === "timestamp"
                          ? uiText("Use YYYY-MM-DD in the selected calendar. Supply the exact start date shown in the forecast export; dates are not automatically shifted.")
                          : undefined
                    }
                  >
                    <Pick
                      disabled={busy}
                      label={uiText(title)}
                      value={form.mapping[key] || ""}
                      options={options}
                      onChange={(v) =>
                        change("mapping", { ...form.mapping, [key]: v })
                      }
                    />
                    <small className="mapping-example">
                      {example(key) || uiText("No example selected")}
                    </small>
                  </Field>
                ))}
                <Field
                  title={uiText("Confirmed quantity unit")}
                  help={uiText('Actuals must use {{unit}}. There is no automatic conversion.',{unit:unitLabel(run.unit)})}
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
                    disabled={busy}
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
              </Grid>
              <Disclosure title={uiText('Exact item IDs')}>
                <p className="muted">{run.items?.slice(0, 10).join(" · ")}</p>
                <DownloadLink ui={ui} href={apiLink(`/api/export/${run.run_id}/csv`)} onError={setError}>{uiText("Download forecast with item IDs")}</DownloadLink>
              </Disclosure>
            </>
          ) : (
            review && (
              <>
                <h3>
                  {fmt(review.coverage.matched)}{' '}{uiText("of")}{' '}{fmt(review.coverage.expected)}{" "}{uiText("expected results supplied")}</h3>
                {review.warnings.map((w, i) => (
                  <p className="muted" key={i}>
                    {uiText(w)}
                  </p>
                ))}
                {review.issue_count > 0 && (
                  <>
                    <h3>{fmt(review.issue_count)}{' '}{uiText("issues to resolve")}</h3>
                    <Table headers={[uiText("Source cell"), uiText("What needs attention")]}>
                      {review.issues.map((r, i) => (
                        <tr key={i}>
                          <td>{r.cell}</td>
                          <td>{uiText(r.message)}</td>
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
                    {fmt(review.coverage.matched)}{' '}{uiText("will be saved.")}</p>
                )}
                {review.coverage.missing > 0 && (
                  <>
                    <Disclosure title={uiText('Missing results')}>
                      <Table headers={[uiText("Item"), uiText("Period")]}>
                        {review.coverage.missing_keys.map((r) => (
                          <tr key={`${r.item_id}/${r.period}`}>
                            <td>{r.item_id}</td>
                            <td>{date(r.period)}</td>
                          </tr>
                        ))}
                      </Table>
                    </Disclosure>
                    <label className="ui-check">
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
                <label className="ui-check">
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
          </FieldGroup><Actions>
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
                  !canEdit || !review ||
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
          </Actions>
        </Panel>
      </Stack>
    );
  return (
    <Stack>
      <Actions>
        {!embedded&&<div>
          <h2>{uiText("Actual results")}</h2>
          <p>{uiText("Compare this forecast with completed sales or demand.")}</p>
        </div>}
        {canEdit&&<Button
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
        </Button>}
      </Actions>
      <ErrorBox error={error} onReload={()=>setReadRevision(value=>value+1)}/>
      {saved.length > 0 && (
        <Actions>
          <Pick
            label={uiText("Saved actual comparison")}
            disabled={busy}
            value={result?.id || ""}
            options={saved.map((s) => [
              s.id,
              `${date(s.closed_through, true)} · ${s.plan?.name || uiText("Forecast only")} · ${date(s.created_at, true)}`,
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
        </Actions>
      )}
      {busy && <p role="status">{uiText("Loading comparison…")}</p>}
      {busy ? null : !result ? (
        <Panel title={uiText('No actual results yet')}>
          <p className="muted">{uiText("Historical tests help choose a method. Actual results show what happened after a forecast was made.")}</p>
        </Panel>
      ) : (
        <>
          <Panel title={uiText('Recorded forecast error')}><DefinitionList rows={[
            [<>{uiText('Recorded forecast error')}<Help text={uiText('Total absolute error divided by total actual demand, across supplied records only. Undefined when actual demand totals zero. Timing checks below distinguish prospective evidence from diagnostics.')}/></>,percent(result.diagnostic.wape_pct)],
            [<>{uiText('Bias')}<Help text={uiText('Forecast total minus actual total, divided by actual total. Positive means the forecast was too high.')}/></>,percent(result.diagnostic.bias_pct)],
            [uiText('Results supplied'),`${fmt(result.coverage.matched)} / ${fmt(result.coverage.expected)}`],
          ]}/></Panel>
          <Panel title={result.prospective.observations ===
                    result.diagnostic.observations
                  ? uiText("Forward-looking check")
                  : uiText("Timing needs attention")}>
            {result.diagnostic.observations >
              result.prospective.observations && (
              <p className="muted">
                {fmt(result.diagnostic.observations -
                  result.prospective.observations)}{" "}{uiText("results have late or undated forecasts. Their errors are diagnostic only.")}</p>
            )}
            {result.coverage.missing > 0 && (
              <p className="muted">
                {fmt(result.coverage.missing)}{' '}{uiText("missing results are excluded, not counted as zero.")}</p>
            )}
            <p>
              {fmt(result.prospective.observations)}{' '}{uiText("results have a forecast issued before their period started.")}{result.prospective.observations > 0 && (
                <>
                  {" "}{uiText("Error on those results:")}{' '}{percent(result.prospective.wape_pct)}
                  .
                </>
              )}
            </p>
            {result.plan && (
              <p>{uiText("Plan:")}<strong>{result.plan.name}</strong>.{" "}
                {fmt(result.paired_baseline.observations)}{' '}{uiText("eligible paired results.")}{" "}
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
          </Panel>
          <Actions>
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
          </Actions>
          <Panel title={uiText('Compared results')}>
            <Table
              headers={[
                uiText("Group"),
                `${uiText('Actual')} (${unitLabel(result.unit)})`,
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
                          ? `${uiText('Step')} ${fmt(r.key)}`
                          : dimension === "item_id" ? salesSeriesLabel(run,r.key) : r.key}
                    </td>
                    <td>{fmt(r.actual_total)}</td>
                    <td>{fmt(r.predicted_total)}</td>
                    <td>{fmt(r.absolute_error)}</td>
                    <td>{percent(r.wape_pct)}</td>
                  </tr>
                ))}
            </Table>
          </Panel>
          <Disclosure title={uiText('Source and review')}>
            {result.warnings.map((w, i) => (
              <p className="muted" key={i}>
                {uiText(w)}
              </p>
            ))}
            <DownloadLink ui={ui} href={apiLink(`/api/actual-results/${result.id}/export`)} onError={setError}>{uiText('Download compared rows')}</DownloadLink>
            <p>
              {result.source.name} · {result.source.sheet || uiText("Table")}{uiText("· closed through")}{date(result.closed_through, true)}{' '}{uiText("· reviewed by")}{" "}
              {result.config?.owner}.
            </p>
            <p className="muted">{uiText("Saved comparisons do not change when another file or plan is edited. Corrections are saved as a new comparison. Uploaded actuals are not automatically added to training data.")}</p>
          </Disclosure>
          {canEdit&&importNew&&<Actions><Button onClick={importNew}>{uiText("Update forecast inputs")}<ArrowRight size={16} /></Button></Actions>}
        </>
      )}
    </Stack>
  );
}

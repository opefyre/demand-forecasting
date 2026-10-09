import React, { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowClockwise,
  CheckCircle,
} from "@phosphor-icons/react";
import { FactorBatch } from "./factor-batch.jsx";
import { OrderReuse } from "./order-reuse";
import { DemandImport } from "./sales-demand";
import { orderRevision } from "./order-revision.mjs";
import { planningBasis, planningMonth } from "./planning-calendar.mjs";
import {t as uiText} from './localization.mjs';
import {Page} from './ui-layout.jsx';

const stages = ["History", "Forecast", "Factors", "Orders", "Review"];
const position = {
  history: 0,
  forecast: 1,
  calculating: 1,
  factors: 2,
  factor_calculating: 2,
  orders: 3,
  review: 4,
  ready: 4,
};
const number = (value) =>
  value == null
    ? "Not present"
    : new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(value);

export function UpdateProgress({ stage }) {
  return (
    <ol className="update-progress" aria-label={uiText("Forecast update progress")}>
      {stages.map((name, index) => (
        <li
          key={name}
          aria-current={index === position[stage] ? "step" : undefined}
          className={index < position[stage] ? "complete" : ""}
        >
          <span>
            {index < position[stage] ? <CheckCircle size={18} /> : index + 1}
          </span>
          {uiText(name)}
        </li>
      ))}
    </ol>
  );
}

export function MonthlyRefresh({
  id,
  api,
  ui,
  datasets,
  refresh,
  runDataset,
  openRun,
  navigate,
  setDataView,
  renderImport,
  canEdit,
  onClose,
}) {
  const { Button, Pick, Field, ErrorBox } = ui;
  const [session, setSession] = useState(null),
    [run, setRun] = useState(null),
    [base, setBase] = useState(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [importing, setImporting] = useState(null),
    [orders, setOrders] = useState(null);
  const [months, setMonths] = useState("6"),
    [method, setMethod] = useState("recommended"),
    [checked, setChecked] = useState(false);
  const request = useRef(null),
    alive = useRef(true);
  const [statusRevision,setStatusRevision]=useState(0);
  async function load() {
    const value = await api("/api/forecast-updates/" + id);
    if (alive.current) {setSession(value);setError('');setStatusRevision(v=>v+1);}
    return value;
  }
  useEffect(() => {
    alive.current = true;
    setSession(null);
    load().catch((e) => alive.current && setError(e));
    return () => {
      alive.current = false;
    };
  }, [id]);
  useEffect(() => {
    setChecked(false);
  }, [session?.revision]);
  useEffect(() => {
    if (!session) return;
    let live = true;
    Promise.all([
      api("/api/runs/" + session.base_run_id),
      session.run_id
        ? api("/api/runs/" + session.run_id)
        : Promise.resolve(null),
    ])
      .then(([before, after]) => {
        if (live) {
          setBase(before);
          setRun(after);
        }
      })
      .catch((e) => live && setError(e));
    if (session.stage === "forecast") {
      const settings = datasets.find(
        (d) => d.id === session.dataset_id,
      )?.settings;
      setMonths(String(settings?.horizon || 6));
      setMethod(settings?.method_selection || "recommended");
    }
    return () => {
      live = false;
    };
  }, [session?.run_id, session?.dataset_id, session?.stage,statusRevision]);
  useEffect(() => {
    if (
      !session ||
      !["calculating", "factor_calculating"].includes(session.stage)
    )
      return;
    let live = true,
      timer;
    const poll = async () => {
      try {
        const value = await api("/api/forecast-updates/" + id);
        if (live) {setSession(value);setError('');}
      } catch (e) {
        if (live) setError(e);
      } finally {
        if (live) timer = setTimeout(poll, 2500);
      }
    };
    timer = setTimeout(poll, 2500);
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [session?.stage, id]);
  async function act(action, extra = {}) {
    if (busy) return;
    setBusy(true);
    setError("");
    const body = { action, revision: session.revision, ...extra },
      signature = JSON.stringify(body);
    if (request.current?.signature !== signature)
      request.current = { signature, id: crypto.randomUUID() };
    try {
      const next = await api("/api/forecast-updates/" + id + "/steps", {
        ...body,
        request_id: request.current.id,
      });
      setSession(next);
      request.current = null;
      await refresh?.();
      return next;
    } catch (e) {
      setError(e);
      throw e;
    } finally {
      setBusy(false);
    }
  }
  // Click handlers own their errors; callbacks throw so existing forms keep their review open.
  const click = (action, extra) => () => {
    act(action, extra).catch(() => {});
  };
  async function uploadHistory() {
    setBusy(true);
    setError("");
    try {
      const source = datasets.find(
        (d) => d.id === (session.dataset_id || session.base_dataset_id),
      );
      if (!source)
        throw Error("Reload the data library to find the saved history.");
      const sourceObjects = Object.fromEntries(
        await Promise.all(
          Object.entries(source.sources).map(async ([role, key]) => [
            role,
            await api("/api/sources/" + key),
          ]),
        ),
      );
      setImporting({ ...source, sourceObjects, repeat_upload: true });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function openOrders(snapshotId) {
    setBusy(true);
    setError("");
    try {
      const initial = snapshotId
        ? orderRevision(await api("/api/sales/inputs/" + snapshotId))
        : {
            inputs: await api("/api/sales/runs/" + session.run_id + "/starter"),
          };
      setOrders(initial);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (importing)
    return renderImport({
      initial: importing,
      draftStorageKey: "demandlab.monthlyHistory." + id,
      returnLabel: "Back to forecast update",
      onCancel: () => setImporting(null),
      onSaved: async (source) => {
        await act("history", { dataset_id: source.id, reviewed: true });
        setImporting(null);
      },
    });
  if (orders && run)
    return (
      <DemandImport
        api={api}
        ui={ui}
        run={run}
        initial={orders}
        onCancel={() => setOrders(null)}
        onSaved={async (saved) => {
          await act("orders", { snapshot_id: saved.id });
          setOrders(null);
        }}
      />
    );
  if (!session)
    return (
      <div className="forecast-update">
        <ErrorBox error={error} busy={busy} onReload={async()=>{if(busy)return;setBusy(true);try{await load();}catch(e){setError(e);}finally{setBusy(false);}}}/>
        {!error&&<p role="status">{uiText('Opening forecast update…')}</p>}
        <Button onClick={onClose}>{uiText('Back to Home')}</Button>
      </div>
    );
  const stage = session.stage,
    source = datasets.find(
      (d) => d.id === (session.dataset_id || session.base_dataset_id),
    );
  const waiting = ["calculating", "factor_calculating"].includes(stage),
    job = session.job;
  const manageSources = () => {
    setDataView?.('external');
    navigate('data');
  };
  return (
    <Page title={uiText('Update forecast')} controls={<UpdateProgress stage={stage}/>} actions={<Button kind="ghost" disabled={busy} onClick={onClose}><ArrowLeft/>{uiText('Home')}</Button>}>
      <ErrorBox error={error} busy={busy} onReload={async()=>{if(busy)return;setBusy(true);try{await load();}catch(e){setError(e);}finally{setBusy(false);}}}/>
      {stage === "history" && (
        <section className="surface update-step">
          <h2>{uiText("Start with your latest sales")}</h2>
          <p>{uiText("Upload complete updated history, or keep the saved version for this update.")}</p>
          <div className="update-input-summary">
            <strong>{source?.name}</strong>
            <span>
              {source?.review?.summary?.end
                ? "History through " +
                  planningMonth(
                    source.review.summary.end,
                    source.settings?.month_basis,
                  )
                : uiText("Saved sales history")}{" "}
              · {source?.settings?.unit}
            </span>
          </div>
          <div className="demand-actions">
            <Button
              kind="primary"
              disabled={busy || !canEdit}
              onClick={uploadHistory}
            >{uiText("Upload updated history")}</Button>
            <Button
              disabled={busy || !canEdit || !source}
              onClick={click("history", {
                dataset_id: source?.id,
                reviewed: true,
              })}
            >{uiText("Use saved history")}</Button>
          </div>
        </section>
      )}
      {stage === "forecast" && (
        <section className="surface update-step">
          <h2>{uiText("Calculate the next forecast")}</h2>
          <div className="update-settings">
            <Field title={uiText("Months ahead")}>
              <Pick
                label={uiText("Forecast horizon")}
                value={months}
                options={Array.from({ length: 24 }, (_, i) => [
                  String(i + 1),
                  String(i + 1),
                ])}
                onChange={(value) => {
                  setMonths(value);
                  setChecked(false);
                }}
              />
            </Field>
            <Field
              title={uiText("Method")}
              help={uiText("Automatic checks past predictions and compares available methods.")}
            >
              <Pick
                label={uiText("Forecast method")}
                value={method}
                options={[
                  ["recommended", uiText("Choose automatically")],
                  ["seasonal", uiText("Seasonal patterns")],
                  ["trend", uiText("Recent trend")],
                  ["intermittent", uiText("Occasional demand")],
                  ["driver", uiText("Use supplied factors")],
                  ...(base?.leaderboard || []).map((row) => [
                    "model:" + row.model,
                    row.model,
                  ]),
                ]}
                onChange={(value) => {
                  setMethod(value);
                  setChecked(false);
                }}
              />
            </Field>
          </div>
          <LiveCheck
            sources={session.live_sources}
            ui={ui}
            onManage={manageSources}
          />
          <p className="table-note">
            {source?.settings?.drivers?.length
              ? uiText("Saved factors and their future values stay attached; missing coverage blocks calculation.")
              : uiText("This first calculation uses sales history and calendar patterns. Add live-factor assumptions in the next step.")}
          </p>
          <label className="check-row">
            <input
              type="checkbox"
              checked={checked}
              disabled={busy || !canEdit}
              onChange={(e) => setChecked(e.target.checked)}
            />{uiText("I reviewed the history, method and months ahead.")}</label>
          <div className="demand-actions">
            <Button disabled={busy} onClick={click("history_back")}>{uiText("Back")}</Button>
            <Button
              kind="primary"
              disabled={busy || !checked || !canEdit}
              onClick={click("calculate", {
                months: Number(months),
                method,
                reviewed: true,
              })}
            >
              {busy ? uiText("Starting…") : uiText("Calculate forecast")}
            </Button>
          </div>
        </section>
      )}
      {waiting && (
        <section className="surface update-step">
          <h2>
            {stage === "calculating"
              ? uiText("Calculating your forecast")
              : uiText("Calculating the factor comparison")}
          </h2>
          <p role="status">
            {job?.error || job?.message || "Waiting for the calculation"}
          </p>
          <div className="demand-actions">
            {job?.state === "succeeded" ? (
              <Button
                kind="primary"
                disabled={busy || !canEdit}
                onClick={click(
                  stage === "calculating" ? "calculated" : "factor_calculated",
                )}
              >{uiText("Review result")}<ArrowRight size={18} />
              </Button>
            ) : ["failed", "cancelled", "interrupted"].includes(job?.state) ? (
              <Button
                disabled={busy || !canEdit}
                onClick={click(
                  stage === "calculating"
                    ? "retry_calculation"
                    : "discard_factor_job",
                )}
              >{uiText("Review settings & retry")}</Button>
            ) : (
              <Button
                kind="ghost"
                disabled={busy || !canEdit}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api("/api/jobs/" + job.id + "/cancel", {});
                    await load();
                  } catch (e) {
                    setError(e.message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >{uiText("Stop calculation")}</Button>
            )}
          </div>
          <p className="table-note">{uiText("You can leave this page. The update is saved here.")}</p>
        </section>
      )}
      {stage === "factors" && run && (
        <section className="surface update-step">
          <h2>{uiText("Include external factors?")}</h2>
          <p>{uiText("Compare relevant sources such as exchange rates or global supply. Review timing and future assumptions before applying them.")}</p>
          <LiveCheck
            sources={session.live_sources}
            ui={ui}
            onManage={manageSources}
          />
          <div className="demand-actions">
            <FactorBatch
              run={run}
              api={api}
              ui={ui}
              canEdit={canEdit && !busy}
              buttonLabel="Review customer/product factors"
              onManageProfiles={()=>{onClose();navigate('customers');}}
              onManageSources={manageSources}
              onSaved={async (saved, requestId) => {
                const job = await runDataset(saved.id, {
                  base_run_id: run.run_id,
                  request_id: requestId,
                });
                if (!job)
                  throw Error(
                    "Calculation could not start. Retry the reviewed comparison.",
                  );
                await act("factor_job", { job_id: job.id });
              }}
            />
            <Button
              disabled={busy || !canEdit}
              onClick={click("no_factors", { reviewed: true })}
            >{uiText("Keep calculated baseline")}</Button>
          </div>
          <p className="table-note">{uiText("Connected data is not automatically used. A comparison shows possible impact, not proof of improved accuracy.")}</p>
        </section>
      )}
      {stage === "orders" && run && (
        <section className="surface update-step">
          <h2>{uiText("Review current customer orders")}</h2>
          <p>{uiText("Use confirmed orders for each customer, product and month. The forecast covers expected demand that is not ordered yet.")}</p>
          <div className="demand-actions">
            <Button
              kind="primary"
              disabled={busy || !canEdit}
              onClick={() => openOrders()}
            >{uiText("Add current orders")}</Button>
            {canEdit && !busy && (
              <OrderReuse
                runId={run.run_id}
                api={api}
                ui={ui}
                onSaved={(saved) => act("orders", { snapshot_id: saved.id })}
              />
            )}
          </div>
          <OrderChoices
            key={statusRevision}
            api={api}
            runId={run.run_id}
            ui={ui}
            onChoose={(snapshot_id) =>
              act("orders", { snapshot_id }).catch(() => {})
            }
            onEdit={openOrders}
            disabled={busy || !canEdit}
          />
        </section>
      )}
      {["review", "ready"].includes(stage) && (
        <section className="surface update-step">
          <h2>
            {session.ready
              ? uiText("Your forecast update is ready")
              : uiText("Review what changed")}
          </h2>
          {session.attention && (
            <p role="alert" className="source-notice">
              {session.attention}
            </p>
          )}
          {session.comparison && (
            <UpdateComparison report={session.comparison} ui={ui} />
          )}
          {!session.ready && session.comparison && (
            <>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={busy || !canEdit}
                  onChange={(e) => setChecked(e.target.checked)}
                />{uiText("I reviewed the changes and current order coverage.")}</label>
              <Button
                kind="primary"
                disabled={busy || !checked || !canEdit}
                onClick={click("review", {
                  reviewed: true,
                  review_token: session.comparison.review_token,
                })}
              >{uiText("Continue to export")}</Button>
            </>
          )}
          <div className="demand-actions update-secondary">
            <Button disabled={busy || !canEdit} onClick={click("orders_back")}>{uiText("Review orders again")}</Button>
            {run && (
              <Button
                kind="ghost"
                disabled={busy}
                onClick={() => {
                  localStorage.setItem(
                    "demandlab.orders." + run.run_id,
                    session.snapshot_id,
                  );
                  openRun(run.run_id, "demand");
                }}
              >{uiText("Open dashboard")}</Button>
            )}
          </div>
          {session.ready && (
            <UpdateExports sessionId={session.id} ui={ui} />
          )}
        </section>
      )}
      <button
        className="home-text-link update-recheck"
        disabled={busy}
        onClick={() => {
          setError("");
          load().catch((e) => setError(e.message));
        }}
      >
        <ArrowClockwise size={16} />{uiText("Check latest status")}</button>
    </Page>
  );
}

function LiveCheck({ sources = [], ui, onManage }) {
  const active = sources.filter((row) => row.enabled || row.series?.length),
    needs = active.filter(
      (row) =>
        row.status === "failed" || row.data_behind || row.refresh_overdue,
    );
  return (
    <details className="help-details update-live">
      <summary>{uiText("Live sources ·")}{active.length}{uiText("saved connections")}{needs.length ? " · " + needs.length + " need attention" : ""}
      </summary>
      <p className="table-note">{uiText("Connection health and age only—not evidence that a source improves this forecast.")}</p>
      {active.map((row) => (
        <div className="update-source" key={row.id}>
          <strong>{row.name || row.id}</strong>
          <span>
            {row.status === "failed"
              ? uiText("Refresh failed")
              : row.data_behind
                ? uiText("Older observations")
                : row.refresh_overdue
                  ? uiText("Refresh overdue")
                  : row.status === "healthy"
                    ? uiText("Latest check succeeded")
                    : uiText("Check required")}
          </span>
          {row.series?.map((s) => (
            <small key={s.id}>
              {s.name} · {s.geography}{' '}{uiText("· Latest")}{" "}
              {s.latest_period || "not available"} · {s.frequency}
            </small>
          ))}
          {row.error && <small>{row.error}</small>}
        </div>
      ))}
      <ui.Button kind="ghost" onClick={onManage}>{uiText("Manage sources in Data")}</ui.Button>
    </details>
  );
}

function OrderChoices({ api, runId, ui, onChoose, onEdit, disabled }) {
  const [choices, setChoices] = useState([]),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api("/api/sales/runs/" + runId + "/inputs")
      .then((value) => live && setChoices(value.snapshots))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [runId]);
  const latest = choices[0];
  return (
    <>
      <ui.ErrorBox error={error} />
      {latest && (
        <div className="update-input-summary">
          <strong>{uiText("Latest saved review:")}{' '}{latest.name}</strong>
          <span>{uiText("Orders as of")}{' '}{latest.as_of}</span>
          <div className="demand-actions">
            <ui.Button disabled={disabled} onClick={() => onChoose(latest.id)}>{uiText("Check & use this review")}</ui.Button>
            <ui.Button
              disabled={disabled}
              kind="ghost"
              onClick={() => onEdit(latest.id)}
            >{uiText("Update these orders")}</ui.Button>
          </div>
        </div>
      )}
    </>
  );
}

export function UpdateComparison({ report, ui }) {
  const [search, setSearch] = useState(""),
    [kind, setKind] = useState("all");
  const visible = report.rows.filter(
    (row) =>
      (kind === "all" || row.change === kind) &&
      (!search ||
        (
          row.customer +
          " " +
          row.sku +
          " " +
          planningMonth(row.period, report.month_basis)
        )
          .toLowerCase()
          .includes(search.toLowerCase())),
  );
  return (
    <div className="update-comparison">
      <div className="update-change-summary">
        <span>
          <strong>
            {number(report.overlap_before)} → {number(report.overlap_after)}{" "}
            {report.unit}
          </strong>{uiText("Calculated demand · matching months only")}</span>
        <span>
          {report.added_rows}{' '}{uiText("added ·")}{' '}{report.removed_rows}{uiText("outside new forecast")}</span>
      </div>
      <p className="table-note">{uiText("History, methods, orders and time can all change the result. Missing months are not zero. Planning quantities below exclude deliveries.")}</p>
      <div className="compact-toolbar">
        <input
          aria-label={uiText("Find changed customer, product or month")}
          placeholder={uiText("Find customer, product or month")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <ui.Pick
          label={uiText("Changes to show")}
          value={kind}
          onChange={setKind}
          options={[
            ["all", uiText("All changes")],
            ["overlap", uiText("Matching months")],
            ["added", uiText("Added months")],
            ["removed", uiText("Outside new forecast")],
          ]}
        />
      </div>
      <div className="order-comparison-table">
        <ui.Table
          headers={[
            uiText("Customer"),
            uiText("Product"),
            uiText("Month"),
            uiText("Previous estimate"),
            uiText("New estimate"),
            uiText("New open orders"),
            uiText("New planning quantity"),
          ]}
        >
          {visible.slice(0, 100).map((row) => (
            <tr key={[row.customer, row.sku, row.period].join("|")}>
              <td>{row.customer}</td>
              <td>{row.sku}</td>
              <td>
                {planningMonth(row.period, report.month_basis)}
                {row.change !== "overlap" && (
                  <small>
                    {row.change === "added" ? uiText("Added") : uiText("Outside new forecast")}
                  </small>
                )}
              </td>
              {[
                "before_forecast",
                "after_forecast",
                "after_open_orders",
                "after_to_serve",
              ].map((key) => (
                <td key={key}>{number(row[key])}</td>
              ))}
            </tr>
          ))}
        </ui.Table>
      </div>
      {visible.length > 100 && (
        <p className="table-note">{uiText("First 100 of")}{visible.length}{uiText("rows. Full demand is available in the dashboard and exports.")}</p>
      )}
      <details className="help-details">
        <summary>{uiText("Order checks")}</summary>
        <p>{report.orders_note}</p>
        <p>{uiText("Current orders as of")}{report.as_of}{uiText("; review again after")}{" "}
          {report.valid_until}.
        </p>
        {report.warnings.map((warning, index) => (
          <p key={index}>{warning}</p>
        ))}
      </details>
    </div>
  );
}

export function UpdateExports({ sessionId, ui }) {
  const [hasOrders, setHasOrders] = useState("");
  const mode = hasOrders === "yes" ? "remaining_forecast" : "combined_demand";
  return (
    <div className="update-exports">
      <h3>{uiText("Export for planning")}</h3>
      <p>{uiText("Does the receiving system already have these customer orders?")}</p>
      <div className="demand-actions">
        <ui.Button
          kind={hasOrders === "yes" ? "primary" : "default"}
          onClick={() => setHasOrders("yes")}
        >{uiText("Yes")}</ui.Button>
        <ui.Button
          kind={hasOrders === "no" ? "primary" : "default"}
          onClick={() => setHasOrders("no")}
        >{uiText("No")}</ui.Button>
      </div>
      {hasOrders && (
        <>
          <p className="table-note">
            {hasOrders === "yes"
              ? uiText("Export expected demand only to avoid counting orders twice.")
              : uiText("Export open orders plus expected demand. Delivered quantities are excluded.")}{" "}{uiText("One row per customer, product and month.")}</p>
          <div className="demand-actions">
            {["xlsx", "csv", "json"].map((kind) => (
              <a
                className="btn"
                key={kind}
                href={
                  "/api/forecast-updates/" +
                  sessionId +
                  "/export?mode=" +
                  mode +
                  "&kind=" +
                  kind
                }
              >
                {kind === "xlsx" ? uiText("Excel") : kind.toUpperCase()}
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

import {apiLink} from './company-api.mjs';
import {localState} from './workspace-storage.mjs';
import React, { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ArrowClockwise,
} from "@phosphor-icons/react";
import { FactorBatch } from "./factor-batch.jsx";
import { OrderReuse } from "./order-reuse";
import { DemandImport } from "./sales-demand";
import { orderRevision } from "./order-revision.mjs";
import { planningBasis, planningMonth } from "./planning-calendar.mjs";
import {t as uiText,unitLabel,i18n} from './localization.mjs';
import {Page,Panel,Stack,Grid,Actions,DefinitionList,Disclosure,Collection,SearchControl,Steps} from './ui-layout.jsx';

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
    ? uiText("Not present")
    : new Intl.NumberFormat(i18n.language, { maximumFractionDigits: 2 }).format(value);
export const updateHorizons = () => Array.from({length:24},(_,i)=>[String(i+1),number(i+1)]);
// A status refresh must not replace unsaved form choices. Reinitialise only
// when entering a different saved step or input version.
export const updateSettingsKey = session => JSON.stringify([session?.id,session?.dataset_id,session?.stage]);
export function savedForecastUpdate(storage,page,canEdit) {
  if(page!=='demand'||!canEdit)return null;
  try{const id=storage.getItem('demandlab.forecastUpdate');return /^[a-f0-9]{32}$/.test(id||'')?id:null;}
  catch{return null;}
}
export const updateNeedsPolling=session=>!!session&&['calculating','factor_calculating'].includes(session.stage)
  && !['succeeded','failed','cancelled','interrupted'].includes(session.job?.state);
export function FactorChoice({hasFactors,children,tools,ui,disabled,onKeep}) {
  return <Panel title={uiText(hasFactors?'Review included factors':'Include external factors?')}>
    {children}
    <Actions>{tools}<ui.Button disabled={disabled} onClick={onKeep}>{uiText(hasFactors?'Keep included factors':'Keep calculated baseline')}</ui.Button></Actions>
  </Panel>;
}

export function UpdateProgress({ stage }) {
  return <Steps items={stages} current={position[stage]} label={uiText("Forecast update progress")}/>;
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
  const settingsKey=updateSettingsKey(session);
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
    return () => {
      live = false;
    };
  }, [session?.run_id, session?.dataset_id, session?.stage,statusRevision]);
  useEffect(()=>{
    if(session?.stage!=='forecast')return;
    const settings=datasets.find(d=>d.id===session.dataset_id)?.settings;
    setMonths(String(session.months||settings?.horizon||6));
    setMethod(session.method||settings?.method_selection||'recommended');
    setChecked(false);
  },[settingsKey]);
  useEffect(() => {
    if (!updateNeedsPolling(session)) return;
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
  }, [session?.stage,session?.job?.state, id]);
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
      <Page title={uiText('Update forecast')} actions={<Button kind="ghost" onClick={onClose}><ArrowLeft/>{uiText('Back to forecast')}</Button>}>
        <ErrorBox error={error} busy={busy} onReload={async()=>{if(busy)return;setBusy(true);try{await load();}catch(e){setError(e);}finally{setBusy(false);}}}/>
        {!error&&<p role="status">{uiText('Opening forecast update…')}</p>}
      </Page>
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
    <Page title={uiText('Update forecast')} controls={<UpdateProgress stage={stage}/>} actions={<Button kind="ghost" disabled={busy} onClick={onClose}><ArrowLeft/>{uiText('Back to forecast')}</Button>}>
      <ErrorBox error={error} busy={busy} onReload={async()=>{if(busy)return;setBusy(true);try{await load();}catch(e){setError(e);}finally{setBusy(false);}}}/>
      {stage === "history" && (
        <Panel title={uiText("Start with your latest sales")} description={uiText("Upload complete updated history, or keep the saved version for this update.")}>
          <DefinitionList rows={[
            [uiText('Sales data'),source?.name||uiText('Not present')],
            [uiText('History through'),source?.review?.summary?.end?planningMonth(source.review.summary.end,source.settings?.month_basis):uiText('Not present')],
            [uiText('Unit'),unitLabel(source?.settings?.unit)],
          ]}/>
          <Actions>
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
          </Actions>
        </Panel>
      )}
      {stage === "forecast" && (
        <Panel title={uiText("Calculate the next forecast")}>
          <Grid>
            <Field title={uiText("Months ahead")}>
              <Pick
                label={uiText("Forecast horizon")}
                value={months}
                options={updateHorizons()}
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
                    uiText(row.model),
                  ]),
                ]}
                onChange={(value) => {
                  setMethod(value);
                  setChecked(false);
                }}
              />
            </Field>
          </Grid>
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
          <label className="ui-check">
            <input
              type="checkbox"
              checked={checked}
              disabled={busy || !canEdit}
              onChange={(e) => setChecked(e.target.checked)}
            />{uiText("I reviewed the history, method and months ahead.")}</label>
          <Actions>
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
          </Actions>
        </Panel>
      )}
      {waiting && (
        <Panel title={job?.state==='succeeded'?uiText('Forecast calculated'):stage === "calculating"
              ? uiText("Calculating your forecast")
              : uiText("Calculating the factor comparison")}>
          <p role="status">
            {uiText(job?.error || job?.message || "Waiting for the calculation")}
          </p>
          <Actions>
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
          </Actions>
          <p className="table-note">{uiText("You can leave this page. The update is saved here.")}</p>
        </Panel>
      )}
      {stage === "factors" && run && (
        <FactorChoice hasFactors={!!source?.settings?.drivers?.length} ui={ui} disabled={busy||!canEdit} onKeep={click('no_factors',{reviewed:true})} tools={<FactorBatch
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
            />}>
          <LiveCheck sources={session.live_sources} ui={ui} onManage={manageSources}/>
        </FactorChoice>
      )}
      {stage === "orders" && run && (
        <Panel title={uiText("Review current customer orders")} description={uiText("Use confirmed orders for each customer, product and month. The forecast covers expected demand that is not ordered yet.")}>
          <Actions>
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
          </Actions>
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
        </Panel>
      )}
      {["review", "ready"].includes(stage) && (
        <Panel title={session.ready
              ? uiText("Your forecast update is ready")
              : uiText("Review what changed")}>
          {session.attention && (
            <p role="alert" className="source-notice">
              {uiText(session.attention)}
            </p>
          )}
          {session.comparison && (
            <UpdateComparison report={session.comparison} ui={ui} />
          )}
          {!session.ready && session.comparison && (
            <>
              <label className="ui-check">
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
          <Actions>
            <Button disabled={busy || !canEdit} onClick={click("orders_back")}>{uiText("Review orders again")}</Button>
            {run && (
              <Button
                kind="ghost"
                disabled={busy}
                onClick={() => {
                  localState.setItem(
                    "demandlab.orders." + run.run_id,
                    session.snapshot_id,
                  );
                  openRun(run.run_id, "demand");
                }}
              >{uiText("Open dashboard")}</Button>
            )}
          </Actions>
          {session.ready && (
            <UpdateExports sessionId={session.id} ui={ui} />
          )}
        </Panel>
      )}
      <Actions><Button kind="ghost"
        disabled={busy}
        onClick={async () => {if(busy)return;setBusy(true);setError('');try{await load();}catch(e){setError(e.message);}finally{setBusy(false);}}}
      >
        <ArrowClockwise />{uiText("Check latest status")}</Button></Actions>
    </Page>
  );
}

export function LiveCheck({ sources = [], ui, onManage }) {
  const active = sources.filter((row) => row.enabled || row.series?.length),
    needs = active.filter(
      (row) =>
        row.status === "failed" || row.data_behind || row.refresh_overdue,
    );
  return (
    <Disclosure title={uiText('Live sources ({{count}})',{count:number(active.length)})}>
      <p className="table-note">{uiText("Connection health and age only—not evidence that a source improves this forecast.")}</p>
      {!!needs.length&&<p role="status">{uiText('{{count}} sources need attention',{count:number(needs.length)})}</p>}
      {active.map((row) => (
        <Stack key={row.id}>
          <DefinitionList rows={[[uiText(row.name || row.id),row.status === "failed"
              ? uiText("Refresh failed")
              : row.data_behind
                ? uiText("Older observations")
                : row.refresh_overdue
                  ? uiText("Refresh overdue")
                  : row.status === "healthy"
                    ? uiText("Latest check succeeded")
                    : uiText("Check required")]]}/>
          {row.series?.map((s) => (
            <DefinitionList key={s.id} rows={[[uiText(s.name),[uiText(s.geography),s.latest_period||uiText('Not present'),uiText(s.frequency)].join(' · ')]]}/>
          ))}
          {row.error && <ui.ErrorBox error={row.error}/>}
        </Stack>
      ))}
      <ui.Button kind="ghost" onClick={onManage}>{uiText("Manage sources in Data")}</ui.Button>
    </Disclosure>
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
        <Stack>
          <DefinitionList rows={[[uiText('Latest saved review'),latest.name],[uiText('Orders as of'),latest.as_of]]}/>
          <Actions>
            <ui.Button disabled={disabled} onClick={() => onChoose(latest.id)}>{uiText("Check & use this review")}</ui.Button>
            <ui.Button
              disabled={disabled}
              kind="ghost"
              onClick={() => onEdit(latest.id)}
            >{uiText("Update these orders")}</ui.Button>
          </Actions>
        </Stack>
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
    <Stack>
      <DefinitionList rows={[
        [uiText('Calculated demand · matching months only'),`${number(report.overlap_before)} → ${number(report.overlap_after)} ${unitLabel(report.unit)}`],
        [uiText('Added months'),number(report.added_rows)],
        [uiText('Outside new forecast'),number(report.removed_rows)],
      ]}/>
      <p className="table-note">{uiText("History, methods, orders and time can all change the result. Missing months are not zero. Planning quantities below exclude deliveries.")}</p>
      <Collection label={uiText('Review changed periods')} controls={<>
        <SearchControl label={uiText("Find changed customer, product or month")} value={search} onChange={setSearch}/>
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
      </>}>
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
                  <span className="ui-record-meta">
                    {row.change === "added" ? uiText("Added") : uiText("Outside new forecast")}
                  </span>
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
      </Collection>
      {visible.length > 100 && (
        <p className="table-note">{uiText("First 100 of")}{' '}{number(visible.length)}{' '}{uiText("rows. Full demand is available in the dashboard and exports.")}</p>
      )}
      <Disclosure title={uiText('Order checks')}>
        <p>{uiText(report.orders_note)}</p>
        <DefinitionList rows={[[uiText('Orders as of'),report.as_of],[uiText('Review again after'),report.valid_until]]}/>
        {(report.warnings||[]).map((warning, index) => (
          <p key={index}>{uiText(warning)}</p>
        ))}
      </Disclosure>
    </Stack>
  );
}

export function UpdateExports({ sessionId, ui }) {
  const [hasOrders, setHasOrders] = useState("");
  const mode = hasOrders === "yes" ? "remaining_forecast" : "combined_demand";
  return (
    <Disclosure title={uiText('Export for planning')} open>
      <p>{uiText("Does the receiving system already have these customer orders?")}</p>
      <Actions>
        <ui.Button
          kind={hasOrders === "yes" ? "primary" : "default"}
          onClick={() => setHasOrders("yes")}
        >{uiText("Yes")}</ui.Button>
        <ui.Button
          kind={hasOrders === "no" ? "primary" : "default"}
          onClick={() => setHasOrders("no")}
        >{uiText("No")}</ui.Button>
      </Actions>
      {hasOrders && (
        <>
          <p className="table-note">
            {hasOrders === "yes"
              ? uiText("Export expected demand only to avoid counting orders twice.")
              : uiText("Export open orders plus expected demand. Delivered quantities are excluded.")}{" "}{uiText("One row per customer, product and month.")}</p>
          <Actions>
            {["xlsx", "csv", "json"].map((kind) => (
              <a
                className="btn"
                key={kind}
                href={
                  apiLink("/api/forecast-updates/" +
                  sessionId +
                  "/export?mode=" +
                  mode +
                  "&kind=" +
                  kind)
                }
              >
                {kind === "xlsx" ? uiText("Excel") : kind.toUpperCase()}
              </a>
            ))}
          </Actions>
        </>
      )}
    </Disclosure>
  );
}

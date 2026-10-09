import {apiLink} from './company-api.mjs';
import {chartTheme} from './chart-theme.mjs';
import {Page,PageTabs,Disclosure} from './ui-layout.jsx';
import {SalesFiles} from './sales-files.jsx';
import {workspacePage,workspaceRequest,writeWorkspaceLocation} from './navigation.mjs';
import {MotionPresence,smoothUpdate,useSmoothState} from './ui-motion.jsx';
import {t as uiText,unitLabel} from './localization.mjs';
import React, { useEffect, useState, useId, useRef } from "react";
import {I18nextProvider} from 'react-i18next';
import {i18n,interfaceDirection} from './localization.mjs';
import {useInterfaceLanguage,LanguageSettings,LanguageSwitch} from './language-settings.jsx';
import { createRoot } from "react-dom/client";
import { AssumptionEditor, AssumptionEvidence } from "./assumptions";
import { ScenarioChart } from "./scenario-chart";
import { WeatherContext } from "./weather";
import { LiveSources } from "./live-sources";
import { RangeCheck } from "./range-check";
import * as Dialog from "@radix-ui/react-dialog";
import * as Select from "@radix-ui/react-select";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  ChartLineUp,
  Database,
  Stack,
  Factory,
  GearSix,
  Plus,
  X,
  ArrowRight,
  ArrowLeft,
  Check,
  CheckCircle,
  WarningCircle,
  Question,
  UploadSimple,
  CaretDown,
  DownloadSimple,
  List,
  FileText,
  Trash,
  ArrowClockwise,
  MagnifyingGlass,
  Flask,
  ChatCircleDots,
  House,
  UsersThree,
  CloudSun,
  Files,
} from "@phosphor-icons/react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as ChartTooltip,
  ReferenceLine,
} from "recharts";
import "./design-system.css";
import { InventoryData, InventoryOutlook } from "./inventory";
import { UnitSettings } from "./units";
import { AISettings } from "./ai-settings";
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {CustomerMatches} from './customer-matches.jsx';
import { ProductionMapping } from "./production";
import { ActualResults } from "./actuals";
import { TodayPage } from "./today";
import { SalesDemand } from "./sales-demand";
import { DemandReviews } from "./demand-reviews";
import { AssistantWorkspace } from "./assistant-workspace";
import {AppSidebar,readSidebarPreference,saveSidebarPreference} from './ui-sidebar.jsx';
import { ImportMappingAssistant } from "./import-mapping.jsx";
import {RepeatUploadReview} from './repeat-upload-review';
import { FactorReview } from "./factor-review.jsx";
import { FactorImports } from "./factor-imports.jsx";
import { FactorLink, FactorLinkEvidence } from "./factor-links.jsx";
import { FactorBatch, BatchEvidence } from "./factor-batch.jsx";
import { Customers } from "./customers";
import {OrderBooks} from './order-books.jsx';
import { HelpPage } from "./help";
import { Home } from "./home";
import {MonthlyRefresh} from './monthly-refresh';
import {NewForecast} from './new-forecast.jsx';
import {SettingsWorkspace} from './settings-workspace.jsx';
import {FORECAST_DRAFT_KEY,readForecastDraft,forecastInputs} from './forecast-start.mjs';
import {salesSeriesLabel} from './demand-view.mjs';
import {FactorEvaluation} from './factor-evaluation';
import { pendingImport } from "./workflow-state.mjs";
import {requestJSON} from './request-errors.mjs';
import {companyMode,companyPage,configureCompanyApi,companyRequest} from './company-api.mjs';
import {configureWorkspaceStorage,workspaceContextKey,localState,sessionState} from './workspace-storage.mjs';
import {CompanyFactors} from './company-factors.jsx';
import {RequestRecovery} from './request-recovery.jsx';
import { AccessGate } from "./access";
import { FolderInputs } from "./folder-inputs";
import { BusinessConnections } from "./business-connections.jsx";
import { FormField, FIELD_CONTROL } from "./form-field.mjs";
import {
  replacementMapping,
  importDraftKey,
  suggestedSalesGrouping,
  salesGroupingReady,
  saveAttempt,
  sameSavedInputs,
} from "./import-state.mjs";

let csrfToken = "";

async function api(url, body, method) {
  return companyRequest(url,body,method,(target,value,verb)=>requestJSON(target,value,verb,{csrfToken,
    onSessionExpired:()=>window.dispatchEvent(new Event('demandlab:session-expired'))}));
}
const fmt = (n, d = 1) =>
  n == null || !Number.isFinite(Number(n))
    ? "—"
    : Number(n).toLocaleString(i18n.language, { maximumFractionDigits: d });
const pct = (n) => (n == null ? "—" : `${fmt(n)}%`);
const date = (s, day = false) =>
  !s
    ? "—"
    : new Intl.DateTimeFormat(i18n.language==='fa'?'fa-IR-u-ca-gregory':'en', {
        month: "short",
        year: "numeric",
        ...(day ? { day: "numeric" } : {}),
      }).format(new Date(s));
const label = (s) =>
  String(s || "")
    .replace(/_synthetic$/, "")
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
const METHODS = [
  ["recommended", "Choose the best fit"],
  ["seasonal", "Repeating seasonal demand"],
  ["trend", "Growing or declining demand"],
  ["intermittent", "Infrequent demand"],
  ["driver", "Use additional factors"],
];
const BASE = {
  history_calendar: 'gregorian',
  history_grain: 'transactions',
  month_basis: 'gregorian',
  sales_measure: 'recorded_sales',
  returns_policy: 'reject',
  future_calendar: 'gregorian',
  date_col: "",
  target_col: "",
  item_col: "",
  series_mode: 'column',
  sku_col: "",
  category_col: "",
  customer_col: "",
  future_date_col: "",
  future_item_col: "",
  frequency: "monthly",
  horizon: 6,
  unit: "units",
  unit_filter: "",
  profile: "deep",
  method_selection: "recommended",
  drivers: [],
  driver_roles: {},
  future_driver_policy: "require",
  missing_strategy: "auto",
  outlier_strategy: "none",
  calendar_country: "IR",
  weekend_days: [4],
  shutdown_dates: [],
  excluded_items: [],
};
const nav = [
  ["today", "Home", House],
  ["demand", "Forecast", ChartLineUp],
  ["data", "Data", Database],
];
const METHOD_HELP = {
  "Last observed":
    "Repeats the last observed quantity. This is the simplest benchmark, not a seasonal model.",
  "Recent average": "Repeats the average of the last three observed periods.",
  "Weighted recent average":
    "Uses the last three periods with weights 1, 2 and 3, giving the newest most weight. Repeats that level; it does not predict a trend.",
  "Holt trend":
    "Learns a changing level and straight-line trend without seasonality. Uses StatsForecast; needs at least six training periods.",
  "Holt-Winters seasonal":
    "Learns trend and an additive repeating pattern. Needs two full cycles in each historical training window; zero quantities are allowed.",
  "MSTL weekly + yearly":
    "Separates seven-day and 365-day patterns in daily data using StatsForecast. Needs at least 731 training days in every test window. A 365-day cycle does not represent movable holidays.",
  "Croston SBA":
    "A bias-corrected Croston method for items with infrequent demand, implemented by StatsForecast.",
  AutoETS:
    "Exponential smoothing: learns level, trend and repeated seasonal patterns.",
  Theta: "Combines a long-term trend with a smoothed recent level.",
  "Seasonal naive":
    "Repeats the quantity from the same period in the previous seasonal cycle. A simple benchmark.",
  AutoARIMA:
    "Models changes over time and how recent changes relate to earlier ones.",
  Croston:
    "Models the size and spacing of demand when many periods have no demand.",
  "TSB intermittent":
    "Updates demand probability and size separately, useful for intermittent or declining demand.",
  "Extra trees":
    "Combines many randomised decision trees using historical patterns and selected factors.",
  "Random forest":
    "Combines decision trees to learn nonlinear patterns in historical data.",
  "LightGBM + drivers":
    "Boosted decision trees trained on past patterns and any selected factors.",
  "Histogram gradient boosting":
    "A sequence of decision trees that correct earlier prediction errors.",
  "Ridge + drivers":
    "Regularised linear regression using past demand and any selected factors.",
  "Elastic Net + drivers":
    "Linear regression that can reduce the influence of weak inputs. Uses past demand and selected factors, with scaling fitted only on each training window. Relationships are not proof of causation.",
};

function Help({ text }) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip.Root open={open} onOpenChange={setOpen}>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          className="help"
          aria-label={text}
          onClick={(e) => {
            e.preventDefault();
            setOpen((v) => !v);
          }}
        >
          <Question size={17} />
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content className="tooltip" sideOffset={7}>
          {text}
          <Tooltip.Arrow />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}
function Button({ children, kind = "secondary", className = "", ...props }) {
  return (
    <button className={`btn ${kind} ${className}`} {...props}>
      {children}
    </button>
  );
}
function Pick({
  value,
  options,
  onChange,
  label: accessible,
  disabled = false,
  id,
  "aria-labelledby": labelledBy,
  "aria-describedby": describedBy,
}) {
  return (
    <Select.Root
      dir={interfaceDirection()}
      value={value || "__none"}
      onValueChange={(v) => onChange(v === "__none" ? "" : v)}
      disabled={disabled}
    >
      <Select.Trigger
        className="select-control"
        id={id}
        aria-label={accessible}
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
      >
        <Select.Value />
        <Select.Icon>
          <CaretDown size={16} />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal>
        <Select.Content
          className="select-menu"
          position="popper"
          sideOffset={5}
        >
          <Select.ScrollUpButton className="select-scroll">
            ↑
          </Select.ScrollUpButton>
          <Select.Viewport>
            {options.map((o) => {
              const [v, t] = typeof o === "string" ? [o, label(o)] : o;
              return (
                <Select.Item
                  key={v || "none"}
                  value={v || "__none"}
                  className="select-option"
                >
                  <Select.ItemText>{t}</Select.ItemText>
                  <Select.ItemIndicator>
                    <Check size={16} />
                  </Select.ItemIndicator>
                </Select.Item>
              );
            })}
          </Select.Viewport>
          <Select.ScrollDownButton className="select-scroll">
            ↓
          </Select.ScrollDownButton>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
Pick[FIELD_CONTROL] = true;
function Field({ title, help, children }) {
  return (
    <FormField title={title} help={help} Help={Help}>
      {children}
    </FormField>
  );
}
function Modal({
  title,
  description,
  open,
  onClose,
  children,
  wide = false,
  dismissible = true,
  className = "",
  returnFocus,
  fixed = false,
}) {
  const opener = useRef(null);
  const content = useRef(null);
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(v) => !v && dismissible && onClose()}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content
          ref={content}
          className={`modal ${wide ? "wide" : ""} ${fixed ? "ui-dialog-fixed" : ""} ${className}`}
          onOpenAutoFocus={(event) => {
            opener.current = document.activeElement;
            const field = content.current?.querySelector(
              'input:not([type="hidden"]):not(:disabled), textarea:not(:disabled), [role="combobox"]:not([disabled])',
            );
            if (field) {
              event.preventDefault();
              field.focus();
            }
          }}
          onCloseAutoFocus={(event) => {
            const target=opener.current?.isConnected?opener.current:returnFocus?.();
            if (target) {
              event.preventDefault();
              target.focus();
            }
          }}
        >
          <div className="modal-heading">
            <Dialog.Title>{title}</Dialog.Title>
            {dismissible && (
              <Dialog.Close asChild>
                <button className="icon-btn" aria-label={uiText("Close dialog")}>
                  <X size={21} />
                </button>
              </Dialog.Close>
            )}
          </div>
          <Dialog.Description className={description ? "muted" : "sr-only"}>
            {description || title}
          </Dialog.Description>
          {fixed?<div className="ui-dialog-body">{children}</div>:children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
function ErrorBox(props) {
  return <RequestRecovery {...props}/>;
}
function Empty({ icon: Icon = FileText, title, children, action }) {
  return (
    <div className="empty">
      <Icon size={36} weight="light" />
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}
function Table({ headers, children, empty }) {
  const scrollRef = useRef(null);
  const [wide, setWide] = useState(false);
  const hintId = useId();
  useEffect(() => {
    const element = scrollRef.current;
    const measure = () =>
      setWide(element.scrollWidth > element.clientWidth + 1);
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    observer.observe(element.querySelector("table"));
    measure();
    return () => observer.disconnect();
  }, []);
  return (
    <>
      {wide && (
        <p className="table-scroll-hint" id={hintId}>{uiText("Scroll sideways for more columns.")}</p>
      )}
      <div
        className="table-scroll"
        ref={scrollRef}
        tabIndex={wide ? 0 : undefined}
        aria-describedby={wide ? hintId : undefined}
      >
        <table>
          <thead>
            <tr>
              {headers.map((h, i) => (
                <th key={i}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {empty ? (
              <tr>
                <td colSpan={headers.length} className="table-empty">
                  {empty}
                </td>
              </tr>
            ) : (
              children
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
function Tabs({ value, onChange, items }) {
  return <PageTabs value={value} onChange={onChange} items={items}/>;
}
function Pill({ children, tone = "" }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

const inventoryUi = { Button, Pick, Field, Table, ErrorBox, Help, Modal };
function App({ access }) {
  useInterfaceLanguage();
  const [sidebarCollapsed,setSidebarCollapsed]=useState(()=>readSidebarPreference(localState));
  function toggleSidebar(){smoothUpdate(()=>setSidebarCollapsed(value=>{saveSidebarPreference(localState,!value);return !value;}));}
  const canEdit =
    access.mode === "local" || ["planner", "admin"].includes(access.user?.role);
  const canReview =
    access.mode === "local" ||
    ["reviewer", "approver", "admin"].includes(access.user?.role);
  const canAdmin = access.mode === "local" || access.user?.role === "admin";
  const canSettings = canAdmin || access.mode === 'better_auth';
  const initial = companyPage(workspaceRequest(location));
  const [page, setPage] = useSmoothState(workspacePage(initial));
  const [forecastRequest,setForecastRequest]=useState(initial==='new'?{id:'legacy-new'}:null);
  const forecastIdentity=useRef(forecastRequest?.id);
  if(forecastRequest)forecastIdentity.current=forecastRequest.id;
  const [forecastBusy,setForecastBusy]=useState(false);
  const [run, setRun] = useState(null),
    [datasets, setDatasets] = useState([]),
    [plans, setPlans] = useState([]),
    [runs, setRuns] = useState([]),
    [workspace, setWorkspace] = useState(null),
    [boot, setBoot] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [mobile, setMobile] = useState(false),
    [notice, setNotice] = useState(""),
    [importing, setImporting] = useState(false),
    [forecastTab, setForecastTab] = useSmoothState("methods");
  const [chosenPlan, setChosenPlan] = useState(() =>
    localState.getItem("demandlab.activePlan"),
  );
  useEffect(() => {
    if (chosenPlan) localState.setItem("demandlab.activePlan", chosenPlan);
    else localState.removeItem("demandlab.activePlan");
  }, [chosenPlan]);
  const [jobRevision, setJobRevision] = useState(0);
  const [updates,setUpdates]=useState([]),[updateId,setUpdateId]=useState(null);
  const updateAttempt=useRef(null);
  useEffect(()=>{if(updateId)localState.setItem('demandlab.forecastUpdate',updateId);else localState.removeItem('demandlab.forecastUpdate');},[updateId]);
  const [dataView, setDataView] = useSmoothState(initial==='customers'?"customers":"files");
  const [decisionTarget, setDecisionTarget] = useState(null);
  const submitting = useRef(false);
  const navigate = (p, target = null) => {
    if(p==='new'){startNewForecast();return;}
    if(p==='assistant')p='today';
    p=companyPage(p);
    if(p==='customers'){p='data';setDataView('customers');}
    if(p!=='demand')setForecastRequest(null);
    if(p==='today'&&!target?.update_id)setUpdateId(null);
    setDecisionTarget(target);
    setPage(p);
    writeWorkspaceLocation(history,location,p);
    setMobile(false);
    window.scrollTo(0, 0);
  };
  const notify = (text) => {
    setNotice(uiText(text));
    setTimeout(() => setNotice(""), 4200);
  };
  const startNewForecast=(datasetId='',method='recommended',customer='')=>{
    if(!canEdit)return;
    try{if(typeof datasetId==='string'&&datasetId)sessionState.setItem(FORECAST_DRAFT_KEY,JSON.stringify({version:2,source:datasetId,step:1,methods:[method],customer,jobs:[]}));else if(readForecastDraft(sessionState)?.step===4)sessionState.removeItem(FORECAST_DRAFT_KEY);}catch{}
    navigate('demand');
    setForecastBusy(false);
    setForecastRequest({id:crypto.randomUUID()});
  };
  const refresh = async () => {
    const [d, p, r, w, u] = await Promise.all([
      companyMode()&&!canEdit?Promise.resolve({datasets:[]}):api("/api/datasets"),
      companyMode()?Promise.resolve({plans:[]}):api("/api/plans"),
      api("/api/run-list"),
      api("/api/workspace"),
      companyMode()&&!canEdit?Promise.resolve({updates:[]}):api('/api/forecast-updates'),
    ]);
    setDatasets(d.datasets);
    setPlans(p.plans);
    setRuns(r.runs);
    setWorkspace(w);
    setUpdates(u.updates);
    return { d, p, r, w };
  };
  useEffect(() => {
    (async () => {
      try {
        const { r } = await refresh();
        const saved = localState.getItem("demandlab.activeRun");
        const key =
          r.runs.find((x) => x.run_id === saved)?.run_id ||
          r.runs.find((x) => !x.scenario_name)?.run_id;
        if (key) setRun(await api(`/api/runs/${key}`));
      } catch (e) {
        setError(e.message);
      } finally {
        setBoot(false);
      }
    })();
    writeWorkspaceLocation(history,location,initial,{replace:true,preserveSearch:true});
    if(initial==='customers'){setPage('data');writeWorkspaceLocation(history,location,'data',{replace:true});}
    const listener = () => {
      const requested=companyPage(workspaceRequest(location)),destination=workspacePage(requested);
      writeWorkspaceLocation(history,location,requested,{replace:true,preserveSearch:true});
      if(requested==='new'){
        setForecastRequest({id:crypto.randomUUID()});
      }else setForecastRequest(null);
      setMobile(false);
      setDecisionTarget(null);
      if(destination==='today')setUpdateId(null);
      if(requested==='customers'){setDataView('customers');setPage('data');writeWorkspaceLocation(history,location,'data',{replace:true});}else setPage(destination);
      window.scrollTo(0,0);
    };
    window.addEventListener("popstate", listener);
    window.addEventListener("hashchange", listener);
    return () => {window.removeEventListener("popstate", listener);window.removeEventListener("hashchange", listener);};
  }, []);
  async function openRun(id, destination = "forecast", target = null) {
    try {
      setBusy("Opening forecast");
      const r = await api(`/api/runs/${id}`);
      setRun(r);
      localState.setItem("demandlab.activeRun", id);
      setChosenPlan(null);
      setForecastTab("outlook");
      navigate(destination, target);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally {
      setBusy("");
    }
  }
  async function openPlan(plan, destination = "forecast") {
    try {
      setBusy("Opening plan");
      const source = await api(`/api/runs/${plan.run_id}`);
      setRun(source);
      localState.setItem("demandlab.activeRun", plan.run_id);
      setChosenPlan(plan.id);
      setForecastTab("outlook");
      navigate(destination);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  async function runDataset(id, opts = {}) {
    if (!canEdit) {
      setError("A planner can start forecast calculations.");
      return;
    }
    if (submitting.current) return;
    submitting.current = true;
    setError("");
    setBusy("Starting calculation");
    try {
      const payload = { dataset_id: id, ...opts };
      const key = JSON.stringify(payload);
      const pending = JSON.parse(
        localState.getItem("demandlab.pendingRequests") || "{}",
      );
      const request_id = pending[key] || crypto.randomUUID();
      pending[key] = request_id;
      localState.setItem(
        "demandlab.pendingRequests",
        JSON.stringify(pending),
      );
      const job = companyMode()?(opts.sales_input_id?(await api('/api/v1/forecasts',{name:opts.forecast_name||'Forecast',
        dataset_id:id,sales_input_id:opts.sales_input_id,methods:[opts.method||'recommended'],request_id})).jobs[0]
        :await api('/api/jobs',{dataset_id:id,base_run_id:opts.base_run_id||null,request_id}))
        :await api("/api/jobs", { ...payload, request_id });
      delete pending[key];
      localState.setItem(
        "demandlab.pendingRequests",
        JSON.stringify(pending),
      );
      setJobRevision((value) => value + 1);
      setImporting(false);
      if(!forecastRequest)notify("Calculation queued. You can keep working.");
      return job;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      submitting.current = false;
      setBusy("");
    }
  }
  const importNew = () => {
    if (!canEdit) {
      setError("A planner can import new forecasting inputs.");
      return;
    }
    setDataView("files");
    setImporting(true);
    navigate("data");
  };
  async function startUpdate(runId, requestId){
    if(!canEdit)return;
    const existing=updates.find(value=>value.base_run_id===runId&&value.stage!=='ready');
    if(existing&&!requestId){setUpdateId(existing.id);navigate('today',{update_id:existing.id});return;}
    setBusy('Opening forecast update');setError('');
    try{
      if(!requestId&&updateAttempt.current?.runId!==runId)updateAttempt.current={runId,id:crypto.randomUUID()};
      const value=await api('/api/forecast-updates',{run_id:runId,request_id:requestId||updateAttempt.current.id});
      setUpdateId(value.id);updateAttempt.current=null;await refresh();navigate('today',{update_id:value.id});
    }catch(e){setError(e.message);}finally{setBusy('');}
  }
  const context = {
    run,
    datasets,
    plans,
    runs,
    workspace,
    refresh,
    notify,
    navigate,
    openRun,
    openPlan,
    runDataset,
    importNew,
    startNewForecast,
    dataView,
    setDataView,
    openInventory: () => {
      setImporting(false);
      setDataView("inventory");
      navigate("data");
    },
    chosenPlan,
    setChosenPlan,
    setError,
    decisionTarget,
    access,
    canEdit,
    canReview,
    canAdmin,
    updates,
    startUpdate,
    resumeUpdate:id=>{setUpdateId(id);navigate('today',{update_id:id});},
  };
  return (
    <Tooltip.Provider delayDuration={250}>
      <div className="app-shell" data-sidebar-collapsed={sidebarCollapsed}>
        <AppSidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} page={page} onNavigate={navigate}
          items={nav.filter(([p])=>p!=='data'||canEdit)} secondary={[
            ['help','Help',Question],['plans','Approvals',Stack],...(canSettings?[['settings','Settings',GearSix]]:[])]}/>
        <div className="main">
          <header className="topbar">
            <LanguageSwitch/>
            <button
              className="icon-btn mobile-trigger"
              aria-label={uiText("Open navigation")}
              onClick={() => setMobile(true)}
            >
              <List size={23} />
            </button>
            <span className="site-name">
              {workspace?.site?.name || "DemandLab"}
            </span>
            {access.user && (
              <div className="account-status">
                <span>
                  {access.user.name} · {uiText(label(access.user.role))}
                </span>
                <button
                  className="text-btn"
                  onClick={async () => {
                    try {
                      await api(access.mode==='better_auth'?'/api/login/sign-out':"/api/auth/logout", {});
                      window.dispatchEvent(
                        new Event("demandlab:session-expired"),
                      );
                    } catch (e) {
                      setError(e.message);
                    }
                  }}
                >{uiText("Sign out")}</button>
              </div>
            )}
          </header>
          <main id="workspace">
            <ErrorBox error={error} />
            {!boot && !forecastRequest && !(page==='today'&&updateId) && (!companyMode()||canEdit||canReview) && (
              <ForecastJobs
                includeCompleted={page==='data'||page==='today'}
                canEdit={canEdit}
                revision={jobRevision}
                onFinished={refresh}
                onOpen={async (job) => {
                  await openRun(
                    job.payload.base_run_id
                      ? job.payload.base_run_id
                      : job.run_id,
                    job.payload.base_run_id ? "forecast" : "demand",
                    job.payload.result_customer ? {customer:job.payload.result_customer} : null,
                  );
                  if (job.payload.base_run_id) setForecastTab("scenarios");
                }}
              />
            )}
            {boot ? (
              <div className="loading-inline">{uiText("Opening workspace…")}</div>
            ) : page === "today" || page === "assistant" ? (
              updateId?<MonthlyRefresh id={updateId} {...context} api={api} ui={inventoryUi}
                onClose={()=>setUpdateId(null)} renderImport={props=><ImportFlow {...props}/>}/>:<AssistantWorkspace {...context} api={api} ui={inventoryUi} home
                onNewForecast={startNewForecast} renderImport={props=><ImportFlow {...props} onRun={runDataset}/>}/>
            ) : page === "demand" ? (
              <SalesDemand {...context} api={api} ui={inventoryUi} />
            ) : page === "data" && !canEdit ? (
              <section className="surface">
                <h1>{uiText("Inputs")}</h1>
                <p>{uiText("A planner can add or update these inputs. You can continue reviewing forecasts and saved plans.")}</p>
                <Button onClick={() => navigate("today")}>{uiText("Back to Home")}</Button>
              </section>
            ) : page === "data" ? (
              <DataPage
                {...context}
                importing={importing}
                setImporting={setImporting}
              />
            ) : page === "plans" ? (
              <DemandReviews {...context} api={api} ui={inventoryUi}/>
            ) : page === "customers" ? (
              <Customers {...context} api={api} ui={inventoryUi} />
            ) : page === "help" ? (
              <HelpPage {...context}/>
            ) : page === "settings" && canSettings ? (
              <SettingsWorkspace {...context} api={api} ui={inventoryUi} fmt={fmt} date={date}/>
            ) : (
              <ForecastPage
                {...context}
                tab={forecastTab}
                setTab={setForecastTab}
              />
            )}
          </main>
        </div>
      </div>
      <Modal title={uiText('New forecast')} wide fixed open={canEdit&&!!forecastRequest&&page==='demand'&&!boot} dismissible={!forecastBusy}
        onClose={()=>setForecastRequest(null)} returnFocus={()=>document.querySelector('[data-action="new-forecast"]')}>
        <NewForecast key={forecastIdentity.current} {...context} api={api} ui={inventoryUi} embedded onWorkingChange={setForecastBusy}
          openRun={async(...args)=>{if(await openRun(...args))setForecastRequest(null);else throw Error(uiText('Could not open the forecast. Try again.'));}}
          renderImport={props=><ImportFlow {...props}/>}/>
      </Modal>
      <Modal title={uiText("Navigation")} open={mobile} onClose={() => setMobile(false)}>
        <nav className="mobile-nav">
          {[
            ...nav.filter(([p]) => p !== "data" || canEdit),
            ["help", "Help", Question],
            ["plans", "Approvals", Stack],
            ...(canSettings ? [["settings", "Settings", GearSix]] : []),
          ].map(([p, n, Icon]) => (
            <button
              key={p}
              className={`nav-link ${page === p ? "active" : ""}`}
              onClick={() => navigate(p)}
            >
              <Icon size={22} />
              {uiText(n)}
            </button>
          ))}
        </nav>
      </Modal>
      <Modal
        title={uiText(busy || "Working")}
        description={uiText("Preparing your saved request.")}
        open={!!busy&&!forecastRequest}
        dismissible={false}
        onClose={() => {}}
      >
        <div className="working-bar" />
      </Modal>
      <MotionPresence present={!!notice}>
        <div role="status" className="toast">
          <CheckCircle size={20} />
          {notice}
        </div>
      </MotionPresence>
    </Tooltip.Provider>
  );
}

function ForecastJobs({ revision, onFinished, onOpen, canEdit, includeCompleted=false }) {
  const [jobs, setJobs] = useState([]),
    [error, setError] = useState(""),
    [worker, setWorker] = useState(true),
    [action, setAction] = useState("");
  const [dismissed, setDismissed] = useState(() =>
    JSON.parse(localState.getItem("demandlab.dismissedJobs") || "[]"),
  );
  const finishRef = useRef(onFinished),
    seen = useRef(new Map());
  finishRef.current = onFinished;
  async function reload() {
    const result = await api("/api/jobs");
    setJobs(result.jobs);
    setWorker(result.worker_available);
    let finished = false;
    for (const job of result.jobs) {
      if (job.state === "succeeded" && seen.current.get(job.id) !== "succeeded")
        finished = true;
      seen.current.set(job.id, job.state);
    }
    if (finished) await finishRef.current();
    setError("");
  }
  useEffect(() => {
    let live = true,
      timer;
    async function poll() {
      if (!live) return;
      try {
        await reload();
      } catch {
        if (live) setError("Calculation status is unavailable. Reconnecting…");
      }
      if (live) timer = setTimeout(poll, 2000);
    }
    poll();
    return () => {
      live = false;
      clearTimeout(timer);
    };
  }, [revision]);
  function dismiss(id) {
    const next = [...dismissed, id].slice(-200);
    setDismissed(next);
    localState.setItem("demandlab.dismissedJobs", JSON.stringify(next));
  }
  async function act(job, operation) {
    setAction(job.id);
    try {
      await api(
        `/api/jobs/${job.id}/${operation}`,
        operation === "retry" ? { request_id: crypto.randomUUID() } : {},
      );
      if (operation === "retry") dismiss(job.id);
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setAction("");
    }
  }
  const visible = jobs.filter(
    (job) =>
      ["queued", "running", "publishing"].includes(job.state) ||
      (!dismissed.includes(job.id)&&(job.state!=='succeeded'||includeCompleted&&Date.now()/1000-job.updated_at<120)),
  );
  if (!visible.length && !error) return null;
  return (
    <section className="job-panel" aria-label={uiText('Forecast calculations')}>
      {error && <p role="alert">{uiText(error)}</p>}
      {visible.map((job) => (
        <div className="job-row" key={job.id}>
          <div className="job-copy">
            <strong>{job.name}</strong>
            <p role="status">
              {job.state === "queued" && !worker
                ? uiText("Waiting for the calculation service to reconnect")
                : uiText(({queued:'Queued',running:'Calculating…',publishing:'Saving…',succeeded:'Forecast ready',failed:'Failed',interrupted:'Interrupted',cancelled:'Cancelled'})[job.state]||'Working')}
            </p>
            {job.error && (
              <details>
                <summary>{uiText("What needs attention?")}</summary>
                <p>{job.error}</p>
              </details>
            )}
          </div>
          <div className="row-actions">
            {["queued", "running"].includes(job.state) && (
              <Button
                disabled={!canEdit || action === job.id || job.cancel_requested}
                onClick={() => act(job, "cancel")}
              >
                {job.cancel_requested ? uiText("Stopping…") : uiText("Cancel")}
              </Button>
            )}
            {job.state === "succeeded" && (
              <Button
                kind="primary"
                onClick={async () => {
                  await onOpen(job);
                  dismiss(job.id);
                }}
              >{uiText("Open result")}<ArrowRight size={16} />
              </Button>
            )}
            {["failed", "interrupted", "cancelled"].includes(job.state) && (
              <Button
                disabled={!canEdit || action === job.id}
                onClick={() => act(job, "retry")}
              >{uiText("Retry")}</Button>
            )}
            {["failed", "interrupted", "cancelled", "succeeded"].includes(
              job.state,
            ) && (
              <button
                className="icon-btn"
                aria-label={uiText('Dismiss calculation {{name}}',{name:job.name})}
                onClick={() => dismiss(job.id)}
              >
                <X size={18} />
              </button>
            )}
          </div>
        </div>
      ))}
    </section>
  );
}

function DataPage({
  datasets,
  canAdmin,
  canEdit,
  run,
  refresh,
  notify,
  runDataset,
  importing,
  setImporting,
  dataView: view,
  setDataView: setView,
}) {
  const [error, setError] = useState(""),
    [selected, setSelected] = useState(null);
  const [search,setSearch] = useState('');
  const [orderDataset,setOrderDataset] = useState(null);
  const viewConnected=(kind,id)=>{setOrderDataset(id||null);setView(kind);};
  const visibleDatasets = forecastInputs(datasets).filter(d => d.name.toLowerCase().includes(search.toLowerCase()));
  const loadSaved = async (d) => {
    setError("");
    try {
      const sources = {};
      await Promise.all(
        Object.entries(d.sources).map(
          async ([role, id]) =>
            (sources[role] = await api(`/api/sources/${id}`)),
        ),
      );
      setSelected({ ...d, sourceObjects: sources });
      setImporting(true);
    } catch (e) {
      setError(e.message);
    }
  };
  const reviewConnection = async (id) => {
    const candidate = await api('/api/v1/connections/imports/'+id);
    if(candidate.accepted_dataset_id)return loadSaved(await api('/api/datasets/'+candidate.accepted_dataset_id));
    await loadSaved({...candidate,id:candidate.id,business_candidate_id:candidate.id,review:null});
  };
  if (importing)
    return (
      <ImportFlow
        key={selected?.id || "new"}
        chooseMethodsLater
        initial={selected}
        onCancel={() => {
          setImporting(false);
          setSelected(null);
        }}
        onSaved={async (d) => {
          await refresh();
          setImporting(false);
          setSelected(null);
          notify("Dataset saved. You can forecast from it any time.");
        }}
      />
    );
  return (
    <Page title={uiText('Data')} controls={<>
      <Tabs
        value={view}
        onChange={setView}
        items={[
          ["files", "Your files"],
          ["customers", "Customers"],
          ["orders", "Orders"],
          ["external", "Factors"],
          ["connections", "Connections"],
        ]}
      />
      </>}>
      <ErrorBox error={error} />
      {view === "customers"?<Customers api={api} ui={inventoryUi} canEdit={canEdit} embedded navigate={()=>setView('files')}/>:view === "orders"?<OrderBooks datasets={datasets} api={api} ui={inventoryUi} canEdit={canEdit} initialDatasetId={orderDataset}/>:view === "connections" && companyMode()?<BusinessConnections api={api} ui={inventoryUi} canAdmin={canAdmin} canEdit={canEdit} datasets={datasets} onReview={reviewConnection} onViewRole={viewConnected}/>:view === "connections" ? (
        <FolderInputs
          api={api}
          ui={inventoryUi}
          datasets={datasets}
          canAdmin={canAdmin}
          onReview={async (id) => {
            const value = await api(
              `/api/integrations/folders/candidates/${id}`,
            );
            if (value.accepted_dataset_id) {
              const saved = (await api("/api/datasets")).datasets.find(
                (d) => d.id === value.accepted_dataset_id,
              );
              if (!saved)
                throw new Error(
                  "The saved dataset is unavailable. Contact your administrator.",
                );
              return loadSaved(saved);
            }
            await loadSaved({
              ...value,
              import_candidate_id: id,
              review: null,
            });
          }}
        />
      ) : view === "external" ? (
        companyMode()?<CompanyFactors api={api} ui={inventoryUi} onConnections={()=>setView('connections')}/>:<ExternalFactors canAdmin={canAdmin} canEdit={canEdit} run={run} refresh={refresh} runDataset={runDataset}/>
      ) : view === "inventory" ? (
        <InventoryData
          ui={inventoryUi}
          api={api}
          fmt={fmt}
          date={date}
          notify={notify}
        />
      ) : <SalesFiles datasets={visibleDatasets} search={search} onSearch={setSearch} ui={inventoryUi} date={date} fmt={fmt} onReview={loadSaved}
        actions={canEdit&&<Button kind="primary" onClick={()=>{setSelected(null);setImporting(true);}}><Plus/>{pendingImport(localState.getItem('demandlab.importDraft')).exists?uiText('Resume import'):uiText('Import data')}</Button>}/>}
    </Page>
  );
}

function ExternalFactors({canAdmin,canEdit,run,refresh,runDataset}) {
  return <LiveSources api={api} ui={inventoryUi} canAdmin={canAdmin} supplemental={[
    {id:'weather',name:uiText('Weather by location'),icon:CloudSun,provider:'NASA POWER',category:uiText('Historical weather'),status:uiText('On demand'),content:<WeatherContext api={api} ui={inventoryUi} fmt={fmt}/>},
    {id:'files',name:uiText('Existing factor files'),icon:Files,provider:uiText('Saved observations'),category:uiText('Dated factor inputs'),status:uiText('Saved data'),content:<FactorImports api={api} ui={inventoryUi} canAdmin={canAdmin} canEdit={canEdit} run={run}
      onDraft={async(saved,request_id)=>{await refresh();const job=await runDataset(saved.id,{base_run_id:run.run_id,request_id});if(!job)throw new Error('Inputs saved, but calculation could not start. Retry to use the same draft.');}}/>},
  ]}/>;
}

function ImportFlow({ initial, onCancel, onSaved, onRun, draftStorageKey, chooseMethodsLater=false, returnLabel='Data library' }) {
  const draftKey = draftStorageKey || importDraftKey(initial?.id);
  const [step, setStep] = useSmoothState(
      initial?.repeat_upload ? 0 : initial?.business_candidate_id ? 1 : initial?.import_candidate_id ? 2 : initial ? 3 : 0,
    ),
    [sources, setSources] = useState(initial?.sourceObjects || {}),
    [settings, setSettings] = useState({ ...BASE, ...initial?.settings }),
    [name, setName] = useState(initial?.name || ""),
    [classification, setClassification] = useState(
      initial?.classification || "user_provided",
    );
  const [error, setError] = useState(""),
    [pending, setPending] = useState(""),
    [review, setReview] = useState(initial?.review || null),
    [accepted, setAccepted] = useState(
      !!initial && !initial.import_candidate_id && !initial.business_candidate_id,
    ),
    [advanced, setAdvanced] = useState(false),
    [optional, setOptional] = useState(
      !!sources.future || !!sources.operations,
    ),
    [restoreReady, setRestoreReady] = useState(false);
  const unchanged = sameSavedInputs(
    initial,
    {
      name,
      classification,
      settings,
      sources: Object.fromEntries(
        Object.entries(sources).map(([role, source]) => [role, source.id]),
      ),
    },
    BASE,
  );
  useEffect(() => {
    let draft;
    try {
      draft = JSON.parse(localState.getItem(draftKey));
    } catch {}
    if (draft) {
      (async () => {
        try {
          const found = {};
          await Promise.all(
            Object.entries(draft.sources).map(
              async ([r, id]) => (found[r] = await api(`/api/sources/${id}`)),
            ),
          );
          setSources(found);
          setSettings({ ...BASE, ...draft.settings });
          const savedOnly = sameSavedInputs(initial, draft, BASE);
          setStep(
            savedOnly ? 3 : Math.min(2, Math.max(0, Number(draft.step) || 0)),
          );
          setName(draft.name || "");
          setClassification(draft.classification || "user_provided");
          setOptional(!!found.future || !!found.operations);
          setReview(savedOnly ? initial.review : null);
          setAccepted(savedOnly);
        } catch {
          setError(
            "The unfinished import could not be restored. Your saved dataset is unchanged; choose the files again.",
          );
        } finally {
          setRestoreReady(true);
        }
      })();
    } else setRestoreReady(true);
  }, []);
  useEffect(() => {
    if (restoreReady && unchanged) {
      localState.removeItem(draftKey);
      return;
    }
    if (restoreReady)
      localState.setItem(
        draftKey,
        JSON.stringify({
          save_request: (() => {
            try {
              return JSON.parse(localState.getItem(draftKey) || "{}")
                .save_request;
            } catch {
              return undefined;
            }
          })(),
          sources: Object.fromEntries(
            Object.entries(sources).map(([r, s]) => [r, s.id]),
          ),
          settings,
          name,
          classification,
          step,
        }),
      );
  }, [sources, settings, name, classification, step, restoreReady, unchanged]);
  const change = (k, v) => {
    setSettings((s) => ({ ...s, [k]: v }));
    setReview(null);
    setAccepted(false);
  };
  const guess = (preview, role) => {
    const cols = preview.columns || [];
    const pick = (names) => names.find((x) => cols.includes(x)) || "";
    if (role === "history")
      return {
        date_col: pick(["date", "month", "timestamp", "period"]),
        target_col: pick([
          "demand_tonnes",
          "demand",
          "sales",
          "quantity",
          "qty",
          "target",
          "consumption",
        ]),
        ...suggestedSalesGrouping(cols),
        production_line_col: pick(["production_line"]),
        category_col: pick(["category"]),
        unit:
          preview.source_review?.units?.length === 1
            ? preview.source_review.units[0]
            : cols.includes("demand_tonnes")
              ? "tonnes"
              : "units",
        unit_filter:
          preview.source_review?.units?.length === 1
            ? preview.source_review.units[0]
            : "",
        drivers: [],
        driver_roles: {},
        ...(preview.source_review?.input_grain?{history_grain:preview.source_review.input_grain,history_calendar:preview.source_review.input_calendar}:{}),
      };
    return {
      future_date_col: pick(["date", "month", "timestamp", "period"]),
      future_item_col: pick(["series_id", "item_id", "sku"]),
    };
  };
  async function attach(role, file, sample = false) {
    if (!file) return;
    setPending(role);
    setError("");
    setReview(null);
    setAccepted(false);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("role", role);
      const source = await api("/api/sources", form);
      setSources((s) => ({ ...s, [role]: source }));
      if (role === "operations")
        setSettings((s) => ({
          ...s,
          operations_mapping: source.preview.suggested_mapping || {
            tables: {},
            stock_as_of: "",
            reviewed: false,
          },
        }));
      if (role !== "operations")
        setSettings((s) => ({
          ...s,
          ...(sources[role]
            ? replacementMapping(s, source.preview.columns, role)
            : guess(source.preview, role)),
          ...(role === "history" ? {history_cell_corrections:[],history_corrections_sha256:null} : {}),
        }));
      if (role === "history" && !name)
        setName(file.name.replace(/\.[^.]+$/, ""));
      if (!sample) setClassification("user_provided");
      return source;
    } catch (e) {
      setError(e);
      return null;
    } finally {
      setPending("");
    }
  }
  async function loadSample() {
    setPending("sample");
    setError("");
    try {
      const roles = [
        ["history", "iran_history", "iran_manufacturing_history_60m.csv"],
        ["future", "iran_future", "iran_manufacturing_scenario_12m.csv"],
      ];
      const next = {};
      for (const [role, url, filename] of roles) {
        const r = await fetch(`/api/sample/${url}`);
        if (!r.ok) throw new Error("Sample file is unavailable.");
        const form = new FormData();
        form.append("file", new File([await r.blob()], filename));
        form.append("role", role);
        next[role] = await api("/api/sources", form);
      }
      setSources(next);
      setSettings({
        ...BASE,
        ...guess(next.history.preview, "history"),
        ...guess(next.future.preview, "future"),
        horizon: 12,
      });
      setName("Sales demand sample");
      setClassification("synthetic_sample");
      setOptional(true);
    } catch (e) {
      setError(e);
    } finally {
      setPending("");
    }
  }
  async function chooseSheet(role, sheet) {
    setPending(role);
    setError("");
    try {
      const source = await api(`/api/sources/${sources[role].id}/sheet`, {
        sheet,
      });
      setSources((s) => ({ ...s, [role]: source }));
      setSettings((s) => ({
        ...s,
        ...replacementMapping(s, source.preview.columns, role),
      }));
      setReview(null);
      setAccepted(false);
    } catch (e) {
      setError(e);
    } finally {
      setPending("");
    }
  }
  function remove(role) {
    setSources((s) =>
      Object.fromEntries(Object.entries(s).filter(([k]) => k !== role)),
    );
    setReview(null);
    setAccepted(false);
    if (role === "history") setSettings((s) => ({ ...s, ...BASE }));
    if (role === "future")
      setSettings((s) => ({
        ...s,
        future_date_col: "",
        future_item_col: "",
        drivers: [],
      }));
  }
  const request = () => ({
    name: name.trim() || "Imported data",
    sources: Object.fromEntries(
      Object.entries(sources).map(([r, s]) => [r, s.id]),
    ),
    settings,
    classification,
    accept_warnings: accepted,
    parent_dataset_id: initial?.import_candidate_id || initial?.business_candidate_id
      ? initial.parent_dataset_id
      : initial?.id || null,
    import_candidate_id: initial?.import_candidate_id || null,
  });
  async function next() {
    setError("");
    if (step === 0 && !sources.history)
      return setError("Upload a history file to continue.");
    if (step === 1) {
      if (!settings.date_col || !settings.target_col)
        return setError("Choose the date and quantity columns.");
      if (!salesGroupingReady(settings))
        return setError('Choose separate customer and product columns. Each pair gets its own forecast.');
      const m = [
        settings.date_col,
        settings.target_col,
        ...(settings.series_mode==='customer_product'?[]:[settings.item_col]),
      ].filter(Boolean);
      if (new Set(m).size !== m.length)
        return setError("Each field needs a different column.");
    }
    if (step === 2) {
      if (!name.trim()) return setError("Give this dataset a name.");
      if (
        !Number.isInteger(Number(settings.horizon)) ||
        Number(settings.horizon) < 1 ||
        Number(settings.horizon) > 24
      )
        return setError("Choose a forecast horizon from 1 to 24 periods.");
      setPending("validation");
      try {
        const r = await api("/api/datasets/validate", request());
        setReview(r);
        setAccepted(false);
        setStep(3);
      } catch (e) {
        setError(e);
      } finally {
        setPending("");
      }
      return;
    }
    setStep(step + 1);
  }
  async function finish(run) {
    setPending("save");
    setError("");
    let inputsSaved = false;
    try {
      const data = request();
      const draft = JSON.parse(localState.getItem(draftKey) || "{}");
      const attempt = saveAttempt(draft.save_request, data, () =>
        crypto.randomUUID(),
      );
      localState.setItem(
        draftKey,
        JSON.stringify({ ...draft, save_request: attempt }),
      );
      const d = unchanged
        ? initial
        : await api(initial?.business_candidate_id?'/api/v1/connections/imports/'+initial.business_candidate_id+'/accept':"/api/datasets",
            initial?.business_candidate_id?{name:data.name,sources:data.sources,settings:data.settings,classification:'user_provided',accept_warnings:data.accept_warnings,parent_dataset_id:data.parent_dataset_id,request_id:attempt.id}:{ ...data, request_id: attempt.id });
      inputsSaved = true;
      if (run && onRun) await onRun(d.id);
      localState.removeItem(draftKey);
      await onSaved(d);
    } catch (e) {
      setError(
        inputsSaved && run
          ? `Your inputs are saved, but the forecast could not start. ${e.message} Retry, or save and return to the library.`
          : e.message,
      );
    } finally {
      setPending("");
    }
  }
  const mapped = [
    settings.date_col,
    settings.target_col,
    settings.item_col,
    settings.sku_col,
    settings.category_col,
    settings.customer_col,
    settings.production_line_col,
  ];
  const exclude = new Set([
    ...mapped,
    "site",
    "province",
    "warehouse",
    "production_line",
    "supplier",
    "product_name",
    "record_type",
    "source_sheet",
    "source_cell",
    "unit",
    "article_description",
    "inventory_on_hand_tonnes",
    "safety_stock_tonnes",
    "unit_cost_irr",
    "monthly_capacity_tonnes",
    "service_level_target",
  ]);
  const factors = (sources.history?.preview.columns || []).filter(
    (c) => !exclude.has(c),
  );
  const titles = [
    "Upload files",
    "Match columns",
    "Forecast settings",
    "Review",
  ].map(uiText);
  const options = (role) => [
    ["", uiText("Choose a column")],
    ...(sources[role]?.preview.columns || []).map((c) => [c, c]),
  ];
  const mapping = (role, key, title, help, required = false) => (
    <Field title={uiText(title)} help={uiText(help || '')}>
      <Pick
        value={settings[key]}
        options={
          required
            ? options(role)
            : [["", uiText("Not needed")], ...options(role).slice(1)]
        }
        label={`${title}${role === "future" ? uiText(" in future factors") : ""}`}
        onChange={(v) => change(key, v)}
      />
      {settings[key] && (
        <small className="field-example">{uiText("e.g.")}{" "}
          {[
            ...new Set(
              sources[role]?.preview.sample.map((r) =>
                String(r[settings[key]] ?? "empty"),
              ),
            ),
          ]
            .slice(0, 2)
            .join(" · ")}
        </small>
      )}
    </Field>
  );
  if (!restoreReady) return <p role="status">{uiText("Restoring import…")}</p>;
  return (
    <Page title={initial?uiText('Review dataset'):uiText('Import data')} actions={<Button onClick={onCancel}><ArrowLeft/>{uiText(returnLabel)}</Button>}>
      <div className="wizard">
        <ol className="steps" aria-label={uiText("Import progress")}>
          {titles.map((t, i) => (
            <li key={t} aria-current={step === i ? "step" : undefined}>
              <button
                disabled={i > step || !!pending || (!!initial?.business_candidate_id && i===0)}
                onClick={() => {
                  setStep(i);
                  setError("");
                }}
              >
                <span>{i < step ? <Check size={16} /> : i + 1}</span>
                <b>{t}</b>
              </button>
            </li>
          ))}
        </ol>
        <ErrorBox error={error} />
        <section className="surface wizard-body">
          {step === 0 ? (
            <>
              <div className="section-heading">
                <div>
                  <h2>{uiText("What would you like to forecast?")}</h2>
                  <p>{uiText("Upload past sales by date, product and customer.")}</p>
                </div>
                {!companyMode()&&<Button disabled={!!pending} onClick={loadSample}>
                  <Flask size={17} />{uiText("Try sample")}</Button>}
              </div>
              <SourceCard
                role="history"
                title={uiText("Historical data")}
                source={sources.history}
                pending={pending}
                onFile={attach}
                onRemove={remove}
                onSheet={chooseSheet}
              />
              {sources.history?.preview.source_review?.warnings?.length > 0 && (
                <div className="source-notice" role="status">
                  <WarningCircle size={22} aria-hidden="true" />
                  <div>
                    <strong>{uiText("Before you continue")}</strong>
                    {sources.history.preview.source_review.warnings.map(
                      (message) => (
                        <p key={message}>{message}</p>
                      ),
                    )}
                  </div>
                </div>
              )}
              <details
                open={optional}
                onToggle={(e) => setOptional(e.currentTarget.open)}
                className="optional-section"
              >
                <summary>{uiText("Add future factors")}<span>{uiText("Optional")}</span>
                </summary>
                <p className="muted">{uiText("Use future factors when you know upcoming prices or events. Add confirmed customer orders from the Forecast page after calculating.")}</p>
                <div className="optional-files">
                  <SourceCard
                    role="future"
                    title={uiText("Future factors")}
                    source={sources.future}
                    pending={pending}
                    onFile={attach}
                    onRemove={remove}
                    onSheet={chooseSheet}
                  />
                </div>
              </details>
            </>
          ) : step === 1 ? (
            <>
              <div className="section-heading">
                <div>
                  <h2>{uiText("Match your columns")}</h2>
                  <p>{uiText("Check the suggestions against the values in your file.")}</p>
                </div>
                <ImportMappingAssistant
                  key={JSON.stringify({sources:Object.fromEntries(Object.entries(sources).map(([r,s])=>[r,s.id])),settings,classification})}
                  sources={sources} settings={settings} classification={classification}
                  api={api} ui={inventoryUi}
                  onApply={(next)=>{setSettings(next);setReview(null);setAccepted(false);}}
                />
              </div>
              <div className="form-grid two">
                {mapping(
                  "history",
                  "date_col",
                  uiText("Date"),
                  uiText("The day, week or month each quantity belongs to."),
                  true,
                )}
                {mapping(
                  "history",
                  "target_col",
                  uiText("Quantity to forecast"),
                  uiText("Actual sales, demand or consumption. Use a consistent unit."),
                  true,
                )}
              </div>
              <div className="form-grid two import-customer-mapping">
                {mapping("history", "sku_col", uiText("Product code"),
                  uiText("Matches products to customer orders and lets you filter the results."))}
                {mapping("history", "customer_col", uiText("Customer"),
                  uiText("Matches customers to their orders. Without this column, customer-level demand is unavailable."))}
              </div>
              <div className="form-grid two">
                <Field title={uiText("Forecast separately for")} help={uiText("Customer & product creates a separate forecast for every pair. No extra identifier column is needed.")}>
                  <Pick label={uiText("Forecast grouping")} value={settings.series_mode} options={[["customer_product",uiText("Each customer & product")],["column",uiText("An existing group column")]]} onChange={v=>change('series_mode',v)}/>
                </Field>
                {settings.series_mode==='column'&&mapping('history','item_col',uiText("Forecast group"),uiText("Choose a distinct customer/product identifier. Leave empty only for one total."))}
              </div>
              <div className="form-grid two">
                <Field title={uiText("Dates in your file")}><Pick label={uiText("Sales file calendar")} disabled={!!sources.history?.preview.wide_forecast_matrix} value={sources.history?.preview.wide_forecast_matrix?'gregorian':settings.history_calendar} options={[["gregorian",uiText("Gregorian")],["jalali",uiText("Persian (Jalali)")]]} onChange={v=>change('history_calendar',v)}/></Field>
                <Field title={uiText("Planning months")} help={uiText("Actual month boundaries are used for history, orders and exports. Monthly totals cannot be moved into another calendar.")}><Pick label={uiText("Planning month calendar")} value={settings.month_basis} options={[["gregorian",uiText("Gregorian months")],["jalali",uiText("Persian months")]]} onChange={v=>change('month_basis',v)}/></Field>
                <Field title={uiText("What each row contains")} help={sources.history?.preview.wide_forecast_matrix?uiText("This workbook contains Gregorian monthly totals, not individual sales dates."):undefined}><Pick label={uiText("Sales row meaning")} disabled={!!sources.history?.preview.wide_forecast_matrix} value={sources.history?.preview.wide_forecast_matrix?'monthly_totals':settings.history_grain} options={[["transactions",uiText("Dated transactions")],["monthly_totals",uiText("Monthly totals")]]} onChange={v=>change('history_grain',v)}/></Field>
                <Field title={uiText("What the quantity means")} help={uiText("Choose Recorded sales if your file only labels values as actual sales. This does not imply shipped quantities or unconstrained demand.")}><Pick label={uiText("Sales quantity meaning")} value={settings.sales_measure} options={[["recorded_sales",uiText("Recorded sales")],["customer_demand",uiText("Customer demand")],["shipped",uiText("Shipped quantities")],["invoiced",uiText("Invoiced quantities")]]} onChange={v=>change('sales_measure',v)}/></Field>
              </div>
              <CustomerMatches api={api} ui={inventoryUi} matches={settings.customer_aliases||{}} onChange={v=>change('customer_aliases',v)}/>
              <details className="optional-section"><summary>{uiText("Returns & corrections")}</summary><Field title={uiText("Negative quantities")} help={uiText("Original files are never changed. Net returns subtract only within the same forecast group and period; negative totals are blocked.")}><Pick label={uiText("Returns policy")} value={settings.returns_policy} options={[["reject",uiText("Stop and review")],["exclude_returns",uiText("Keep returns separate · forecast gross sales")],["net_returns",uiText("Subtract from the same item and period")]]} onChange={v=>change('returns_policy',v)}/></Field></details>
              <details className="optional-section">
                <summary>{uiText("Product category")}<span>{uiText("Optional")}</span>
                </summary>
                <div className="form-grid two">
                  {mapping(
                    "history",
                    "category_col",
                    uiText("Category"),
                    uiText("Group forecasts by product family."),
                  )}
                </div>
              </details>
              <div className="preview-label">{uiText("Your file ·")}{' '}{sources.history?.name}{" "}
                <span>{uiText("First")}{' '}{sources.history?.preview.sample.length}{' '}{uiText("rows")}</span>
              </div>
              <Preview
                source={sources.history}
                columns={[...new Set([
                  settings.date_col,
                  settings.target_col,
                  settings.item_col,
                  settings.sku_col,
                  settings.customer_col,
                ].filter(Boolean))]}
              />
              {sources.future && (
                <>
                  <h3 className="subsection">{uiText("Future factors")}</h3>
                  <Field title={uiText("Future-file dates")}><Pick label={uiText("Future file calendar")} value={settings.future_calendar} options={[["gregorian",uiText("Gregorian")],["jalali",uiText("Persian (Jalali)")]]} onChange={v=>change('future_calendar',v)}/></Field>
                  <div className="form-grid two">
                    {mapping(
                      "future",
                      "future_date_col",
                      uiText("Date"),
                      uiText("Forecast dates that correspond to future factor values."),
                      true,
                    )}
                    {mapping(
                      "future",
                      "future_item_col",
                      uiText("Item"),
                      uiText("Match the historical item identifiers. Leave blank for factors shared by every item."),
                    )}
                  </div>
                  <Preview
                    source={sources.future}
                    columns={[
                      settings.future_date_col,
                      settings.future_item_col,
                      ...sources.future.preview.columns
                        .filter((c) => !mapped.includes(c))
                        .slice(0, 2),
                    ].filter(Boolean)}
                  />
                </>
              )}
              {sources.operations && (
                <ProductionMapping
                  source={sources.operations}
                  value={settings.operations_mapping}
                  onChange={(v) => change("operations_mapping", v)}
                  ui={inventoryUi}
                  api={api}
                  lineControl={mapping(
                    "history",
                    "production_line_col",
                    "Production line in history",
                    "Match each item to its capacity line. Multiple-stage routing needs a separate reviewed routing.",
                    true,
                  )}
                />
              )}
            </>
          ) : step === 2 ? (
            <>
              <div className="section-heading">
                <div>
                  <h2>{uiText("Set up your forecast")}</h2>
                </div>
              </div>
              <div className="form-grid two">
                <Field title={uiText("Dataset name")}>
                  <input
                    aria-label={uiText("Dataset name")}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    maxLength={120}
                  />
                </Field>
                <Field
                  title={uiText("Quantity unit")}
                  help={uiText("Use the unit in your file. Different units are kept separate; selecting a unit never converts quantities.")}
                >
                  <Pick
                    label={uiText("Quantity unit")}
                    value={settings.unit}
                    options={
                      sources.history?.preview.source_review?.units?.length
                        ? sources.history.preview.source_review.units
                        : ["units", "tonnes", "kg", "litres", "hours"].map(v=>[v,uiText({units:'Units',tonnes:'Tonnes',kg:'Kg',litres:'Litres',hours:'Hours'}[v])])
                    }
                    onChange={(v) => {
                      change("unit", v);
                      change(
                        "unit_filter",
                        sources.history?.preview.source_review?.units?.length
                          ? v
                          : "",
                      );
                    }}
                  />
                </Field>
                <Field title={uiText("Time interval")}>
                  <Pick
                    label={uiText("Time interval")}
                    value={settings.frequency}
                    options={["monthly", "weekly", "daily"]}
                    onChange={(v) => change("frequency", v)}
                  />
                </Field>
                <Field
                  title={uiText("How far ahead?")}
                  help={uiText("Shorter horizons can be validated with less history.")}
                >
                  <div className="input-suffix">
                    <input
                      aria-label={uiText("Forecast horizon")}
                      type="number"
                      min="1"
                      max="24"
                      value={settings.horizon}
                      onChange={(e) =>
                        change(
                          "horizon",
                          e.target.value === "" ? "" : Number(e.target.value),
                        )
                      }
                    />
                    <span>
                      {settings.frequency === "monthly"
                        ? uiText("months")
                        : settings.frequency === "weekly"
                          ? uiText("weeks")
                          : uiText("days")}
                    </span>
                  </div>
                </Field>
              </div>
              {!chooseMethodsLater&&<Field
                title={uiText("Forecast method")}
                help={uiText("The default compares methods on past periods and selects the strongest fit for each item.")}
              >
                <Pick
                  label={uiText("Forecast method")}
                  value={settings.method_selection}
                  options={METHODS.map(([value,text])=>[value,uiText(text)])}
                  onChange={(v) => change("method_selection", v)}
                />
              </Field>}
              <details className="optional-section">
                <summary>{uiText("Working calendar")}{" "}
                  <span>
                    {settings.calendar_country === "IR"
                      ? uiText("Iran")
                      : settings.calendar_country || "No holidays"}
                  </span>
                </summary>
                <p className="muted">{uiText("Public holidays are added automatically. Confirm the factory’s weekly breaks and extra closures. Moon-based dates may need local confirmation.")}</p>
                <div className="form-grid two">
                  <Field title={uiText("Holiday calendar")}>
                    <Pick
                      label={uiText("Holiday calendar")}
                      value={settings.calendar_country || "none"}
                      options={[
                        ["IR", uiText("Iran")],
                        ["TR", uiText("Turkey")],
                        ["AE", uiText("United Arab Emirates")],
                        ["DE", uiText("Germany")],
                        ["US", uiText("United States")],
                        ["none", uiText("No public holidays")],
                      ]}
                      onChange={(v) =>
                        change("calendar_country", v === "none" ? "" : v)
                      }
                    />
                  </Field>
                  <Field title={uiText("Weekly days off")}>
                    <Pick
                      label={uiText("Weekly days off")}
                      value={(settings.weekend_days || [4]).join(",") || "none"}
                      options={[
                        ["4", uiText("Friday")],
                        ["3,4", uiText("Thursday and Friday")],
                        ["4,5", uiText("Friday and Saturday")],
                        ["5,6", uiText("Saturday and Sunday")],
                        ["none", uiText("None")],
                      ]}
                      onChange={(v) =>
                        change(
                          "weekend_days",
                          v === "none" ? [] : v.split(",").map(Number),
                        )
                      }
                    />
                  </Field>
                </div>
                <Field
                  title={uiText("Extra closure dates")}
                  help="Use Gregorian dates, separated by commas. These affect calendar features, not supplied machine-capacity limits."
                >
                  <input
                    aria-label={uiText("Extra closure dates")}
                    placeholder="2026-10-01, 2026-10-02"
                    value={(settings.shutdown_dates || []).join(", ")}
                    onChange={(e) =>
                      change(
                        "shutdown_dates",
                        e.target.value
                          ? e.target.value.split(",").map((v) => v.trim())
                          : [],
                      )
                    }
                  />
                </Field>
              </details>
              {sources.history?.preview.source_review?.quantity_issues?.length >
                0 && (
                <details className="optional-section" open>
                  <summary>{uiText("Items needing review")}<span>{uiText("Negative quantities")}</span>
                  </summary>
                  <p className="muted">{uiText("Check these cells in the source. To explore the other items now, select the items to leave out. Their original values stay unchanged.")}</p>
                  {[
                    ...new Set(
                      sources.history.preview.source_review.quantity_issues
                        .filter(
                          (r) =>
                            !settings.unit_filter ||
                            r.unit === settings.unit_filter,
                        )
                        .map((r) => r.item),
                    ),
                  ].map((item) => (
                    <label className="check-row" key={item}>
                      <input
                        type="checkbox"
                        checked={(settings.excluded_items || []).includes(item)}
                        onChange={(e) =>
                          change(
                            "excluded_items",
                            e.target.checked
                              ? [...(settings.excluded_items || []), item]
                              : (settings.excluded_items || []).filter(
                                  (v) => v !== item,
                                ),
                          )
                        }
                      />
                      <span>{uiText("Leave out")}{item}
                        <small>
                          {sources.history.preview.source_review.quantity_issues
                            .filter((r) => r.item === item)
                            .map((r) => `${r.cell}: ${fmt(r.value)}`)
                            .join(" · ")}
                        </small>
                      </span>
                    </label>
                  ))}
                </details>
              )}
              <details
                className="optional-section"
                open={advanced}
                onToggle={(e) => setAdvanced(e.currentTarget.open)}
              >
                <summary>{uiText("Additional factors")}{" "}
                  <span>
                    {settings.drivers.length
                      ? `${settings.drivers.length} selected`
                      : uiText("Optional")}
                  </span>
                </summary>
                <p className="muted">{uiText("Select only factors you want the model to test. They need values for the future periods.")}</p>
                {factors.length ? (
                  <div className="factor-list">
                    {factors.map((c) => (
                      <label key={c} className="check-row">
                        <input
                          type="checkbox"
                          checked={settings.drivers.includes(c)}
                          onChange={(e) =>
                            change(
                              "drivers",
                              e.target.checked
                                ? [...settings.drivers, c]
                                : settings.drivers.filter((x) => x !== c),
                            )
                          }
                        />
                        <span>
                          {label(c)}
                          <small>
                            {sources.future?.preview.columns.includes(c)
                              ? uiText("Available in future file")
                              : uiText("No future column")}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="muted">{uiText("Your file has no additional factor columns.")}</p>
                )}
                {settings.drivers.length > 0 && (
                  <Field
                    title={uiText("If future values are missing")}
                    help={uiText("Keeping this at “Ask me to fix the file” avoids inventing future assumptions.")}
                  >
                    <Pick
                      label={uiText("Missing future values")}
                      value={settings.future_driver_policy}
                      options={[
                        ["require", uiText("Ask me to fix the file")],
                        ["carry", uiText("Repeat the last known value")],
                        ["median", uiText("Use the historical middle value")],
                      ]}
                      onChange={(v) => change("future_driver_policy", v)}
                    />
                  </Field>
                )}
              </details>
            </>
          ) : (
            <>
              <div className="section-heading">
                <div>
                  <h2>{unchanged ? uiText("Saved data") : uiText("Ready to save")}</h2>
                  <p>
                    {unchanged
                      ? uiText("Use these inputs for a forecast, or go back to make changes.")
                      : uiText("Check the data that will go into the forecast.")}
                  </p>
                </div>
                <CheckCircle size={26} />
              </div>
              <dl className="review-list">
                <div>
                  <dt>{uiText("Name")}</dt>
                  <dd>{name}</dd>
                </div>
                <div>
                  <dt>{uiText("History")}</dt>
                  <dd>
                    {settings.frequency==='monthly'&&settings.month_basis==='jalali'?planningMonth(review?.summary.start,'jalali'):date(review?.summary.start)} – {settings.frequency==='monthly'&&settings.month_basis==='jalali'?planningMonth(review?.summary.end,'jalali'):date(review?.summary.end)}
                  </dd>
                </div>
                <div>
                  <dt>{uiText("Data")}</dt>
                  <dd>
                    {fmt(review?.summary.rows, 0)}{' '}{uiText("rows ·")}{" "}
                    {fmt(review?.summary.series, 0)} {settings.series_mode === 'customer_product' ? uiText("customer–product pairs") : uiText("groups")}
                  </dd>
                </div>
                <div>
                  <dt>{uiText("Forecast")}</dt>
                  <dd>
                    {settings.frequency==='monthly'&&settings.month_basis==='jalali'?planningMonth(review?.forecast_start,'jalali'):date(review?.forecast_start)} –{" "}
                    {settings.frequency==='monthly'&&settings.month_basis==='jalali'?planningMonth(review?.forecast_end,'jalali'):date(review?.forecast_end)} · {settings.unit}
                  </dd>
                </div>
                {!chooseMethodsLater&&<div>
                  <dt>{uiText("Method")}</dt>
                  <dd>
                    {uiText(METHODS.find(
                      ([v]) => v === settings.method_selection,
                    )?.[1] ||
                      settings.method_selection?.replace(/^model:/, "") ||
                      "Choose the best fit")}
                  </dd>
                </div>}
                <div><dt>{uiText("Planning months")}</dt><dd>{(review?.sales_conventions?.forecast_month_basis||settings.month_basis)==='jalali'?uiText("Persian"):uiText("Gregorian")}</dd></div>
                <div><dt>{uiText("Sales meaning")}</dt><dd>{uiText({customer_demand:'Customer demand',shipped:'Shipped quantities',invoiced:'Invoiced quantities'}[review?.sales_conventions?.sales_measure||settings.sales_measure]||'Recorded sales · meaning unconfirmed')}</dd></div>
                <div>
                  <dt>{uiText("Extra factors")}</dt>
                  <dd>
                    {settings.drivers.length
                      ? settings.drivers.map(label).join(", ")
                      : uiText("None selected")}
                  </dd>
                </div>
              </dl>
              <RepeatUploadReview review={review?.repeat_upload} ui={inventoryUi} basis={settings.month_basis}/>
              {!!review?.repeat_upload&&!review?.warnings.length&&<label className="check-row"><input type="checkbox" checked={accepted} onChange={e=>setAccepted(e.target.checked)}/>{uiText("I reviewed the changed and removed history.")}</label>}
              {review?.warnings.length > 0 && (
                <div className="review-warnings">
                  <h3>{uiText("Check these data adjustments")}</h3>
                  <ul>
                    {review.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                  <label className="check-row">
                    <input
                      type="checkbox"
                      checked={accepted}
                      onChange={(e) => setAccepted(e.target.checked)}
                    />
                    {review?.repeat_upload?uiText("I reviewed the changed history and these adjustments"):uiText("I reviewed these adjustments")}
                  </label>
                </div>
              )}
            </>
          )}
        </section>
        <footer className="wizard-footer">
          <Button
            disabled={step === 0 || !!pending}
            onClick={() => {
              if(initial?.business_candidate_id&&step===1)return onCancel();
              setStep(step - 1);
              setError("");
            }}
          >
            <ArrowLeft size={17} />{uiText("Back")}</Button>
          <span aria-live="polite">
            {pending
              ? pending === "validation"
                ? uiText("Checking dates, quantities and future coverage…")
                : pending === "save"
                  ? uiText("Saving dataset…")
                  : uiText("Reading file…")
              : uiText('stepProgress',{step:step+1,total:4})}
          </span>
          <div className="row-actions">
            {step === 3 ? (
              <>
                <Button
                  kind={onRun ? undefined : 'primary'}
                  disabled={
                    !!pending || ((!!review?.warnings.length || !!review?.repeat_upload) && !accepted)
                  }
                  onClick={() => finish(false)}
                >
                  {unchanged ? uiText("Done") : onRun ? uiText("Save data") : uiText("Save & continue")}
                </Button>
                {onRun && <Button
                  kind="primary"
                  disabled={
                    !!pending || ((!!review?.warnings.length || !!review?.repeat_upload) && !accepted)
                  }
                  onClick={() => finish(true)}
                >
                  {unchanged ? uiText("Forecast") : uiText("Save & forecast")}
                  <ArrowRight size={17} />
                </Button>}
              </>
            ) : (
              <Button
                kind="primary"
                disabled={!!pending || (step === 0 && !sources.history)}
                onClick={next}
              >
                {step === 2 ? uiText("Check data") : uiText("Continue")}
                <ArrowRight size={17} />
              </Button>
            )}
          </div>
        </footer>
      </div>
    </Page>
  );
}

function SourceCard({
  role,
  title,
  source,
  pending,
  onFile,
  onRemove,
  onSheet,
}) {
  const id = useId();
  const fileInput = useRef(null);
  const [drag, setDrag] = useState(false);
  return (
    <div
      className={`source-card ${source ? "attached" : ""} ${drag ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDrag(false);
        if (!pending) onFile(role, e.dataTransfer.files[0]);
      }}
    >
      <div className="source-top">
        <div className="file-icon">
          {source ? <FileText size={25} /> : <UploadSimple size={25} />}
        </div>
        <div className="source-copy">
          <h3>{title}</h3>
          {source ? (
            <>
              <strong>{source.name}</strong>
              <small>
                {fmt(source.preview.rows, 0)}{' '}{uiText("rows")}{role === "operations" ? uiText(" in first worksheet") : ""}
                {source.sheet ? ` · ${source.sheet}` : ""}
              </small>
            </>
          ) : (
            <p>
              {role === "operations"
                ? "Excel workbook with recipes, material stock and monthly capacity. Match your columns in the next step."
                : uiText("Drop a file here or choose one.")}
            </p>
          )}
        </div>
        <input
          id={id}
          ref={fileInput}
          hidden
          type="file"
          aria-label={uiText('Upload {{label}}',{label:title})}
          accept={
            role === "operations"
              ? ".xlsx,.xlsm"
              : ".csv,.xlsx,.xlsm,.tsv,.json,.jsonl,.ndjson,.txt"
          }
          disabled={!!pending}
          onChange={(e) => {
            onFile(role, e.target.files[0]);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          disabled={!!pending}
          aria-label={uiText(source?'Replace {{label}}':'Upload {{label}}',{label:title})}
          className="btn secondary file-trigger"
          onClick={() => fileInput.current?.click()}
        >
          {source ? uiText("Replace") : uiText("Choose file")}
        </button>
        {source && (
          <button
            className="icon-btn"
            aria-label={uiText('Remove {{label}}',{label:title})}
            disabled={!!pending}
            onClick={() => onRemove(role)}
          >
            <X size={19} />
          </button>
        )}
      </div>
      {source?.preview.sheets?.length > 1 && role !== "operations" && (
        <Field title={uiText("Worksheet")}>
          <Pick
            label={`${title} worksheet`}
            value={source.sheet}
            options={source.preview.sheets.map((x) => [x, x])}
            disabled={!!pending}
            onChange={(v) => onSheet(role, v)}
          />
        </Field>
      )}
      {role === "history" && !source && (
        <div className="file-hint">{uiText("CSV · Excel · TSV · JSON · up to 50 MB")}</div>
      )}
    </div>
  );
}
function Preview({ source, columns }) {
  const cols = [
    ...new Set(
      columns.length ? columns : (source?.preview.columns || []).slice(0, 4),
    ),
  ];
  return (
    <Table headers={cols}>
      {source?.preview.sample.map((r, i) => (
        <tr key={i}>
          {cols.map((c) => (
            <td key={c}>
              {r[c] == null ? (
                <span className="muted">{uiText("Empty")}</span>
              ) : (
                String(r[c]).slice(0, 100)
              )}
            </td>
          ))}
        </tr>
      ))}
    </Table>
  );
}

function ForecastPage({
  run,
  datasets,
  runs,
  plans,
  openRun,
  runDataset,
  importNew,
  startNewForecast,
  navigate,
  setDataView,
  tab,
  setTab,
  refresh,
  notify,
  chosenPlan,
  setChosenPlan,
  decisionTarget,
  access,
  canEdit,
}) {
  const [item, setItem] = useState("__all__"),
    [accuracyView, setAccuracyView] = useState("tests"),
    [range, setRange] = useState(true),
    [error, setError] = useState(""),
    [dialog, setDialog] = useState(""),
    [form, setForm] = useState({}),
    [working, setWorking] = useState(false);
  const [editingAssumptions, setEditingAssumptions] = useState(false);
  useEffect(() => {
    setItem(
      decisionTarget?.item && run?.series?.[decisionTarget.item]
        ? decisionTarget.item
        : "__all__",
    );
    setError("");
    setEditingAssumptions(false);
    if (decisionTarget?.save) {
      setForm({
        name: run?.dataset_name || "Demand plan",
        owner: access.user?.name || "",
      });
      setDialog("plan");
    }
  }, [run?.run_id, decisionTarget]);
  const periodDate = (s) => run?.run_settings?.frequency==='monthly'&&planningBasis(run)==='jalali'?planningMonth(s,'jalali'):date(s, run?.run_settings?.frequency !== "monthly");
  const dataset = datasets.find((d) => d.id === run?.dataset_id);
  const plan = plans.find(
    (p) =>
      p.id === chosenPlan &&
      p.run_id === run?.run_id &&
      ["approved", "published"].includes(p.status),
  );
  const series = run?.series?.[item];
  const forecasts = series?.forecast || [];
  const historical = series?.history || [];
  const unit = run?.unit || "tonnes";
  const total = forecasts.reduce((a, r) => a + r.mean, 0);
  const currentOverrides = new Map();
  for (const o of plan?.overrides || [])
    if (!o.reverted_at)
      currentOverrides.set(`${o.item_id}/${o.period.slice(0, 10)}`, o.value);
  const adjusted = (row) => {
    let value = row.mean;
    if (item !== "__all__")
      return (
        currentOverrides.get(`${item}/${row.timestamp.slice(0, 10)}`) ?? value
      );
    for (const id of run?.items || []) {
      const v = currentOverrides.get(`${id}/${row.timestamp.slice(0, 10)}`);
      if (v != null) {
        const original = run.series[id].forecast.find(
          (x) => x.timestamp === row.timestamp,
        );
        if (original) value += v - original.mean;
      }
    }
    return value;
  };
  const hasOverrides = forecasts.some((r) => adjusted(r) !== r.mean);
  const history = historical.slice(-24);
  const chart = history
    .map((r, i) => ({
      date: r.timestamp,
      actual: r.target,
      ...(i === history.length - 1
        ? {
            forecast: r.target,
            ...(hasOverrides ? { approved: r.target } : {}),
            range: [r.target, r.target],
          }
        : {}),
    }))
    .concat(
      forecasts.map((r) => ({
        date: r.timestamp,
        forecast: r.mean,
        ...(hasOverrides ? { approved: adjusted(r) } : {}),
        range: r.p10 != null && r.p90 != null ? [r.p10, r.p90] : null,
      })),
    );
  const runOptions = runs
    .filter((r) => !r.scenario_name || r.run_id === run.run_id)
    .map((r) => [
      r.run_id,
      `${r.name} · ${new Date(r.created_at * 1000).toLocaleString(i18n.language==='fa'?'fa-IR-u-ca-gregory':'en-GB', { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`,
    ]);
  async function submit(e) {
    e.preventDefault();
    setWorking(true);
    setError("");
    try {
      if (dialog === "plan") {
        const p = await api("/api/plans", {
          name: form.name,
          owner: form.owner,
          run_id: run.run_id,
          site_id: run.site?.id,
        });
        await refresh();
        notify("Draft plan saved");
        setDialog("");
        setChosenPlan(p.id);
        navigate("plans");
      } else if (dialog === "scenario") {
        await runDataset(dataset.id, {
          adjustment: Number(form.adjustment),
          scenario_name: form.name,
          base_run_id: run.run_id,
        });
        setDialog("");
      } else if (dialog === "method") {
        startNewForecast(dataset.id, `model:${form.model}`);
        setDialog("");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  }
  if (!run)
    return (
      <Page title={uiText('Calculation details')}>
        <section className="surface">
          <Empty
            icon={ChartLineUp}
            title={uiText("Create your first forecast")}
            action={
              <Button kind="primary" onClick={importNew} disabled={!canEdit}>{uiText("Import data")}<ArrowRight size={17} />
              </Button>
            }
          >{uiText("Start with your historical data. We’ll help you match the columns and choose a forecasting method.")}</Empty>
        </section>
      </Page>
    );
  return (
    <Page title={uiText('Calculation details')} actions={<Button onClick={()=>navigate('demand')}><ArrowLeft/>{uiText('Forecast')}</Button>}>
      <div className="forecast-toolbar">
        <div className="run-select">
          <Pick
            label={uiText("Forecast version")}
            value={run.run_id}
            options={
              runOptions.length
                ? runOptions
                : [[run.run_id, uiText("Current forecast")]]
            }
            onChange={openRun}
          />
        </div>
        <div className="row-actions">
          <a className="btn secondary" href={apiLink(`/api/export/${run.run_id}/xlsx`)}>
            <DownloadSimple size={18} />{uiText("Export model estimate")}</a>
          <Button onClick={()=>navigate('demand')}>{uiText("Review demand & orders")}</Button>
        </div>
      </div>
      <p className="forecast-method-note">{uiText("Method:")}{" "}
        <strong>
          {run.method_selection === "recommended"
            ? uiText("Chosen automatically per item")
            : run.method_selection?.startsWith("model:")
              ? uiText(run.method_selection.slice(6))
              : uiText(run.best_model || "Not recorded")}
        </strong>
      </p>
      {plans.some(
        (p) =>
          p.run_id === run.run_id &&
          ["approved", "published"].includes(p.status),
      ) && (
        <div className="plan-comparison-control">
          <Pick
            label={uiText("Compare with approved plan")}
            value={plan?.id || ""}
            onChange={(value) => setChosenPlan(value || null)}
            options={[
              ["", uiText("Forecast only")],
              ...plans
                .filter(
                  (p) =>
                    p.run_id === run.run_id &&
                    ["approved", "published"].includes(p.status),
                )
                .map((p) => [p.id, p.name]),
            ]}
          />
        </div>
      )}
      {run.scenario_name && (
        <div className="section-heading">
          <div>
            <strong>{run.scenario_name}</strong>
            <p>
              {run.scenario?.type === "factor_assumptions"
                ? uiText("Forecast recalculated with reviewed future inputs.")
                : run.scenario?.type === "factor_comparison"
                  ? uiText("Recalculated without extra factors. Sales history and calendar are unchanged; customer orders are not included in this comparison.")
                : run.scenario?.type === "factor_link"
                  ? uiText("Recalculated with a reviewed, dated factor. Original sales quantities and customer orders are unchanged.")
                : run.scenario?.type === "factor_batch"
                  ? uiText("Each customer/product group was calculated separately. Other products retain their baseline. Review orders next.")
                : uiText("A percentage adjustment to the original forecast.")}
            </p>
          </div>
          <Button onClick={() => openRun(run.base_run_id)}>{uiText("Back to baseline")}</Button>
        </div>
      )}
      <FactorLinkEvidence scenario={run.scenario} ui={inventoryUi}/>
      <BatchEvidence scenario={run.scenario} run={run} ui={inventoryUi}/>
      <FactorEvaluation run={run} ui={inventoryUi}/>
      <AssumptionEvidence
        scenario={run.scenario}
        ui={inventoryUi}
        fmt={fmt}
        date={date}
      />
      {run.metrics?.evidence_level === "limited" && run.evidence_policy!=='reviewed_what_if' && run.scenario?.type !== "factor_batch" && (
        <div className="source-notice forecast-evidence" role="status">
          <div>
            <strong>{uiText("More history needed")}</strong>
            <p>{uiText("Check the limited test evidence before using this forecast.")}</p>
          </div>
          <Button onClick={() => setTab("accuracy")}>{uiText("View accuracy check")}</Button>
        </div>
      )}
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          ["outlook", "Outlook"],
          ["methods", "Methods"],
          ["accuracy", "Accuracy"],
          ["scenarios", "Scenarios"],
        ]}
      />
      <ErrorBox error={!dialog ? error : ""} />
      {tab === "orders" ? (
        <SalesDemand api={api} ui={inventoryUi} run={run} canEdit={canEdit} showHeading={false} startNewForecast={startNewForecast}/>
      ) : tab === "outlook" ? (
        <>
          <div className="view-toolbar">
            <Pick
              label={uiText("Product or total")}
              value={item}
              options={[
                ["__all__", uiText('All customers & products')],
                ...(run.items || []).map((id) => [id, salesSeriesLabel(run,id)]),
              ]}
              onChange={setItem}
            />
            {run.evidence_policy!=='reviewed_what_if'&&(run.scenario?.type !== "factor_batch" || forecasts.some(r=>r.p10!=null&&r.p90!=null))&&<label className="check-row">
              <input
                type="checkbox"
                checked={range}
                onChange={(e) => setRange(e.target.checked)}
              />{uiText("Show planning range")}<Help
                text={
                  run.metrics?.range_check
                    ? uiText("A range targeting 80% of outcomes, based on earlier errors. See Accuracy for its later-period check. Small samples, pooled forecast steps and changing conditions limit confidence. Blank bounds mean more history is needed; scenarios are not verified probabilities.")
                    : uiText("An indicative range based on earlier errors. Its future coverage has not been independently verified; it is not a guarantee.")
                }
              />
            </label>}
          </div>
          <section className="surface chart-surface">
            {run.evidence_policy==='reviewed_what_if'?<p className="table-note">{uiText('What-if forecast. Past accuracy and forecast ranges are not verified.')}</p>:range && forecasts.some((r) => r.p10 == null || r.p90 == null) && (
              <p className="muted">
                {run.scenario?.type === "factor_batch"
                  ? uiText("A combined planning range is not available. See each group’s calculation evidence.")
                  : uiText("Some periods have no supported range. More historical observations are needed.")}
              </p>
            )}
            <div className="forecast-stats">
              <div>
                <span>{uiText("Forecast total")}<Help text={uiText("The sum of forecasts across the selected future periods.")} />
                </span>
                <strong>
                  {fmt(total, 0)}
                  <small>{unitLabel(unit)}</small>
                </strong>
              </div>
              <div>
                <span>{periodDate(forecasts[0]?.timestamp)}</span>
                <strong>
                  {fmt(forecasts[0]?.mean)}
                  <small>{unitLabel(unit)}</small>
                </strong>
              </div>
              <div>
                <span>
                  {run.metrics?.independent_accuracy_verified
                    ? uiText("Later-period error")
                    : uiText("Selection error")}
                  <Help text={uiText("Later-period error uses periods kept out of automatic method selection. If you choose a method after viewing these results, confirm your choice against new actuals. Selection error uses the periods that chose the method. Neither guarantees future accuracy.")} />
                </span>
                <strong>
                  {pct(
                    item === "__all__"
                      ? run.metrics?.wape_pct
                      : run.series_diagnostics?.[item]?.wape_pct,
                  )}
                </strong>
              </div>
            </div>
            <div className="chart-legend">
              <span>
                <i className="actual" />{uiText("Actual")}</span>
              <span>
                <i />{uiText("Forecast")}</span>
              {hasOverrides && (
                <span>
                  <i className="approved" />{uiText("Approved plan")}</span>
              )}
            </div>
            <div className="forecast-chart">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={chart}
                  margin={chartTheme.forecastMargin}
                >
                  <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d) => periodDate(d)}
                    minTickGap={65}
                    interval="preserveStartEnd"
                    padding={{ left: 8, right: 16 }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    width={78}
                    tickFormatter={(v) => fmt(v, 0)}
                    tickLine={false}
                    axisLine={false}
                  />
                  <ChartTooltip
                    labelFormatter={(d) => periodDate(d)}
                    formatter={(value, name) => [
                      Array.isArray(value)
                        ? value.map((x) => fmt(x)).join(" – ")
                        : `${fmt(value)} ${unit}`,
                      {
                        forecast: "Forecast",
                        actual: "Actual",
                        range: "Indicative range",
                        approved: "Approved plan",
                      }[name],
                    ]}
                  />
                  {range && (
                    <Area
                      type="linear"
                      dataKey="range"
                      fill="var(--chart-range)"
                      stroke="none"
                      fillOpacity={0.6}
                      isAnimationActive={false}
                    />
                  )}
                  <Line
                    type="linear"
                    dataKey="actual"
                    stroke="var(--chart-history)"
                    strokeWidth={2.3}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="linear"
                    dataKey="forecast"
                    stroke="var(--chart-forecast)"
                    strokeWidth={2.7}
                    dot={false}
                    isAnimationActive={false}
                  />
                  {hasOverrides && (
                    <Line
                      type="linear"
                      dataKey="approved"
                      stroke="var(--chart-forecast)"
                      strokeWidth={2.4}
                      strokeDasharray="6 3"
                      dot={false}
                      isAnimationActive={false}
                    />
                  )}
                  <ReferenceLine
                    x={history.at(-1)?.timestamp}
                    stroke="var(--chart-expected)"
                    strokeDasharray="4 6"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </section>
          <details className="surface disclosure">
            <summary>{uiText("Period values")}<span>{forecasts.length}{' '}{uiText("periods")}</span>
            </summary>
            <Table
              headers={[
                uiText("Period"),
                `Forecast (${unit})`,
                ...(hasOverrides ? [uiText("Approved plan")] : []),
                uiText("Low"),
                uiText("High"),
              ]}
            >
              {forecasts.map((r) => (
                <tr key={r.timestamp}>
                  <td>{periodDate(r.timestamp)}</td>
                  <td>{fmt(r.mean)}</td>
                  {hasOverrides && <td>{fmt(adjusted(r))}</td>}
                  <td>{fmt(r.p10)}</td>
                  <td>{fmt(r.p90)}</td>
                </tr>
              ))}
            </Table>
          </details>
          {run.drivers?.length > 0 && (
            <details className="surface disclosure">
              <summary>{uiText("Factors used in this forecast")}<span>{run.drivers.length}{' '}{uiText("factors")}</span>
              </summary>
              <Table headers={[uiText("Factor"), uiText("Association"), uiText("Role")]}>
                {run.drivers.map((d) => (
                  <tr key={d.feature}>
                    <td>{label(d.feature)}</td>
                    <td>
                      {label(d.direction)}
                      <Help text={uiText("Association shows how this factor moved with demand historically; it does not establish causation.")} />
                    </td>
                    <td>{label(d.role)}</td>
                  </tr>
                ))}
              </Table>
            </details>
          )}
        </>
      ) : tab === "methods" ? (
        <>
          <div className="section-heading">
            <div>
              <h2>{uiText("Compare forecasting methods")}</h2>
              <p>{uiText(run.evidence_policy==='reviewed_what_if'?'What-if forecast. Past accuracy and forecast ranges are not verified.':"Choose using earlier periods. Check the choice against a later period when enough history is available.")}</p>
            </div>
          </div>
          {!dataset && (
            <div className="inline-message">{uiText("This earlier run has no saved inputs.")}{" "}
              <button onClick={importNew}>{uiText("Import its source files")}</button>{uiText("to rerun a method.")}</div>
          )}
          <section className="surface methods-table">
            <Table
              headers={[
                uiText("Method"),
                <>{uiText("Selection error")}<Help text={uiText("Error on the earlier periods used to choose a method. Lower is better, but this is not independent evidence of future performance.")} />
                </>,
                <>{uiText("Later check")}<Help text={uiText("These later periods are kept out of automatic method selection. If you choose a method after comparing this column, it is no longer an independent test of your choice. Confirm that choice against new actual results.")} />
                </>,
                "",
              ]}
              empty={
                !run.leaderboard?.length && uiText("No model comparison is available.")
              }
            >
              {run.leaderboard?.map((m, i) => (
                <tr key={m.model}>
                  <td>
                    <strong>{uiText(m.model)}</strong>
                    <Help
                      text={
                        uiText(METHOD_HELP[m.model] ||
                        "This mathematical method is tested against the same held-out periods as the other methods.")
                      }
                    />
                    {i === 0 && m.wape_pct!=null && m.status !== "unavailable" && (
                      <small>{uiText("Lowest selection error")}</small>
                    )}
                    {m.status === "unavailable" && (
                      <small>{uiText("Not enough evidence or could not fit")}<Help
                          text={
                            m.failure_examples?.[0] ||
                            "This method could not be tested on all selection periods."
                          }
                        />
                      </small>
                    )}
                  </td>
                  <td>{pct(m.wape_pct)}</td>
                  <td>{pct(m.confirmation?.wape_pct)}</td>
                  <td>
                    {run.method_selection === 'factor_test' ? <span className="muted">{uiText("Per-customer factor test")}</span> : run.method_selection === `model:${m.model}` ? (
                      <span>{uiText("Current method")}</span>
                    ) : (
                      <Button
                        disabled={
                          !canEdit || !dataset || m.status === "unavailable"
                        }
                        onClick={() => {
                          setError("");
                          setForm({ model: m.model });
                          setDialog("method");
                        }}
                      >{uiText("Use method")}</Button>
                    )}
                  </td>
                </tr>
              ))}
            </Table>
          </section>
        </>
      ) : tab === "accuracy" ? (
        <>
          <Tabs
            value={accuracyView}
            onChange={setAccuracyView}
            items={[
              ["tests", "Historical tests"],
              ["actuals", "Actual results"],
            ]}
          />
          {accuracyView === "actuals" ? (
            <ActualResults
              key={run.run_id}
              ui={inventoryUi}
              api={api}
              run={run}
              plans={plans}
              fmt={fmt}
              date={date}
              importNew={importNew}
            />
          ) : run.evidence_policy==='reviewed_what_if'?<section className="surface"><p>{uiText('What-if forecast. Past accuracy and forecast ranges are not verified.')}</p></section> : (
            <>
              <div className="section-heading">
                <div>
                  <h2>{uiText("How well did it predict past demand?")}</h2>
                  <p>
                    {fmt(run.metrics?.validation_points, 0)}{' '}{uiText("observations ·")}{" "}
                    {run.metrics?.independent_accuracy_verified
                      ? uiText("Separate later-period check")
                      : uiText("Selection periods only — no independent check")}
                  </p>
                </div>
                <Pill
                  tone={
                    run.metrics?.evidence_level === "limited" ? "warning" : ""
                  }
                >
                  {label(run.metrics?.evidence_level)}{uiText("evidence")}</Pill>
              </div>
              <div className="accuracy-summary surface">
                <div>
                  <span>
                    {run.metrics?.independent_accuracy_verified
                      ? uiText("Later-period error")
                      : uiText("Selection error")}
                    <Help text={uiText("Total absolute error divided by total actual demand (WAPE). Later periods are kept out of automatic method selection. Choosing manually after viewing their results needs a fresh check against new actuals.")} />
                  </span>
                  <strong>{pct(run.metrics?.wape_pct)}</strong>
                </div>
                <div>
                  <span>{uiText("Bias")}<Help text={uiText("Near zero is better. Negative means forecasts were too low on average.")} />
                  </span>
                  <strong>{pct(run.metrics?.bias_pct)}</strong>
                </div>
                <div>
                  <span>{uiText("Independent check")}<Help text={uiText("Later periods are kept out of automatic method selection. If available, the range check below separately shows how often actual demand fell inside the planning range.")} />
                  </span>
                  <strong>
                    {run.metrics?.independent_accuracy_verified
                      ? uiText("Available")
                      : uiText("Not available")}
                  </strong>
                </div>
              </div>
              <RangeCheck run={run} ui={inventoryUi} fmt={fmt} />
              {!!run.input_manifest?.settings?.drivers?.length && <p className="muted">{run.metrics?.factor_test_note || 'This saved run predates the factor cutoff check. Recalculate before judging factor usefulness.'}</p>}
              <section className="surface">
                <Table headers={[uiText("Item"), uiText("Test error"), uiText("Bias"), uiText("Best method")]}>
                  {Object.entries(run.series_diagnostics || {}).map(
                    ([id, d]) => (
                      <tr key={id}>
                        <td>{salesSeriesLabel(run,id)}</td>
                        <td>{pct(d.wape_pct)}</td>
                        <td>{pct(d.bias_pct)}</td>
                        <td>{d.best_model}</td>
                      </tr>
                    ),
                  )}
                </Table>
              </section>
            </>
          )}
        </>
      ) : editingAssumptions ? (
        <AssumptionEditor
          key={run.run_id}
          run={run}
          api={api}
          ui={inventoryUi}
          fmt={fmt}
          date={periodDate}
          onCancel={() => setEditingAssumptions(false)}
          onSave={async (saved) => {
            await refresh();
            await runDataset(saved.id, { base_run_id: run.run_id });
            setEditingAssumptions(false);
          }}
        />
      ) : (
        <>
          <div className="section-heading scenario-actions">
            <div>
              <h2>{uiText("What if conditions change?")}</h2>
              <p>{uiText("Compare future inputs or a demand adjustment with this forecast.")}</p>
            </div>
            <div className="row-actions">
              <Button
                kind="primary"
                disabled={!canEdit || !dataset || !!run.scenario_name}
                onClick={() => setEditingAssumptions(true)}
              >{uiText("Change inputs")}</Button>
              <Button
                disabled={!canEdit || !dataset || !!run.scenario_name}
                onClick={() => {
                  setError("");
                  setForm({ name: "", adjustment: 10 });
                  setDialog("scenario");
                }}
              >
                <Plus size={17} />{uiText("Adjust demand")}</Button>
            </div>
          </div>
          {!dataset && (
            <div className="inline-message">{uiText("Import and save this forecast’s source files to create scenarios.")}</div>
          )}
          {!!dataset && !run.scenario_name && <FactorBatch key={`link-${run.run_id}`} run={run} api={api} ui={inventoryUi} canEdit={canEdit}
            onManageProfiles={()=>navigate('customers')}
            onManageSources={()=>{setDataView('external');navigate('data');}}
            onSaved={async(saved,request_id)=>{await refresh();const job=await runDataset(saved.id,{base_run_id:run.run_id,request_id});if(!job)throw new Error('Inputs saved, but calculation could not start. Retry to use the same saved comparison.');}}/>}
          <ScenarioList run={run} runs={runs} unit={unit} openRun={openRun} canEdit={canEdit} />
          {!!run.input_manifest?.settings?.drivers?.length && !run.scenario_name && <FactorReview
            key={`review-${run.run_id}`} run={run} api={api} ui={inventoryUi} canEdit={canEdit} fmt={fmt} date={(s)=>date(s,true)}
            onSaved={async(saved,request_id)=>{await refresh();const job=await runDataset(saved.id,{base_run_id:run.run_id,request_id});if(!job)throw new Error('Inputs saved, but calculation could not start. Retry to use the same saved comparison.');}}
          />}
        </>
      )}
      <Modal
        title={
          dialog === "plan"
            ? "Save as a plan"
            : dialog === "method"
              ? `Use ${form.model}`
              : uiText("New scenario")
        }
        open={!!dialog}
        onClose={() => !working && setDialog("")}
        description={
          dialog === "method"
            ? uiText("Creates a new forecast from the saved dataset using this method.")
            : undefined
        }
      >
        <form onSubmit={submit}>
          <ErrorBox error={error} />
          {dialog === "method" ? (
            <p>{uiText("Dataset:")}<strong>{dataset?.name}</strong>
            </p>
          ) : (
            <>
              <Field title={dialog === "plan" ? "Plan name" : uiText("Scenario name")}>
                <input
                  aria-label={dialog === "plan" ? "Plan name" : uiText("Scenario name")}
                  value={form.name || ""}
                  required
                  maxLength={120}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </Field>
              {dialog === "plan" ? (
                <Field title={uiText("Owner")}>
                  <input
                    aria-label="Plan owner"
                    disabled={!!access.user}
                    required
                    value={form.owner || ""}
                    onChange={(e) =>
                      setForm({ ...form, owner: e.target.value })
                    }
                  />
                </Field>
              ) : (
                <Field
                  title={uiText("Demand change")}
                  help={uiText("Applied to the forecast quantities. A value of 10 means 10% higher demand; −10 means 10% lower demand.")}
                >
                  <div className="input-suffix">
                    <input
                      aria-label={uiText("Demand change")}
                      type="number"
                      min="-90"
                      max="300"
                      step="0.1"
                      required
                      value={form.adjustment}
                      onChange={(e) =>
                        setForm({ ...form, adjustment: e.target.value })
                      }
                    />
                    <span>%</span>
                  </div>
                </Field>
              )}
            </>
          )}
          <div className="dialog-actions">
            <Button
              type="button"
              disabled={working}
              onClick={() => setDialog("")}
            >{uiText("Cancel")}</Button>
            <Button kind="primary" disabled={working} type="submit">
              {working
                ? uiText("Working…")
                : dialog === "plan"
                  ? "Save draft"
                  : dialog === "method"
                    ? uiText("Run forecast")
                    : uiText("Calculate scenario")}
            </Button>
          </div>
        </form>
      </Modal>
    </Page>
  );
}

function ScenarioList({ run, runs, unit, openRun, canEdit }) {
  const [rows, setRows] = useState([]);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    let live = true;
    setRows([]);
    setLoadError("");
    const scenarios = runs.filter(
      (r) => r.base_run_id === run.run_id && r.scenario_name,
    );
    Promise.all(scenarios.map((r) => api(`/api/runs/${r.run_id}`)))
      .then((rs) => live && setRows(rs))
      .catch((error) => live && setLoadError(error.message));
    return () => {
      live = false;
    };
  }, [run.run_id, runs]);
  const baseline = run.series.__all__.forecast.reduce((s, r) => s + r.mean, 0);
  const hasSupply = false;
  return (
    <section className="surface">
      <ErrorBox error={loadError} />
      <ScenarioChart
        api={api} canEdit={canEdit}
        base={run}
        scenarios={rows}
        ui={inventoryUi}
        fmt={fmt}
        date={(value) => date(value, run.run_settings?.frequency !== "monthly")}
      />
      {!!rows.length && <h3>{uiText("Overall totals · all customers and SKUs")}</h3>}
      <Table
        headers={[
          uiText("Scenario"),
          `Forecast (${unit})`,
          uiText("Change"),
          ...(hasSupply ? ["Material shortages", "Capacity shortfalls"] : []),
          "",
        ]}
      >
        <tr>
          <td>
            <strong>{uiText("Current forecast")}</strong>
          </td>
          <td>{fmt(baseline, 0)}</td>
          <td>—</td>
          {hasSupply && (
            <>
              <td>
                {run.operations.materials?.filter(
                  (r) => r.projected_balance < 0,
                ).length ?? "—"}
              </td>
              <td>
                {run.operations.capacity?.filter(
                  (r) => (r.gap_quantity ?? r.gap_tonnes) < 0,
                ).length ?? "—"}
              </td>
            </>
          )}
          <td />
        </tr>
        {rows.map((r) => {
          const total = r.series.__all__.forecast.reduce(
            (s, r) => s + r.mean,
            0,
          );
          return (
            <tr key={r.run_id}>
              <td>{r.scenario_name}</td>
              <td>{fmt(total, 0)}</td>
              <td>{baseline ? pct((total / baseline - 1) * 100) : "—"}</td>
              {hasSupply && (
                <>
                  <td>
                    {!r.operations?.source
                      ? "—"
                      : (r.operations?.materials?.filter(
                          (row) => row.projected_balance < 0,
                        ).length ?? "—")}
                  </td>
                  <td>
                    {!r.operations?.source
                      ? "—"
                      : (r.operations?.capacity?.filter(
                          (row) => (row.gap_quantity ?? row.gap_tonnes) < 0,
                        ).length ?? "—")}
                  </td>
                </>
              )}
              <td>
                <Button onClick={() => openRun(r.run_id)}>{uiText("Open scenario")}</Button>
              </td>
            </tr>
          );
        })}
      </Table>
      {hasSupply && (
        <p className="table-note">
          Shortages count material-periods below zero. Capacity shortfalls count
          overloaded machine-periods, not unique machines.
        </p>
      )}
      {!rows.length && <p className="table-note">{uiText("No scenarios yet.")}</p>}
    </section>
  );
}
function PlansPage({
  plans,
  refresh,
  notify,
  openPlan,
  chosenPlan,
  setChosenPlan,
  access,
  canEdit,
  canReview,
  navigate,
  importNew,
}) {
  const id = chosenPlan,
    setId = setChosenPlan;
  const [dialog, setDialog] = useState(""),
    [error, setError] = useState(""),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [source, setSource] = useState(null),
    [review, setReview] = useState(null),
    [search, setSearch] = useState(""),
    [onlyChanges, setOnlyChanges] = useState(false),
    [statusTarget, setStatusTarget] = useState(""),
    [actionReason, setActionReason] = useState(""),
    [reviewPage, setReviewPage] = useState(0),
    [revisionForm, setRevisionForm] = useState({}),
    [reversal, setReversal] = useState(null),
    [edit, setEdit] = useState({ item: "", period: "", value: "", reason: "" });
  const visiblePlans = plans;
  const plan = plans.find((p) => p.id === id);
  const currentAdjustmentIds = new Set([
    ...new Map(
      (plan?.overrides || [])
        .filter((o) => !o.reverted_at)
        .map((o) => [`${o.item_id}/${o.period.slice(0, 10)}`, o.id]),
    ).values(),
  ]);
  useEffect(() => {
    setReviewPage(0);
  }, [id, search, onlyChanges, plan?.updated_at]);
  useEffect(() => {
    let cancelled = false;
    setError("");
    setSource(null);
    setReview(null);
    if (plan)
      Promise.all([
        api(`/api/runs/${plan.run_id}`),
        api(`/api/plans/${id}/quantities`),
      ])
        .then(([source, quantities]) => {
          if (!cancelled) {
            setSource(source);
            setReview(quantities);
          }
        })
        .catch((e) => {
          if (!cancelled) setError(e.message);
        });
    return () => {
      cancelled = true;
    };
  }, [id, plan?.updated_at]);
  const reviewRows = (review?.rows || []).filter(
    (r) =>
      (!onlyChanges || (r.revision_change ?? r.adjustment) !== 0) &&
      (!search ||
        `${r.item_id} ${r.period}`
          .toLowerCase()
          .includes(search.toLowerCase())),
  );
  const currentQuantity = (item, period) =>
    review?.rows.find(
      (r) => r.item_id === item && r.period === period.slice(0, 10),
    )?.plan_quantity ??
    source?.series[item]?.forecast.find((r) => r.timestamp === period)?.mean;
  const beginEdit = (row) => {
    setEdit({
      item: row.item_id,
      period: row.period,
      value: row.plan_quantity,
      reason: "",
    });
    setDialog("override");
  };
  async function transition(status) {
    setBusy(true);
    setError("");
    try {
      await api(
        `/api/plans/${id}/status`,
        { status, actor: plan.owner, note: actionReason },
        "PATCH",
      );
      await refresh();
      setDialog("");
      setActionReason("");
      notify(`Plan ${status}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const next = { draft: "review", review: "approved", approved: "published" }[
    plan?.status
  ];
  const samePerson = (identity) =>
    !!identity &&
    !!access.user &&
    identity.issuer === access.user.issuer &&
    identity.subject === access.user.subject;
  const selfReview =
    samePerson(plan?.created_by) ||
    (plan?.overrides || []).some(
      (change) =>
        samePerson(change.identity) || samePerson(change.reverted_identity),
    );
  const approvalAccess =
    access.mode === "local"
      ? plan?.settings?.source_classification === "synthetic_sample"
      : canReview && !!plan?.created_by && !selfReview;
  return (
    <>
      <div className="page-heading">
        <div>
          {plan && (
            <button className="back-link" onClick={() => setId(null)}>
              <ArrowLeft size={16} />
              All plans
            </button>
          )}
          <h1>{plan ? plan.name : uiText("Saved reviews")}</h1>
          {!plan && <p>Review and approve saved model estimates. Start on Home to create a new sales forecast.</p>}
          {plan && (
            <p>
              {plan.owner} · {date(plan.updated_at, true)}
            </p>
          )}
        </div>
        {plan ? <Pill>{label(plan.status)}</Pill> : <Button onClick={() => navigate("today")}>Go to Home<ArrowRight size={17}/></Button>}
      </div>
      <ErrorBox error={error} />
      {plan?.parent_plan_id && (
        <div className="section-heading">
          <p>{uiText("Version")}{plan.version} · {plan.revision_reason}
          </p>
          <Button onClick={() => setId(plan.parent_plan_id)}>
            View previous version
          </Button>
        </div>
      )}
      {!plan ? (
        <section className="surface">
          {visiblePlans.length ? (
            <div className="record-list">
              {visiblePlans.map((p) => (
                <article key={p.id}>
                  <div className="record-info">
                    <strong>{p.name}</strong>
                    <p>
                      {p.owner} · {date(p.updated_at, true)}
                    </p>
                  </div>
                  <div className="row-actions">
                    <Pill>{label(p.status)}</Pill>
                    <Button onClick={() => setId(p.id)}>
                      Open
                      <ArrowRight size={16} />
                    </Button>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <Empty icon={Stack} title="No reviews waiting">
              Saved model estimates appear here for review and approval. This is not where you start a forecast.
            </Empty>
          )}
        </section>
      ) : (
        <>
          <div className="plan-toolbar">
            {["approved", "published"].includes(plan.status) && (
              <Button
                kind={plan.status === "published" ? "primary" : "secondary"}
                disabled={!review || !canEdit}
                onClick={() => {
                  setError("");
                  setRevisionForm({
                    name: `${plan.name} · revision`.slice(0, 120),
                    owner: access.user?.name || plan.owner,
                    reason: "",
                    request_id: crypto.randomUUID(),
                  });
                  setDialog("revision");
                }}
              >
                Create new version
              </Button>
            )}
            <a className="btn secondary" href={apiLink(`/api/plans/${plan.id}/export`)}>
              <DownloadSimple size={18} />
              Export plan
            </a>
            <Button onClick={() => openPlan(plan)}>{uiText("View forecast")}<ArrowRight size={16} />
            </Button>
            {["draft", "review"].includes(plan.status) && (
              <Button
                disabled={!source || !review || !canEdit}
                onClick={() => {
                  setEdit({
                    item: source.items[0],
                    period:
                      source.series[source.items[0]].forecast[0].timestamp,
                    value: currentQuantity(
                      source.items[0],
                      source.series[source.items[0]].forecast[0].timestamp,
                    ),
                    reason: "",
                  });
                  setDialog("override");
                }}
              >
                Adjust a value
              </Button>
            )}
            {next && (
              <Button
                kind="primary"
                disabled={
                  !review ||
                  busy ||
                  (next === "review" ? !canEdit : !approvalAccess) ||
                  (["approved", "published"].includes(next) &&
                    plan.metrics?.evidence_level === "limited")
                }
                onClick={() => {
                  setStatusTarget(next);
                  setActionReason("");
                  setDialog("status");
                }}
              >
                {next === "review"
                  ? "Send for review"
                  : next === "approved"
                    ? "Approve plan"
                    : "Publish plan"}
              </Button>
            )}
            {["review", "approved"].includes(plan.status) && (
              <Button
                disabled={busy || (!canEdit && !canReview)}
                onClick={() => {
                  setStatusTarget(
                    plan.status === "review" ? "draft" : "review",
                  );
                  setActionReason("");
                  setDialog("status");
                }}
              >
                Return to {plan.status === "review" ? "draft" : "review"}
              </Button>
            )}
          </div>
          {plan.metrics?.evidence_level === "limited" && (
            <p className="inline-message">
              More historical evidence is needed before this plan can be
              approved.
            </p>
          )}
          {["draft", "review", "approved"].includes(plan.status) &&
            !approvalAccess && (
              <p className="inline-message">
                {access.mode === "local"
                  ? "Company sign-in is required to approve real operating plans."
                  : selfReview
                    ? "A different reviewer must approve this plan."
                    : !plan.created_by
                      ? "This is a legacy local record. Save a new plan while signed in before approval."
                      : "An authorised reviewer can approve this plan."}
              </p>
            )}
          <section className="surface plan-quantities">
            <div className="section-heading">
              <h2>Quantities to review</h2>
              <Help
                text={`Forecast is the saved model output. Plan is the latest active adjustment, or the forecast where unchanged. These are the same quantities used in plan exports and approved supply.${plan.parent_plan_id ? " Previous plan is frozen when the draft version is created. Changed values only shows differences from that previous plan." : ""}`}
              />
            </div>
            {!review ? (
              <p role="status">
                {error
                  ? "Quantities could not be loaded."
                  : "Loading plan quantities…"}
              </p>
            ) : (
              <>
                <div className="plan-review-filters">
                  <input
                    aria-label="Find plan item or period"
                    placeholder="Find an item or period"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                  <label className="check-row">
                    <input
                      type="checkbox"
                      checked={onlyChanges}
                      onChange={(e) => setOnlyChanges(e.target.checked)}
                    />
                    Changed values only
                  </label>
                </div>
                <p className="muted">
                  {reviewRows.length}{" "}
                  {reviewRows.length === 1 ? "value" : "values"} ·{" "}
                  {source?.unit || plan.settings?.unit || "units"} · Forecast{" "}
                  {fmt(
                    reviewRows.reduce((sum, r) => sum + r.forecast_quantity, 0),
                  )}{" "}
                  → plan{" "}
                  {fmt(reviewRows.reduce((sum, r) => sum + r.plan_quantity, 0))}
                </p>
                <Table
                  headers={[
                    uiText("Item"),
                    uiText("Period"),
                    uiText("Forecast"),
                    ...(plan.parent_plan_id ? ["Previous plan"] : []),
                    "Plan",
                    plan.parent_plan_id ? "From previous" : uiText("Change"),
                    "Reason",
                    "",
                  ]}
                >
                  {reviewRows
                    .slice(reviewPage * 50, (reviewPage + 1) * 50)
                    .map((r) => (
                      <tr key={`${r.item_id}/${r.period}`}>
                        <td>{r.item_id}</td>
                        <td>{date(r.period)}</td>
                        <td>{fmt(r.forecast_quantity)}</td>
                        {plan.parent_plan_id && (
                          <td>{fmt(r.previous_plan_quantity)}</td>
                        )}
                        <td>{fmt(r.plan_quantity)}</td>
                        <td>
                          {(r.revision_change ?? r.adjustment) > 0 ? "+" : ""}
                          {fmt(r.revision_change ?? r.adjustment)}
                        </td>
                        <td>{r.reason || "—"}</td>
                        <td>
                          {["draft", "review"].includes(plan.status) && (
                            <Button
                              disabled={!canEdit}
                              onClick={() => beginEdit(r)}
                            >
                              Adjust
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                </Table>
                {!reviewRows.length && <p>No matching values.</p>}
                {reviewRows.length > 50 && (
                  <div className="row-actions plan-review-pagination">
                    <Button
                      disabled={reviewPage === 0}
                      onClick={() => setReviewPage((p) => p - 1)}
                    >
                      Previous values
                    </Button>
                    <span>
                      Page {reviewPage + 1}{' '}{uiText("of")}{" "}
                      {Math.ceil(reviewRows.length / 50)}
                    </span>
                    <Button
                      disabled={(reviewPage + 1) * 50 >= reviewRows.length}
                      onClick={() => setReviewPage((p) => p + 1)}
                    >
                      Next values
                    </Button>
                  </div>
                )}
              </>
            )}
          </section>
          {!!plan.overrides?.length && (
            <details className="surface disclosure">
              <summary>
                Adjustment history<span>{plan.overrides.length}</span>
              </summary>
              <div className="detail-body">
                <Table
                  headers={[
                    "Item / period",
                    "Quantity",
                    "Reason",
                    uiText("Status"),
                    "",
                  ]}
                >
                  {[...plan.overrides].reverse().map((o) => (
                    <tr key={o.id}>
                      <td>
                        {o.item_id}
                        <small>{date(o.period)}</small>
                      </td>
                      <td>{fmt(o.value)}</td>
                      <td>{o.reason}</td>
                      <td>
                        {o.reverted_at
                          ? "Reversed"
                          : plan.overrides.some(
                                (later) =>
                                  !later.reverted_at &&
                                  later.item_id === o.item_id &&
                                  later.period.slice(0, 10) ===
                                    o.period.slice(0, 10) &&
                                  plan.overrides.indexOf(later) >
                                    plan.overrides.indexOf(o),
                              )
                            ? "Replaced by later change"
                            : "Current"}
                      </td>
                      <td>
                        {currentAdjustmentIds.has(o.id) &&
                          ["draft", "review"].includes(plan.status) && (
                            <Button
                              disabled={!canEdit}
                              onClick={() => {
                                setReversal(o);
                                setActionReason("");
                                setDialog("revert");
                              }}
                            >
                              Reverse
                            </Button>
                          )}
                      </td>
                    </tr>
                  ))}
                </Table>
              </div>
            </details>
          )}
          <section className="surface">
            <div className="section-heading">
              <h2>Activity</h2>
            </div>
            <div className="activity-list">
              {[...(plan.history || [])].reverse().map((a, i) => (
                <article key={i}>
                  <div>
                    <strong>{a.note || label(a.status)}</strong>
                    <small>
                      {a.actor} · {date(a.at, true)}
                    </small>
                  </div>
                  <Pill>{label(a.status)}</Pill>
                </article>
              ))}
            </div>
          </section>
          <form
            className="surface note-form"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              try {
                await api(`/api/plans/${id}/comments`, {
                  text: note,
                  actor: plan.owner,
                });
                setNote("");
                await refresh();
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field title="Add a review note">
              <textarea
                aria-label={uiText("Review note")}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                required
                maxLength={1000}
                rows={3}
              />
            </Field>
            <Button
              disabled={busy || !note.trim() || (!canEdit && !canReview)}
              type="submit"
            >
              Add note
            </Button>
          </form>
        </>
      )}
      <Modal
        title={
          dialog === "status"
            ? `Move plan to ${label(statusTarget)}`
            : dialog === "revision"
              ? "Create a new draft version"
              : dialog === "revert"
                ? "Reverse adjustment"
                : "Adjust forecast value"
        }
        open={!!dialog}
        onClose={() => !busy && setDialog("")}
      >
        <ErrorBox error={error} />
        {dialog === "revision" ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                const created = await api(
                  `/api/plans/${id}/versions`,
                  revisionForm,
                );
                await refresh();
                setId(created.id);
                setDialog("");
                setOnlyChanges(false);
                notify("New draft version created");
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <p>
              The published or approved version stays unchanged. This draft uses
              the same forecast and current adjustments.
            </p>
            <Field title={uiText("Name")}>
              <input
                aria-label="Version name"
                required
                maxLength={120}
                value={revisionForm.name || ""}
                onChange={(e) =>
                  setRevisionForm({ ...revisionForm, name: e.target.value })
                }
              />
            </Field>
            <Field title={uiText("Owner")}>
              <input
                aria-label="Version owner"
                required
                maxLength={120}
                value={revisionForm.owner || ""}
                disabled={!!access.user}
                onChange={(e) =>
                  setRevisionForm({ ...revisionForm, owner: e.target.value })
                }
              />
            </Field>
            <Field title="Reason">
              <textarea
                aria-label="Version reason"
                required
                minLength={3}
                maxLength={500}
                rows={2}
                value={revisionForm.reason || ""}
                onChange={(e) =>
                  setRevisionForm({ ...revisionForm, reason: e.target.value })
                }
              />
            </Field>
            <div className="dialog-actions">
              <Button
                type="button"
                disabled={busy}
                onClick={() => setDialog("")}
              >{uiText("Cancel")}</Button>
              <Button kind="primary" disabled={busy}>
                Create draft
              </Button>
            </div>
          </form>
        ) : dialog === "revert" ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await api(`/api/plans/${id}/overrides/${reversal.id}/revert`, {
                  reason: actionReason,
                  actor: plan.owner,
                });
                await refresh();
                setDialog("");
                setActionReason("");
                notify("Adjustment reversed");
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <p>
              Reverse {reversal?.item_id} · {date(reversal?.period)}? The
              previous active value will apply; history is kept.
            </p>
            <Field title="Reason">
              <textarea
                required
                minLength={3}
                maxLength={500}
                aria-label="Reversal reason"
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
              />
            </Field>
            <div className="dialog-actions">
              <Button type="button" onClick={() => setDialog("")}>{uiText("Cancel")}</Button>
              <Button kind="primary" disabled={busy}>
                Reverse adjustment
              </Button>
            </div>
          </form>
        ) : dialog === "status" ? (
          <>
            <p>
              {statusTarget === "published"
                ? "Publishing locks this local plan version. It does not send it to an ERP or notify anyone."
                : `Move ${plan?.name} to ${label(statusTarget)}?`}
            </p>
            <Field title="Review note (optional)">
              <textarea
                aria-label="Status review note"
                value={actionReason}
                maxLength={1000}
                rows={2}
                onChange={(e) => setActionReason(e.target.value)}
              />
            </Field>
            <p className="muted">
              {access.user
                ? `Recorded as ${access.user.name} through company sign-in.`
                : "Local sample record only; identities are not verified."}
            </p>
            <div className="dialog-actions">
              <Button onClick={() => setDialog("")}>{uiText("Cancel")}</Button>
              <Button
                kind="primary"
                disabled={busy}
                onClick={() => transition(statusTarget)}
              >
                Confirm
              </Button>
            </div>
          </>
        ) : (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                await api(`/api/plans/${id}/overrides`, {
                  item_id: edit.item,
                  period: edit.period,
                  value: Number(edit.value),
                  reason: edit.reason,
                  actor: plan.owner,
                });
                await refresh();
                setDialog("");
                notify("Adjustment saved");
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field title={uiText("Item")}>
              <Pick
                label="Adjustment item"
                value={edit.item}
                options={source?.items.map((x) => [x, x]) || []}
                onChange={(v) =>
                  setEdit({
                    ...edit,
                    item: v,
                    period: source.series[v].forecast[0].timestamp,
                    value: currentQuantity(
                      v,
                      source.series[v].forecast[0].timestamp,
                    ),
                  })
                }
              />
            </Field>
            <Field title={uiText("Period")}>
              <Pick
                label="Adjustment period"
                value={edit.period}
                options={
                  source?.series[edit.item]?.forecast.map((r) => [
                    r.timestamp,
                    date(r.timestamp),
                  ]) || []
                }
                onChange={(v) =>
                  setEdit({
                    ...edit,
                    period: v,
                    value: currentQuantity(edit.item, v),
                  })
                }
              />
            </Field>
            <Field title={`New quantity (${source?.unit || "tonnes"})`}>
              <input
                aria-label="Adjusted quantity"
                type="number"
                step="any"
                min="0"
                required
                value={edit.value}
                onChange={(e) => setEdit({ ...edit, value: e.target.value })}
              />
            </Field>
            <Field title="Reason">
              <textarea
                aria-label="Adjustment reason"
                required
                minLength={3}
                maxLength={500}
                value={edit.reason}
                onChange={(e) => setEdit({ ...edit, reason: e.target.value })}
              />
            </Field>
            <div className="dialog-actions">
              <Button type="button" onClick={() => setDialog("")}>{uiText("Cancel")}</Button>
              <Button kind="primary" disabled={busy}>
                Save adjustment
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </>
  );
}

function SupplyPage({
  canEdit,
  run,
  plans,
  navigate,
  openInventory,
  chosenPlan,
  decisionTarget,
}) {
  const [tab, setTab] = useState(decisionTarget?.tab || "inventory"),
    [risk, setRisk] = useState(true),
    [period, setPeriod] = useState(""),
    [search, setSearch] = useState(decisionTarget?.search || ""),
    [planId, setPlanId] = useState(chosenPlan || ""),
    [approvedOp, setApprovedOp] = useState(null),
    [supplyError, setSupplyError] = useState(""),
    [loading, setLoading] = useState(false);
  const eligiblePlans = (plans || []).filter(
    (p) =>
      p.run_id === run?.run_id && ["approved", "published"].includes(p.status),
  );
  const op = planId ? approvedOp : run?.operations;
  useEffect(() => {
    let cancelled = false;
    setApprovedOp(null);
    setSupplyError("");
    if (!planId || !eligiblePlans.some((p) => p.id === planId)) {
      setPlanId("");
      setLoading(false);
      return;
    }
    if (tab === "inventory") {
      setLoading(false);
      return;
    }
    setLoading(true);
    api(`/api/plans/${planId}/supply`)
      .then((value) => {
        if (!cancelled) setApprovedOp(value);
      })
      .catch((error) => {
        if (!cancelled) setSupplyError(error.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [planId, run?.run_id, tab]);
  const periods = [
    ...new Set(
      [...(op?.materials || []), ...(op?.capacity || [])].map((r) => r.period),
    ),
  ].sort();
  const rows = (tab === "materials" ? op?.materials : op?.capacity) || [];
  const filtered = rows.filter(
    (r) =>
      (!risk ||
        (tab === "materials"
          ? r.status === "shortage"
          : r.status !== "available")) &&
      (!period || r.period === period) &&
      `${r.material_name || ""} ${r.production_line || ""} ${r.supplier || ""}`
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  useEffect(() => {
    setPeriod(
      periods.includes(decisionTarget?.period)
        ? decisionTarget.period
        : periods[0] || "",
    );
  }, [run?.run_id, op]);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Supply</h1>
          <p>Stock, material requirements and capacity.</p>
        </div>
        {tab !== "inventory" && planId && approvedOp && (
          <a
            className="btn secondary"
            href={apiLink(`/api/plans/${planId}/export?include_supply=true`)}
          >
            <DownloadSimple size={18} />
            Export plan & supply
          </a>
        )}
      </div>
      {run && (
        <div className="view-toolbar supply-basis">
          <Pick
            label="Use quantities from"
            value={planId || "forecast"}
            options={[
              ["forecast", "Statistical forecast"],
              ...eligiblePlans.map((p) => [
                p.id,
                `${p.name} · ${label(p.status)}`,
              ]),
            ]}
            onChange={(value) => setPlanId(value === "forecast" ? "" : value)}
          />
          <Help text="An approved plan includes its saved adjustments. The statistical forecast does not. Inventory uses the stock snapshot you select; materials and capacity use the attached production file." />
        </div>
      )}
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          ["inventory", "Inventory"],
          ["materials", "Materials"],
          ["capacity", "Capacity"],
        ]}
      />
      <ErrorBox error={supplyError} />
      {loading && (
        <p role="status">Calculating supply from approved quantities…</p>
      )}
      {tab === "inventory" ? (
        <InventoryOutlook
          canEdit={canEdit}
          ui={inventoryUi}
          api={api}
          fmt={fmt}
          date={date}
          run={run}
          planId={planId}
          openInventory={openInventory}
        />
      ) : loading || supplyError ? null : !op?.source ? (
        <section className="surface">
          <Empty
            icon={Factory}
            title="Add production data"
            action={
              <Button onClick={() => navigate("data")}>
                Go to data
                <ArrowRight size={17} />
              </Button>
            }
          >
            Include BOM, Materials and Capacity sheets when importing a monthly
            dataset.
          </Empty>
        </section>
      ) : (
        <>
          <div className="supply-filters">
            <div className="search">
              <MagnifyingGlass size={18} />
              <input
                aria-label="Search supply"
                placeholder={
                  tab === "materials"
                    ? "Find a material or supplier"
                    : op?.capacity_unit === "hours"
                      ? "Find a machine"
                      : "Find a production line"
                }
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Pick
              label="Supply period"
              value={period}
              options={[
                ["", "All periods"],
                ...periods.map((p) => [p, date(p)]),
              ]}
              onChange={setPeriod}
            />
            <label className="check-row">
              <input
                type="checkbox"
                checked={risk}
                onChange={(e) => setRisk(e.target.checked)}
              />
              Only needs attention
            </label>
          </div>
          <section className="surface supply-table">
            {tab === "materials" ? (
              <Table
                headers={[
                  "Material",
                  uiText("Period"),
                  "Required",
                  "Receipts",
                  <>
                    Balance
                    <Help text="Projected stock using confirmed receipts only. Proposed orders are not included until you place them." />
                  </>,
                  "Suggested order",
                  "Release date",
                ]}
                empty={
                  !filtered.length && "No material records match your filters."
                }
              >
                {filtered.map((r, i) => (
                  <tr key={i}>
                    <td>
                      <strong>{r.material_name}</strong>
                      <small>{r.supplier}</small>
                    </td>
                    <td>{date(r.period)}</td>
                    <td>
                      {fmt(r.gross_requirement)} {r.unit}
                    </td>
                    <td>{fmt(r.scheduled_receipts)}</td>
                    <td className={r.projected_balance < 0 ? "negative" : ""}>
                      {fmt(r.projected_balance)}
                    </td>
                    <td>{fmt(r.recommended_order)}</td>
                    <td>{date(r.planned_release_date, true)}</td>
                  </tr>
                ))}
              </Table>
            ) : (
              <Table
                headers={[
                  op?.capacity_unit === "hours"
                    ? "Machine / work centre"
                    : "Production line",
                  uiText("Period"),
                  op?.capacity_unit === "hours" ? "Required (h)" : "Demand (t)",
                  op?.capacity_unit === "hours"
                    ? "Available (h)"
                    : "Available (t)",
                  uiText("Use"),
                  op?.capacity_unit === "hours"
                    ? "Shortfall (h)"
                    : "Shortfall (t)",
                ]}
                empty={
                  !filtered.length && "No capacity records match your filters."
                }
              >
                {filtered.map((r, i) => (
                  <tr key={i}>
                    <td>
                      <strong>{r.production_line}</strong>
                    </td>
                    <td>{date(r.period)}</td>
                    <td>{fmt(r.required_quantity ?? r.forecast_tonnes)}</td>
                    <td>{fmt(r.available_quantity ?? r.available_tonnes)}</td>
                    <td>
                      <Pill tone={r.utilisation_pct > 100 ? "warning" : ""}>
                        {pct(r.utilisation_pct)}
                      </Pill>
                    </td>
                    <td>
                      {fmt(Math.max(0, -(r.gap_quantity ?? r.gap_tonnes)))}
                    </td>
                  </tr>
                ))}
              </Table>
            )}
          </section>
          <details className="help-details">
            <summary>How are these values calculated?</summary>
            <p>
              {tab === "materials"
                ? "Requirements use the product forecast and BOM. Usable stock excludes quality holds. Confirmed receipts are included. Order proposals are rounded to the minimum order quantity and offset by supplier lead time. They are suggestions, not placed orders."
                : op?.capacity_unit === "hours"
                  ? "Each product passes through its supplied production steps. Run time and optional batch setups are added for each machine. Net available hours already include downtime and efficiency losses; these are not deducted again. This is a monthly workload check, not a feasible job schedule."
                  : "Product demand is grouped by production line and compared with available tonnes from your capacity calendar. Downtime and working days are supplied by your file; they are not fetched automatically."}
            </p>
          </details>
          {tab === "capacity" && op?.workload_details?.length > 0 && (
            <details className="surface disclosure">
              <summary>Product steps behind this workload</summary>
              <div className="detail-body">
                <p className="muted">
                  Steps for the machines and months currently shown. Setup
                  batches combine customers for the same product.
                </p>
                <Table
                  headers={[
                    uiText("Product"),
                    "Step",
                    "Machine",
                    uiText("Period"),
                    "Quantity",
                    "Run (h)",
                    "Setup (h)",
                    "Total (h)",
                  ]}
                >
                  {op.workload_details
                    .filter((r) =>
                      filtered.some(
                        (c) =>
                          c.production_line === r.production_line &&
                          c.period === r.period,
                      ),
                    )
                    .map((r, i) => (
                      <tr key={i}>
                        <td>{r.sku}</td>
                        <td>
                          {r.sequence} · {r.stage}
                        </td>
                        <td>{r.production_line}</td>
                        <td>{date(r.period)}</td>
                        <td>
                          {fmt(r.product_quantity)} {r.product_unit}
                        </td>
                        <td>{fmt(r.run_hours)}</td>
                        <td>{fmt(r.setup_hours)}</td>
                        <td>{fmt(r.required_hours)}</td>
                      </tr>
                    ))}
                </Table>
              </div>
            </details>
          )}
        </>
      )}
    </>
  );
}


createRoot(document.getElementById("root")).render(
  <I18nextProvider i18n={i18n}><AccessGate
    api={api}
    onSession={(value) => {
      csrfToken = value?.csrf || "";
      configureCompanyApi(value);
      configureWorkspaceStorage(value);
    }}
  >
    {(access) => <App key={workspaceContextKey(access)} access={access} />}
  </AccessGate></I18nextProvider>,
);

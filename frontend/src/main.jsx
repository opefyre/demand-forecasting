import React, { useEffect, useState, useId, useRef } from "react";
import { createRoot } from "react-dom/client";
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
import "./workspace.css";

async function api(url, body, method) {
  const r = await fetch(url, {
    method: method || (body ? "POST" : "GET"),
    ...(body instanceof FormData
      ? { body }
      : body
        ? {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }
        : {}),
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    throw new Error(
      typeof e.detail === "string"
        ? e.detail
        : "The request could not be completed. Check the highlighted fields.",
    );
  }
  return r.json();
}
const fmt = (n, d = 1) =>
  n == null || !Number.isFinite(Number(n))
    ? "—"
    : Number(n).toLocaleString("en", { maximumFractionDigits: d });
const pct = (n) => (n == null ? "—" : `${fmt(n)}%`);
const date = (s, day = false) =>
  !s
    ? "—"
    : new Intl.DateTimeFormat("en", {
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
  date_col: "",
  target_col: "",
  item_col: "",
  sku_col: "",
  category_col: "",
  customer_col: "",
  future_date_col: "",
  future_item_col: "",
  frequency: "monthly",
  horizon: 6,
  unit: "units",
  profile: "deep",
  method_selection: "recommended",
  drivers: [],
  driver_roles: {},
  future_driver_policy: "require",
  missing_strategy: "auto",
  outlier_strategy: "none",
};
const nav = [
  ["forecast", "Forecast", ChartLineUp],
  ["data", "Data", Database],
  ["plans", "Plans", Stack],
  ["supply", "Supply", Factory],
];
const METHOD_HELP = {
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
}) {
  return (
    <Select.Root
      value={value || "__none"}
      onValueChange={(v) => onChange(v === "__none" ? "" : v)}
      disabled={disabled}
    >
      <Select.Trigger className="select-control" aria-label={accessible}>
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
function Field({ title, help, children }) {
  return (
    <div className="field">
      <div className="field-label">
        {title}
        {help && <Help text={help} />}
      </div>
      {children}
    </div>
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
          className={`modal ${wide ? "wide" : ""}`}
          onOpenAutoFocus={(event) => {
            opener.current = document.activeElement;
            const field = content.current?.querySelector(
              'input:not([type="hidden"]), textarea',
            );
            if (field) {
              event.preventDefault();
              field.focus();
            }
          }}
          onCloseAutoFocus={(event) => {
            if (opener.current?.isConnected) {
              event.preventDefault();
              opener.current.focus();
            }
          }}
        >
          <div className="modal-heading">
            <Dialog.Title>{title}</Dialog.Title>
            {dismissible && (
              <Dialog.Close asChild>
                <button className="icon-btn" aria-label="Close dialog">
                  <X size={21} />
                </button>
              </Dialog.Close>
            )}
          </div>
          <Dialog.Description className={description ? "muted" : "sr-only"}>
            {description || title}
          </Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
function ErrorBox({ error }) {
  return error ? (
    <div role="alert" className="error-box">
      <WarningCircle size={20} />
      <span>{error}</span>
    </div>
  ) : null;
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
  return (
    <div className="table-scroll">
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
  );
}
function Tabs({ value, onChange, items }) {
  return (
    <nav className="tabs" aria-label="View options">
      {items.map(([v, l]) => (
        <button
          key={v}
          aria-current={value === v ? "page" : undefined}
          data-selected={value === v}
          onClick={() => onChange(v)}
        >
          {l}
        </button>
      ))}
    </nav>
  );
}
function Pill({ children, tone = "" }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

function App() {
  const initial = location.hash.slice(1);
  const [page, setPage] = useState(
    ["data", "plans", "supply", "settings"].includes(initial)
      ? initial
      : "forecast",
  );
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
    [forecastTab, setForecastTab] = useState("outlook");
  const [chosenPlan, setChosenPlan] = useState(null);
  const navigate = (p) => {
    setPage(p);
    location.hash = p;
    setMobile(false);
    window.scrollTo(0, 0);
  };
  const notify = (text) => {
    setNotice(text);
    setTimeout(() => setNotice(""), 4200);
  };
  const refresh = async () => {
    const [d, p, r, w] = await Promise.all([
      api("/api/datasets"),
      api("/api/plans"),
      api("/api/run-list"),
      api("/api/workspace"),
    ]);
    setDatasets(d.datasets);
    setPlans(p.plans);
    setRuns(r.runs);
    setWorkspace(w);
    return { d, p, r, w };
  };
  useEffect(() => {
    (async () => {
      try {
        const { r } = await refresh();
        const saved = localStorage.getItem("demandlab.activeRun");
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
    const listener = () =>
      setPage(
        ["data", "plans", "supply", "settings"].includes(location.hash.slice(1))
          ? location.hash.slice(1)
          : "forecast",
      );
    window.addEventListener("hashchange", listener);
    return () => window.removeEventListener("hashchange", listener);
  }, []);
  async function openRun(id) {
    try {
      setBusy("Opening forecast");
      const r = await api(`/api/runs/${id}`);
      setRun(r);
      localStorage.setItem("demandlab.activeRun", id);
      setChosenPlan(null);
      setForecastTab("outlook");
      navigate("forecast");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  async function runDataset(id, opts = {}) {
    setError("");
    setBusy(
      opts.scenario_name
        ? "Calculating scenario"
        : "Testing forecasting methods",
    );
    try {
      const r = await api("/api/run-saved", { dataset_id: id, ...opts });
      if (!opts.scenario_name) {
        setRun(r);
        localStorage.setItem("demandlab.activeRun", r.run_id);
        setChosenPlan(null);
        setImporting(false);
        setForecastTab("outlook");
        navigate("forecast");
      }
      await refresh();
      notify(opts.scenario_name ? "Scenario saved" : "Forecast ready");
      return r;
    } catch (e) {
      setError(e.message);
      throw e;
    } finally {
      setBusy("");
    }
  }
  const importNew = () => {
    setImporting(true);
    navigate("data");
  };
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
    runDataset,
    importNew,
    chosenPlan,
    setChosenPlan,
    setError,
  };
  return (
    <Tooltip.Provider delayDuration={250}>
      <div className="app-shell">
        <aside className="sidebar">
          <a
            className="brand"
            href="#forecast"
            onClick={() => navigate("forecast")}
          >
            <ChartLineUp size={26} weight="bold" />
            <span>DemandLab</span>
          </a>
          <nav aria-label="Main navigation">
            {nav.map(([p, n, Icon]) => (
              <button
                key={p}
                className={`nav-link ${page === p ? "active" : ""}`}
                onClick={() => navigate(p)}
                aria-current={page === p ? "page" : undefined}
              >
                <Icon size={22} />
                <span>{n}</span>
              </button>
            ))}
          </nav>
          <button
            className={`nav-link settings-link ${page === "settings" ? "active" : ""}`}
            onClick={() => navigate("settings")}
          >
            <GearSix size={22} />
            <span>Settings</span>
          </button>
        </aside>
        <div className="main">
          <header className="topbar">
            <button
              className="icon-btn mobile-trigger"
              aria-label="Open navigation"
              onClick={() => setMobile(true)}
            >
              <List size={23} />
            </button>
            <span className="site-name">
              {workspace?.site?.name || "DemandLab"}
            </span>
            {["forecast", "supply"].includes(page) &&
              run?.source_classification === "synthetic_sample" && (
                <Pill>Sample data</Pill>
              )}
          </header>
          <main id="workspace">
            <ErrorBox error={error} />
            {boot ? (
              <div className="loading-inline">Opening workspace…</div>
            ) : page === "data" ? (
              <DataPage
                {...context}
                importing={importing}
                setImporting={setImporting}
              />
            ) : page === "plans" ? (
              <PlansPage {...context} />
            ) : page === "supply" ? (
              <SupplyPage {...context} />
            ) : page === "settings" ? (
              <SettingsPage {...context} />
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
      <Modal title="Navigation" open={mobile} onClose={() => setMobile(false)}>
        <nav className="mobile-nav">
          {[...nav, ["settings", "Settings", GearSix]].map(([p, n, Icon]) => (
            <button
              key={p}
              className={`nav-link ${page === p ? "active" : ""}`}
              onClick={() => navigate(p)}
            >
              <Icon size={22} />
              {n}
            </button>
          ))}
        </nav>
      </Modal>
      <Modal
        title={busy || "Working"}
        description="This may take a minute. Your saved files and mappings are retained."
        open={!!busy}
        dismissible={false}
        onClose={() => {}}
      >
        <div className="working-bar" />
        <p className="muted">
          Please keep this window open until the result is ready.
        </p>
      </Modal>
      {notice && (
        <div role="status" className="toast">
          <CheckCircle size={20} />
          {notice}
        </div>
      )}
    </Tooltip.Provider>
  );
}

function DataPage({
  datasets,
  refresh,
  notify,
  runDataset,
  importing,
  setImporting,
}) {
  const [error, setError] = useState(""),
    [selected, setSelected] = useState(null);
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
  if (importing)
    return (
      <ImportFlow
        key={selected?.id || "new"}
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
        onRun={runDataset}
      />
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Data</h1>
          {datasets.length > 0 && <p>Saved files and forecast settings.</p>}
        </div>
        {datasets.length > 0 && (
          <Button
            kind="primary"
            onClick={() => {
              setSelected(null);
              setImporting(true);
            }}
          >
            <Plus />
            {localStorage.getItem("demandlab.importDraft")
              ? "Resume import"
              : "Import data"}
          </Button>
        )}
      </div>
      <ErrorBox error={error} />
      {datasets.length ? (
        <section className="surface record-list">
          {datasets.map((d) => (
            <article key={d.id}>
              <div className="record-info">
                <strong>{d.name}</strong>
                <p>
                  {date(d.review.summary.start)} – {date(d.review.summary.end)}
                  {" · "}
                  {fmt(d.review.summary.series, 0)} items
                </p>
                {d.classification === "synthetic_sample" && (
                  <small>Sample data</small>
                )}
              </div>
              <div className="row-actions">
                <Button onClick={() => loadSaved(d)}>Review data</Button>
                <Button
                  onClick={() =>
                    runDataset(d.id).catch((e) => setError(e.message))
                  }
                >
                  Forecast
                  <ArrowRight size={16} />
                </Button>
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section className="surface">
          <Empty
            icon={Database}
            title="Start with your historical data"
            action={
              <Button kind="primary" onClick={() => setImporting(true)}>
                Import data
                <ArrowRight size={17} />
              </Button>
            }
          >
            Upload a spreadsheet of sales, demand or consumption. You’ll match
            its columns before anything is calculated.
          </Empty>
        </section>
      )}
      <p className="footnote">
        CSV, Excel, TSV and JSON. Files are saved on this computer.
      </p>
    </>
  );
}

function ImportFlow({ initial, onCancel, onSaved, onRun }) {
  const [step, setStep] = useState(initial ? 3 : 0),
    [sources, setSources] = useState(initial?.sourceObjects || {}),
    [settings, setSettings] = useState({ ...BASE, ...initial?.settings }),
    [name, setName] = useState(initial?.name || ""),
    [classification, setClassification] = useState(
      initial?.classification || "user_provided",
    );
  const [error, setError] = useState(""),
    [pending, setPending] = useState(""),
    [review, setReview] = useState(initial?.review || null),
    [accepted, setAccepted] = useState(!!initial),
    [advanced, setAdvanced] = useState(false),
    [optional, setOptional] = useState(
      !!sources.future || !!sources.operations,
    ),
    [restoreReady, setRestoreReady] = useState(!!initial);
  useEffect(() => {
    if (initial) return;
    let draft;
    try {
      draft = JSON.parse(localStorage.getItem("demandlab.importDraft"));
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
          setStep(Math.min(2, Math.max(0, Number(draft.step) || 0)));
          setName(draft.name || "");
          setClassification(draft.classification || "user_provided");
          setOptional(!!found.future || !!found.operations);
        } catch {
        } finally {
          setRestoreReady(true);
        }
      })();
    } else setRestoreReady(true);
  }, []);
  useEffect(() => {
    if (restoreReady && !initial)
      localStorage.setItem(
        "demandlab.importDraft",
        JSON.stringify({
          sources: Object.fromEntries(
            Object.entries(sources).map(([r, s]) => [r, s.id]),
          ),
          settings,
          name,
          classification,
          step,
        }),
      );
  }, [sources, settings, name, classification, step, restoreReady]);
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
          "target",
          "consumption",
        ]),
        item_col: pick(["series_id", "item_id", "sku"]),
        sku_col: pick(["sku"]),
        category_col: pick(["category"]),
        customer_col: pick(["customer"]),
        unit: cols.includes("demand_tonnes") ? "tonnes" : "units",
        drivers: [],
        driver_roles: {},
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
      if (role !== "operations")
        setSettings((s) => ({ ...s, ...guess(source.preview, role) }));
      if (role === "history" && !name)
        setName(file.name.replace(/\.[^.]+$/, ""));
      if (!sample) setClassification("user_provided");
      return source;
    } catch (e) {
      setError(e.message);
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
        ["operations", "iran_operations", "iran_operations_master.xlsx"],
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
      setName("Qazvin manufacturing sample");
      setClassification("synthetic_sample");
      setOptional(true);
    } catch (e) {
      setError(e.message);
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
      setSettings((s) => ({ ...s, ...guess(source.preview, role) }));
      setReview(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setPending("");
    }
  }
  function remove(role) {
    setSources((s) =>
      Object.fromEntries(Object.entries(s).filter(([k]) => k !== role)),
    );
    setReview(null);
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
  });
  async function next() {
    setError("");
    if (step === 0 && !sources.history)
      return setError("Upload a history file to continue.");
    if (step === 1) {
      if (!settings.date_col || !settings.target_col)
        return setError("Choose the date and quantity columns.");
      const m = [
        settings.date_col,
        settings.target_col,
        settings.item_col,
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
        setError(e.message);
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
    try {
      const data = request();
      const unchanged =
        initial &&
        name === initial.name &&
        JSON.stringify(data.sources) === JSON.stringify(initial.sources) &&
        JSON.stringify(settings) ===
          JSON.stringify({ ...BASE, ...initial.settings });
      const d = unchanged ? initial : await api("/api/datasets", data);
      localStorage.removeItem("demandlab.importDraft");
      await onSaved(d);
      if (run) await onRun(d.id);
    } catch (e) {
      setError(e.message);
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
  ];
  const options = (role) => [
    ["", "Choose a column"],
    ...(sources[role]?.preview.columns || []).map((c) => [c, c]),
  ];
  const mapping = (role, key, title, help, required = false) => (
    <Field title={title} help={help}>
      <Pick
        value={settings[key]}
        options={
          required
            ? options(role)
            : [["", "Not needed"], ...options(role).slice(1)]
        }
        label={`${title}${role === "future" ? " in future factors" : ""}`}
        onChange={(v) => change(key, v)}
      />
      {settings[key] && (
        <small className="field-example">
          e.g.{" "}
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
  return (
    <>
      <div className="page-heading">
        <div>
          <button className="back-link" onClick={onCancel}>
            <ArrowLeft size={16} />
            Data library
          </button>
          <h1>{initial ? "Review dataset" : "Import data"}</h1>
        </div>
      </div>
      <div className="wizard">
        <ol className="steps" aria-label="Import progress">
          {titles.map((t, i) => (
            <li key={t} aria-current={step === i ? "step" : undefined}>
              <button
                disabled={i > step || !!pending}
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
                  <h2>What would you like to forecast?</h2>
                  <p>Start with past sales, demand or consumption.</p>
                </div>
                <Button disabled={!!pending} onClick={loadSample}>
                  <Flask size={17} />
                  Try sample
                </Button>
              </div>
              <SourceCard
                role="history"
                title="Historical data"
                source={sources.history}
                pending={pending}
                onFile={attach}
                onRemove={remove}
                onSheet={chooseSheet}
              />
              <details
                open={optional}
                onToggle={(e) => setOptional(e.currentTarget.open)}
                className="optional-section"
              >
                <summary>
                  Add future factors or production data <span>Optional</span>
                </summary>
                <p className="muted">
                  Use future factors when you know upcoming prices, orders or
                  events. Add production data for material and capacity
                  planning.
                </p>
                <div className="optional-files">
                  <SourceCard
                    role="future"
                    title="Future factors"
                    source={sources.future}
                    pending={pending}
                    onFile={attach}
                    onRemove={remove}
                    onSheet={chooseSheet}
                  />
                  <SourceCard
                    role="operations"
                    title="Production data"
                    source={sources.operations}
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
                  <h2>Match your columns</h2>
                  <p>Check the suggestions against the values in your file.</p>
                </div>
              </div>
              <div className="form-grid three">
                {mapping(
                  "history",
                  "date_col",
                  "Date",
                  "The day, week or month each quantity belongs to.",
                  true,
                )}
                {mapping(
                  "history",
                  "target_col",
                  "Quantity to forecast",
                  "Actual sales, demand or consumption. Use a consistent unit.",
                  true,
                )}
                {mapping(
                  "history",
                  "item_col",
                  "Item",
                  "Each distinct value becomes a separate forecast. Leave empty for one total.",
                )}
              </div>
              <details className="optional-section">
                <summary>
                  Category and customer <span>Optional</span>
                </summary>
                <div className="form-grid three">
                  {mapping(
                    "history",
                    "sku_col",
                    "Product code",
                    "A product identifier for grouping and matching the BOM.",
                  )}
                  {mapping(
                    "history",
                    "category_col",
                    "Category",
                    "Group forecasts by product family.",
                  )}
                  {mapping(
                    "history",
                    "customer_col",
                    "Customer",
                    "Group forecasts by customer or market.",
                  )}
                </div>
              </details>
              <div className="preview-label">
                Your file · {sources.history?.name}{" "}
                <span>First {sources.history?.preview.sample.length} rows</span>
              </div>
              <Preview
                source={sources.history}
                columns={[
                  settings.date_col,
                  settings.target_col,
                  settings.item_col,
                ].filter(Boolean)}
              />
              {sources.future && (
                <>
                  <h3 className="subsection">Future factors</h3>
                  <div className="form-grid two">
                    {mapping(
                      "future",
                      "future_date_col",
                      "Date",
                      "Forecast dates that correspond to future factor values.",
                      true,
                    )}
                    {mapping(
                      "future",
                      "future_item_col",
                      "Item",
                      "Match the historical item identifiers. Leave blank for factors shared by every item.",
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
            </>
          ) : step === 2 ? (
            <>
              <div className="section-heading">
                <div>
                  <h2>Set up your forecast</h2>
                </div>
              </div>
              <div className="form-grid two">
                <Field title="Dataset name">
                  <input
                    aria-label="Dataset name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    maxLength={120}
                  />
                </Field>
                <Field
                  title="Quantity unit"
                  help="Use the unit in your file. Production calculations currently use tonnes."
                >
                  <Pick
                    label="Quantity unit"
                    value={settings.unit}
                    options={["units", "tonnes", "kg", "litres", "hours"]}
                    onChange={(v) => change("unit", v)}
                  />
                </Field>
                <Field title="Time interval">
                  <Pick
                    label="Time interval"
                    value={settings.frequency}
                    options={["monthly", "weekly", "daily"]}
                    onChange={(v) => change("frequency", v)}
                  />
                </Field>
                <Field
                  title="How far ahead?"
                  help="Shorter horizons can be validated with less history."
                >
                  <div className="input-suffix">
                    <input
                      aria-label="Forecast horizon"
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
                        ? "months"
                        : settings.frequency === "weekly"
                          ? "weeks"
                          : "days"}
                    </span>
                  </div>
                </Field>
              </div>
              <Field
                title="Forecast method"
                help="The default compares methods on past periods and selects the strongest fit for each item."
              >
                <Pick
                  label="Forecast method"
                  value={settings.method_selection}
                  options={METHODS}
                  onChange={(v) => change("method_selection", v)}
                />
              </Field>
              <details
                className="optional-section"
                open={advanced}
                onToggle={(e) => setAdvanced(e.currentTarget.open)}
              >
                <summary>
                  Additional factors{" "}
                  <span>
                    {settings.drivers.length
                      ? `${settings.drivers.length} selected`
                      : "Optional"}
                  </span>
                </summary>
                <p className="muted">
                  Select only factors you want the model to test. They need
                  values for the future periods.
                </p>
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
                              ? "Available in future file"
                              : "No future column"}
                          </small>
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <p className="muted">
                    Your file has no additional factor columns.
                  </p>
                )}
                {settings.drivers.length > 0 && (
                  <Field
                    title="If future values are missing"
                    help="Keeping this at “Ask me to fix the file” avoids inventing future assumptions."
                  >
                    <Pick
                      label="Missing future values"
                      value={settings.future_driver_policy}
                      options={[
                        ["require", "Ask me to fix the file"],
                        ["carry", "Repeat the last known value"],
                        ["median", "Use the historical middle value"],
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
                  <h2>Ready to save</h2>
                  <p>Check the data that will go into the forecast.</p>
                </div>
                <CheckCircle size={26} />
              </div>
              {classification === "synthetic_sample" && (
                <Pill>Sample dataset</Pill>
              )}
              <dl className="review-list">
                <div>
                  <dt>Name</dt>
                  <dd>{name}</dd>
                </div>
                <div>
                  <dt>History</dt>
                  <dd>
                    {date(review?.summary.start)} – {date(review?.summary.end)}
                  </dd>
                </div>
                <div>
                  <dt>Data</dt>
                  <dd>
                    {fmt(review?.summary.rows, 0)} rows ·{" "}
                    {fmt(review?.summary.series, 0)} items
                  </dd>
                </div>
                <div>
                  <dt>Forecast</dt>
                  <dd>
                    {date(review?.forecast_start)} –{" "}
                    {date(review?.forecast_end)} · {settings.unit}
                  </dd>
                </div>
                <div>
                  <dt>Method</dt>
                  <dd>
                    {
                      METHODS.find(
                        ([v]) => v === settings.method_selection,
                      )?.[1]
                    }
                  </dd>
                </div>
                <div>
                  <dt>Extra factors</dt>
                  <dd>
                    {settings.drivers.length
                      ? settings.drivers.map(label).join(", ")
                      : "None selected"}
                  </dd>
                </div>
              </dl>
              {review?.warnings.length > 0 && (
                <div className="review-warnings">
                  <h3>Check these data adjustments</h3>
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
                    I reviewed these adjustments
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
              setStep(step - 1);
              setError("");
            }}
          >
            <ArrowLeft size={17} />
            Back
          </Button>
          <span aria-live="polite">
            {pending
              ? pending === "validation"
                ? "Checking dates, quantities and future coverage…"
                : pending === "save"
                  ? "Saving dataset…"
                  : "Reading file…"
              : `Step ${step + 1} of 4`}
          </span>
          <div className="row-actions">
            {step === 3 ? (
              <>
                <Button
                  disabled={
                    !!pending || (!!review?.warnings.length && !accepted)
                  }
                  onClick={() => finish(false)}
                >
                  Save data
                </Button>
                <Button
                  kind="primary"
                  disabled={
                    !!pending || (!!review?.warnings.length && !accepted)
                  }
                  onClick={() => finish(true)}
                >
                  Save & forecast
                  <ArrowRight size={17} />
                </Button>
              </>
            ) : (
              <Button
                kind="primary"
                disabled={!!pending || (step === 0 && !sources.history)}
                onClick={next}
              >
                {step === 2 ? "Check data" : "Continue"}
                <ArrowRight size={17} />
              </Button>
            )}
          </div>
        </footer>
      </div>
    </>
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
                {fmt(source.preview.rows, 0)} rows
                {source.sheet ? ` · ${source.sheet}` : ""}
              </small>
            </>
          ) : (
            <p>
              {role === "operations"
                ? "Excel workbook with BOM, Materials and Capacity sheets."
                : "Drop a file here or choose one."}
            </p>
          )}
        </div>
        <input
          id={id}
          className="sr-only"
          type="file"
          aria-label={`Upload ${title.toLowerCase()}`}
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
        <label
          htmlFor={id}
          className={`btn secondary file-trigger ${pending ? "disabled" : ""}`}
        >
          {source ? "Replace" : "Choose file"}
        </label>
        {source && (
          <button
            className="icon-btn"
            aria-label={`Remove ${title.toLowerCase()}`}
            disabled={!!pending}
            onClick={() => onRemove(role)}
          >
            <X size={19} />
          </button>
        )}
      </div>
      {source?.preview.sheets?.length > 1 && role !== "operations" && (
        <Field title="Worksheet">
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
        <div className="file-hint">CSV · Excel · TSV · JSON · up to 50 MB</div>
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
                <span className="muted">Empty</span>
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
  navigate,
  tab,
  setTab,
  refresh,
  notify,
}) {
  const [item, setItem] = useState("__all__"),
    [range, setRange] = useState(true),
    [error, setError] = useState(""),
    [dialog, setDialog] = useState(""),
    [form, setForm] = useState({}),
    [working, setWorking] = useState(false);
  useEffect(() => {
    setItem("__all__");
    setError("");
  }, [run?.run_id]);
  const periodDate = (s) => date(s, run?.run_settings?.frequency !== "monthly");
  const dataset = datasets.find((d) => d.id === run?.dataset_id);
  const plan = plans.find(
    (p) =>
      p.run_id === run?.run_id && ["approved", "published"].includes(p.status),
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
        range: [r.p10, r.p90],
      })),
    );
  const runOptions = runs
    .filter((r) => !r.scenario_name)
    .map((r) => [
      r.run_id,
      `${r.name} · ${new Date(r.created_at * 1000).toLocaleString("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}`,
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
        navigate("plans");
      } else if (dialog === "scenario") {
        await runDataset(dataset.id, {
          adjustment: Number(form.adjustment),
          scenario_name: form.name,
          base_run_id: run.run_id,
        });
        setDialog("");
      } else if (dialog === "method") {
        await runDataset(dataset.id, { method: `model:${form.model}` });
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
      <>
        <div className="page-heading">
          <h1>Forecast</h1>
        </div>
        <section className="surface">
          <Empty
            icon={ChartLineUp}
            title="Create your first forecast"
            action={
              <Button kind="primary" onClick={importNew}>
                Import data
                <ArrowRight size={17} />
              </Button>
            }
          >
            Start with your historical data. We’ll help you match the columns
            and choose a forecasting method.
          </Empty>
        </section>
      </>
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Forecast</h1>
          <p>
            {periodDate(forecasts[0]?.timestamp)} –{" "}
            {periodDate(forecasts.at(-1)?.timestamp)}
          </p>
        </div>
        <Button kind="primary" onClick={importNew}>
          <Plus size={17} />
          New forecast
        </Button>
      </div>
      <div className="forecast-toolbar">
        <div className="run-select">
          <Pick
            label="Forecast version"
            value={run.run_id}
            options={
              runOptions.length
                ? runOptions
                : [[run.run_id, "Current forecast"]]
            }
            onChange={openRun}
          />
        </div>
        <div className="row-actions">
          <a className="btn secondary" href={`/api/export/${run.run_id}/xlsx`}>
            <DownloadSimple size={18} />
            Export
          </a>
          <Button
            onClick={() => {
              setForm({
                name: `${run.dataset_name || "Operating plan"} · ${periodDate(forecasts[0]?.timestamp)}`,
                owner: "",
              });
              setError("");
              setDialog("plan");
            }}
          >
            Save plan
          </Button>
        </div>
      </div>
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
      {tab === "outlook" ? (
        <>
          <div className="view-toolbar">
            <Pick
              label="Product or total"
              value={item}
              options={[
                ["__all__", "All items"],
                ...(run.items || []).map((id) => [id, id]),
              ]}
              onChange={setItem}
            />
            <label className="check-row">
              <input
                type="checkbox"
                checked={range}
                onChange={(e) => setRange(e.target.checked)}
              />
              Show likely range
              <Help text="An 80% range estimated from historical forecast errors. Future results may fall outside it." />
            </label>
          </div>
          <section className="surface chart-surface">
            <div className="forecast-stats">
              <div>
                <span>
                  Forecast total
                  <Help text="The sum of forecasts across the selected future periods." />
                </span>
                <strong>
                  {fmt(total, 0)}
                  <small>{unit}</small>
                </strong>
              </div>
              <div>
                <span>
                  Next{" "}
                  {run.run_settings?.frequency === "monthly"
                    ? "month"
                    : "period"}
                </span>
                <strong>
                  {fmt(forecasts[0]?.mean)}
                  <small>{unit}</small>
                </strong>
              </div>
              <div>
                <span>
                  Historical test error
                  <Help text="Weighted absolute percentage error across held-out historical periods. Lower is better; this is not guaranteed future accuracy." />
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
                <i className="actual" />
                Actual
              </span>
              <span>
                <i />
                Forecast
              </span>
              {hasOverrides && (
                <span>
                  <i className="approved" />
                  Approved plan
                </span>
              )}
            </div>
            <div className="forecast-chart">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={chart}
                  margin={{ left: 0, right: 12, top: 12, bottom: 0 }}
                >
                  <CartesianGrid vertical={false} stroke="#ecece9" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d) => periodDate(d)}
                    minTickGap={65}
                    tickLine={false}
                    axisLine={false}
                  />
                  <YAxis
                    width={55}
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
                        range: "80% range",
                        approved: "Approved plan",
                      }[name],
                    ]}
                  />
                  {range && (
                    <Area
                      type="linear"
                      dataKey="range"
                      fill="#dddeda"
                      stroke="none"
                      fillOpacity={0.6}
                    />
                  )}
                  <Line
                    type="linear"
                    dataKey="actual"
                    stroke="#9a9d97"
                    strokeWidth={2.3}
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Line
                    type="linear"
                    dataKey="forecast"
                    stroke="#191c18"
                    strokeWidth={2.7}
                    dot={false}
                    isAnimationActive={false}
                  />
                  {hasOverrides && (
                    <Line
                      type="linear"
                      dataKey="approved"
                      stroke="#557b67"
                      strokeWidth={2.4}
                      strokeDasharray="6 3"
                      dot={false}
                      isAnimationActive={false}
                    />
                  )}
                  <ReferenceLine
                    x={history.at(-1)?.timestamp}
                    stroke="#adb0a9"
                    strokeDasharray="4 6"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </section>
          <details className="surface disclosure">
            <summary>
              Period values<span>{forecasts.length} periods</span>
            </summary>
            <Table
              headers={[
                "Period",
                `Forecast (${unit})`,
                ...(hasOverrides ? ["Approved plan"] : []),
                "Low",
                "High",
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
              <summary>
                Factors used in this forecast
                <span>{run.drivers.length} factors</span>
              </summary>
              <Table headers={["Factor", "Association", "Role"]}>
                {run.drivers.map((d) => (
                  <tr key={d.feature}>
                    <td>{label(d.feature)}</td>
                    <td>
                      {label(d.direction)}
                      <Help text="Association shows how this factor moved with demand historically; it does not establish causation." />
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
              <h2>Compare forecasting methods</h2>
              <p>Each method was tested on the same historical periods.</p>
            </div>
          </div>
          {!dataset && (
            <div className="inline-message">
              This earlier run has no saved inputs.{" "}
              <button onClick={importNew}>Import its source files</button> to
              rerun a method.
            </div>
          )}
          <section className="surface methods-table">
            <Table
              headers={[
                "Method",
                <>
                  Test error
                  <Help text="Weighted absolute percentage error. Lower values mean closer forecasts on the historical test periods." />
                </>,
                "",
              ]}
              empty={
                !run.leaderboard?.length && "No model comparison is available."
              }
            >
              {run.leaderboard?.map((m, i) => (
                <tr key={m.model}>
                  <td>
                    <strong>{m.model}</strong>
                    <Help
                      text={
                        METHOD_HELP[m.model] ||
                        "This mathematical method is tested against the same held-out periods as the other methods."
                      }
                    />
                    {i === 0 && <small>Lowest test error</small>}
                  </td>
                  <td>{pct(m.wape_pct)}</td>
                  <td>
                    <Button
                      disabled={!dataset}
                      onClick={() => {
                        setError("");
                        setForm({ model: m.model });
                        setDialog("method");
                      }}
                    >
                      Use method
                    </Button>
                  </td>
                </tr>
              ))}
            </Table>
          </section>
        </>
      ) : tab === "accuracy" ? (
        <>
          <div className="section-heading">
            <div>
              <h2>How well did it predict past demand?</h2>
              <p>
                {run.metrics?.rolling_folds || 0} test windows ·{" "}
                {fmt(run.metrics?.validation_points, 0)} held-out observations
              </p>
            </div>
            <Pill
              tone={run.metrics?.evidence_level === "limited" ? "warning" : ""}
            >
              {label(run.metrics?.evidence_level)} evidence
            </Pill>
          </div>
          <div className="accuracy-summary surface">
            <div>
              <span>
                Test error
                <Help text="Total absolute error divided by total actual demand. This is WAPE." />
              </span>
              <strong>{pct(run.metrics?.wape_pct)}</strong>
            </div>
            <div>
              <span>
                Bias
                <Help text="Near zero is better. Negative means forecasts were too low on average." />
              </span>
              <strong>{pct(run.metrics?.bias_pct)}</strong>
            </div>
            <div>
              <span>
                Range coverage
                <Help text="The share of held-out values inside the predicted range. The target is 80%." />
              </span>
              <strong>{pct(run.metrics?.interval_coverage_pct)}</strong>
            </div>
          </div>
          <section className="surface">
            <Table headers={["Item", "Test error", "Bias", "Best method"]}>
              {Object.entries(run.series_diagnostics || {}).map(([id, d]) => (
                <tr key={id}>
                  <td>{id}</td>
                  <td>{pct(d.wape_pct)}</td>
                  <td>{pct(d.bias_pct)}</td>
                  <td>{d.best_model}</td>
                </tr>
              ))}
            </Table>
          </section>
          <Fva run={run} />
        </>
      ) : (
        <>
          <div className="section-heading">
            <div>
              <h2>What if demand changes?</h2>
              <p>Compare a percentage adjustment with this forecast.</p>
            </div>
            <Button
              kind="primary"
              disabled={!dataset}
              onClick={() => {
                setError("");
                setForm({ name: "", adjustment: 10 });
                setDialog("scenario");
              }}
            >
              <Plus size={17} />
              Add scenario
            </Button>
          </div>
          {!dataset && (
            <div className="inline-message">
              Import and save this forecast’s source files to create scenarios.
            </div>
          )}
          <ScenarioList run={run} runs={runs} unit={unit} />
        </>
      )}
      <Modal
        title={
          dialog === "plan"
            ? "Save as a plan"
            : dialog === "method"
              ? `Use ${form.model}`
              : "New scenario"
        }
        open={!!dialog}
        onClose={() => !working && setDialog("")}
        description={
          dialog === "method"
            ? "Creates a new forecast from the saved dataset using this method."
            : undefined
        }
      >
        <form onSubmit={submit}>
          <ErrorBox error={error} />
          {dialog === "method" ? (
            <p>
              Dataset: <strong>{dataset?.name}</strong>
            </p>
          ) : (
            <>
              <Field title={dialog === "plan" ? "Plan name" : "Scenario name"}>
                <input
                  aria-label={dialog === "plan" ? "Plan name" : "Scenario name"}
                  value={form.name || ""}
                  required
                  maxLength={120}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </Field>
              {dialog === "plan" ? (
                <Field title="Owner">
                  <input
                    aria-label="Plan owner"
                    required
                    value={form.owner || ""}
                    onChange={(e) =>
                      setForm({ ...form, owner: e.target.value })
                    }
                  />
                </Field>
              ) : (
                <Field
                  title="Demand change"
                  help="Applied to the forecast quantities. A value of 10 means 10% higher demand; −10 means 10% lower demand."
                >
                  <div className="input-suffix">
                    <input
                      aria-label="Demand change"
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
            >
              Cancel
            </Button>
            <Button kind="primary" disabled={working} type="submit">
              {working
                ? "Working…"
                : dialog === "plan"
                  ? "Save draft"
                  : dialog === "method"
                    ? "Run forecast"
                    : "Calculate scenario"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}

function ScenarioList({ run, runs, unit }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    let live = true;
    const scenarios = runs.filter(
      (r) => r.base_run_id === run.run_id && r.scenario_name,
    );
    Promise.all(scenarios.map((r) => api(`/api/runs/${r.run_id}`))).then(
      (rs) => live && setRows(rs),
    );
    return () => {
      live = false;
    };
  }, [run.run_id, runs]);
  const baseline = run.series.__all__.forecast.reduce((s, r) => s + r.mean, 0);
  return (
    <section className="surface">
      <Table headers={["Scenario", `Forecast (${unit})`, "Change"]}>
        <tr>
          <td>
            <strong>Current forecast</strong>
          </td>
          <td>{fmt(baseline, 0)}</td>
          <td>—</td>
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
            </tr>
          );
        })}
      </Table>
      {!rows.length && <p className="table-note">No scenarios yet.</p>}
    </section>
  );
}
function Fva({ run }) {
  const [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const id = useId();
  return (
    <details className="surface disclosure">
      <summary>
        Did planner changes help?
        <Help text="Upload actual results for closed periods to compare forecast error before and after approved planner adjustments." />
      </summary>
      <div className="detail-body">
        <p className="muted">
          Upload actuals with columns: item_id, timestamp, actual.
        </p>
        <input
          id={id}
          type="file"
          aria-label="Closed-period actuals"
          accept=".csv,.xlsx"
          disabled={busy}
          onChange={async (e) => {
            if (!e.target.files[0]) return;
            setBusy(true);
            setError("");
            try {
              const f = new FormData();
              f.append("actuals_file", e.target.files[0]);
              setResult(await api(`/api/fva/${run.run_id}`, f));
            } catch (e) {
              setError(e.message);
            } finally {
              setBusy(false);
            }
          }}
        />
        <ErrorBox error={error} />
        {result && (
          <p>
            Historical baseline error:{" "}
            <strong>{pct(result.baseline_wape_pct)}</strong>.{" "}
            {result.plan_id ? (
              <>
                Approved plan error:{" "}
                <strong>{pct(result.approved_wape_pct)}</strong>.
              </>
            ) : (
              <>No approved plan is available for comparison.</>
            )}{" "}
            Compared across {result.observations} observations.
          </p>
        )}
      </div>
    </details>
  );
}

function PlansPage({ plans, refresh, notify, openRun }) {
  const [id, setId] = useState(null),
    [dialog, setDialog] = useState(""),
    [error, setError] = useState(""),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [source, setSource] = useState(null),
    [edit, setEdit] = useState({ item: "", period: "", value: "", reason: "" });
  const plan = plans.find((p) => p.id === id);
  useEffect(() => {
    setError("");
    setSource(null);
    if (plan)
      api(`/api/runs/${plan.run_id}`)
        .then(setSource)
        .catch((e) => setError(e.message));
  }, [id]);
  async function transition(status) {
    setBusy(true);
    setError("");
    try {
      await api(
        `/api/plans/${id}/status`,
        { status, actor: plan.owner, note },
        "PATCH",
      );
      await refresh();
      setDialog("");
      setNote("");
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
          <h1>{plan ? plan.name : "Plans"}</h1>
          {plan && (
            <p>
              {plan.owner} · {date(plan.updated_at, true)}
            </p>
          )}
        </div>
        {plan && <Pill>{label(plan.status)}</Pill>}
      </div>
      <ErrorBox error={error} />
      {!plan ? (
        <section className="surface">
          {plans.length ? (
            <div className="record-list">
              {plans.map((p) => (
                <article key={p.id}>
                  <div className="record-info">
                    <strong>{p.name}</strong>
                    <p>
                      {p.owner} · {date(p.updated_at, true)}
                    </p>
                    {p.settings?.source_classification ===
                      "synthetic_sample" && <small>Sample data</small>}
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
            <Empty icon={Stack} title="No saved plans yet">
              Open a forecast and choose “Save plan” to begin review.
            </Empty>
          )}
        </section>
      ) : (
        <>
          <div className="plan-toolbar">
            <Button onClick={() => openRun(plan.run_id)}>
              Open forecast
              <ArrowRight size={16} />
            </Button>
            {["draft", "review"].includes(plan.status) && (
              <Button
                disabled={!source}
                onClick={() => {
                  setEdit({
                    item: source.items[0],
                    period:
                      source.series[source.items[0]].forecast[0].timestamp,
                    value: source.series[source.items[0]].forecast[0].mean,
                    reason: "",
                  });
                  setDialog("override");
                }}
              >
                Adjust a value
              </Button>
            )}
            {next && (
              <Button kind="primary" onClick={() => setDialog("status")}>
                {next === "review"
                  ? "Send for review"
                  : next === "approved"
                    ? "Approve plan"
                    : "Publish plan"}
              </Button>
            )}
          </div>
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
                aria-label="Review note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                required
                maxLength={1000}
                rows={3}
              />
            </Field>
            <Button disabled={busy || !note.trim()} type="submit">
              Add note
            </Button>
          </form>
        </>
      )}
      <Modal
        title={
          dialog === "status"
            ? `${next === "review" ? "Send for review" : next === "approved" ? "Approve" : "Publish"} plan`
            : "Adjust forecast value"
        }
        open={!!dialog}
        onClose={() => !busy && setDialog("")}
      >
        <ErrorBox error={error} />
        {dialog === "status" ? (
          <>
            <p>
              {next === "published"
                ? "Publishing locks this plan against further edits."
                : `Move ${plan?.name} to ${next === "review" ? "review" : "approved"}?`}
            </p>
            <div className="dialog-actions">
              <Button onClick={() => setDialog("")}>Cancel</Button>
              <Button
                kind="primary"
                disabled={busy}
                onClick={() => transition(next)}
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
            <Field title="Item">
              <Pick
                label="Adjustment item"
                value={edit.item}
                options={source?.items.map((x) => [x, x]) || []}
                onChange={(v) =>
                  setEdit({
                    ...edit,
                    item: v,
                    period: source.series[v].forecast[0].timestamp,
                    value: source.series[v].forecast[0].mean,
                  })
                }
              />
            </Field>
            <Field title="Period">
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
                    value: source.series[edit.item].forecast.find(
                      (r) => r.timestamp === v,
                    ).mean,
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
              <Button type="button" onClick={() => setDialog("")}>
                Cancel
              </Button>
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

function SupplyPage({ run, navigate }) {
  const [tab, setTab] = useState("materials"),
    [risk, setRisk] = useState(true),
    [period, setPeriod] = useState(""),
    [search, setSearch] = useState("");
  const op = run?.operations;
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
  useEffect(() => { setPeriod(periods[0] || ''); }, [run?.run_id]);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Supply</h1>
          <p>Material requirements and capacity for the current forecast.</p>
        </div>
      </div>
      {!op?.source ? (
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
          <Tabs
            value={tab}
            onChange={setTab}
            items={[
              ["materials", "Materials"],
              ["capacity", "Capacity"],
            ]}
          />
          <div className="supply-filters">
            <div className="search">
              <MagnifyingGlass size={18} />
              <input
                aria-label="Search supply"
                placeholder={
                  tab === "materials"
                    ? "Find a material or supplier"
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
                  "Period",
                  "Required",
                  "Receipts",
                  <>Balance<Help text="Projected stock using confirmed receipts only. Proposed orders are not included until you place them."/></>,
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
                  "Production line",
                  "Period",
                  "Demand (t)",
                  "Available (t)",
                  "Use",
                  "Downtime (h)",
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
                    <td>{fmt(r.forecast_tonnes)}</td>
                    <td>{fmt(r.available_tonnes)}</td>
                    <td>
                      <Pill tone={r.utilisation_pct > 100 ? "warning" : ""}>
                        {pct(r.utilisation_pct)}
                      </Pill>
                    </td>
                    <td>{fmt(r.planned_downtime_hours)}</td>
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
                : "Product demand is grouped by production line and compared with available tonnes from your capacity calendar. Downtime and working days are supplied by your file; they are not fetched automatically."}
            </p>
          </details>
        </>
      )}
    </>
  );
}

function SettingsPage({ workspace, refresh, notify }) {
  const [site, setSite] = useState(workspace?.site || {});
  const [connections, setConnections] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState("");
  useEffect(() => {
    api("/api/integrations")
      .then((r) => setConnections(r.integrations))
      .catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Settings</h1>
        </div>
      </div>
      <section className="surface settings-section">
        <h2>Manufacturing site</h2>
        <form
          className="site-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy("site");
            setError("");
            try {
              await api(
                "/api/site",
                {
                  name: site.name,
                  province: site.province,
                  timezone: site.timezone,
                },
                "PUT",
              );
              await refresh();
              notify("Site settings saved");
            } catch (e) {
              setError(e.message);
            } finally {
              setBusy("");
            }
          }}
        >
          <ErrorBox error={error} />
          <Field title="Site name">
            <input
              aria-label="Site name"
              value={site.name || ""}
              required
              minLength={2}
              maxLength={120}
              onChange={(e) => setSite({ ...site, name: e.target.value })}
            />
          </Field>
          <div className="form-grid two">
            <Field title="Province in Iran">
              <input
                aria-label="Province in Iran"
                value={site.province || ""}
                required
                minLength={2}
                maxLength={100}
                onChange={(e) => setSite({ ...site, province: e.target.value })}
              />
            </Field>
            <Field title="Time zone">
              <input
                aria-label="Time zone"
                value={site.timezone || ""}
                required
                onChange={(e) => setSite({ ...site, timezone: e.target.value })}
              />
            </Field>
          </div>
          <Button kind="primary" disabled={!!busy}>
            {busy === "site" ? "Saving…" : "Save settings"}
          </Button>
        </form>
        <p className="muted">
          Location settings don’t fetch economic or weather data. Import values
          for your region with your forecast.
        </p>
      </section>
      <details className="surface disclosure">
        <summary>
          Connection diagnostics<span>{connections.length} configured</span>
        </summary>
        <div className="detail-body">
          <p className="muted">
            These checks test availability only. Import files in Data to use
            them in a forecast.
          </p>
          <ErrorBox error={error} />
          <Table headers={["Connection", "Last checked", "Status", ""]}>
            {connections.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{date(c.last_sync, true)}</td>
                <td>
                  {c.status === "healthy" ? "Reachable" : label(c.status)}
                </td>
                <td>
                  <Button
                    disabled={!!busy}
                    onClick={async () => {
                      setBusy(c.id);
                      setError("");
                      try {
                        const r = await api(
                          `/api/integrations/${c.id}/sync`,
                          {},
                        );
                        setConnections((cs) =>
                          cs.map((x) => (x.id === r.id ? r : x)),
                        );
                      } catch (e) {
                        setError(e.message);
                      } finally {
                        setBusy("");
                      }
                    }}
                  >
                    {busy === c.id ? "Checking…" : "Check"}
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        </div>
      </details>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);

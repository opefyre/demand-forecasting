import React, { useEffect, useRef, useState } from "react";
import { ReceiptEditor } from "./receipts";
import {
  ArrowLeft,
  ArrowRight,
  Plus,
  UploadSimple,
} from "@phosphor-icons/react";

const EMPTY = {
  source_id: "",
  name: "",
  sheet: "",
  header_row: 1,
  as_of: "",
  mapping: {},
  fixed_unit: "",
  quality_mode: "unknown",
  quality_map: {},
  reviewed: false,
  distinct_records_confirmed: false,
  classification: "user_provided",
};
const QUALITY = [
  ["unknown", "Not confirmed"],
  ["available", "Usable"],
  ["hold", "On hold / not usable"],
];
const draftKey = "demandlab.inventoryDraft";
function draft() {
  try {
    return JSON.parse(localStorage.getItem(draftKey) || "null");
  } catch {
    return null;
  }
}

export function InventoryData({ ui, api, fmt, date, notify }) {
  const { Button, Pick, Field, Table, ErrorBox, Help } = ui;
  const saved = useRef(draft());
  const [snapshots, setSnapshots] = useState([]),
    [selected, setSelected] = useState(null),
    [importing, setImporting] = useState(false),
    [step, setStep] = useState(0),
    [source, setSource] = useState(saved.current?.source || null),
    [preview, setPreview] = useState(saved.current?.preview || null),
    [form, setForm] = useState(saved.current?.form || EMPTY),
    [review, setReview] = useState(null),
    [statusValues, setStatusValues] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const file = useRef();
  const workflow = useRef();
  useEffect(() => {
    workflow.current?.scrollIntoView({ block: "start" });
  }, [step, error]);
  const load = () =>
    api("/api/inventory").then((r) => setSnapshots(r.snapshots));
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (source)
      localStorage.setItem(draftKey, JSON.stringify({ source, preview, form }));
  }, [source, preview, form]);
  useEffect(() => {
    let live = true;
    setStatusValues([]);
    if (form.quality_mode === "column" && form.mapping.quality && source)
      api(`/api/inventory/sources/${source.id}/values`, {
        sheet: form.sheet,
        header_row: form.header_row,
        column: form.mapping.quality,
      })
        .then((r) => {
          if (live) setStatusValues(r.values);
        })
        .catch((e) => {
          if (live) setError(e.message);
        });
    return () => {
      live = false;
    };
  }, [
    form.quality_mode,
    form.mapping.quality,
    form.sheet,
    form.header_row,
    source?.id,
  ]);
  function change(key, value) {
    setForm((f) => ({ ...f, [key]: value, reviewed: false }));
    setReview(null);
  }
  function map(key, value) {
    change("mapping", { ...form.mapping, [key]: value });
  }
  async function upload(event) {
    const incoming = event.target.files?.[0];
    if (!incoming) return;
    setBusy(true);
    setError("");
    try {
      const body = new FormData();
      body.append("file", incoming);
      const s = await api("/api/inventory/sources", body);
      setSource(s);
      setPreview(s.preview);
      setReview(null);
      setForm({
        ...EMPTY,
        source_id: s.id,
        name: incoming.name.replace(/\.[^.]+$/, ""),
        sheet: s.preview.sheet || "",
      });
      setStep(0);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }
  async function next() {
    setBusy(true);
    setError("");
    try {
      if (step === 0) {
        const p = await api(`/api/inventory/sources/${source.id}/preview`, {
          sheet: form.sheet,
          header_row: form.header_row,
        });
        setPreview(p);
        if (!p.columns.length)
          throw new Error(
            "That heading row is empty. Choose the row containing the stock column names.",
          );
        const choose = (regex) =>
          p.columns.find((c) => regex.test(c.label))?.id || "";
        if (
          !Object.keys(form.mapping).length ||
          p.sheet !== preview?.sheet ||
          p.header_row !== preview?.header_row
        )
          change("mapping", {
            sku: choose(
              /external.*article|product.*code|^sku$|article.*n|item.*code/i,
            ),
            quantity: choose(/^amount$|on.hand|^quantity$|^qty$/i),
            unit: choose(/stock.unit|^unit$|^uom$/i),
            location: choose(/stock.location|warehouse|^location$/i),
            record_key: choose(/pallet.*n|record.id/i),
            record_key_2: choose(/^m.order/i),
          });
        setStep(1);
      } else {
        const r = await api("/api/inventory/validate", form);
        setReview(r);
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
      const s = await api("/api/inventory", form);
      localStorage.removeItem(draftKey);
      saved.current = null;
      setSource(null);
      setPreview(null);
      setForm(EMPTY);
      setReview(null);
      setImporting(false);
      await load();
      setSelected(await api(`/api/inventory/${s.id}`));
      notify("Inventory snapshot saved");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const options = [
    ["", "Not selected"],
    ...(preview?.columns || []).map((c) => [c.id, `${c.id} · ${c.label}`]),
  ];
  const example = (field) =>
    (preview?.rows || [])
      .slice(0, 3)
      .map((r) => r.values[form.mapping[field]])
      .filter(Boolean)
      .join(" · ");
  const stockTable = (rows) => (
    <Table
      headers={["Product", "On hand", "Unit", "Stock status", "Source row"]}
    >
      {rows.map((r, i) => (
        <tr key={i}>
          <td>{r.sku}</td>
          <td>{fmt(r.quantity)}</td>
          <td>{r.unit}</td>
          <td>{QUALITY.find((q) => q[0] === r.quality)?.[1]}</td>
          <td>{r.source_row}</td>
        </tr>
      ))}
    </Table>
  );
  if (!importing)
    return (
      <>
        <ErrorBox error={error} />
        <div className="section-heading">
          <div>
            {selected && (
              <button className="back-link" onClick={() => setSelected(null)}>
                <ArrowLeft size={16} />
                All snapshots
              </button>
            )}
            <h2>{selected ? selected.name : "Inventory"}</h2>
            {selected && (
              <p className="muted">
                {selected.classification === "synthetic_sample"
                  ? "Sample · "
                  : ""}
                Closing stock · {date(selected.as_of, true)} ·{" "}
                {selected.source.name} / {selected.source.sheet || "Table"}
              </p>
            )}
          </div>
          <Button
            kind="primary"
            onClick={() => {
              setImporting(true);
              setStep(0);
              setError("");
            }}
          >
            <Plus size={18} />
            {source ? "Resume stock import" : "Import stock"}
          </Button>
        </div>
        {selected ? (
          <section className="surface">
            {selected.warnings.map((w, i) => (
              <p className="muted" key={i}>
                {w}
              </p>
            ))}
            {stockTable(selected.rows.slice(0, 100))}
            {selected.rows.length > 100 && (
              <p className="footnote">
                Showing the first 100 of {selected.row_count} records. All
                records are retained.
              </p>
            )}
          </section>
        ) : snapshots.length ? (
          <section className="surface record-list">
            {snapshots.map((s) => (
              <article key={s.id}>
                <div className="record-info">
                  <strong>{s.name}</strong>
                  <p>
                    {date(s.as_of, true)} · {s.sku_count} products ·{" "}
                    {s.row_count} stock records
                    {s.classification === "synthetic_sample" ? " · Sample" : ""}
                  </p>
                </div>
                <Button
                  onClick={() =>
                    api(`/api/inventory/${s.id}`)
                      .then(setSelected)
                      .catch((e) => setError(e.message))
                  }
                >
                  View stock
                  <ArrowRight size={16} />
                </Button>
              </article>
            ))}
          </section>
        ) : (
          <section className="surface">
            <h3>Bring in your stock file</h3>
            <p className="muted">
              Choose a sheet, match its columns, and confirm the stock date.
              Stock remains separate from sales history.
            </p>
          </section>
        )}
      </>
    );
  return (
    <section className="inventory-import" ref={workflow}>
      <button
        className="back-link"
        onClick={() => {
          setImporting(false);
          setError("");
        }}
      >
        <ArrowLeft size={16} />
        Inventory
      </button>
      <div className="section-heading">
        <h2>Import stock</h2>
        <span className="muted">
          {step + 1} of 3 ·{" "}
          {["Choose file", "Match columns", "Review stock"][step]}
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
              accept=".xlsx,.xlsm,.csv,.tsv,.json"
              onChange={upload}
            />
            <div className="section-heading">
              <div>
                <strong>{source?.name || "Inventory file"}</strong>
                <p className="muted">Excel, CSV, TSV or JSON.</p>
              </div>
              <Button disabled={busy} onClick={() => file.current.click()}>
                <UploadSimple size={18} />
                {source ? "Replace file" : "Choose stock file"}
              </Button>
            </div>
            {source && (
              <div className="field-grid">
                {(source.preview.sheets || []).length > 0 && (
                  <Field title="Worksheet">
                    <Pick
                      label="Inventory worksheet"
                      value={form.sheet}
                      options={source.preview.sheets.map((s) => [s, s])}
                      onChange={(v) => change("sheet", v)}
                    />
                  </Field>
                )}
                <Field
                  title="Heading row"
                  help="The row containing names such as Product, Quantity and Unit."
                >
                  <input
                    aria-label="Inventory heading row"
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
              {[
                ["sku", "Product code"],
                ["quantity", "On-hand quantity"],
                ["unit", "Stock unit"],
                ["location", "Warehouse / location (optional)"],
                ["record_key", "Pallet or record key (optional)"],
                ["record_key_2", "Order or second key (optional)"],
              ].map(([key, title]) => (
                <Field
                  key={key}
                  title={title}
                  help={
                    key === "record_key"
                      ? "Use keys to distinguish separate pallets or lots and detect repeated imports within this file."
                      : undefined
                  }
                >
                  <Pick
                    label={title}
                    value={form.mapping[key] || ""}
                    options={options}
                    onChange={(v) => map(key, v)}
                  />
                  <small className="mapping-example">
                    {example(key) || "No example selected"}
                  </small>
                </Field>
              ))}
              {!form.mapping.unit && (
                <Field title="Confirmed unit for every row">
                  <input
                    aria-label="Confirmed stock unit"
                    value={form.fixed_unit}
                    onChange={(e) => change("fixed_unit", e.target.value)}
                    placeholder="e.g. pieces"
                  />
                </Field>
              )}
              <Field
                title="Stock as of"
                help="The date this stock was counted or exported. Do not use a product's packaging date or guess from the file name."
              >
                <input
                  type="date"
                  aria-label="Stock as of"
                  value={form.as_of}
                  onInput={(e) => change("as_of", e.currentTarget.value)}
                  onChange={(e) => change("as_of", e.target.value)}
                />
              </Field>
              <Field title="Snapshot name">
                <input
                  aria-label="Inventory snapshot name"
                  value={form.name}
                  onChange={(e) => change("name", e.target.value)}
                />
              </Field>
              <Field title="Data type">
                <Pick
                  label="Inventory data type"
                  value={form.classification || "user_provided"}
                  options={[
                    ["user_provided", "Real stock data"],
                    ["synthetic_sample", "Sample / test data"],
                  ]}
                  onChange={(v) => change("classification", v)}
                />
              </Field>
              <Field title="Which stock is usable?">
                <Pick
                  label="Inventory quality treatment"
                  value={form.quality_mode}
                  options={[
                    ["unknown", "Not confirmed yet"],
                    ["column", "Use a stock-status column"],
                    ["available", "All rows confirmed usable"],
                  ]}
                  onChange={(v) => change("quality_mode", v)}
                />
              </Field>
              {form.quality_mode === "column" && (
                <Field title="Stock-status column">
                  <Pick
                    label="Stock-status column"
                    value={form.mapping.quality || ""}
                    options={options}
                    onChange={(v) => map("quality", v)}
                  />
                </Field>
              )}
            </div>
            {form.quality_mode === "column" && statusValues.length > 0 && (
              <div className="stock-status-map">
                <h3>Interpret stock status</h3>
                <div className="field-grid">
                  {statusValues.map((v) => (
                    <Field key={v} title={v || "(blank)"}>
                      <Pick
                        label={`Stock status ${v || "blank"}`}
                        value={form.quality_map[v] || "unknown"}
                        options={QUALITY}
                        onChange={(q) =>
                          change("quality_map", { ...form.quality_map, [v]: q })
                        }
                      />
                    </Field>
                  ))}
                </div>
              </div>
            )}
            <details className="help-details">
              <summary>Preview source rows</summary>
              <Table
                headers={[
                  "Row",
                  ...preview.columns
                    .slice(0, 12)
                    .map((c) => `${c.id} · ${c.label}`),
                ]}
              >
                {preview.rows.map((r) => (
                  <tr key={r.source_row}>
                    <td>{r.source_row}</td>
                    {preview.columns.slice(0, 12).map((c) => (
                      <td key={c.id}>{r.values[c.id] || "—"}</td>
                    ))}
                  </tr>
                ))}
              </Table>
            </details>
          </>
        ) : (
          review && (
            <>
              <h3>
                {review.row_count} stock records · {review.sku_count} products
              </h3>
              <p className="muted">
                Closing stock as of {date(review.as_of, true)}. Totals stay
                separate by unit.
              </p>
              <div className="stock-totals">
                {Object.entries(review.totals_by_unit).map(([unit, total]) => (
                  <span key={unit}>
                    <strong>{fmt(total)}</strong> {unit}
                  </span>
                ))}
              </div>
              {review.issue_count > 0 && (
                <>
                  <h3>{review.issue_count} issues to resolve</h3>
                  <Table headers={["Source cell", "What needs attention"]}>
                    {review.issues.map((r, i) => (
                      <tr key={i}>
                        <td>{r.cell}</td>
                        <td>{r.message}</td>
                      </tr>
                    ))}
                  </Table>
                </>
              )}
              {review.warnings.map((w, i) => (
                <p className="muted" key={i}>
                  {w}
                </p>
              ))}
              {stockTable(review.rows.slice(0, 10))}
              {review.duplicate_looking_rows > 0 && (
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={form.distinct_records_confirmed}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        distinct_records_confirmed: e.target.checked,
                      }))
                    }
                  />
                  Repeated-looking rows represent distinct physical stock.
                </label>
              )}
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={form.reviewed}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, reviewed: e.target.checked }))
                  }
                />
                I have checked the stock date, units and matched quantities.
              </label>
            </>
          )
        )}
        <div className="inventory-actions">
          {step > 0 && (
            <Button disabled={busy} onClick={() => setStep(step - 1)}>
              Back
            </Button>
          )}
          {step < 2 ? (
            <Button kind="primary" disabled={busy || !source} onClick={next}>
              {busy
                ? "Reading file…"
                : step === 0
                  ? "Match columns"
                  : "Review stock"}
              <ArrowRight size={16} />
            </Button>
          ) : (
            <Button
              kind="primary"
              disabled={busy || !form.reviewed || review?.issue_count > 0}
              onClick={save}
            >
              {busy ? "Saving…" : "Save stock snapshot"}
            </Button>
          )}
        </div>
      </section>
    </section>
  );
}

export function InventoryOutlook({
  ui,
  api,
  fmt,
  date,
  run,
  planId,
  openInventory,
  canEdit,
}) {
  const { Button, Pick, Table, ErrorBox, Field, Help } = ui;
  const [snapshots, setSnapshots] = useState([]),
    [selected, setSelected] = useState(""),
    [versions, setVersions] = useState([]),
    [unitVersion, setUnitVersion] = useState(""),
    [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [period, setPeriod] = useState(""),
    [search, setSearch] = useState("");
  const [receiptVersions, setReceiptVersions] = useState([]);
  const [receiptVersion, setReceiptVersion] = useState("");
  const [editingReceipts, setEditingReceipts] = useState(false);
  useEffect(() => {
    let live = true;
    setReceiptVersions([]);
    setReceiptVersion("");
    setEditingReceipts(false);
    if (selected)
      api(`/api/inventory/${selected}/receipts`)
        .then((r) => {
          if (live) setReceiptVersions(r.versions);
        })
        .catch((e) => {
          if (live) setError(e.message);
        });
    return () => {
      live = false;
    };
  }, [selected]);
  useEffect(() => {
    api("/api/inventory")
      .then((r) => setSnapshots(r.snapshots))
      .catch((e) => setError(e.message));
    api("/api/units")
      .then((r) => setVersions(r.versions))
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    let live = true;
    setResult(null);
    setError("");
    if (!selected || !run) {
      setBusy(false);
      return;
    }
    setBusy(true);
    api(
      `/api/inventory/${selected}/projection?run_id=${run.run_id}${planId ? `&plan_id=${planId}` : ""}${unitVersion ? `&unit_version_id=${unitVersion}` : ""}${receiptVersion ? `&receipt_version_id=${receiptVersion}` : ""}`,
    )
      .then((r) => {
        if (live) {
          setResult(r);
          setPeriod(r.rows[0]?.period || "");
        }
      })
      .catch((e) => {
        if (live) setError(e.message);
      })
      .finally(() => {
        if (live) setBusy(false);
      });
    return () => {
      live = false;
    };
  }, [selected, run?.run_id, planId, unitVersion, receiptVersion]);
  const rows = (result?.rows || []).filter(
    (r) =>
      (!period || r.period === period) &&
      r.sku.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      {!snapshots.length ? (
        <section className="surface">
          <h2>Add your stock snapshot</h2>
          <p className="muted">
            Import stock in its original units to compare it with demand.
          </p>
          <Button onClick={openInventory}>
            Import stock
            <ArrowRight size={16} />
          </Button>
        </section>
      ) : (
        <div className="inventory-controls">
          <Field title="Stock snapshot">
            <Pick
              label="Stock snapshot"
              value={selected}
              options={[
                ["", "Choose stock"],
                ...snapshots.map((s) => [
                  s.id,
                  `${s.name} · ${date(s.as_of, true)}${s.classification === "synthetic_sample" ? " · Sample" : ""}`,
                ]),
              ]}
              onChange={setSelected}
            />
          </Field>
          {result && (
            <Field title="Period">
              <Pick
                label="Stock outlook period"
                value={period}
                options={[
                  ["", "All periods"],
                  ...[...new Set(result.rows.map((r) => r.period))].map((p) => [
                    p,
                    date(p),
                  ]),
                ]}
                onChange={setPeriod}
              />
            </Field>
          )}
          {selected && (
            <Field
              title="Unit definitions"
              help="Choose a reviewed version for packaging or factory-specific units. Manage versions in Settings."
            >
              <Pick
                label="Stock unit definitions"
                value={unitVersion}
                onChange={setUnitVersion}
                options={[
                  ["", "Standard units only"],
                  ...versions.map((v) => [
                    v.id,
                    `${v.name} · ${v.id.slice(0, 6)}${v.classification === "synthetic_sample" ? " · Sample" : ""}`,
                  ]),
                ]}
              />
            </Field>
          )}
        </div>
      )}
      <ErrorBox error={error} />
      {selected && (
        <div className="inventory-controls">
          <Field
            title="Expected deliveries"
            help="Choose one reviewed schedule. Versions replace each other; they are never added together."
          >
            <Pick
              label="Receipt schedule"
              value={receiptVersion}
              onChange={setReceiptVersion}
              options={[
                ["", "No future receipts"],
                ...receiptVersions.map((v) => [
                  v.id,
                  `${v.name} · ${v.created_at.slice(0, 16).replace("T", " ")} UTC`,
                ]),
              ]}
            />
          </Field>
          {canEdit && (
            <Button
              onClick={() => setEditingReceipts(true)}
              disabled={editingReceipts}
            >
              {receiptVersion ? "Revise deliveries" : "Add deliveries"}
            </Button>
          )}
        </div>
      )}
      {editingReceipts && (
        <ReceiptEditor
          key={`${selected}/${receiptVersion}`}
          ui={ui}
          api={api}
          snapshotId={selected}
          current={receiptVersions.find((v) => v.id === receiptVersion)}
          onClose={() => setEditingReceipts(false)}
          onSaved={(v) => {
            setReceiptVersions((previous) => [
              v,
              ...previous.filter((p) => p.id !== v.id),
            ]);
            setReceiptVersion(v.id);
            setEditingReceipts(false);
          }}
        />
      )}
      {busy && <p role="status">Calculating stock outlook…</p>}
      {!run && (
        <p className="muted">
          Create or open a forecast first to compare demand with stock.
        </p>
      )}
      {result &&
        (result.stock_classification === "synthetic_sample" ||
          result.forecast_classification === "synthetic_sample") && (
          <p className="footnote">
            Sample inputs are included. This is a demonstration, not an
            operational stock decision.
          </p>
        )}
      {result && (
        <section className="surface inventory-outlook">
          <div className="section-heading">
            <div>
              <h2>
                Stock outlook <Help text={result.assumption} />
              </h2>
              <p className="muted">
                {result.receipt_version
                  ? "Period-end estimate. A delivery later in the period may not prevent an earlier shortage."
                  : "On-hand stock only. No future deliveries included."}
              </p>
            </div>
            <input
              className="stock-search"
              aria-label="Find stock product"
              placeholder="Find product code"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Table
            headers={[
              "Product",
              "Period",
              `Opening (${result.unit})`,
              "Demand",
              "Receipts",
              "Closing",
              "Status",
            ]}
            empty={!rows.length && "No products match your search."}
          >
            {rows.map((r) => (
              <tr key={`${r.sku}/${r.period}`}>
                <td>{r.sku}</td>
                <td>{date(r.period)}</td>
                <td>{r.opening == null ? "Not known" : fmt(r.opening)}</td>
                <td>{fmt(r.demand)}</td>
                <td>{fmt(r.receipts)}</td>
                <td>{r.closing == null ? "Not known" : fmt(r.closing)}</td>
                <td>{r.status}</td>
              </tr>
            ))}
          </Table>
          {result.receipt_version && (
            <details className="disclosure">
              <summary>
                Full receipt schedule · {result.receipt_evidence.length}{" "}
                included, {result.excluded_receipts.length} excluded
              </summary>
              <div className="detail-body">
                <p>{result.receipt_version.reason}</p>
                <Table
                  headers={[
                    "Reference",
                    "Product",
                    "Usable from",
                    "Quantity",
                    "Treatment",
                  ]}
                >
                  {result.receipt_evidence.map((r) => (
                    <tr key={r.reference}>
                      <td>{r.reference}</td>
                      <td>{r.sku}</td>
                      <td>{date(r.due_date, true)}</td>
                      <td>
                        {fmt(r.quantity)} {r.to_unit}
                      </td>
                      <td>
                        {r.kind === "production" ? "Production" : "Purchase"} ·
                        included
                      </td>
                    </tr>
                  ))}
                  {result.excluded_receipts.map((r) => (
                    <tr key={r.reference}>
                      <td>{r.reference}</td>
                      <td>{r.sku}</td>
                      <td>{date(r.due_date, true)}</td>
                      <td>
                        {fmt(r.quantity)} {r.unit}
                      </td>
                      <td>{r.exclusion}</td>
                    </tr>
                  ))}
                </Table>
              </div>
            </details>
          )}
          {(result.conversions.length > 0 ||
            result.conversion_issues.length > 0) && (
            <details className="disclosure">
              <summary>Unit conversion details</summary>
              <div className="detail-body">
                <p className="muted">
                  Stock quantities remain unchanged in the source.{" "}
                  {result.unit_version
                    ? `Using ${result.unit_version.name}, version ${result.unit_version.id.slice(0, 6)}, reviewed by ${result.unit_version.reviewer}.`
                    : "Using standard physical units only."}
                </p>
                {result.conversion_issues
                  .filter((r) =>
                    r.sku.toLowerCase().includes(search.toLowerCase()),
                  )
                  .map((r, i) => (
                    <p key={i}>
                      {r.message} Source row {r.source_row}.
                    </p>
                  ))}
                <Table
                  headers={[
                    "Product",
                    "Source row",
                    "Original stock",
                    "Converted stock",
                    "Stock status",
                    "Basis",
                  ]}
                >
                  {result.conversions
                    .filter((r) =>
                      r.sku.toLowerCase().includes(search.toLowerCase()),
                    )
                    .map((r, i) => (
                      <tr key={i}>
                        <td>{r.sku}</td>
                        <td>{r.source_row}</td>
                        <td>
                          {fmt(r.source_quantity, 6)} {r.from_unit}
                        </td>
                        <td>
                          {fmt(r.quantity, 6)} {r.to_unit}
                        </td>
                        <td>
                          {r.stock_status === "available"
                            ? "Usable"
                            : r.stock_status === "hold"
                              ? "On hold"
                              : "Not confirmed"}
                        </td>
                        <td>{r.reference || r.method}</td>
                      </tr>
                    ))}
                </Table>
              </div>
            </details>
          )}
        </section>
      )}
    </>
  );
}

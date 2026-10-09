import React, { useRef, useState } from "react";

const fields = [
  ["reference", "Order-line reference"],
  ["sku", "Product code"],
  ["quantity", "Outstanding quantity"],
  ["due_date", "Usable from"],
  ["unit", "Unit"],
  ["kind", "Type"],
  ["status", "Status"],
];
const kinds = [
  ["purchase", "Purchase delivery"],
  ["production", "Production completion"],
];
const statuses = [
  ["confirmed", "Confirmed"],
  ["unconfirmed", "Not confirmed"],
  ["cancelled", "Cancelled"],
];

export function ReceiptImport({
  ui,
  api,
  snapshotId,
  current,
  onSaved,
  onBack,
}) {
  const { Button, Field, Pick, Table, ErrorBox } = ui;
  const [source, setSource] = useState(null),
    [preview, setPreview] = useState(null);
  const [config, setConfig] = useState({
    sheet: "",
    header_row: 1,
    mapping: {},
    fixed_unit: "",
    fixed_kind: "purchase",
    fixed_status: "unconfirmed",
    kind_map: {},
    status_map: {},
  });
  const [review, setReview] = useState(null),
    [name, setName] = useState("");
  const [reason, setReason] = useState(""),
    [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const attempt = useRef(null);
  const change = (key, value) => {
    setConfig((previous) => ({ ...previous, [key]: value }));
    setReview(null);
    setConfirmed(false);
  };
  async function act(work) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    await act(async () => {
      const body = new FormData();
      body.append("file", file);
      const saved = await api("/api/receipts/sources", body);
      setSource(saved);
      setPreview(saved.preview);
      setReview(null);
      setConfirmed(false);
      setConfig((previous) => ({
        ...previous,
        source_id: saved.id,
        sheet: saved.preview.sheet || "",
        header_row: 1,
        mapping: {},
        fixed_unit: "",
        fixed_kind: "purchase",
        fixed_status: "unconfirmed",
        kind_map: {},
        status_map: {},
      }));
      setName(file.name.replace(/\.[^.]+$/, ""));
    });
    event.target.value = "";
  }
  async function readTable() {
    await act(async () => {
      const p = await api(`/api/receipts/sources/${source.id}/preview`, config);
      setPreview(p);
      setReview(null);
      setConfirmed(false);
      setConfig((previous) => ({
        ...previous,
        mapping: {},
        kind_map: {},
        status_map: {},
      }));
    });
  }
  async function map(key, value) {
    const next = { ...config, mapping: { ...config.mapping, [key]: value } };
    setConfig(next);
    setReview(null);
    setConfirmed(false);
    if (["kind", "status"].includes(key)) {
      setConfig((previous) => ({ ...previous, [key + "_map"]: {} }));
      if (value)
        await act(async () => {
          const result = await api(
            `/api/receipts/sources/${source.id}/preview`,
            { ...next, value_columns: [value] },
          );
          setPreview((previous) => ({
            ...previous,
            values: { ...previous.values, ...result.values },
          }));
        });
    }
  }
  const sameTable =
    preview &&
    preview.header_row === config.header_row &&
    (preview.sheet || "") === config.sheet;
  const options = [
    ["", "Choose column"],
    ...(preview?.columns || []).map((c) => [c.id, `${c.id} · ${c.label}`]),
  ];
  async function save() {
    const payload = {
      name,
      reason,
      reviewed: confirmed,
      import_config: config,
      parent_id: current?.id || null,
    };
    const fingerprint = JSON.stringify(payload);
    if (attempt.current?.fingerprint !== fingerprint)
      attempt.current = { fingerprint, id: crypto.randomUUID() };
    await act(async () =>
      onSaved(
        await api(`/api/inventory/${snapshotId}/receipts`, {
          ...payload,
          request_id: attempt.current.id,
        }),
      ),
    );
  }
  return (
    <section className="surface receipt-editor">
      <div className="section-heading">
        <h2>Import deliveries</h2>
        <Button onClick={onBack} disabled={busy}>
          Back
        </Button>
      </div>
      <ErrorBox error={error} />
      {!review ? (
        <>
          <Field title="Delivery export">
            <input
              type="file"
              accept=".xlsx,.xlsm,.csv,.tsv,.json"
              disabled={busy}
              onChange={upload}
            />
          </Field>
          {source && (
            <>
              <p className="muted">{source.name}</p>
              <div className="receipt-entry">
                {preview.sheets.length > 0 && (
                  <Field title="Worksheet">
                    <Pick
                      label="Receipt worksheet"
                      value={config.sheet}
                      options={preview.sheets}
                      disabled={busy}
                      onChange={(v) => change("sheet", v)}
                    />
                  </Field>
                )}
                <Field title="Heading row">
                  <input
                    type="number"
                    min="1"
                    max="200"
                    value={config.header_row}
                    disabled={busy}
                    onChange={(e) =>
                      change("header_row", Number(e.target.value))
                    }
                  />
                </Field>
                <Button disabled={busy} onClick={readTable}>
                  Read table
                </Button>
              </div>
              {sameTable && (
                <>
                  <Table
                    headers={preview.columns.map((c) => `${c.id} · ${c.label}`)}
                    empty={!preview.rows.length && "No rows found."}
                  >
                    {preview.rows.map((r) => (
                      <tr key={r.source_row}>
                        {preview.columns.map((c) => (
                          <td key={c.id}>{r.values[c.id]}</td>
                        ))}
                      </tr>
                    ))}
                  </Table>
                  <div className="receipt-entry">
                    {fields.map(([key, title]) => (
                      <Field
                        key={key}
                        title={title}
                        help={
                          key === "due_date"
                            ? "Use real Excel dates or Gregorian YYYY-MM-DD dates. This is when the goods are usable, after quality checks."
                            : undefined
                        }
                      >
                        <Pick
                          label={`Receipt column: ${title}`}
                          disabled={busy}
                          value={config.mapping[key] || ""}
                          options={
                            ["unit", "kind", "status"].includes(key)
                              ? [
                                  ["", "Use one value for all lines"],
                                  ...options.slice(1),
                                ]
                              : options
                          }
                          onChange={(v) => map(key, v)}
                        />
                      </Field>
                    ))}
                  </div>
                  <div className="receipt-entry">
                    {!config.mapping.unit && (
                      <Field title="Unit for all lines">
                        <input
                          disabled={busy}
                          value={config.fixed_unit}
                          onChange={(e) => change("fixed_unit", e.target.value)}
                        />
                      </Field>
                    )}
                    {!config.mapping.kind && (
                      <Field title="Type for all lines">
                        <Pick
                          label="Imported receipt type"
                          disabled={busy}
                          value={config.fixed_kind}
                          options={kinds}
                          onChange={(v) => change("fixed_kind", v)}
                        />
                      </Field>
                    )}
                    {!config.mapping.status && (
                      <Field title="Status for all lines">
                        <Pick
                          label="Imported receipt status"
                          disabled={busy}
                          value={config.fixed_status}
                          options={statuses}
                          onChange={(v) => change("fixed_status", v)}
                        />
                      </Field>
                    )}
                  </div>
                  {["kind", "status"]
                    .filter((key) => config.mapping[key])
                    .map((key) => (
                      <div className="receipt-entry" key={key}>
                        {(preview.values?.[config.mapping[key]] || []).map(
                          (raw) => (
                            <Field
                              title={`${key === "kind" ? "Type" : "Status"}: ${raw || "(blank)"}`}
                              key={raw}
                            >
                              <Pick
                                label={`Receipt ${key} meaning: ${raw || "blank"}`}
                                disabled={busy}
                                value={
                                  Object.hasOwn(config[key + "_map"], raw)
                                    ? config[key + "_map"][raw]
                                    : ""
                                }
                                options={[
                                  ["", "Choose meaning"],
                                  ...(key === "kind" ? kinds : statuses),
                                ]}
                                onChange={(v) =>
                                  change(key + "_map", {
                                    ...config[key + "_map"],
                                    [raw]: v,
                                  })
                                }
                              />
                            </Field>
                          ),
                        )}
                      </div>
                    ))}
                  <Button
                    kind="primary"
                    disabled={busy}
                    onClick={() =>
                      act(async () =>
                        setReview(
                          await api(
                            `/api/inventory/${snapshotId}/receipts/validate`,
                            { import_config: config },
                          ),
                        ),
                      )
                    }
                  >
                    {busy ? "Checking…" : "Review deliveries"}
                  </Button>
                </>
              )}
            </>
          )}
        </>
      ) : (
        <>
          <p>
            {review.row_count} delivery lines ·{" "}
            {review.classification === "synthetic_sample"
              ? "Sample stock"
              : "Client stock"}
          </p>
          <p className="muted">
            This file becomes one complete schedule. It is not added to an
            earlier version.
          </p>
          {review.import_evidence.warnings.map((w) => (
            <p key={w} role="note">
              {w}
            </p>
          ))}
          <Table
            headers={[
              "Reference",
              "Product",
              "Outstanding",
              "Usable from",
              "Status",
            ]}
          >
            {review.rows.map((r) => (
              <tr key={r.reference}>
                <td>{r.reference}</td>
                <td>{r.sku}</td>
                <td>
                  {r.quantity} {r.unit}
                </td>
                <td>{r.due_date}</td>
                <td>{statuses.find(([v]) => v === r.status)?.[1]}</td>
              </tr>
            ))}
          </Table>
          {review.row_count > review.rows.length && (
            <p className="footnote">
              Showing the first {review.rows.length} lines; all{" "}
              {review.row_count} were checked and will be saved.
            </p>
          )}
          <div className="receipt-entry">
            <Field title="Schedule name">
              <input
                value={name}
                maxLength={120}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <Field title="Review note">
              <textarea
                value={reason}
                maxLength={1000}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
          </div>
          <label className="check">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I checked the dates, units and statuses. Quantities are outstanding
            and not already counted in stock or another line.
          </label>
          <div className="dialog-actions">
            <Button
              disabled={busy}
              onClick={() => {
                setReview(null);
                setConfirmed(false);
              }}
            >
              Back to columns
            </Button>
            <Button
              kind="primary"
              disabled={busy || !confirmed || !name.trim() || !reason.trim()}
              onClick={save}
            >
              {busy ? "Saving…" : "Save receipt schedule"}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}

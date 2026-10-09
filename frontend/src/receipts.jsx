import React, { useEffect, useRef, useState } from "react";
import { ReceiptImport } from "./receipt-import";

const empty = {
  reference: "",
  sku: "",
  quantity: "",
  unit: "",
  due_date: "",
  kind: "purchase",
  status: "confirmed",
};

export function ReceiptEditor({
  ui,
  api,
  snapshotId,
  current,
  onSaved,
  onClose,
}) {
  const { Button, Field, Pick, Table, ErrorBox } = ui;
  const [rows, setRows] = useState(current?.rows || []);
  const [line, setLine] = useState(empty);
  const [name, setName] = useState(current?.name || "");
  const [reason, setReason] = useState("");
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [importing, setImporting] = useState(false);
  const attempt = useRef(null);
  const editor = useRef(null);
  useEffect(() => {
    editor.current?.scrollIntoView({ block: "start" });
  }, []);
  const update = (key, value) => {
    setLine({ ...line, [key]: value });
    setReviewed(false);
  };
  function add(event) {
    event.preventDefault();
    if (rows.some((row) => row.reference === line.reference.trim())) {
      setError("Use a unique order-line reference for each delivery.");
      return;
    }
    setRows([
      ...rows,
      {
        ...line,
        reference: line.reference.trim(),
        quantity: Number(line.quantity),
      },
    ]);
    setLine(empty);
    setError("");
    setReviewed(false);
  }
  async function save() {
    setBusy(true);
    setError("");
    const payload = {
      name,
      reason,
      rows,
      reviewed,
      parent_id: current?.id || null,
    };
    const fingerprint = JSON.stringify(payload);
    if (attempt.current?.fingerprint !== fingerprint)
      attempt.current = { fingerprint, id: crypto.randomUUID() };
    try {
      const saved = await api(`/api/inventory/${snapshotId}/receipts`, {
        ...payload,
        request_id: attempt.current.id,
      });
      onSaved(saved);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (importing)
    return (
      <ReceiptImport
        ui={ui}
        api={api}
        snapshotId={snapshotId}
        current={current}
        onSaved={onSaved}
        onBack={() => setImporting(false)}
      />
    );
  return (
    <section className="surface receipt-editor" ref={editor}>
      <div className="section-heading">
        <h2>Expected deliveries</h2>
        <Button onClick={onClose} disabled={busy}>
          Close
        </Button>
      </div>
      <p className="muted">
        Only outstanding usable quantities. Enter the expected release date,
        after any quality checks.
      </p>
      <ErrorBox error={error} />
      <Button disabled={busy} onClick={() => setImporting(true)}>
        Import a delivery file
      </Button>
      <Field title="Schedule name">
        <input
          aria-label="Schedule name"
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
        />
      </Field>
      <form onSubmit={add} className="receipt-entry">
        <Field title="Order-line reference">
          <input
            aria-label="Order-line reference"
            required
            maxLength={200}
            value={line.reference}
            onChange={(e) => update("reference", e.target.value)}
          />
        </Field>
        <Field title="Product code">
          <input
            aria-label="Receipt product code"
            required
            value={line.sku}
            onChange={(e) => update("sku", e.target.value)}
          />
        </Field>
        <Field title="Outstanding quantity">
          <input
            aria-label="Outstanding quantity"
            required
            type="number"
            min="0.000001"
            step="any"
            value={line.quantity}
            onChange={(e) => update("quantity", e.target.value)}
          />
        </Field>
        <Field title="Unit">
          <input
            aria-label="Receipt unit"
            required
            value={line.unit}
            onChange={(e) => update("unit", e.target.value)}
          />
        </Field>
        <Field title="Usable from">
          <input
            aria-label="Usable from"
            required
            type="date"
            value={line.due_date}
            onChange={(e) => update("due_date", e.target.value)}
          />
        </Field>
        <Field title="Type">
          <Pick
            label="Receipt type"
            value={line.kind}
            onChange={(v) => update("kind", v)}
            options={[
              ["purchase", "Purchase delivery"],
              ["production", "Production completion"],
            ]}
          />
        </Field>
        <Field title="Status">
          <Pick
            label="Receipt status"
            value={line.status}
            onChange={(v) => update("status", v)}
            options={[
              ["confirmed", "Confirmed"],
              ["unconfirmed", "Not confirmed"],
              ["cancelled", "Cancelled"],
            ]}
          />
        </Field>
        <Button type="submit" disabled={busy}>
          Add line
        </Button>
      </form>
      <Table
        headers={[
          "Reference",
          "Product",
          "Quantity",
          "Usable from",
          "Status",
          "",
        ]}
        empty={!rows.length && "No receipts added."}
      >
        {rows.map((r, i) => (
          <tr key={r.reference}>
            <td>{r.reference}</td>
            <td>{r.sku}</td>
            <td>
              {r.quantity} {r.unit}
            </td>
            <td>{r.due_date}</td>
            <td>
              {r.status === "confirmed"
                ? "Confirmed"
                : r.status === "cancelled"
                  ? "Cancelled"
                  : "Not confirmed"}
            </td>
            <td>
              <Button
                disabled={busy}
                aria-label={`Remove ${r.reference}`}
                onClick={() => {
                  setRows(rows.filter((_, n) => i !== n));
                  setReviewed(false);
                }}
              >
                Remove
              </Button>
            </td>
          </tr>
        ))}
      </Table>
      <div className="receipt-entry">
        <Field title="Review note">
          <textarea
            aria-label="Receipt review note"
            value={reason}
            maxLength={1000}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Source and changes checked"
          />
        </Field>
        <label className="check">
          <input
            type="checkbox"
            checked={reviewed}
            onChange={(e) => setReviewed(e.target.checked)}
          />
          These quantities are outstanding and not already counted in the stock
          snapshot or another receipt line.
        </label>
      </div>
      <Button
        kind="primary"
        disabled={
          busy ||
          !reviewed ||
          !name.trim() ||
          !reason.trim() ||
          Object.keys(empty).some(
            (k) => !["kind", "status"].includes(k) && line[k],
          )
        }
        onClick={save}
      >
        {busy ? "Saving…" : "Save receipt schedule"}
      </Button>
      <p className="footnote">
        A new version is saved. Earlier schedules stay unchanged. Production
        quantities are supplied plans, not a capacity-approved schedule.
      </p>
    </section>
  );
}

import React, { useEffect, useState } from "react";

export function ProductionMapping({
  source,
  value,
  onChange,
  ui,
  api,
  lineControl,
}) {
  const { Field, Pick, Table, ErrorBox } = ui;
  const [sheets, setSheets] = useState([]),
    [versions, setVersions] = useState([]),
    [schema, setSchema] = useState(null),
    [active, setActive] = useState("bom"),
    [preview, setPreview] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const config = value || { tables: {}, stock_as_of: "", reviewed: false };
  const spec = config.tables?.[active] || {
    sheet: "",
    header_row: 1,
    columns: {},
  };
  useEffect(() => {
    let live = true;
    setSchema(null);
    api(`/api/production/schema?mode=${config.mode || "tonnes"}`)
      .then((r) => {
        if (live) setSchema(r);
      })
      .catch((e) => setError(e.message));
    return () => {
      live = false;
    };
  }, [config.mode]);
  useEffect(() => {
    api("/api/units")
      .then((r) => setVersions(r.versions))
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    api(`/api/production/sources/${source.id}`)
      .then((r) => {
        setSheets(r.sheets);
        if (!value) onChange(r.suggested_mapping);
      })
      .catch((e) => setError(e.message));
  }, [source.id]);
  function change(update) {
    onChange({ ...config, ...update, reviewed: false });
  }
  function table(update) {
    change({ tables: { ...config.tables, [active]: { ...spec, ...update } } });
  }
  useEffect(() => {
    let live = true;
    setPreview(null);
    setError("");
    if (!spec.sheet) {
      setBusy(false);
      return;
    }
    setBusy(true);
    api(`/api/production/sources/${source.id}/preview`, {
      sheet: spec.sheet,
      header_row: spec.header_row,
    })
      .then((r) => {
        if (live) setPreview(r);
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
  }, [source.id, active, spec.sheet, spec.header_row]);
  return (
    <section className="production-mapping">
      <h3>Production data</h3>
      <p className="muted">
        {config.mode === "routed"
          ? "Recipes use the declared product unit. Production steps turn demand into machine hours."
          : "Finished-product quantities and capacity use tonnes. Recipes use each material’s own unit."}
      </p>
      <Field
        title="Capacity planning"
        help="Use product routes when products pass through several machines or demand is not measured in tonnes. Changing this choice clears incompatible recipe and capacity fields."
      >
        <Pick
          label="Capacity planning basis"
          value={config.mode || "tonnes"}
          options={[
            ["tonnes", "Tonnes per production line"],
            ["routed", "Product routes and machine hours"],
          ]}
          onChange={(mode) => {
            setActive("bom");
            change({
              mode,
              tables: {
                ...config.tables,
                bom: { ...config.tables?.bom, columns: {} },
                capacity: { ...config.tables?.capacity, columns: {} },
              },
            });
          }}
        />
      </Field>
      <div className="form-grid two">
        {config.mode !== "routed" && lineControl}
        <Field
          title="Material stock date"
          help="Closing balance date, including any stock on hold. It must be the day before the forecast starts."
        >
          <input
            aria-label="Material stock date"
            type="date"
            value={config.stock_as_of}
            onInput={(e) => change({ stock_as_of: e.target.value })}
            onChange={(e) => change({ stock_as_of: e.target.value })}
          />
        </Field>
      </div>
      {config.mode === "routed" && (
        <Field
          title="Product-unit definitions"
          help="Use a reviewed version only when forecast and recipe or route product units differ. Rules apply to each forecast month. Physical-unit conversions use Pint; packaging relationships are never guessed."
        >
          <Pick
            label="Production unit definitions"
            value={config.unit_version_id || ""}
            options={[
              ["", "Standard units only"],
              ...versions.map((v) => [
                v.id,
                `${v.name} · ${v.id.slice(0, 6)}${v.classification === "synthetic_sample" ? " · Sample" : ""}`,
              ]),
            ]}
            onChange={(v) => change({ unit_version_id: v })}
          />
        </Field>
      )}
      {schema && (
        <>
          <Field title="Table to match">
            <Pick
              label="Production table"
              value={active}
              onChange={setActive}
              options={Object.entries(schema).map(([key, s]) => [key, s.label])}
            />
          </Field>
          <div className="form-grid two">
            <Field title="Worksheet">
              <Pick
                label="Production worksheet"
                value={spec.sheet}
                options={[
                  [
                    "",
                    active === "open_pos"
                      ? "No deliveries supplied"
                      : "Choose worksheet",
                  ],
                  ...sheets.map((s) => [s, s]),
                ]}
                onChange={(v) =>
                  table({ sheet: v, columns: {}, header_row: 1 })
                }
              />
            </Field>
            <Field title="Heading row">
              <input
                aria-label="Production heading row"
                type="number"
                min="1"
                max="200"
                value={spec.header_row}
                onChange={(e) =>
                  table({ header_row: Number(e.target.value), columns: {} })
                }
              />
            </Field>
          </div>
          <ErrorBox error={error} />
          {busy && <p role="status">Reading worksheet…</p>}
          {preview && !busy && (
            <>
              <div className="form-grid two">
                {Object.entries(schema[active].required).map(
                  ([field, title]) => (
                    <Field
                      key={field}
                      title={title}
                      help={
                        {
                          available_hours:
                            "Net hours after downtime and efficiency losses. These are not reduced again.",
                          hours_per_unit:
                            "Hours per good finished-product unit, including any process losses. No yield is inferred.",
                          valid_from:
                            "Use the first day of a month. Each step needs a valid definition throughout the forecast.",
                        }[field]
                      }
                    >
                      <Pick
                        label={`Production ${title}`}
                        value={spec.columns[field] || ""}
                        options={[
                          ["", "Choose column"],
                          ...preview.columns.map((c) => [
                            c.id,
                            `${c.id} · ${c.label}`,
                          ]),
                        ]}
                        onChange={(v) =>
                          table({ columns: { ...spec.columns, [field]: v } })
                        }
                      />
                    </Field>
                  ),
                )}
              </div>
              {Object.keys(schema[active].optional).length > 0 && (
                <details className="optional-section">
                  <summary>
                    Additional fields <span>Optional</span>
                  </summary>
                  <div className="form-grid two">
                    {Object.entries(schema[active].optional).map(
                      ([field, title]) => (
                        <Field
                          key={field}
                          title={title}
                          help={
                            {
                              valid_to:
                                "Use the last day of a month, or leave empty for no end date.",
                              batch_size:
                                "Match both batch size and setup hours. Batches are rounded up per product and month after combining customers.",
                              setup_hours_per_batch:
                                "Map together with batch size. If both are absent, no setup allowance is included.",
                            }[field]
                          }
                        >
                          <Pick
                            label={`Production ${title}`}
                            value={spec.columns[field] || ""}
                            options={[
                              ["", "Not supplied"],
                              ...preview.columns.map((c) => [
                                c.id,
                                `${c.id} · ${c.label}`,
                              ]),
                            ]}
                            onChange={(v) =>
                              table({
                                columns: { ...spec.columns, [field]: v },
                              })
                            }
                          />
                        </Field>
                      ),
                    )}
                  </div>
                </details>
              )}
              <details className="disclosure">
                <summary>
                  Source rows <span>{preview.rows.length} shown</span>
                </summary>
                <Table
                  headers={[
                    "Row",
                    ...preview.columns.map((c) => `${c.id} · ${c.label}`),
                  ]}
                >
                  {preview.rows.map((r) => (
                    <tr key={r.source_row}>
                      <td>{r.source_row}</td>
                      {preview.columns.map((c) => (
                        <td key={c.id}>{r.values[c.id]}</td>
                      ))}
                    </tr>
                  ))}
                </Table>
              </details>
            </>
          )}
          {Object.entries(schema)
            .filter(
              ([key, s]) =>
                key !== "open_pos" &&
                (!config.tables?.[key]?.sheet ||
                  !Object.keys(s.required).every(
                    (f) => config.tables[key].columns?.[f],
                  )),
            )
            .map(([key, s]) => (
              <p className="muted" key={key}>
                Still to match: {s.label}
              </p>
            ))}
          <label className="check-row">
            <input
              type="checkbox"
              checked={config.reviewed === true}
              onChange={(e) =>
                onChange({ ...config, reviewed: e.target.checked })
              }
            />
            <span>
              I checked the units, stock date and table mappings. Unmapped holds
              or allowances mean zero; unmapped deliveries are excluded.{" "}
              {config.mode === "routed" &&
                "Machine hours are net of losses. Unmapped batch setup means no setup allowance."}
            </span>
          </label>
        </>
      )}
    </section>
  );
}

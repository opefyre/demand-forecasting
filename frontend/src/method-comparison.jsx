import React, { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import { t as uiText, i18n, unitLabel } from "./localization.mjs";
import { FORECAST_CHOICES } from "./forecast-start.mjs";
import { methodRows,comparisonAvailability } from "./forecast-groups.mjs";
import { planningBasis, planningMonth } from "./planning-calendar.mjs";
import { coverageStatus } from "./demand-view.mjs";
import { chartTheme } from "./chart-theme.mjs";
import { Stack, Actions } from "./ui-layout.jsx";
export const methodName = (id) =>
  uiText(
    FORECAST_CHOICES.find(([key]) => key === id)?.[1] || id || "Automatic",
  );
export function MethodComparison({
  group,
  activeRun,
  api,
  ui,
  filters,
  selectedOrders,
  onReviewCoverage,
}) {
  const { ErrorBox, Table, Button, Help } = ui;
  const [entries, setEntries] = useState([]),
    [selected, setSelected] = useState([]),
    [error, setError] = useState(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    setEntries([]);
    Promise.all(
      group.runs.map(async (item) => {
        const run = await api("/api/runs/" + item.run_id);
        if (!run.sales_input_snapshot_id)
          throw Error(uiText("This forecast has no saved order review."));
        const outlook = await api(
          "/api/sales/inputs/" + run.sales_input_snapshot_id + "/outlook",
        );
        return { ...run, rows: outlook.rows, coverage: coverageStatus };
      }),
    )
      .then((values) => {
        const first = values[0];
        if (
          values.some(
            (r) =>
              r.dataset_id !== first.dataset_id ||
              r.forecast_order_inputs_id !== first.forecast_order_inputs_id ||
              r.unit !== first.unit ||
              planningBasis(r) !== planningBasis(first),
          )
        )
          throw Error(
            uiText("Choose methods from the same forecast to compare."),
          );
        if (live) {
          setEntries(values);
          setSelected(values.map((r) => r.run_id));
        }
      })
      .catch((e) => live && setError(e))
      .finally(() => live && setLoading(false));
    return () => {
      live = false;
    };
  }, [group.id, group.runs.map((r) => r.run_id).join("|"), api]);
  const visible = entries.filter((r) => selected.includes(r.run_id)),
    rows = methodRows(visible, filters),
    basis = planningBasis(activeRun);
  const availability=comparisonAvailability(rows,visible.map(r=>r.run_id));
  function exportComparison() {
    const cell = (v) =>
      '"' +
      String(v ?? "")
        .replaceAll('"', '""')
        .replace(/^[=+@-]/, "'$&") +
      '"';
    const csv = [
      [
        uiText("Month"),
        ...visible.map(
          (r) => methodName(r.method_selection) + " (" + r.unit + ")",
        ),
      ],
      ...rows.map((row) => [
        planningMonth(row.period, basis),
        ...visible.map((r) => row[r.run_id]),
      ]),
    ]
      .map((row) => row.map(cell).join(","))
      .join("\r\n");
    const url = URL.createObjectURL(
      new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "forecast-methods.csv";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <Stack>
      <ErrorBox error={error} />
      {loading ? (
        <p role="status">{uiText("Loading…")}</p>
      ) : (
        !error && (
          <>
            <Actions>
              {entries.map((r) => (
                <label className="ui-check" key={r.run_id}>
                  <input
                    type="checkbox"
                    checked={selected.includes(r.run_id)}
                    onChange={(e) =>
                      setSelected((v) =>
                        e.target.checked
                          ? [...v, r.run_id]
                          : v.filter((id) => id !== r.run_id),
                      )
                    }
                  />
                  {methodName(r.method_selection)}
                </label>
              ))}
              <Help
                text={uiText(
                  "Compare the same saved sales, factors and orders. Methods are not added together.",
                )}
              />
              <Button disabled={!rows.length} onClick={exportComparison}>
                {uiText("Export comparison")}
              </Button>
            </Actions>
            {selectedOrders !== activeRun.sales_input_snapshot_id && (
              <p className="table-note">
                {uiText(
                  "Comparison uses the orders saved when this forecast was created.",
                )}
              </p>
            )}
            {!!rows.length && (
              <>
                {availability.hasMissing&&<Actions><p role="status">{uiText('Some estimates are missing. Check customer history and order coverage.')}</p>{onReviewCoverage&&<Button onClick={onReviewCoverage}>{uiText('Check coverage')}</Button>}</Actions>}
                {availability.hasEstimate&&<div className="chart-frame">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={rows} margin={chartTheme.margin}>
                      <XAxis
                        dataKey="period"
                        tick={chartTheme.ticks}
                        tickFormatter={(v) => planningMonth(v, basis)}
                      />
                      <YAxis tick={chartTheme.ticks} />
                      <Tooltip
                        labelFormatter={(v) => planningMonth(v, basis)}
                        formatter={(v,name)=>[new Intl.NumberFormat(i18n.language,{maximumFractionDigits:2}).format(v)+' '+unitLabel(activeRun.unit),name]}
                      />
                      <Legend />
                      {visible.map((r, i) => (
                        <Line
                          key={r.run_id}
                          dataKey={r.run_id}
                          name={methodName(r.method_selection)}
                          stroke={"var(--chart-method-" + ((i % 5) + 1) + ")"}
                          strokeDasharray={i < 5 ? undefined : "6 4"}
                          dot={rows.length===1}
                          connectNulls={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>}
                <Table
                  headers={[
                    uiText("Month"),
                    ...visible.map(
                      (r) =>
                        methodName(r.method_selection) + " (" + unitLabel(r.unit) + ")",
                    ),
                  ]}
                >
                  {rows.map((row) => (
                    <tr key={row.period}>
                      <td>{planningMonth(row.period, basis)}</td>
                      {visible.map((r) => (
                        <td key={r.run_id}>
                          {row[r.run_id] == null
                            ? uiText("Unknown")
                            : new Intl.NumberFormat(i18n.language, {
                                maximumFractionDigits: 2,
                              }).format(row[r.run_id])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </Table>
              </>
            )}
            {!rows.length && (
              <p>{uiText("Select methods or change the filters.")}</p>
            )}
          </>
        )
      )}
    </Stack>
  );
}

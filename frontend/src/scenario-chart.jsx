import {t as uiText} from './localization.mjs';
import React, { useState } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { scenarioRows, factorComparisonScores } from "./scenario-data.mjs";
import {OrderComparison} from './order-comparison.jsx';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {chartTheme} from './chart-theme.mjs';

export function ScenarioChart({ base, scenarios, ui, fmt, date, api, canEdit }) {
  const { Pick, Table, ErrorBox } = ui;
  const [selected, setSelected] = useState("");
  const [item,setItem]=useState('__all__');
  if (!scenarios.length) return null;
  const scenario =
    scenarios.find((row) => row.run_id === selected) || scenarios[0];
  let rows, error;
  try {
    rows = scenarioRows(base, scenario,item);
  } catch (e) {
    error = e.message;
  }
  const scores=factorComparisonScores(base,scenario);
  const periodDate=planningBasis(base)==='jalali'?(value=>planningMonth(value,'jalali')):date;
  return (
    <section className="scenario-comparison" id="scenario-period-comparison">
      <div className="section-heading">
        <h3>Forecast by period · {base.unit}</h3>
        <Pick
          label={uiText("Chart scenario")}
          value={scenario.run_id}
          options={scenarios.map((row) => [row.run_id, row.scenario_name])}
          onChange={setSelected}
        />
      </div>
      <ErrorBox error={error} />
      <div className="scenario-comparison-controls">
      <Pick label={uiText("Comparison customer and SKU")} value={item} onChange={setItem} options={[
        ['__all__',uiText("All customers and SKUs")],...Object.keys(base.series).filter(i=>i!=='__all__').map(i=>[i,i])
      ]}/>
      {scenario.scenario?.type==='factor_link'&&<OrderComparison key={scenario.run_id} base={base} scenario={scenario} api={api} ui={ui} fmt={fmt} canEdit={canEdit}/>}
      </div>
      {scores&&(scores.error?<p role="status">{scores.error}</p>:<p>Past error · all customers and SKUs: {fmt(scores.before,2)}% baseline → {fmt(scores.after,2)}% {scenario.scenario?.type==='factor_link'?'with factors':'without extra factors'}. {scores.difference>0?'The baseline had lower error.':scores.difference<0?'This scenario had lower error.':'Past error is unchanged.'} {scenario.factor_validation?.method_changed?'The method or model mix also changed. ':''}Future accuracy and original factor release dates remain unverified.</p>)}
      {scenario.metrics?.evidence_policy==='reviewed_what_if'&&base.method_selection!==scenario.method_selection&&<p className="table-note">Methods also differ: {base.best_model} → {scenario.best_model}. The change is not due to factors alone.</p>}
      {rows && (
        <>
          <div className="scenario-chart-key">
            <span>
              <i className="baseline-key" />{uiText("Baseline")}</span>
            <span>
              <i className="scenario-key" />{uiText("Scenario")}</span>
          </div>
          <div className="scenario-chart">
            <ResponsiveContainer>
              <ComposedChart
                data={rows}
                accessibilityLayer
                margin={chartTheme.margin}
              >
                <XAxis
                  dataKey="period"
                  tickFormatter={periodDate}
                  interval="preserveStartEnd"
                  minTickGap={48}
                  tick={chartTheme.ticks}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  domain={[0, "auto"]}
                  tickFormatter={(v) => fmt(v, 0)}
                  tick={chartTheme.ticks}
                  width={70}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  labelFormatter={periodDate}
                  formatter={(value, name) => [
                    `${Array.isArray(value) ? value.map((v) => fmt(v, 1)).join(" – ") : fmt(value, 1)} ${base.unit}`,
                    name,
                  ]}
                />
                <Area
                  dataKey="range"
                  name="Indicative range"
                  fill="var(--chart-range)"
                  fillOpacity={0.45}
                  stroke="none"
                  isAnimationActive={false}
                />
                <Line
                  dataKey="baseline"
                  name={uiText("Baseline")}
                  stroke="var(--chart-history)"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                  dot={false}
                  isAnimationActive={false}
                />
                <Line
                  dataKey="scenario"
                  name={uiText("Scenario")}
                  stroke="var(--chart-forecast)"
                  strokeWidth={2}
                  dot={rows.length < 4}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {scenario.metrics?.evidence_policy!=='reviewed_what_if'&&<p className="table-note">
            {rows.some((row) => row.range)
              ? "The shaded scenario range uses earlier model errors; its future coverage is not independently verified."
              : "A planning range is not available for this scenario."}{" "}
            Assumptions are not confidence limits.
          </p>}
          <details className="help-details">
            <summary>{uiText("Exact comparison values")}</summary>
            <Table
              headers={[
                uiText("Period"),
                `Baseline (${base.unit})`,
                `Scenario (${base.unit})`,
                `Change (${base.unit})`,
              ]}
            >
              {rows.map((row) => (
                <tr key={row.period}>
                  <td>{periodDate(row.period)}</td>
                  <td>{fmt(row.baseline, 2)}</td>
                  <td>
                    {row.scenario === null
                      ? uiText("Not available")
                      : fmt(row.scenario, 2)}
                  </td>
                  <td>
                    {row.difference === null
                      ? uiText("Not available")
                      : fmt(row.difference, 2)}
                  </td>
                </tr>
              ))}
            </Table>
          </details>
        </>
      )}
    </section>
  );
}

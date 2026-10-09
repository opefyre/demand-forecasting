import React from "react";

export function RangeCheck({ run, ui, fmt }) {
  const { Table, Help } = ui;
  const check = run.metrics?.range_check;
  if (!check || run.metrics?.evidence_policy==='reviewed_what_if') return null;
  const percentage = (value) =>
    value == null ? "Not available" : `${fmt(value)}%`;
  return (
    <details className="surface disclosure range-check">
      <summary>
        Did the range cover later demand?
        <span>
          {check.items.checked
            ? `${fmt(check.items.coverage_pct)}% inside`
            : "More history needed"}
        </span>
      </summary>
      <div className="detail-body">
        <p>
          The range aims to include 80% of outcomes. This checks later
          historical demand, not future certainty.
        </p>
        <Table headers={["What was checked", "Inside range", "Observations"]}>
          {[
            ["Individual items", check.items],
            ["All items combined", check.portfolio],
          ].map(([name, evidence]) => (
            <tr key={name}>
              <td>{name}</td>
              <td>{percentage(evidence.coverage_pct)}</td>
              <td>
                {evidence.inside} of {evidence.checked}
              </td>
            </tr>
          ))}
        </Table>
        <p className="muted">
          {check.fitting_separate_from_selection
            ? "Range widths were fitted on separate earlier periods."
            : "Not enough history for separate range fitting; widths reuse method-selection errors."}{" "}
          One later window is a limited check.{" "}
          <Help text="Widths may pool different forecast steps for the same item. Total ranges use errors from the same dates across all items. Choosing a method after viewing this check needs new actuals to confirm it. Scenario changes and planner adjustments are not tested here." />
        </p>
        {(check.items.unavailable > 0 ||
          check.missing_prediction_points > 0 ||
          check.skipped_incomplete_portfolio_periods > 0) && (
          <p className="inline-message">
            {check.items.unavailable} observations had no supported range;{" "}
            {check.missing_prediction_points} had no prediction.{" "}
            {check.skipped_incomplete_portfolio_periods} incomplete total
            periods were excluded.
          </p>
        )}
        <h3>
          By forecast step{" "}
          <Help text="Step 1 is the first period after the historical forecast was issued. Coverage counts individual item-period observations; they are not assumed to be independent." />
        </h3>
        <Table headers={["Step", "Inside range", "Checked", "Average width"]}>
          {check.by_horizon.map((row) => (
            <tr key={row.step}>
              <td>{row.step}</td>
              <td>{percentage(row.coverage_pct)}</td>
              <td>
                {row.checked} of {row.observations}
              </td>
              <td>
                {fmt(row.mean_width)} {run.unit}
              </td>
            </tr>
          ))}
        </Table>
        <p className="muted">
          Exact actuals, bounds and fitting values are included in the forecast
          export.
        </p>
      </div>
    </details>
  );
}

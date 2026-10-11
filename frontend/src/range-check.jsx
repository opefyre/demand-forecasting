import React from "react";
import {Disclosure,Stack,DefinitionList} from './ui-layout.jsx';
import {t as uiText,unitLabel} from './localization.mjs';

export function RangeCheck({ run, ui, fmt }) {
  const { Table, Help } = ui;
  const check = run.metrics?.range_check;
  if (!check || run.metrics?.evidence_policy==='reviewed_what_if') return null;
  const percentage = (value) =>
    value == null ? uiText("Not available") : `${fmt(value)}%`;
  return (
    <Disclosure title={uiText('Did the range cover later demand?')}>
      <Stack>
        <DefinitionList rows={[[uiText('Inside range'),check.items.checked?percentage(check.items.coverage_pct):uiText('More history needed')]]}/>
        <p>
          {uiText('The range aims to include 80% of outcomes. This checks later historical demand, not future certainty.')}
        </p>
        <Table headers={["What was checked", "Inside range", "Observations"].map(value=>uiText(value))}>
          {[
            ["Individual items", check.items],
            ["All items combined", check.portfolio],
          ].map(([name, evidence]) => (
            <tr key={name}>
              <td>{uiText(name)}</td>
              <td>{percentage(evidence.coverage_pct)}</td>
              <td>
                {fmt(evidence.inside)} {uiText('of')} {fmt(evidence.checked)}
              </td>
            </tr>
          ))}
        </Table>
        <p className="muted">
          {uiText(check.fitting_separate_from_selection
            ? "Range widths were fitted on separate earlier periods."
            : "Not enough history for separate range fitting; widths reuse method-selection errors.")}{" "}
          {uiText('One later window is a limited check.')} {" "}
          <Help text={uiText('Widths may pool different forecast steps for the same item. Total ranges use errors from the same dates across all items. Choosing a method after viewing this check needs new actuals to confirm it. Scenario changes and planner adjustments are not tested here.')} />
        </p>
        {(check.items.unavailable > 0 ||
          check.missing_prediction_points > 0 ||
          check.skipped_incomplete_portfolio_periods > 0) && (
          <p className="inline-message">
            {uiText('Range unavailable: {{ranges}} · Prediction unavailable: {{predictions}} · Incomplete total periods excluded: {{periods}}',{ranges:fmt(check.items.unavailable),predictions:fmt(check.missing_prediction_points),periods:fmt(check.skipped_incomplete_portfolio_periods)})}
          </p>
        )}
        <Disclosure title={uiText('By forecast step')}>
          <Help text={uiText('Step 1 is the first period after the historical forecast was issued. Coverage counts individual item-period observations; they are not assumed to be independent.')} />
        <Table headers={["Step", "Inside range", "Checked", "Average width"].map(value=>uiText(value))}>
          {check.by_horizon.map((row) => (
            <tr key={row.step}>
              <td>{fmt(row.step)}</td>
              <td>{percentage(row.coverage_pct)}</td>
              <td>
                {fmt(row.checked)} {uiText('of')} {fmt(row.observations)}
              </td>
              <td>
                {fmt(row.mean_width)} {unitLabel(run.unit)}
              </td>
            </tr>
          ))}
        </Table>
        </Disclosure>
        <p className="muted">
          {uiText('Exact actuals, bounds and fitting values are included in the forecast export.')}
        </p>
      </Stack>
    </Disclosure>
  );
}

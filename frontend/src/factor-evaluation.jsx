import {t as uiText} from './localization.mjs';
import React from 'react';

const value=n=>n==null?'Not available':new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(n);

export function FactorEvaluation({run,ui,customer='',sku=''}) {
  const report=run?.factor_evaluation;
  if(!report)return null;
  const {Table}=ui;
  const labels=Object.fromEntries((run.scenario?.alignment?.factors||[run.scenario?.alignment]).filter(Boolean).map(f=>[f.column,f.factor]));
  const name=column=>labels[column]||column.replaceAll('_',' ');
  const rows=report.rows.filter(r=>{
    const meta=run.metadata?.[r.item_id]||{};
    return (!customer||meta.customer===customer)&&(!sku||meta.sku===sku);
  });
  return <details className="surface disclosure factor-evaluation">
    <summary>{uiText("Which factors helped?")}</summary>
    <div className="detail-body">
      <p>{uiText("Compared with history-only forecasts. Final checks were not used to choose factors.")}</p>
      <Table headers={[uiText("Customer / product"),uiText("Factors used"),uiText("Earlier tests"),uiText("Final check")]}>
        {rows.map(row=>{
          const meta=run.metadata?.[row.item_id]||{},before=row.confirmation_baseline,after=row.confirmation_selected;
          return <tr key={row.item_id}>
            <td>{meta.customer||row.item_id}<small>{meta.sku||''}</small></td>
            <td>{row.selected_factors.length?row.selected_factors.map(name).join(' + '):uiText("History & seasonality only")}<small>{row.reason}</small></td>
            <td>{row.decision==='factors_selected'?value(row.selection_gain_pct)+'% less error':uiText("Kept history-only method")}</td>
            <td>{before&&after?<>{value(before.mae)} → {value(after.mae)} {run.unit}<small>{row.confirmation_improved?uiText("Lower error"):row.confirmation_improved===false?uiText("No improvement"):uiText("Not available")} · {row.confirmation_points}{' '}{uiText("observations")}</small></>:uiText("Not enough separate history")}</td>
          </tr>;
        })}
      </Table>
      {!rows.length&&<p>{uiText("No factor tests for this customer/product filter.")}</p>}
      <details className="help-details"><summary>{uiText("What does this mean?")}</summary>
        <p>{uiText("Customer/product filters apply to historical tests; the forecast-month filter does not.")}</p>
        <p>{uiText("Earlier tests must improve by at least")}{' '}{report.minimum_gain_pct}{uiText("% to use extra factors. This is a practical guardrail, not a statistical guarantee. Final-check error is average absolute quantity error—not a percentage.")}</p>
        <p>{report.note}</p><p>{report.search}</p>
        <p>{uiText("Future assumptions are still required. These tests do not measure uncertainty in future exchange rates or inflation.")}</p>
        <p>{report.selection_periods.length}{' '}{uiText("earlier test periods ·")}{' '}{report.confirmation_periods.length}{' '}{uiText("final-check periods. This is not live-source validation or proof of client accuracy.")}</p>
      </details>
    </div>
  </details>;
}

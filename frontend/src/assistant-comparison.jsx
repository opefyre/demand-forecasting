import {t as uiText} from './localization.mjs';
import React from 'react';
import {planningMonth} from './planning-calendar.mjs';

const quantity=value=>value==null?'Unknown':new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(value);

export function AssistantComparison({action,result,expired,busy,canEdit,onConfirm,onOpen,ui}) {
  const {Button,Table}=ui, preview=action.preview;
  return <div className="ai-proposal ai-comparison">
    <h3>{uiText("Save a separate scenario draft?")}</h3>
    <p>{action.name}{' '}{uiText("· All")}{' '}{preview.customer_count}{' '}{uiText("customers ·")}{' '}{preview.sku_count}{' '}{uiText("SKUs")}</p>
    <div className="order-comparison-table"><Table headers={[uiText("Month"),uiText("Open orders"),uiText("Remaining · before → after"),uiText("Total · before → after")]}>
      {preview.months.map(row=><tr key={row.period+row.unit}>
        <td>{planningMonth(row.period,action.month_basis)}<small>{row.unit}</small></td>
        <td>{quantity(row.booked)}{!!row.fulfilled&&<small>{uiText("Delivered")}{' '}{quantity(row.fulfilled)}</small>}</td>
        <td>{quantity(row.before_remaining)} → {quantity(row.after_remaining)}</td>
        <td>{quantity(row.before_total)} → {quantity(row.after_total)}</td>
      </tr>)}
    </Table></div>
    {!!preview.warnings.length&&<details><summary>{uiText("Checks to review")}</summary><ul>{preview.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></details>}
    <p className="table-note">{uiText("Orders stay unchanged. Totals include deliveries; exports exclude them. This saves all customers and SKUs, not just a filtered preview.")}</p>
    {result?.snapshot_id?<><p role="status">{uiText("Separate draft saved. The original is unchanged.")}</p><div className="demand-actions">
      <Button onClick={onOpen}>{uiText("Open forecast")}</Button>
      <a href={`/api/sales/inputs/${encodeURIComponent(result.snapshot_id)}/export?mode=combined_demand&kind=xlsx`}>{uiText("Full scenario · Excel")}</a>
      <a href={`/api/sales/inputs/${encodeURIComponent(result.snapshot_id)}/export?mode=remaining_forecast&kind=csv`}>{uiText("Remaining forecast · CSV")}</a>
    </div></>:expired?<p>{uiText("This proposal expired. Ask again to refresh it.")}</p>:<Button kind="primary" disabled={!canEdit||busy} onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Approve & save draft")}</Button>}
  </div>;
}

import {t as uiText} from './localization.mjs';
import React from 'react';

const labels={date_col:'Sales date',target_col:'Sales quantity',item_col:'Customer–SKU series',customer_col:'Customer',sku_col:'SKU',future_date_col:'Factor date',future_item_col:'Factor series'};
const quantity=v=>v==null?'Unknown':new Intl.NumberFormat('en',{maximumFractionDigits:3}).format(v);

export function InputMappingProposal({action,result,expired,busy,canEdit,onConfirm,ui,onUse}){
  const {Button,Table}=ui;
  return <div className="ai-proposal">
    <h3>{uiText("Review input mappings")}</h3><p>{action.reason}</p>
    <Table headers={[uiText("Field"),uiText("Before"),uiText("After")]}>{action.diff.map(d=><tr key={d.field}><td>{labels[d.field]||d.field}</td><td>{d.before||'Not mapped'}</td><td>{d.after}</td></tr>)}</Table>
    <p>{uiText("Source quantity total:")}{' '}{quantity(action.before_total)} → {quantity(action.after_total)} {action.unit}</p>
    <p>{uiText("History used after date grouping and gap treatment:")}{' '}{quantity(action.before_prepared_total)} → {quantity(action.after_prepared_total)} {action.unit}</p>
    {!!action.warnings?.length&&<details open><summary>{action.warnings.length}{' '}{uiText("checks to review")}</summary><ul>{action.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></details>}
    <p>{uiText("Original files, orders and forecasts stay unchanged.")}</p>
    {result?.dataset_id?<><p role="status">{uiText("Saved “")}{result.dataset_name}”.</p>{onUse?<Button disabled={busy} onClick={onUse}>{uiText("Use these inputs")}</Button>:<a href="/data">{uiText("Open Data")}</a>}</>:expired?<p>{uiText("This proposal expired. Ask again to refresh it.")}</p>:<Button disabled={!canEdit||busy} kind="primary" onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Approve & save new input version")}</Button>}
  </div>;
}

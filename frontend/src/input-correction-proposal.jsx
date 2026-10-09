import {t as uiText} from './localization.mjs';
import React,{useState} from 'react';
const quantity=v=>v==null?'Unknown':new Intl.NumberFormat('en',{maximumFractionDigits:3}).format(v);
export function InputCorrectionProposal({action,result,expired,busy,canEdit,onConfirm,ui,onUse}){
  const {Button,Table}=ui;
  const [reviewed,setReviewed]=useState(false);
  return <div className="ai-proposal">
    <h3>{uiText("Review formatting corrections")}</h3>
    <p>{action.reason}</p>
    <Table headers={[uiText("Data row"),uiText("Column"),uiText("Before"),uiText("After")]}>{action.changes.map(c=><tr key={c.row+':'+c.column}><td>{c.row}</td><td>{c.column}</td><td><code>{JSON.stringify(c.before)}</code></td><td><code>{JSON.stringify(c.after)}</code></td></tr>)}</Table>
    <p>{uiText("Sales used:")}{' '}{quantity(action.before_prepared_total)} → {quantity(action.after_prepared_total)} {action.unit}</p>
    {!!action.warnings?.length&&<details><summary>{uiText("Checks to review")}</summary><ul>{action.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></details>}
    <p>{uiText("Original files, orders and forecasts stay unchanged.")}</p>
    {result?.dataset_id?<><p role="status">{uiText("Saved “")}{result.dataset_name}”.</p>{onUse&&<Button disabled={busy} onClick={onUse}>{uiText("Use these inputs")}</Button>}</>:expired?<p>{uiText("This proposal expired. Ask again.")}</p>:<><label className="check-row"><input type="checkbox" checked={reviewed} disabled={!canEdit||busy} onChange={e=>setReviewed(e.target.checked)}/>{uiText("I reviewed the cells and their customer/product matches.")}</label><Button kind="primary" disabled={!canEdit||busy||!reviewed} onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Approve & save new version")}</Button></>}
    <small>{action.row_reference}</small>
  </div>;
}

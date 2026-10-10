import {t as uiText,i18n,unitLabel} from './localization.mjs';
import React,{useState} from 'react';
import {Panel,Disclosure,Actions} from './ui-layout.jsx';
const quantity=v=>v==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:3}).format(v);
export function InputCorrectionProposal({action,result,expired,busy,canEdit,onConfirm,ui,onUse}){
  const {Button,Table}=ui;
  const [reviewed,setReviewed]=useState(false);
  return <Panel title={uiText("Review formatting corrections")}>
    <p>{action.reason}</p>
    <Table headers={[uiText("Data row"),uiText("Column"),uiText("Before"),uiText("After")]}>{action.changes.map(c=><tr key={c.row+':'+c.column}><td>{c.row}</td><td>{c.column}</td><td><code>{JSON.stringify(c.before)}</code></td><td><code>{JSON.stringify(c.after)}</code></td></tr>)}</Table>
    <p>{uiText("Sales used:")}{' '}<bdi>{quantity(action.before_prepared_total)} → {quantity(action.after_prepared_total)}</bdi> {unitLabel(action.unit)}</p>
    {!!action.warnings?.length&&<Disclosure title={uiText("Checks to review")}><ul>{action.warnings.map((w,i)=><li key={i}>{uiText(w)}</li>)}</ul></Disclosure>}
    <p>{uiText("Original files, orders and forecasts stay unchanged.")}</p>
    {result?.dataset_id?<><p role="status">{uiText("Saved “")}{result.dataset_name}”.</p>{onUse&&<Actions><Button disabled={busy} onClick={onUse}>{uiText("Use these inputs")}</Button></Actions>}</>:expired?<p role="status">{uiText("This proposal expired. Ask again.")}</p>:<><label className="ui-check"><input type="checkbox" checked={reviewed} disabled={!canEdit||busy} onChange={e=>setReviewed(e.target.checked)}/>{uiText("I reviewed the cells and their customer/product matches.")}</label><Actions><Button kind="primary" disabled={!canEdit||busy||!reviewed} onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Approve & save new version")}</Button></Actions></>}
    <small>{action.row_reference}</small>
  </Panel>;
}

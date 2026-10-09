import {t as uiText} from './localization.mjs';
import React,{useEffect,useRef,useState} from 'react';
import {planningMonth} from './planning-calendar.mjs';

export function OrderReuse({runId,api,ui,onSaved}) {
  const {Button,Modal,Pick,Table,ErrorBox}=ui;
  const [choices,setChoices]=useState([]),[open,setOpen]=useState(false),[source,setSource]=useState('');
  const [report,setReport]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[approved,setApproved]=useState(false);
  const attempt=useRef(null),version=useRef(0);
  useEffect(()=>{let live=true;version.current++;setChoices([]);setReport(null);setOpen(false);setSource('');setError('');
    api(`/api/sales/runs/${runId}/order-reuse/choices`).then(r=>live&&setChoices(r.sources)).catch(e=>live&&setError(e.message));
    return()=>{live=false;version.current++;};},[runId]);
  async function preview(id){const current=++version.current;setSource(id);setReport(null);setApproved(false);setError('');attempt.current=null;
    if(!id){setBusy(false);return;}setBusy(true);
    try{const value=await api(`/api/sales/runs/${runId}/order-reuse/preview`,{snapshot_id:id});if(current===version.current)setReport(value);}
    catch(e){if(current===version.current)setError(e.message);}finally{if(current===version.current)setBusy(false);}}
  async function save(){setBusy(true);setError('');const current=version.current;
    try{attempt.current ||= crypto.randomUUID();const saved=await api(`/api/sales/runs/${runId}/order-reuse`,{
      snapshot_id:source,review_token:report.review_token,request_id:attempt.current,reviewed:true,coverage_confirmed:true});
      if(current===version.current){await onSaved(saved);setOpen(false);}}
    catch(e){if(current===version.current)setError(e.message);}finally{if(current===version.current)setBusy(false);}}
  const number=v=>v==null?'Unknown':new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(v);
  if(!choices.length&&!error)return null;
  return <><Button onClick={()=>{setOpen(true);if(choices.length===1)preview(choices[0].id);}}>{uiText("Use saved orders")}</Button>
    <Modal title={uiText("Review saved orders")} description={uiText("Reuse the order book, not the old forecast.")} open={open} onClose={()=>!busy&&setOpen(false)} wide>
      <ErrorBox error={error}/>
      {choices.length>1&&<Pick label={uiText("Order source")} value={source} onChange={preview} options={[["",uiText("Choose a forecast")],...choices.map(s=>[s.id,`${s.name} · ${s.as_of}`])]}/>}
      {busy&&!report&&<p role="status">{uiText("Checking orders…")}</p>}
      {report&&<>
        <p>{report.customer_count}{' '}{uiText("customers ·")}{' '}{report.order_count}{' '}{uiText("order lines ·")}{' '}{report.unit}</p>
        <p className="table-note">{uiText("Orders as of")}{' '}{report.as_of}{uiText(". Review expires")}{' '}{report.valid_until}{uiText("; reuse does not refresh the source.")}</p>
        {report.warnings.map((w,i)=><p role="status" key={i}>{w}</p>)}
        <div className="order-comparison-table"><Table headers={[uiText("Month"),uiText("Coverage review"),uiText("Open orders"),uiText("Still expected"),uiText("Total demand")]}>
          {report.months.map(row=><tr key={row.period}><td>{planningMonth(row.period,report.month_basis)}</td><td>{row.added?uiText("Added month"):uiText("Existing month")}</td><td>{number(row.booked)}</td><td>{number(row.remaining)}</td><td>{number(row.total)}</td></tr>)}
        </Table></div>
        {!!report.outside_open_orders.length&&<details open><summary>{report.outside_open_orders.length}{' '}{uiText("open order lines outside this forecast")}</summary><ul>{report.outside_open_orders.map(r=><li key={r.reference}>{r.reference} · {planningMonth(r.period,report.month_basis)} · {number(r.quantity)} {report.unit}</li>)}</ul><p>{uiText("These lines remain saved, but are not included in this forecast's totals or exports.")}</p></details>}
        <p className="table-note">{uiText("Total includes deliveries. Exports exclude deliveries. Customers without orders retain their calculated demand.")}</p>
        <label className="order-comparison-approval"><input type="checkbox" checked={approved} disabled={busy||!report.can_save} onChange={e=>setApproved(e.target.checked)}/>{uiText("I confirm this order book includes all known orders for every displayed month, including added months, and I reviewed any excluded orders. Save all customers and SKUs as a separate draft.")}</label>
      </>}
      <div className="dialog-actions"><Button disabled={busy} onClick={()=>setOpen(false)}>{uiText("Cancel")}</Button><Button kind="primary" disabled={busy||!approved||!report?.can_save} onClick={save}>{busy?uiText("Saving…"):uiText("Save demand draft")}</Button></div>
    </Modal>
  </>;
}

export function AssistantSavedOrders({action,result,expired,busy,canEdit,onConfirm,onOpen,ui}){
  const {Button,Table}=ui,[confirmed,setConfirmed]=useState(false),report=action.preview;
  const number=value=>value==null?'Unknown':new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(value);
  return <div className="ai-proposal">
    <h3>{uiText("Use these saved orders?")}</h3>
    <p>{report.source_name}{' '}{uiText("· All")}{' '}{report.customer_count}{' '}{uiText("customers ·")}{' '}{report.order_count}{' '}{uiText("order lines ·")}{' '}{report.unit}</p>
    <p className="table-note">{uiText("Orders as of")}{' '}{report.as_of}{uiText(". Review expires")}{' '}{report.valid_until}{uiText(". Reusing orders does not refresh them.")}</p>
    <div className="order-comparison-table"><Table headers={[uiText("Month"),uiText("Open orders"),uiText("Still expected"),uiText("Total demand")]}>
      {report.months.map(row=><tr key={row.period}><td>{planningMonth(row.period,report.month_basis)}{row.added&&<small>{uiText("Added month")}</small>}</td><td>{number(row.booked)}</td><td>{number(row.remaining)}</td><td>{number(row.total)}</td></tr>)}
    </Table></div>
    {!!report.warnings.length&&<details open><summary>{uiText("Checks to review")}</summary><ul>{report.warnings.map((w,i)=><li key={i}>{w}</li>)}</ul></details>}
    {!!report.outside_open_orders.length&&<details open><summary>{report.outside_open_orders.length}{' '}{uiText("open orders outside this forecast")}</summary><ul>{report.outside_open_orders.map(row=><li key={row.reference}>{row.reference} · {planningMonth(row.period,report.month_basis)} · {number(row.quantity)} {report.unit}</li>)}</ul></details>}
    <p className="table-note">{uiText("Orders use up the forecast, not add to it twice. Customers without orders keep their calculated demand. Exports exclude delivered quantities.")}</p>
    {result?.snapshot_id?<><p role="status">{uiText("Separate demand draft saved. Original orders unchanged.")}</p><Button onClick={onOpen}>{uiText("Open demand forecast")}</Button></>:expired?<p>{uiText("This proposal expired. Ask again to refresh it.")}</p>:<>
      <label className="order-comparison-approval"><input type="checkbox" checked={confirmed} disabled={busy||!canEdit||!report.can_save} onChange={e=>setConfirmed(e.target.checked)}/>{uiText("I reviewed all displayed months and any excluded orders. This order book includes all known orders.")}</label>
      <Button kind="primary" disabled={!confirmed||busy||!canEdit||!report.can_save} onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Confirm & save demand draft")}</Button>
    </>}
  </div>;
}

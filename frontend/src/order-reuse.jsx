import {t as uiText,unitLabel,i18n} from './localization.mjs';
import React,{useEffect,useRef,useState} from 'react';
import {planningMonth} from './planning-calendar.mjs';
import {Stack,Actions,DefinitionList,Disclosure,Panel} from './ui-layout.jsx';

const number=value=>value==null?uiText('Not present'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:2}).format(value);
export function orderSourceOptions(choices) {
  const label=s=>`${s.name} · ${s.as_of}`;
  return choices.map(s=>[s.id,label(s)+(choices.filter(other=>label(other)===label(s)).length>1?' · '+uiText('Review {{id}}',{id:s.id.slice(-6)}):'')]);
}
export function OrderReuseReport({report,ui}) {
  return <Stack>
    <DefinitionList rows={[[uiText('Customers'),number(report.customer_count)],[uiText('Order lines'),number(report.order_count)],
      [uiText('Unit'),unitLabel(report.unit)],[uiText('Orders as of'),report.as_of],[uiText('Valid until'),report.valid_until]]}/>
    {report.warnings.map((w,i)=><p role="status" key={i}>{uiText(w)}</p>)}
    <ui.Table headers={[uiText('Month'),uiText('Coverage review'),uiText('Open orders'),uiText('Still expected'),uiText('Total demand')]}>
      {report.months.map(row=><tr key={row.period}><td>{planningMonth(row.period,report.month_basis)}</td><td>{uiText(row.added?'Added month':'Existing month')}</td><td>{number(row.booked)}</td><td>{number(row.remaining)}</td><td>{number(row.total)}</td></tr>)}
    </ui.Table>
    {!!report.outside_open_orders.length&&<Disclosure open title={uiText('open order lines outside this forecast')}>
      <ul>{report.outside_open_orders.map(r=><li key={r.reference}>{r.reference} · {planningMonth(r.period,report.month_basis)} · {number(r.quantity)} {unitLabel(report.unit)}</li>)}</ul>
      <p>{uiText("These lines remain saved, but are not included in this forecast's totals or exports.")}</p>
    </Disclosure>}
    <p className="table-note">{uiText('Total includes deliveries. Exports exclude deliveries. Customers without orders retain their calculated demand.')}</p>
  </Stack>;
}

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
  if(!choices.length&&!error)return null;
  return <><Button onClick={()=>{setOpen(true);if(choices.length===1)preview(choices[0].id);}}>{uiText("Use saved orders")}</Button>
    <Modal title={uiText("Review saved orders")} open={open} onClose={()=>!busy&&setOpen(false)} wide fixed><Stack>
      <ErrorBox error={error}/>
      {choices.length>1&&<Pick label={uiText("Order source")} disabled={busy} value={source} onChange={preview} options={[["",uiText("Choose a forecast")],...orderSourceOptions(choices)]}/>}
      {busy&&!report&&<p role="status">{uiText("Checking orders…")}</p>}
      {report&&<>
        <OrderReuseReport report={report} ui={ui}/>
        <label className="ui-check"><input type="checkbox" checked={approved} disabled={busy||!report.can_save} onChange={e=>setApproved(e.target.checked)}/>{uiText("I confirm this order book includes all known orders for every displayed month, including added months, and I reviewed any excluded orders. Save all customers and SKUs as a separate draft.")}</label>
      </>}
      <Actions><Button disabled={busy} onClick={()=>setOpen(false)}>{uiText("Cancel")}</Button><Button kind="primary" disabled={busy||!approved||!report?.can_save} onClick={save}>{busy?uiText(report?"Saving…":"Checking orders…"):uiText("Save demand draft")}</Button></Actions>
    </Stack></Modal>
  </>;
}

export function AssistantSavedOrders({action,result,expired,busy,canEdit,onConfirm,onOpen,ui}){
  const {Button}=ui,[confirmed,setConfirmed]=useState(false),report=action.preview;
  return <Panel title={uiText("Use these saved orders?")}>
    <strong>{report.source_name}</strong>
    <OrderReuseReport report={report} ui={ui}/>
    {result?.snapshot_id?<><p role="status">{uiText("Separate demand draft saved. Original orders unchanged.")}</p><Actions><Button disabled={busy} onClick={onOpen}>{uiText("Open demand forecast")}</Button></Actions></>:expired?<p role="status">{uiText("This proposal expired. Ask again to refresh it.")}</p>:<>
      <label className="ui-check"><input type="checkbox" checked={confirmed} disabled={busy||!canEdit||!report.can_save} onChange={e=>setConfirmed(e.target.checked)}/>{uiText("I reviewed all displayed months and any excluded orders. This order book includes all known orders.")}</label>
      <Actions><Button kind="primary" disabled={!confirmed||busy||!canEdit||!report.can_save} onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Confirm & save demand draft")}</Button></Actions>
    </>}
  </Panel>;
}

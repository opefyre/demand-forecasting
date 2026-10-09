import {t as uiText} from './localization.mjs';
import React, {useState} from 'react';

export function OrderFolder({api,ui,runId,onReview}) {
  const {Button,Modal,Field,Pick,ErrorBox}=ui;
  const [open,setOpen]=useState(false),[data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [form,setForm]=useState({path:'',filename:'',minutes:0,confirmed_local_access:false});
  const [reuseSource,setReuseSource]=useState('');
  const endpoint=`/api/integrations/order-folders/${runId}`;
  const ExportForm=data?.choices?.length?'details':'div';
  async function act(fn){setBusy(true);setError('');try{await fn();}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function load(){const value=await api(endpoint);setData(value);return value;}
  return <>
    <Button onClick={()=>{setOpen(true);act(load);}}>{uiText("Connect order export")}</Button>
    {open&&<Modal open={open} title={uiText("Order export")} dismissible={!busy} onClose={()=>setOpen(false)}>
      <div className="order-folder-form">
      <ErrorBox error={error}/>
      {data?.connection ? <>
        <p>{data.connection.files.orders} · {data.connection.enabled?`Checks every ${data.connection.minutes} minutes`:uiText("Automatic checks off")}</p>
        <p>{data.connection.message||'Not checked yet.'}</p>
        <p>{uiText("Full order book only. New files wait for your review; dates and approval are not renewed automatically.")}</p>
        <div className="row-actions">
          <Button kind="primary" disabled={busy} onClick={()=>act(async()=>{const draft=await api(endpoint+'/review',{});onReview(draft);setOpen(false);})}>{uiText("Refresh & review")}</Button>
          {!!data.connection.minutes&&<Button disabled={busy} onClick={()=>act(async()=>{await api(endpoint+'/enabled',{enabled:!data.connection.enabled});await load();})}>{data.connection.enabled?uiText("Pause"):uiText("Resume")}</Button>}
          <Button disabled={busy} onClick={()=>{const c=data.connection;setForm({path:c.path,filename:c.files.orders,minutes:c.minutes,confirmed_local_access:false});setData({...data,connection:null});}}>{uiText("Change connection")}</Button>
        </div>
      </> : data&&<>
        {!!data.choices?.length&&<div className="order-folder-form">
          <Field title={uiText("Use an existing connection")}><Pick label={uiText("Existing order connection")} value={reuseSource} onChange={setReuseSource} options={[["",uiText("Choose connection")],...data.choices.map(c=>[c.id,`${c.name} · ${c.filename}`])]}/></Field>
          <Button disabled={busy||!reuseSource} onClick={()=>act(async()=>{await api(endpoint+'/reuse',{source_id:reuseSource});await load();})}>{uiText("Use connection")}</Button>
        </div>}
        <ExportForm>{!!data.choices?.length&&<summary>{uiText("Connect a different export file")}</summary>}<div className="order-folder-form">
        <p>{uiText("First save an order-file mapping. The export must contain the full order book with the same headings and delivery-line references.")}</p>
        <Field title={uiText("Export folder")}><input aria-label={uiText("Export folder")} value={form.path} onChange={e=>setForm({...form,path:e.target.value})}/></Field>
        <small>{uiText("Allowed locations:")}{' '}{data.approved_roots.join(', ')}</small>
        <Field title={uiText("Filename")}><input aria-label={uiText("Filename")} value={form.filename} onChange={e=>setForm({...form,filename:e.target.value})}/></Field>
        <Field title={uiText("Check for updates")}><Pick label={uiText("Check for updates")} value={String(form.minutes)} onChange={v=>setForm({...form,minutes:Number(v)})} options={[["0",uiText("Manually")],["15",uiText("Every 15 minutes")],["60",uiText("Hourly")],["360",uiText("Every 6 hours")],["1440",uiText("Daily")]]}/></Field>
        <label className="checkbox-row"><input type="checkbox" checked={form.confirmed_local_access} onChange={e=>setForm({...form,confirmed_local_access:e.target.checked})}/>{uiText("I permit this app to read this export file.")}</label>
        <Button kind="primary" disabled={busy||!form.confirmed_local_access||!form.path||!form.filename} onClick={()=>act(async()=>{await api(endpoint,form);await load();})}>{uiText("Connect")}</Button>
        </div></ExportForm>
      </>}
      </div>
    </Modal>}
  </>;
}

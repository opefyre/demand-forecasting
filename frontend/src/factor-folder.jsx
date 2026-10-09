import {t as uiText} from './localization.mjs';
import React,{useState} from 'react';
import {Plugs} from '@phosphor-icons/react';

export function FactorFolder({snapshot,api,ui,onReview,onAccepted}) {
  const {Button,Modal,Field,Pick,ErrorBox}=ui;
  const [open,setOpen]=useState(false),[data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [form,setForm]=useState({path:'',filename:'',minutes:0,confirmed_local_access:false});
  const endpoint='/api/integrations/factor-folders/'+snapshot.id;
  async function act(fn){setBusy(true);setError('');try{await fn();}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function load(){setData(await api(endpoint));}
  return <>
    <button className="icon-button" title="Connect factor export" aria-label={'Connect export for '+snapshot.name} onClick={()=>{setOpen(true);act(load);}}><Plugs size={20}/></button>
    <Modal open={open} title="Factor export" description={snapshot.name} dismissible={!busy} onClose={()=>setOpen(false)}>
      <ErrorBox error={error}/>
      {data?.connection?<>
        <p>{data.connection.files.factor_observations} · {data.connection.enabled?`Checks every ${data.connection.minutes} minutes`:uiText("Automatic checks off")}</p>
        <p role="status">{data.connection.message||'Not checked yet.'}</p>
        <small>Use the complete factor history with the same columns, dates and units. Changes wait for review.</small>
        <div className="dialog-actions">
          <Button disabled={busy} onClick={()=>{const c=data.connection;setForm({path:c.path,filename:c.files.factor_observations,minutes:c.minutes,confirmed_local_access:false});setData({...data,connection:null});}}>{uiText("Change connection")}</Button>
          {!!data.connection.minutes&&<Button disabled={busy} onClick={()=>act(async()=>{await api(endpoint+'/enabled',{enabled:!data.connection.enabled});await load();})}>{data.connection.enabled?uiText("Pause"):uiText("Resume")}</Button>}
          <Button kind="primary" disabled={busy} onClick={()=>act(async()=>{const result=await api(endpoint+'/review',{});if(result.saved)await onAccepted(result.saved);else await onReview({...result,endpoint});setOpen(false);})}>{uiText("Refresh & review")}</Button>
        </div>
      </>:data&&<fieldset className="order-folder-form" disabled={busy}>
        <Field title={uiText("Export folder")}><input aria-label="Factor export folder" value={form.path} onChange={e=>setForm({...form,path:e.target.value})}/></Field>
        <small>{uiText("Allowed locations:")}{' '}{data.approved_roots.join(', ')}</small>
        <Field title={uiText("Filename")}><input aria-label="Factor export filename" value={form.filename} onChange={e=>setForm({...form,filename:e.target.value})}/></Field>
        <Field title={uiText("Check for updates")}><Pick label="Factor refresh interval" value={String(form.minutes)} onChange={v=>setForm({...form,minutes:Number(v)})} options={[["0",uiText("Manually")],["15",uiText("Every 15 minutes")],["60",uiText("Hourly")],["360",uiText("Every 6 hours")],["1440",uiText("Daily")]]}/></Field>
        <label className="check-line"><input type="checkbox" checked={form.confirmed_local_access} onChange={e=>setForm({...form,confirmed_local_access:e.target.checked})}/>{uiText("I permit this app to read this export file.")}</label>
        <div className="dialog-actions"><Button disabled={busy} onClick={()=>setOpen(false)}>{uiText("Cancel")}</Button><Button kind="primary" disabled={busy||!form.confirmed_local_access||!form.path||!form.filename} onClick={()=>act(async()=>{await api(endpoint,form);await load();})}>{uiText("Connect")}</Button></div>
      </fieldset>}
    </Modal>
  </>;
}

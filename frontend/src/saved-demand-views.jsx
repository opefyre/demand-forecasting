import {t as uiText} from './localization.mjs';
import React,{useEffect,useState} from 'react';
import {demandViewLabel} from './demand-view.mjs';
import {BookmarkSimple} from '@phosphor-icons/react';

export function SavedDemandViews({api,ui,runId,snapshotId,settings,onApply,canEdit}){
  const {Button,Modal,Field,ErrorBox}=ui;
  const [open,setOpen]=useState(false),[views,setViews]=useState([]),[name,setName]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{setViews([]);setOpen(false);setName('');setError('');},[runId]);
  async function show(){
    setOpen(true);setBusy(true);setError('');
    try{setViews((await api('/api/sales/views?run_id='+encodeURIComponent(runId))).views);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function save(e){
    e.preventDefault();setBusy(true);setError('');
    try{const result=await api('/api/sales/views',{name,run_id:runId,snapshot_id:snapshotId,settings});setViews(v=>[result,...v]);setName('');}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <><Button onClick={show} title={uiText("Save or reopen filters and layout for this forecast")}><BookmarkSimple/>{uiText("Views")}</Button><Modal title={uiText("Saved views")} description={uiText("Your filters, layout and order version for this forecast.")} open={open} onClose={()=>setOpen(false)}><ErrorBox error={error}/>{busy&&<p role="status">{uiText("Loading…")}</p>}<div className="saved-view-list">{views.map(v=><button key={v.id} disabled={busy} onClick={()=>{try{onApply(v);setOpen(false);}catch(e){setError(e.message);}}}><strong>{v.name}</strong><span>{v.settings.customer||uiText('All customers')} · {uiText(demandViewLabel(v.settings.display))}</span></button>)}{!busy&&!views.length&&<p>{uiText("No saved views yet.")}</p>}</div>{canEdit&&<form className="save-view-form" onSubmit={save}><Field title={uiText("Save current view")}><input aria-label={uiText("View name")} required maxLength={80} placeholder={uiText("e.g. Export customers · next month")} value={name} onChange={e=>setName(e.target.value)}/></Field><Button type="submit" kind="primary" disabled={busy||!name.trim()}>{uiText("Save view")}</Button></form>}</Modal></>;
}

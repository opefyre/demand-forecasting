import {t as uiText} from './localization.mjs';
import React, {useEffect,useRef,useState} from 'react';
import {applyMappingSuggestion,mappingLabels} from './import-mapping.mjs';
import {recipient} from './ai-sharing.mjs';

export function ImportMappingAssistant({sources,settings,classification,onApply,api,ui}) {
  const {Button,Modal,Table,ErrorBox} = ui;
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[result,setResult]=useState(null);
  const [provider,setProvider]=useState(null);
  const mounted=useRef(true),generation=useRef(0);
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;generation.current++;};},[]);
  const close=()=>{generation.current++;setOpen(false);setBusy(false);setError('');setResult(null);setProvider(null);};
  async function prepare() {
    const request=++generation.current;setOpen(true);setBusy(true);setError('');setProvider(null);
    try {
      const status=await api('/api/ai/status');
      if(mounted.current&&generation.current===request){setProvider(status);if(!status.ready)setError(status.message);}
    } catch(e){if(mounted.current&&generation.current===request)setError(e.message);}
    finally{if(mounted.current&&generation.current===request)setBusy(false);}
  }
  async function suggest() {
    const request=++generation.current;
    setBusy(true);setError('');
    try {
      const data=await api('/api/ai/import-mapping',{
        sources:Object.fromEntries(Object.entries(sources).filter(([role])=>['history','future'].includes(role)).map(([role,s])=>[role,s.id])),
        settings,classification,consent:true,provider_id:provider.consent_id,
      });
      if(mounted.current&&generation.current===request)setResult(data);
    } catch(e) {if(mounted.current&&generation.current===request)setError(e.message);}
    finally {if(mounted.current&&generation.current===request)setBusy(false);}
  }
  function apply() {
    try {onApply(applyMappingSuggestion(settings,sources,result.diff));close();}
    catch(e){setError(e.message);}
  }
  const quantity=v=>v==null?'Not available':new Intl.NumberFormat('en',{maximumFractionDigits:3}).format(v);
  return <>
    <Button onClick={prepare} title={uiText("Ask AI to suggest column matches; review before applying")}>{uiText("Suggest mappings")}</Button>
    <Modal open={open} onClose={close} title={result?uiText("Review suggested mappings"):uiText("Suggest column mappings")} description={result?uiText("Only approved column selections change. Your files stay unchanged."):`Share column names and up to three sample rows per file with ${recipient(provider)}. Samples may contain customer information. Your files stay unchanged.`}>
      <ErrorBox error={error}/>
      {result&&<>
        <p>{result.reason}</p>
        {result.diff.length>0?<>
          <Table headers={[uiText("Field"),uiText("Current"),uiText("Suggested")]}>{result.diff.map(row=><tr key={row.field}><td>{mappingLabels[row.field]}</td><td>{row.before||'Not mapped'}</td><td>{row.after}</td></tr>)}</Table>
          <p>{uiText("Source quantity:")}{' '}{quantity(result.before_total)} → {quantity(result.after_total)} {result.unit}</p>
        </>:<p>{uiText("No mapping changes suggested.")}</p>}
        {!!result.questions?.length&&<ul>{result.questions.map((q,i)=><li key={i}>{q}</li>)}</ul>}
        {!!result.errors?.length&&<div role="status"><h3>{uiText("Resolve before saving")}</h3><ul>{result.errors.map((q,i)=><li key={i}>{q}</li>)}</ul></div>}
        {!!result.warnings?.length&&<details><summary>{result.warnings.length}{' '}{uiText("checks to review")}</summary><ul>{result.warnings.map((q,i)=><li key={i}>{q}</li>)}</ul></details>}
      </>}
      <div className="dialog-actions">
        <Button onClick={close}>{result?uiText("Keep current mappings"):uiText("Continue manually")}</Button>
        {result?<Button kind="primary" disabled={!result.diff.length} onClick={apply}>{uiText("Use suggestions")}</Button>:<Button kind="primary" disabled={busy||!provider?.ready} onClick={suggest}>{busy?uiText("Preparing…"):uiText("Share sample & suggest")}</Button>}
      </div>
    </Modal>
  </>;
}

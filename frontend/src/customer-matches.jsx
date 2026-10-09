import {t as uiText} from './localization.mjs';
import React,{useEffect,useState} from 'react';
import {directoryMatches} from './customer-matches.mjs';

export function CustomerMatches({api,ui,matches,onChange}) {
  const {Table,ErrorBox}=ui;
  const [items,setItems]=useState([]),[error,setError]=useState('');
  useEffect(()=>{let live=true;api('/api/customers').then(r=>live&&setItems(r.customers)).catch(e=>live&&setError(e.message));return()=>{live=false;};},[]);
  const selected=Object.keys(matches).length>0;
  return <details className="optional-section"><summary>{uiText("Customer name matching")}<span>{uiText("Optional")}</span></summary>
    <ErrorBox error={error}/>
    <label className="check-row"><input type="checkbox" checked={selected} disabled={!selected&&!items.some(c=>c.aliases?.length||c.external_id)} onChange={e=>{try{onChange(e.target.checked?directoryMatches(items):{});}catch(err){setError(err.message);}}}/>{uiText("Use reviewed names and IDs from Customers")}</label>
    {selected?<Table headers={[uiText("Name / ID in file"),uiText("Customer")]}>
      {Object.entries(matches).map(([from,to])=><tr key={from}><td>{from}</td><td>{to}</td></tr>)}
    </Table>:<p className="muted">{uiText("Names match exactly. Add alternative names or ERP IDs in Customers to review them here; no fuzzy merging.")}</p>}
  </details>;
}

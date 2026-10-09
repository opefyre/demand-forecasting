import {t as uiText,unitLabel} from './localization.mjs';
import React, {useEffect,useState} from 'react';
import {Plus,UploadSimple,Trash} from '@phosphor-icons/react';
import {Collection,SearchControl,Page,PanelHeader,Grid,Actions,Disclosure} from './ui-layout.jsx';
import {FactorProfileEditor} from './factor-profile-editor.jsx';

export function Customers({api,ui,canEdit,navigate,embedded=false}) {
  const {Button,Field,Table,ErrorBox,Modal,Help}=ui;
  const [customers,setCustomers]=useState([]),[search,setSearch]=useState(''),[editing,setEditing]=useState(null);
  const [error,setError]=useState(''),[busy,setBusy]=useState(false),[loading,setLoading]=useState(true),[importing,setImporting]=useState(false),[preview,setPreview]=useState(null);
  const [showArchived,setShowArchived]=useState(false);
  const [profileCustomer,setProfileCustomer]=useState(null);
  const refresh=()=>api('/api/customers').then(r=>setCustomers(r.customers));
  useEffect(()=>{refresh().catch(e=>setError(e.message)).finally(()=>setLoading(false));},[]);
  const filtered=customers.filter(c=>(showArchived||c.active)&&[c.customer,...c.products.map(p=>p.sku)].join(' ').toLowerCase().includes(search.toLowerCase()));
  async function save(e) {
    e.preventDefault();setBusy(true);setError('');
    try {
      const {id,customer,products,active}=editing;
      const identity={external_id:editing.external_id||'',aliases:(editing.aliases||[]).filter(v=>v.trim())};
      await api(id?'/api/customers/'+id:'/api/customers',id?{customer,products,active,...identity}:{customers:[{customer,products,active,...identity}]},id?'PUT':'POST');
      await refresh();setEditing(null);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function upload(file) {
    if(!file)return;setBusy(true);setError('');setPreview(null);
    try {const form=new FormData();form.append('file',file);setPreview(await api('/api/customers/preview',form));}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  async function confirmImport() {
    setBusy(true);setError('');
    try {await api('/api/customers',preview);await refresh();setImporting(false);setPreview(null);}
    catch(e){setError(e.message);}finally{setBusy(false);}
  }
  function updateProduct(index,key,value){setEditing(c=>({...c,products:c.products.map((p,i)=>i===index?{...p,[key]:value}:p)}));}
  const Wrapper=embedded?React.Fragment:Page;
  return <Wrapper {...(!embedded?{title:uiText('Customers')}:{})}>
    <Collection label={uiText('Customers')} controls={<><SearchControl label={uiText('Search customers or products')} value={search} onChange={setSearch}/><label className="ui-check"><input type="checkbox" checked={showArchived} onChange={e=>setShowArchived(e.target.checked)}/>{uiText('Show inactive')}</label></>} actions={canEdit&&<><Button onClick={()=>{setError('');setPreview(null);setImporting(true);}}><UploadSimple/>{uiText('Import')}</Button><Button kind="primary" onClick={()=>{setError('');setEditing({customer:'',products:[],active:true});}}><Plus/>{uiText('Add customer')}</Button></>}>
    {!editing&&!importing&&<ErrorBox error={error}/>}
    <CustomerList bare customers={filtered} loading={loading} search={search} canEdit={canEdit} ui={ui} onEdit={c=>{setError('');setEditing(c);}} onFactors={setProfileCustomer}/>
    </Collection>
    {profileCustomer&&<FactorProfileEditor customer={profileCustomer} api={api} ui={ui} canEdit={canEdit} onClose={()=>setProfileCustomer(null)}/>}
    <Modal title={editing?.id?uiText("Edit customer"):uiText("Add customer")} open={!!editing} onClose={()=>!busy&&setEditing(null)}>
      {editing&&<form className="ui-stack" onSubmit={save}><ErrorBox error={error}/><Field title={uiText("Customer")} help={uiText("Use one customer name. Add alternative names or an ERP ID when your files use something different.")}><input required maxLength={200} autoFocus value={editing.customer} onChange={e=>setEditing(c=>({...c,customer:e.target.value}))}/></Field>
        <Disclosure title={uiText('IDs & alternative names')}><Field title={uiText('Customer ID in your ERP')}><input maxLength={160} value={editing.external_id||''} onChange={e=>setEditing(c=>({...c,external_id:e.target.value}))}/></Field><Field title={uiText('Alternative names')} help={uiText('One per line. Include Persian/English names or codes used in your files. Review matches before import.')}><textarea rows={3} value={(editing.aliases||[]).join('\n')} onChange={e=>setEditing(c=>({...c,aliases:e.target.value.split('\n')}))}/></Field></Disclosure>
        <PanelHeader title={<>{uiText('Products')}<Help text={uiText('Optional now. Link products before including this customer in a demand forecast. Missing sales history is flagged, not guessed.')}/></>} actions={<Button type="button" onClick={()=>setEditing(c=>({...c,products:[...c.products,{sku:'',unit:''}]}))}><Plus/>{uiText('Add product')}</Button>}/>
        {editing.products.map((p,i)=><Grid actionColumn key={i}><Field title={uiText("SKU")}><input required maxLength={200} value={p.sku} onChange={e=>updateProduct(i,'sku',e.target.value)}/></Field><Field title={uiText("Unit")}><input required maxLength={80} placeholder={uiText("e.g. tonnes")} value={p.unit} onChange={e=>updateProduct(i,'unit',e.target.value)}/></Field><Actions><Button type="button" aria-label={uiText('Remove product {{number}}',{number:i+1})} onClick={()=>setEditing(c=>({...c,products:c.products.filter((_,n)=>n!==i)}))}><Trash/></Button></Actions></Grid>)}
        <label className="ui-check"><input type="checkbox" checked={editing.active} onChange={e=>setEditing(c=>({...c,active:e.target.checked}))}/>{uiText("Active customer")}</label><Actions><Button type="button" disabled={busy} onClick={()=>setEditing(null)}>{uiText("Cancel")}</Button><Button kind="primary" type="submit" disabled={busy}>{busy?uiText("Saving…"):uiText("Save customer")}</Button></Actions>
      </form>}
    </Modal>
    <Modal title={uiText("Import customers")} description={uiText("CSV or Excel. Columns: customer, sku, unit. Use one row per product; sku and unit can both be blank.")} open={importing} onClose={()=>!busy&&setImporting(false)}><ErrorBox error={error}/><label className="sales-upload"><UploadSimple/>{busy?uiText("Reading…"):uiText("Choose file")}<input aria-label={uiText("Customer file")} type="file" accept=".csv,.xlsx" disabled={busy} onChange={e=>upload(e.target.files[0])}/></label>{preview&&<><p>{preview.customers.length}{' '}{uiText("customers ready to add. Existing customers are never overwritten.")}</p><Table headers={[uiText("Customer"),uiText("Products")]}>{preview.customers.slice(0,30).map(c=><tr key={c.customer}><td>{c.customer}</td><td>{c.products.length}</td></tr>)}</Table>{preview.customers.length>30&&<p>{uiText("First 30 shown.")}</p>}<div className="ui-actions"><Button kind="primary" disabled={busy} onClick={confirmImport}>{uiText("Add")}{' '}{preview.customers.length}{' '}{uiText("customers")}</Button></div></>}</Modal>
  </Wrapper>;
}

export function CustomerList({customers:filtered,loading=false,search="",canEdit=false,ui,onEdit,onFactors,bare=false}){
  const {Table,Button}=ui;
  const table=<Table headers={[uiText("Customer"),uiText("Products"),uiText("Status"),'']} empty={loading?uiText("Loading customers…"):filtered.length?false:search?uiText("No matching customers."):uiText("No customers yet. Add one or import your list.")}>{filtered.map(c=><tr key={c.id}><td><strong>{c.customer}</strong></td><td>{c.products.length?c.products.map(p=>p.sku+' ('+unitLabel(p.unit)+')').join(', '):uiText("Not linked yet")}</td><td>{c.active?uiText("Active"):uiText("Inactive")}</td><td><div className="ui-record-actions">{onFactors&&<Button aria-label={uiText('Forecast factors for {{name}}',{name:c.customer})} onClick={()=>onFactors(c)}>{uiText("Factors")}</Button>}{canEdit&&<Button aria-label={uiText('Edit {{name}}',{name:c.customer})} onClick={()=>onEdit(c)}>{uiText("Edit")}</Button>}</div></td></tr>)}</Table>;
  return bare?table:<div className="ui-collection-body">{table}</div>;
}

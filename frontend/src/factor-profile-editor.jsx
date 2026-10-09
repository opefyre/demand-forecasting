import {t as uiText} from './localization.mjs';
import React,{useEffect,useState} from 'react';

export const blankExposure=()=>({currency_exposure:false,global_supply:false,hormuz_route:false,materials:[]});

export function ExposureFields({value,onChange,materials,ui,disabled=false}){
  const {Field,Pick,Button}=ui;
  const [material,setMaterial]=useState('');
  useEffect(()=>setMaterial(''),[value]);
  return <>
    <div className="source-exposures" role="group" aria-label={uiText("Sales exposure")}>
      {[['currency_exposure','Currency changes affect our prices or customers'],['global_supply','Overseas supply affects our sales'],['hormuz_route','Our supplies or customers use the Hormuz route']].map(([key,label])=>
        <label className="check-line" key={key}><input type="checkbox" checked={value[key]} disabled={disabled} onChange={e=>onChange({...value,[key]:e.target.checked})}/>{uiText(label)}</label>)}
    </div>
    <Field title={uiText("Relevant materials")} help={uiText("Choose only materials relevant to these sales. Product codes cannot establish exposure.")}>
      <div className="factor-add-row"><Pick label={uiText("Relevant material")} disabled={disabled} value={material} options={[["",uiText("Choose a material")],...materials.filter(([key])=>!value.materials.includes(key))]} onChange={setMaterial}/>
        <Button disabled={!material||value.materials.length>=5||disabled} onClick={()=>{onChange({...value,materials:[...value.materials,material]});setMaterial('');}}>{uiText("Add")}</Button></div>
    </Field>
    {!!value.materials.length&&<div className="source-material-tags">{value.materials.map(key=><Button key={key} disabled={disabled} title={uiText("Remove material")} onClick={()=>onChange({...value,materials:value.materials.filter(k=>k!==key)})}>{materials.find(([k])=>k===key)?.[1]||key} ×</Button>)}</div>}
  </>;
}

export function FactorProfileEditor({customer,api,ui,canEdit,onClose}){
  const {Modal,Pick,Field,Button,ErrorBox}=ui;
  const [data,setData]=useState(null),[scope,setScope]=useState(''),[context,setContext]=useState(blankExposure),
    [enabled,setEnabled]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
  const product=scope?data?.customer.products[Number(scope)-1]:null;
  const current=data?.profiles.find(r=>(r.sku||'')===(product?.sku||'')&&(r.unit||'')===(product?.unit||''));
  const defaultProfile=data?.profiles.find(r=>!r.sku)?.context;
  const changed=enabled!==!!current?.context||(enabled&&JSON.stringify(context)!==JSON.stringify(current?.context));
  useEffect(()=>{let live=true;api('/api/customers/'+customer.id+'/factor-profiles').then(r=>{if(live)setData(r);}).catch(e=>live&&setError(e.message));return()=>{live=false;};},[customer.id]);
  useEffect(()=>{setContext(current?.context||defaultProfile||blankExposure());setEnabled(!!current?.context);},[scope,data]);
  async function save(){
    setBusy(true);setError('');setSaved(false);
    try{const result=await api('/api/customers/'+customer.id+'/factor-profiles',{
      sku:product?.sku||'',unit:product?.unit||'',expected_revision:current?.revision||0,context:enabled?context:null},'PUT');
      setData(d=>({...d,profiles:[...d.profiles.filter(r=>(r.sku||'')!==result.sku||(r.unit||'')!==result.unit),result]}));setSaved(true);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <Modal open title={uiText('Forecast factors')+' · '+customer.customer} onClose={onClose} dismissible={!busy} wide className="factor-link-modal">
    <ErrorBox error={error}/>
    {!data?<p role="status">{uiText("Loading profile…")}</p>:<>
      <Field title={uiText("Apply to")}><Pick label={uiText("Profile scope")} value={scope} disabled={busy} options={[["",uiText("Customer default")],...data.customer.products.map((p,i)=>[String(i+1),p.sku+' · '+p.unit])]} onChange={v=>{setScope(v);setSaved(false);}}/></Field>
      <div className="source-preparation-body factor-profile-fields">
        <label className="check-line"><input type="checkbox" checked={enabled} disabled={!canEdit||busy||!data.customer.active} onChange={e=>{setEnabled(e.target.checked);setSaved(false);}}/>{product?uiText("Use a product-specific profile"):uiText("Use a customer-wide profile")}</label>
        {enabled?<ExposureFields value={context} materials={data.materials} ui={ui} disabled={busy||!canEdit||!data.customer.active} onChange={value=>{setContext(value);setSaved(false);}}/>:
          <p className="muted">{product?defaultProfile?uiText("Uses the customer default."):uiText("No saved default. Choose factors when forecasting."):uiText("No saved default. Choose factors when forecasting.")}</p>}
      </div>
      <p className="muted">{uiText("Defaults only. Sources and future values are reviewed when forecasting.")}</p>
      {saved&&<p role="status">{uiText("Profile saved. Existing forecasts and orders are unchanged.")}</p>}
      <div className="dialog-actions"><Button disabled={busy} onClick={onClose}>{uiText("Close")}</Button><Button kind="primary" disabled={busy||!changed||!canEdit||!data.customer.active} onClick={save}>{busy?uiText("Saving…"):uiText("Save profile")}</Button></div>
    </>}
  </Modal>;
}

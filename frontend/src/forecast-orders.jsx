import React,{useCallback,useEffect,useState} from 'react';
import {t as uiText} from './localization.mjs';
import {SalesSource} from './sales-demand.jsx';
import {Actions,Disclosure,Grid,Stack} from './ui-layout.jsx';
import {OrderReview} from './order-books.jsx';
import {methodName} from './method-comparison.jsx';
import {orderCoverageTitle} from './forecast-start.mjs';

export function ForecastOrders({api,ui,dataset,snapshotId,onReady,canEdit=true,onWorkingChange,onPendingEditChange}){
  const {Button,Pick,Field,ErrorBox,Table}=ui;
  const [loaded,setLoaded]=useState(null),[schema,setSchema]=useState(null),[inputs,setInputs]=useState(null);
  const [imports,setImports]=useState({}),[reading,setReading]=useState({}),[reuse,setReuse]=useState('');
  const [busy,setBusy]=useState(false),[error,setError]=useState(null),[checked,setChecked]=useState(false);
  const [editingOrder,setEditingOrder]=useState(false);
  useEffect(()=>{onPendingEditChange?.(editingOrder);return()=>onPendingEditChange?.(false);},[editingOrder,onPendingEditChange]);
  useEffect(()=>{onWorkingChange?.(busy);return()=>onWorkingChange?.(false);},[busy,onWorkingChange]);
  const [customerName,setCustomerName]=useState(''),[product,setProduct]=useState(''),[adding,setAdding]=useState(false);
  const [attempt]=useState(()=>crypto.randomUUID());
  const path='/api/datasets/'+dataset.id+'/forecast-orders';
  useEffect(()=>{let live=true;
    Promise.all([api(path),api('/api/sales/schema'),snapshotId?api('/api/sales/inputs/'+snapshotId):Promise.resolve(null)])
      .then(([data,rules,saved])=>{if(live){setLoaded(data);setSchema(rules);setInputs(saved?.inputs?.run_id===data.context.run_id?saved.inputs:data.inputs);}})
      .catch(e=>live&&setError(e));return()=>{live=false;};
  },[dataset.id]);
  const fileBusy=useCallback((role,value)=>setReading(r=>({...r,[role]:value})),[]);
  function change(field,value){setInputs(i=>({...i,[field]:value,reviewed:false}));setChecked(false);setReuse('');onReady(null);setError(null);}
  async function useSaved(id){if(!id)return;setBusy(true);setError(null);
    try{const saved=await api('/api/sales/inputs/'+id);setInputs({...saved.inputs,run_id:loaded.context.run_id,reviewed:false});setImports({});setReuse(id);setChecked(false);onReady(null);}catch(e){setError(e);}finally{setBusy(false);}}
  async function addCustomer(){if(!customerName.trim())return;setBusy(true);setError(null);
    try{const p=inputs.customers.find(c=>c.sku===product);if(!p)throw Error(uiText('Choose a product'));
      await api('/api/customers',{customers:[{customer:customerName.trim(),products:[{sku:p.sku,unit:p.unit}],active:true}]});
      change('customers',[...inputs.customers,{customer:customerName.trim(),sku:p.sku,unit:p.unit,series_id:''}]);setCustomerName('');setAdding(false);
    }catch(e){setError(e);}finally{setBusy(false);}}
  async function check(){setBusy(true);setError(null);
    const payload={inputs:{...inputs,reviewed:true,note:'Customers and order coverage reviewed in the forecast wizard.'},imports,reuse_snapshot_id:reuse||undefined,request_id:attempt};
    try{const review=await api(path+'/preview',payload);const {as_of,valid_until,order_feed,orders}=review.inputs;
      const book=await api('/api/order-books/'+dataset.id,{version:loaded.version,as_of,valid_until,order_feed,orders},'PUT');setLoaded(v=>({...v,version:book.version}));
      const saved=await api(path,{...payload,review_token:review.review_token});onReady(saved.id);}catch(e){setError(e);}finally{setBusy(false);}}
  if(!inputs||!schema)return <Stack><ErrorBox error={error}/>{!error&&<p role="status">{uiText('Loading…')}</p>}</Stack>;
  const blocked=busy||!canEdit||Object.values(reading).some(Boolean);
  return <Stack><ErrorBox error={error}/>
    <Disclosure title={uiText('Customers')}><Table headers={[uiText('Customer'),uiText('SKU'),uiText('Sales history')]}>{inputs.customers.map((c,i)=><tr key={i}><td>{c.customer==='Unassigned demand'?uiText('Unassigned demand'):c.customer}</td><td>{c.sku}</td><td>{uiText(c.series_id?'Linked':'No history')}</td></tr>)}</Table>
      <Button disabled={blocked} onClick={()=>setAdding(v=>!v)}>{uiText('Add customer')}</Button>
      {adding&&<Grid><Field title={uiText('Customer')}><input disabled={blocked} value={customerName} onChange={e=>setCustomerName(e.target.value)}/></Field><Field title={uiText('SKU')}><Pick label={uiText('SKU')} disabled={blocked} value={product} onChange={setProduct} options={[["",uiText('Choose a product')],...[...new Set(inputs.customers.map(c=>c.sku))].map(s=>[s,s])]}/></Field><Button disabled={blocked||!customerName.trim()||!product} onClick={addCustomer}>{uiText('Save customer')}</Button></Grid>}
    </Disclosure>
    <OrderReview inputs={inputs} ui={ui} canEdit={!blocked} onEditingChange={setEditingOrder} onChange={rows=>{change('orders',rows);setImports(v=>{const next={...v};delete next.orders;return next;});}}/>
    <Disclosure title={uiText('Import or reuse orders')}>
      {!!loaded.saved_orders.length&&<Field title={uiText('Reuse saved orders')}><Pick label={uiText('Reuse saved orders')} value={reuse} onChange={useSaved} options={[["",uiText('Choose saved orders')],...loaded.saved_orders.map(s=>[s.id,s.name+(s.method?' · '+methodName(s.method):'')+' · '+s.as_of])]}/></Field>}
      <SalesSource embedded api={api} ui={ui} role="orders" schema={schema.orders} config={imports.orders} run={loaded.context} templateBase={path+'/template'} fallbackCount={inputs.orders.length} orderMode="replace" onBusyChange={fileBusy} setConfig={config=>{setImports(v=>{const next={...v};if(config)next.orders=config;else delete next.orders;return next;});setChecked(false);onReady(null);}}/>
    </Disclosure>
    <Disclosure title={uiText('Order coverage')}><Grid><Field title={uiText('Orders correct as of')}><input disabled={blocked} type="date" value={inputs.as_of} onChange={e=>change('as_of',e.target.value)}/></Field><Field title={uiText('Review again after')}><input disabled={blocked} type="date" value={inputs.valid_until} onChange={e=>change('valid_until',e.target.value)}/></Field></Grid></Disclosure>
    <Field title={uiText('Order coverage')}><Pick disabled={blocked} label={uiText('Order coverage')} value={inputs.order_feed} onChange={v=>change('order_feed',v)} options={[["unknown",uiText('Orders not provided or incomplete')],["complete_snapshot",uiText(orderCoverageTitle(inputs.orders,imports.orders))]]}/></Field>
    <label className="ui-check"><input type="checkbox" checked={checked} disabled={blocked} onChange={e=>setChecked(e.target.checked)}/>{uiText('I checked the customers, products, order quantities and coverage.')}</label>
    <Actions><Button kind="primary" disabled={blocked||editingOrder||!checked||!!snapshotId} onClick={check}>{uiText(busy?'Checking…':snapshotId?'Inputs ready':'Continue')}</Button></Actions>
  </Stack>;
}

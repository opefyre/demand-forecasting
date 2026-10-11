import React,{useCallback,useEffect,useState,useRef} from 'react';
import {t as uiText,unitLabel,i18n} from './localization.mjs';
import {SalesSource} from './sales-demand.jsx';
import {Actions,Disclosure,Grid,Stack} from './ui-layout.jsx';
import {OrderReview} from './order-books.jsx';
import {methodName} from './method-comparison.jsx';
import {orderCoverageTitle,forecastOrderDraft} from './forecast-start.mjs';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {reviewedOrderRequest,checkForecastOrderReview,saveForecastOrderReview} from './order-update-state.mjs';
import {coverageStatus} from './demand-view.mjs';
import {OrderChanges} from './order-changes.jsx';
import {Commitments} from './commitments.jsx';

export function OrderDemandReceipt({review,ui,basis,page=0}){
  const amount=value=>value==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:2}).format(value);
  return <ui.Table headers={['Customer','SKU','Month','Calculated estimate','Open orders','Already fulfilled','Still expected','Total demand','Coverage'].map(label=>uiText(label))}>
    {review.rows.slice(page*25,(page+1)*25).map((row,index)=><tr key={index}><td>{row.customer}</td><td>{row.sku}</td><td><bdi>{row.period_label||planningMonth(row.period,basis)}</bdi></td>{['baseline','booked','fulfilled','remaining','total'].map(field=><td key={field}>{amount(row[field])} {unitLabel(row.unit)}</td>)}<td>{uiText(coverageStatus(row))}{row.issue&&<span className="ui-record-meta">{uiText(row.issue)}</span>}</td></tr>)}
  </ui.Table>;
}

export function ForecastOrders({api,ui,dataset,snapshotId,onReady,canEdit=true,onWorkingChange,onPendingEditChange,targetRun=null,initial=null,draft=null,onDraftChange}){
  const {Button,Pick,Field,ErrorBox,Table}=ui;
  const [loaded,setLoaded]=useState(null),[schema,setSchema]=useState(null),[inputs,setInputs]=useState(null);
  const restored=forecastOrderDraft(draft,dataset?.id);
  const [imports,setImports]=useState(restored?.imports||initial?.imports||{}),[reading,setReading]=useState({}),[reuse,setReuse]=useState(restored?.reuse||'');
  const [busy,setBusy]=useState(false),[error,setError]=useState(null),[checked,setChecked]=useState(false);
  const [readRevision,setReadRevision]=useState(0);
  const [editingOrder,setEditingOrder]=useState(false);
  const [editingCommitment,setEditingCommitment]=useState(false);
  const [review,setReview]=useState(null),[page,setPage]=useState(0),[orderMode,setOrderMode]=useState(initial?.order_mode||'replace');
  useEffect(()=>{onPendingEditChange?.(editingOrder||editingCommitment);return()=>onPendingEditChange?.(false);},[editingOrder,editingCommitment,onPendingEditChange]);
  useEffect(()=>{onWorkingChange?.(busy);return()=>onWorkingChange?.(false);},[busy,onWorkingChange]);
  const [customerName,setCustomerName]=useState(''),[product,setProduct]=useState(''),[adding,setAdding]=useState(false);
  const [attempt]=useState(()=>crypto.randomUUID());
  const submitting=useRef(false);
  const path=targetRun?'/api/sales/runs/'+targetRun.run_id:'/api/datasets/'+dataset.id+'/forecast-orders';
  useEffect(()=>{let live=true;
    setError(null);
    const starter=targetRun?(initial?Promise.resolve({context:targetRun,inputs:initial.inputs,saved_orders:[]}):api(path+'/starter').then(inputs=>({context:targetRun,inputs,saved_orders:[]}))):api(path);
    Promise.all([starter,api('/api/sales/schema'),!targetRun&&snapshotId?api('/api/sales/inputs/'+snapshotId):Promise.resolve(null)])
      .then(([data,rules,saved])=>{if(live){setLoaded(data);setSchema(rules);
        const currentDraft=restored?.inputs.run_id===data.context.run_id&&restored.bookVersion===data.version;
        const staleDraft=!!restored&&!currentDraft;
        setInputs(currentDraft?restored.inputs:!staleDraft&&saved?.inputs?.run_id===data.context.run_id?saved.inputs:data.inputs);
        if(staleDraft){setImports({});setReuse('');onReady(null);setError(Error(uiText('Orders changed since this draft was saved. Current orders have been loaded; review them again.')));}
      }})
      .catch(e=>live&&setError(e));return()=>{live=false;};
  },[dataset?.id,targetRun?.run_id,readRevision]);
  useEffect(()=>{if(inputs&&!targetRun)onDraftChange?.({datasetId:dataset.id,bookVersion:loaded.version,inputs,imports,reuse});},[inputs,imports,reuse,loaded?.version,dataset?.id,targetRun?.run_id,onDraftChange]);
  const fileBusy=useCallback((role,value)=>setReading(r=>({...r,[role]:value})),[]);
  function change(field,value){setInputs(i=>({...i,[field]:value,reviewed:false}));setChecked(false);setReuse('');setReview(null);onReady(null);setError(null);}
  async function useSaved(id){if(!id||busy||!canEdit||Object.values(reading).some(Boolean))return;setBusy(true);setError(null);
    try{const saved=await api('/api/sales/inputs/'+id);setInputs({...saved.inputs,run_id:loaded.context.run_id,reviewed:false});setImports({});setReuse(id);setChecked(false);setReview(null);onReady(null);}catch(e){setError(e);}finally{setBusy(false);}}
  async function addCustomer(){if(!customerName.trim())return;setBusy(true);setError(null);
    try{const p=inputs.customers.find(c=>c.sku===product);if(!p)throw Error(uiText('Choose a product'));
      if(inputs.customers.some(c=>c.customer===customerName.trim()&&c.sku===p.sku))throw Error(uiText('This customer already has this product.'));
      await api('/api/customers',{customers:[{customer:customerName.trim(),products:[{sku:p.sku,unit:p.unit}],active:true}]});
      change('customers',[...inputs.customers,{customer:customerName.trim(),sku:p.sku,unit:p.unit,series_id:''}]);setCustomerName('');setAdding(false);
    }catch(e){setError(e);}finally{setBusy(false);}}
  async function check(){if(submitting.current||!canEdit)return;submitting.current=true;setBusy(true);setError(null);
    if(targetRun){try{setReview(await api('/api/sales/validate',reviewedOrderRequest(initial,inputs,imports,attempt,orderMode)));setPage(0);}catch(e){setError(e);}finally{submitting.current=false;setBusy(false);}return;}
    const payload={inputs:{...inputs,reviewed:true,note:'Customers and order coverage reviewed in the forecast wizard.'},imports,reuse_snapshot_id:reuse||undefined,request_id:attempt};
    try{const result=await checkForecastOrderReview(api,path,dataset.id,loaded.version,payload,version=>setLoaded(v=>({...v,version})));
      if(result.review){setReview(result);return;}
      setLoaded(v=>({...v,version:result.version}));onReady(result.saved.id);
    }catch(e){setError(e);}finally{submitting.current=false;setBusy(false);}}
  async function continueWithWarnings(){if(submitting.current||!canEdit||!review)return;submitting.current=true;setBusy(true);setError(null);
    try{const result=await saveForecastOrderReview(api,path,dataset.id,loaded.version,review.payload,review.review,version=>setLoaded(v=>({...v,version})));
      setLoaded(v=>({...v,version:result.version}));onReady(result.saved.id);
    }catch(e){setError(e);}finally{submitting.current=false;setBusy(false);}}
  async function saveReview(){if(submitting.current||!canEdit||!review)return;submitting.current=true;setBusy(true);setError(null);
    try{const saved=await api('/api/sales/inputs',{...reviewedOrderRequest(initial,inputs,imports,attempt,orderMode),review_token:review.review_token});await onReady(saved.id);}catch(e){setError(e);}finally{submitting.current=false;setBusy(false);}}
  if(!inputs||!schema)return <Stack><ErrorBox error={error} onReload={()=>setReadRevision(value=>value+1)}/>{!error&&<p role="status">{uiText('Loading…')}</p>}</Stack>;
  const blocked=busy||!canEdit||Object.values(reading).some(Boolean);
  const amount=value=>value==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:2}).format(value);
  if(!targetRun&&review)return <Stack><ErrorBox error={error}/>
    <Disclosure open title={uiText('Checks to review')}><ul>{review.review.warnings.map((warning,index)=><li key={index}>{uiText(warning)}</li>)}</ul>
      {!!review.review.missing_history?.length&&<Table headers={[uiText('Customer'),uiText('SKU')]}>{review.review.missing_history.map((row,index)=><tr key={index}><td>{row.customer}</td><td>{row.sku}</td></tr>)}</Table>}
    </Disclosure>
    <Actions><Button disabled={busy} onClick={()=>setReview(null)}>{uiText('Edit inputs')}</Button><Button kind="primary" disabled={blocked} onClick={continueWithWarnings}>{uiText(busy?'Saving…':'Continue after review')}</Button></Actions>
  </Stack>;
  if(targetRun&&review)return <Stack><ErrorBox error={error}/>
    <OrderChanges changes={review.order_changes} ui={ui}/>
    <OrderDemandReceipt review={review} ui={ui} basis={planningBasis(targetRun)} page={page}/>
    {review.rows.length>25&&<Actions><Button disabled={busy||!page} onClick={()=>setPage(p=>p-1)}>{uiText('Previous')}</Button><span>{amount(page*25+1)}–{amount(Math.min((page+1)*25,review.rows.length))} {uiText('of')} {amount(review.rows.length)}</span><Button disabled={busy||(page+1)*25>=review.rows.length} onClick={()=>setPage(p=>p+1)}>{uiText('Next')}</Button></Actions>}
    {!!review.warnings.length&&<Disclosure open title={uiText('Checks to review')}><ul>{review.warnings.map((warning,index)=><li key={index}>{uiText(warning)}</li>)}</ul></Disclosure>}
    <Actions><Button disabled={busy} onClick={()=>setReview(null)}>{uiText('Edit orders')}</Button><Button kind="primary" disabled={blocked} onClick={saveReview}>{uiText(busy?'Saving…':'Save reviewed orders')}</Button></Actions>
  </Stack>;
  return <Stack><ErrorBox error={error}/>
    <Disclosure title={uiText('Customers')}><Table headers={[uiText('Customer'),uiText('SKU'),uiText('Sales history')]}>{inputs.customers.map((c,i)=><tr key={i}><td>{c.customer==='Unassigned demand'?uiText('Unassigned demand'):c.customer}</td><td>{c.sku}</td><td>{uiText(c.series_id?'Linked':'No history')}</td></tr>)}</Table>
      <Button disabled={blocked} onClick={()=>setAdding(v=>!v)}>{uiText('Add customer')}</Button>
      {adding&&<Grid><Field title={uiText('Customer')}><input disabled={blocked} value={customerName} onChange={e=>setCustomerName(e.target.value)}/></Field><Field title={uiText('SKU')}><Pick label={uiText('SKU')} disabled={blocked} value={product} onChange={setProduct} options={[["",uiText('Choose a product')],...[...new Set(inputs.customers.map(c=>c.sku))].map(s=>[s,s])]}/></Field><Button disabled={blocked||!customerName.trim()||!product} onClick={addCustomer}>{uiText('Save customer')}</Button></Grid>}
    </Disclosure>
    <Commitments inputs={inputs} run={loaded.context} ui={ui} canEdit={!blocked&&!editingOrder} onEditingChange={setEditingCommitment} onChange={rows=>{change('commitments',rows);setImports(v=>{const next={...v};delete next.commitments;return next;});}}/>
    {targetRun&&<Disclosure title={uiText('Import monthly commitments')}>
      <SalesSource embedded api={api} ui={ui} role="commitments" schema={schema.commitments} config={imports.commitments} run={loaded.context} fallbackCount={inputs.commitments.length} onBusyChange={fileBusy} setConfig={config=>{setImports(v=>{const next={...v};if(config)next.commitments=config;else delete next.commitments;return next;});setChecked(false);setReview(null);}}/>
    </Disclosure>}
    <OrderReview inputs={inputs} ui={ui} canEdit={!blocked&&!editingCommitment} onEditingChange={setEditingOrder} onChange={rows=>{change('orders',rows);setOrderMode('replace');setImports(v=>{const next={...v};delete next.orders;return next;});}}/>
    <Disclosure title={uiText('Import or reuse orders')}>
      {!!loaded.saved_orders.length&&<Field title={uiText('Reuse saved orders')}><Pick label={uiText('Reuse saved orders')} disabled={blocked} value={reuse} onChange={useSaved} options={[["",uiText('Choose saved orders')],...loaded.saved_orders.map(s=>[s.id,s.name+(s.method?' · '+methodName(s.method):'')+' · '+s.as_of])]}/></Field>}
      {targetRun&&initial?.base_snapshot_id&&inputs.order_feed==='complete_snapshot'&&<Field title={uiText('Order file contains')}><Pick label={uiText('Order file contains')} disabled={blocked} value={orderMode} onChange={value=>{setOrderMode(value);setChecked(false);setReview(null);}} options={[["replace",uiText('Full order book')],["changes",uiText('Only changed order lines')]]}/></Field>}
      <SalesSource embedded api={api} ui={ui} role="orders" schema={schema.orders} config={imports.orders} run={loaded.context} templateBase={targetRun?undefined:path+'/template'} fallbackCount={inputs.orders.length} orderMode={orderMode} onBusyChange={fileBusy} setConfig={config=>{setImports(v=>{const next={...v};if(config)next.orders=config;else delete next.orders;return next;});setChecked(false);setReview(null);onReady(null);}}/>
    </Disclosure>
    <Disclosure title={uiText('Order coverage')}><Grid><Field title={uiText('Orders correct as of')}><input disabled={blocked} type="date" value={inputs.as_of} onChange={e=>change('as_of',e.target.value)}/></Field><Field title={uiText('Review again after')}><input disabled={blocked} type="date" value={inputs.valid_until} onChange={e=>change('valid_until',e.target.value)}/></Field></Grid></Disclosure>
    <Field title={uiText('Order coverage')}><Pick disabled={blocked} label={uiText('Order coverage')} value={inputs.order_feed} onChange={v=>change('order_feed',v)} options={[["unknown",uiText('Orders not provided or incomplete')],["complete_snapshot",uiText(orderCoverageTitle(inputs.orders,imports.orders))]]}/></Field>
    <label className="ui-check"><input type="checkbox" checked={checked} disabled={blocked} onChange={e=>setChecked(e.target.checked)}/>{uiText('I checked the customers, products, order quantities and coverage.')}</label>
    <Actions><Button kind="primary" disabled={blocked||editingCommitment||editingOrder||!checked||(!targetRun&&!!snapshotId)} onClick={check}>{uiText(busy?'Checking…':targetRun?'Review demand':snapshotId?'Inputs ready':'Continue')}</Button></Actions>
  </Stack>;
}

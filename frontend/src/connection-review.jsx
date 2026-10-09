import React,{useState} from 'react';
import {Actions,Grid,Stack,Disclosure} from './ui-layout.jsx';
import {t as uiText} from './localization.mjs';

const customerFields=['customer','external_id','sku','unit','aliases','active'];
const orderFields=['reference','customer','sku','unit','due_date','ordered','fulfilled','cancelled','status'];
const labels={customer:'Customer',external_id:'Customer ID in your ERP',sku:'SKU',unit:'Unit',aliases:'Alternative names',active:'Active customer',
  reference:'Order line',due_date:'Due date',ordered:'Ordered',fulfilled:'Delivered',cancelled:'Cancelled',status:'Status'};
export const reviewPayload=form=>({...form,as_of:form.as_of||null,valid_until:form.valid_until||null});

export function ConnectionRowReview({candidate,api,ui,onClose,onSaved}){
  const {Modal,Button,Field,Pick,Table,ErrorBox}=ui;
  const isOrders=candidate.role==='sales_orders',fields=isOrders?orderFields:customerFields;
  const [table,setTable]=useState(candidate.source.preview);
  const columns=table.columns||[];
  const [form,setForm]=useState(()=>({mapping:Object.fromEntries(fields.map(key=>[key,columns.find(c=>c.label.toLowerCase()===key)?.id||''])),
    sheet:candidate.source.sheet,header_row:1,calendar:'gregorian',order_mode:'changes',as_of:'',valid_until:'',order_feed:'unknown',confirm_empty:false}));
  const [report,setReport]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(null),[confirmed,setConfirmed]=useState(false);
  const [loadedSpec,setLoadedSpec]=useState(()=>({sheet:candidate.source.sheet,header_row:1}));
  const columnsCurrent=form.sheet===loadedSpec.sheet&&form.header_row===loadedSpec.header_row;
  const root='/api/v1/connections/imports/'+candidate.id+'/rows';
  const change=(key,value)=>{setForm(f=>({...f,[key]:value}));setReport(null);setConfirmed(false);};
  async function preview(){setBusy(true);setError(null);try{setReport(await api(root+'/preview',reviewPayload(form)));}catch(e){setError(e);}finally{setBusy(false);}}
  async function updateTable(){setBusy(true);setError(null);try{const next=await api('/api/v1/sources/'+candidate.source_id+'/preview',{sheet:form.sheet,header_row:form.header_row});setTable(next);setLoadedSpec({sheet:form.sheet,header_row:form.header_row});change('mapping',Object.fromEntries(fields.map(key=>[key,next.columns.find(c=>c.label.toLowerCase()===key)?.id||''])));}catch(e){setError(e);}finally{setBusy(false);}}
  async function save(){setBusy(true);setError(null);try{await api(root+'/accept',{...reviewPayload(form),reviewed:true,review_token:report.review_token});await onSaved();onClose();}catch(e){setError(e);}finally{setBusy(false);}}
  return <Modal title={uiText(isOrders?'Review connected orders':'Review connected customers')} open onClose={()=>!busy&&onClose()} fixed>
    <Stack><ErrorBox error={error}/>
      {!report?<>
        <Grid>{fields.map(key=><Field key={key} title={uiText(labels[key])}><Pick label={uiText(labels[key])} value={form.mapping[key]} onChange={v=>change('mapping',{...form.mapping,[key]:v})}
          options={[["",uiText('Not mapped')],...columns.map(c=>[c.id,c.label])]}/></Field>)}</Grid>
        <Disclosure title={uiText('Table settings')}><Grid>
          {candidate.source.preview.sheets?.length>0&&<Field title={uiText('Worksheet')}><Pick label={uiText('Worksheet')} value={form.sheet||''} options={candidate.source.preview.sheets.map(s=>[s,s])} onChange={v=>change('sheet',v)}/></Field>}
          <Field title={uiText('Header row')}><input type="number" min={1} max={200} value={form.header_row} onChange={e=>change('header_row',Number(e.target.value))}/></Field>
        </Grid><Actions><Button disabled={busy} onClick={updateTable}>{uiText('Update columns')}</Button></Actions></Disclosure>
        {isOrders&&<><Grid>
          <Field title={uiText('Date calendar')}><Pick label={uiText('Date calendar')} value={form.calendar} onChange={v=>change('calendar',v)} options={[["gregorian",uiText('Gregorian')],["jalali",uiText('Persian')]]}/></Field>
          <Field title={uiText('Order update')} help={uiText('Changed lines keep other saved orders. A full order book replaces them after review.')}><Pick label={uiText('Order update')} value={form.order_mode} onChange={v=>{change('order_mode',v);change('order_feed','unknown');}} options={[["changes",uiText('Changed lines')],["replace",uiText('Full order book')]]}/></Field>
          <Field title={uiText('Orders correct as of')}><input type="date" value={form.as_of} onChange={e=>change('as_of',e.target.value)}/></Field>
          <Field title={uiText('Review again after')}><input type="date" value={form.valid_until} onChange={e=>change('valid_until',e.target.value)}/></Field>
        </Grid>{form.order_mode==='replace'&&<Disclosure title={uiText('Order coverage')}><Stack>
          <label className="ui-check"><input type="checkbox" checked={form.order_feed==='complete_snapshot'} onChange={e=>change('order_feed',e.target.checked?'complete_snapshot':'unknown')}/>{uiText('This contains all orders for these customers and products.')}</label>
          <label className="ui-check"><input type="checkbox" checked={form.confirm_empty} onChange={e=>change('confirm_empty',e.target.checked)}/>{uiText('Allow an empty full export to clear saved orders.')}</label>
        </Stack></Disclosure>}</>}
      </>:<>
        <Table headers={isOrders?[uiText('Order line'),uiText('Customer'),uiText('SKU'),uiText('Due date'),uiText('Ordered'),uiText('Delivered'),uiText('Cancelled'),uiText('Status')]:[uiText('Customer'),uiText('Products'),uiText('Status')]}>
          {report.rows.map((r,i)=><tr key={i}>{isOrders?<><td>{r.reference}</td><td>{r.customer}</td><td>{r.sku}</td><td>{r.due_date}</td><td>{r.ordered} {r.unit}</td><td>{r.fulfilled}</td><td>{r.cancelled}</td><td>{uiText(r.status==='confirmed'?'Confirmed':r.status==='cancelled'?'Cancelled':'Unconfirmed')}</td></>:<><td>{r.customer}</td><td>{r.products.map(p=>p.sku+' · '+p.unit).join(', ')||'—'}</td><td>{uiText(r.active?'Active':'Inactive')}</td></>}</tr>)}
        </Table>
        {report.count>report.rows.length&&<span>{uiText('Showing the first {{count}} rows.',{count:report.rows.length})}</span>}
        <label className="ui-check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{uiText('Approve importing {{count}} rows.',{count:report.count})}</label>
      </>}
      <Actions>{report?<Button disabled={busy} onClick={()=>{setReport(null);setConfirmed(false);}}>{uiText('Back')}</Button>:<Button disabled={busy} onClick={onClose}>{uiText('Cancel')}</Button>}
        <Button kind="primary" disabled={busy||!columnsCurrent||(!!report&&!confirmed)} onClick={report?save:preview}>{uiText(busy?'Saving…':report?'Save inputs':!columnsCurrent?'Update columns':'Review rows')}</Button></Actions>
    </Stack>
  </Modal>;
}

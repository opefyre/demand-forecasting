import {apiLink} from './company-api.mjs';
import React,{useState,useRef,useEffect} from 'react';
import {t as uiText,i18n,unitLabel} from './localization.mjs';
import {comparisonRows} from './order-comparison.mjs';
import {planningBasis,planningMonth} from './planning-calendar.mjs';
import {Stack,Grid,Actions,DefinitionList,Disclosure} from './ui-layout.jsx';

const quantity=value=>value==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:2}).format(value);
// Proposals and dialogs share quantities, units and missing-value semantics.
export function OrderComparisonReport({rows,basis,warnings=[],ui}) {
  return <Stack>
    <ui.Table headers={[uiText('Month'),uiText('Open orders'),uiText('Remaining · before → after'),uiText('Total · before → after'),uiText('Change')]}
      empty={!rows.length?uiText('No matching customers and SKUs.'):undefined}>
      {rows.map(row=><tr key={row.period+row.unit}>
        <td>{planningMonth(row.period,basis)}<span className="ui-record-meta">{unitLabel(row.unit)}</span></td>
        <td>{quantity(row.booked)}{!!row.fulfilled&&<span className="ui-record-meta">{uiText('Delivered')} {quantity(row.fulfilled)}</span>}</td>
        <td><bdi>{quantity(row.before_remaining)} → {quantity(row.after_remaining)}</bdi></td>
        <td><bdi>{quantity(row.before_total)} → {quantity(row.after_total)}</bdi></td>
        <td>{quantity(row.difference)}</td>
      </tr>)}
    </ui.Table>
    {!!warnings.length&&<Disclosure open title={uiText('Checks to review')}><ul>{warnings.map((warning,index)=><li key={index}>{uiText(warning)}</li>)}</ul></Disclosure>}
  </Stack>;
}

export function OrderComparison({base,scenario,api,ui,canEdit}) {
  const {Button,Modal,Pick,ErrorBox}=ui;
  const [open,setOpen]=useState(false),[report,setReport]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [customer,setCustomer]=useState(''),[sku,setSku]=useState(''),[approved,setApproved]=useState(false),[saved,setSaved]=useState(null);
  const attempt=useRef(null),version=useRef(0),inFlight=useRef(false);
  useEffect(()=>{version.current++;setOpen(false);setReport(null);setSaved(null);setError('');setBusy(false);inFlight.current=false;
    return()=>{version.current++;};},[base.run_id,scenario.run_id]);
  async function act(work,onDone){
    if(inFlight.current)return;
    inFlight.current=true;setBusy(true);setError('');const current=version.current;
    try{const value=await work();if(current===version.current)onDone(value);}
    catch(e){if(current===version.current)setError(e.message);}
    finally{if(current===version.current){inFlight.current=false;setBusy(false);}}
  }
  async function start(){if(inFlight.current)return;setOpen(true);setReport(null);setSaved(null);setApproved(false);setCustomer('');setSku('');attempt.current=null;
    await act(async()=>{const list=await api(`/api/sales/runs/${base.run_id}/inputs`);
      if(!list.snapshots.length)throw Error(uiText('Save customers and orders on the baseline first, then compare them here.'));
      return api(`/api/sales/runs/${scenario.run_id}/order-comparison/preview`,{snapshot_id:list.snapshots[0].id});},setReport);}
  const rows=report?comparisonRows(report.rows,customer,sku):[];
  return <>
    <Button disabled={!canEdit||busy} onClick={start}>{uiText('Compare with orders')}</Button>
    <Modal open={open} onClose={()=>!busy&&setOpen(false)} title={uiText('Demand comparison')} wide fixed>
      <Stack><ErrorBox error={error}/>{busy&&!report&&<p role="status">{uiText('Loading saved orders…')}</p>}
      {report&&<>
        <DefinitionList rows={[[uiText('Order source'),report.source_name],[uiText('Orders as of'),report.as_of],[uiText('Unit'),unitLabel(report.unit)]]}/>
        <Grid>
          <Pick label={uiText('Comparison customer')} disabled={busy} value={customer} onChange={setCustomer} options={[["",uiText('All customers')],...[...new Set(report.rows.map(r=>r.customer))].sort().map(v=>[v,v])]}/>
          <Pick label={uiText('Comparison SKU')} disabled={busy} value={sku} onChange={setSku} options={[["",uiText('All SKUs')],...[...new Set(report.rows.map(r=>r.sku))].sort().map(v=>[v,v])]}/>
        </Grid>
        <OrderComparisonReport rows={rows} basis={planningBasis(base)} warnings={report.warnings} ui={ui}/>
        <p className="table-note">{uiText('Total = delivered + open orders + remaining expectation. Exports exclude quantities already delivered.')}</p>
        {!saved&&<label className="ui-check"><input type="checkbox" checked={approved} disabled={busy||!canEdit||!report.can_save} onChange={e=>setApproved(e.target.checked)}/>{uiText('I reviewed the scenario for all customers and SKUs. Save a separate draft; keep the original unchanged.')}</label>}
        {saved&&<><p role="status">{uiText('Separate draft saved. Publication approval was not copied.')}</p><Actions>
          <a className="btn secondary" href={apiLink(`/api/sales/inputs/${saved.id}/export?mode=combined_demand&kind=xlsx`)}>{uiText('Full scenario · Excel')}</a>
          <a className="btn secondary" href={apiLink(`/api/sales/inputs/${saved.id}/export?mode=remaining_forecast&kind=csv`)}>{uiText('Remaining forecast · CSV')}</a>
        </Actions></>}
      </>}
      <Actions><Button disabled={busy} onClick={()=>setOpen(false)}>{uiText('Close')}</Button>{report&&!saved&&<Button kind="primary" disabled={busy||!canEdit||!approved||!report.can_save} onClick={()=>act(async()=>{
        attempt.current ||= crypto.randomUUID();return api(`/api/sales/runs/${scenario.run_id}/order-comparison`,{snapshot_id:report.source_snapshot_id,review_token:report.review_token,reviewed:true,request_id:attempt.current});
      },setSaved)}>{uiText(busy?'Saving…':'Save scenario draft')}</Button>}</Actions>
      </Stack>
    </Modal>
  </>;
}

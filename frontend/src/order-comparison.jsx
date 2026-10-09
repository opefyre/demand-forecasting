import React,{useState,useRef} from 'react';
import {comparisonRows} from './order-comparison.mjs';
import {planningBasis,planningMonth} from './planning-calendar.mjs';

export function OrderComparison({base,scenario,api,ui,fmt,canEdit}) {
  const {Button,Modal,Pick,Table,ErrorBox}=ui;
  const [open,setOpen]=useState(false),[report,setReport]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
  const [customer,setCustomer]=useState(''),[sku,setSku]=useState(''),[approved,setApproved]=useState(false),[saved,setSaved]=useState(null);
  const attempt=useRef(null);
  async function act(work){setBusy(true);setError('');try{await work();}catch(e){setError(e.message);}finally{setBusy(false);}}
  async function start(){setOpen(true);setReport(null);setSaved(null);setApproved(false);setCustomer('');setSku('');attempt.current=null;
    await act(async()=>{const list=await api(`/api/sales/runs/${base.run_id}/inputs`);
      if(!list.snapshots.length)throw Error('Save customers and orders on the baseline first, then compare them here.');
      setReport(await api(`/api/sales/runs/${scenario.run_id}/order-comparison/preview`,{snapshot_id:list.snapshots[0].id}));});}
  const rows=report?comparisonRows(report.rows,customer,sku):[];
  const show=v=>v==null?'Unknown':fmt(v,2);
  return <>
    <Button disabled={!canEdit} onClick={start}>Compare with orders</Button>
    <Modal open={open} onClose={()=>!busy&&setOpen(false)} title="Demand comparison" wide description="The same customers and orders, with two forecasts.">
      <ErrorBox error={error}/>{busy&&!report&&<p role="status">Loading saved orders…</p>}
      {report&&<>
        <p>{report.source_name} · Orders as of {report.as_of} · {report.unit}</p>
        {!!report.warnings.length&&<p role="alert">{report.warnings.join(' ')}</p>}
        <div className="order-comparison-filters">
          <Pick label="Comparison customer" value={customer} onChange={setCustomer} options={[["","All customers"],...[...new Set(report.rows.map(r=>r.customer))].sort().map(v=>[v,v])]}/>
          <Pick label="Comparison SKU" value={sku} onChange={setSku} options={[["","All SKUs"],...[...new Set(report.rows.map(r=>r.sku))].sort().map(v=>[v,v])]}/>
        </div>
        <div className="order-comparison-table"><Table headers={['Month','Open orders','Remaining · before → after','Total · before → after','Change']} empty={!rows.length?'No matching customers and SKUs.':undefined}>
          {rows.map(r=><tr key={`${r.period}-${r.unit}`}><td>{planningMonth(r.period,planningBasis(base))}</td><td>{show(r.booked)}{!!r.fulfilled&&<small>Delivered {show(r.fulfilled)}</small>}</td><td>{show(r.before_remaining)} → {show(r.after_remaining)}</td><td>{show(r.before_total)} → {show(r.after_total)}</td><td>{show(r.difference)}</td></tr>)}
        </Table></div>
        <p className="table-note">Total = delivered + open orders + remaining expectation. Exports exclude quantities already delivered.</p>
        {!saved&&<label className="order-comparison-approval"><input type="checkbox" checked={approved} disabled={busy||!report.can_save} onChange={e=>setApproved(e.target.checked)}/> I reviewed the scenario for all customers and SKUs. Save a separate draft; keep the original unchanged.</label>}
        {saved&&<p role="status">Separate draft saved. Publication approval was not copied.</p>}
        {saved&&<p><a href={`/api/sales/inputs/${saved.id}/export?mode=combined_demand&kind=xlsx`}>Export full scenario · Excel</a>{' · '}<a href={`/api/sales/inputs/${saved.id}/export?mode=remaining_forecast&kind=csv`}>Export full remaining forecast · CSV</a></p>}
      </>}
      <div className="dialog-actions"><Button disabled={busy} onClick={()=>setOpen(false)}>Close</Button>{report&&!saved&&<Button kind="primary" disabled={busy||!approved||!report.can_save} onClick={()=>act(async()=>{
        attempt.current ||= crypto.randomUUID();setSaved(await api(`/api/sales/runs/${scenario.run_id}/order-comparison`,{snapshot_id:report.source_snapshot_id,review_token:report.review_token,reviewed:true,request_id:attempt.current}));
      })}>{busy?'Saving…':'Save scenario draft'}</Button>}</div>
    </Modal>
  </>;
}

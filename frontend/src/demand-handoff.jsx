import {t as uiText} from './localization.mjs';
import {useSmoothState} from './ui-motion.jsx';
import React,{useEffect,useRef,useState} from 'react';
import {releaseModes,releaseLabel,releaseDownload,releaseReady} from './demand-release-state.mjs';

const number=v=>new Intl.NumberFormat('en',{maximumFractionDigits:2}).format(v);

export function DemandHandoff({open,onClose,snapshotId,runId,outlook,canEdit,api,ui,releaseId}){
  const {Button,Modal,Field,Pick,Table,ErrorBox,Help}=ui;
  const [tab,setTab]=useSmoothState('draft'),[mode,setMode]=useState('remaining_forecast');
  const [receiver,setReceiver]=useState(''),[report,setReport]=useState(null),[approved,setApproved]=useState(false);
  const [items,setItems]=useState([]),[record,setRecord]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [page,setPage]=useState(0);
  const attempt=useRef(null);
  const panel=useRef(null);
  async function act(work){setBusy(true);setError('');try{await work();}catch(e){setError(e);}finally{setBusy(false);}}
  async function load(){const data=await api('/api/sales/releases?run_id='+encodeURIComponent(runId));setItems(data.releases);}
  async function detail(id){setRecord(await api('/api/sales/releases/'+id));setApproved(false);setPage(0);}
  useEffect(()=>{if(open){setTab(releaseId?'planning':'draft');setReport(null);setRecord(null);setApproved(false);setError('');setPage(0);attempt.current=null;act(releaseId?()=>detail(releaseId):load);}},[open,snapshotId,runId,releaseId]);
  useEffect(()=>{panel.current?.closest('[role="dialog"]')?.scrollTo({top:0});},[tab,record?.id,record?.state]);
  const body=()=>({snapshot_id:snapshotId,receiver:receiver.trim(),mode});
  function change(fn){fn();setReport(null);setApproved(false);setPage(0);attempt.current=null;}
  const months=record?.report.months||report?.months||[];
  const rows=record?.outlook.rows||outlook?.rows||[];
  const outputMode=record?.contract.mode||mode;
  return <Modal open={open} title={releaseId?uiText("Review demand"):uiText("Export demand")} wide dismissible={!busy} onClose={onClose} description={uiText("All customers, products and months. Already delivered quantities are excluded.")}>
    <div className="demand-handoff" ref={panel}>
    <ErrorBox error={error}/>
    {!releaseId&&<div className="demand-segments" role="group" aria-label={uiText("Export stage")}><button disabled={busy} aria-pressed={tab==='draft'} onClick={()=>setTab('draft')}>{uiText("Draft download")}</button><button disabled={busy} aria-pressed={tab==='planning'} onClick={()=>setTab('planning')}>{uiText("For planning")}</button></div>}
    {releaseId&&!record&&!error&&<p role="status">{uiText("Loading demand review…")}</p>}
    {tab==='draft'?<>
      <Field title={uiText("Does the receiving system already have these orders?")}><Pick label={uiText("Draft export contents")} value={mode} options={releaseModes.map(([value,label])=>[value,uiText(label)])} onChange={v=>change(()=>setMode(v))}/></Field>
      <small>{uiText("Draft only. Use For planning when the quantities need sign-off.")}</small>
      <div className="dialog-actions">{['xlsx','csv','json'].map(kind=>outlook?.can_export?<a className={'btn '+(kind==='xlsx'?'primary':'secondary')} key={kind} href={`/api/sales/inputs/${snapshotId}/export?mode=${mode}&kind=${kind}`}>{kind==='xlsx'?uiText("Download Excel"):kind.toUpperCase()}</a>:<Button key={kind} disabled>{kind.toUpperCase()}</Button>)}</div>
      {!outlook?.can_export&&<p role="alert">{uiText("Resolve the flagged inputs before exporting.")}</p>}
    </>:<>
      {record?<>
        <div className="section-heading"><h3>{record.contract.receiver}{' '}{uiText("· v")}{record.version}</h3><span>{uiText(releaseLabel(record))}</span></div>
        <p>{record.contract.mode==='remaining_forecast'?uiText("Expected demand only. The receiver already includes orders."):uiText("Open orders + expected demand. The receiver expects both.")}</p>
        <small>{uiText("Orders as of")}{' '}{record.report.as_of}{' '}{uiText("· Review again after")}{' '}{record.report.valid_until}</small>
        {record.blocked&&<p role="alert">{record.blocked}</p>}
        {record.superseded&&<p role="status">{uiText("A newer approved version replaces this one.")}</p>}
      </>:canEdit?<fieldset disabled={busy} className="release-controls">
        <Field title={uiText("Receiving system")}><input aria-label={uiText("Receiving planning system")} value={receiver} maxLength={120} onChange={e=>change(()=>setReceiver(e.target.value))}/></Field>
        <Field title={uiText("Does that system already have these orders?")}><Pick label={uiText("Planning release contents")} value={mode} options={releaseModes.map(([value,label])=>[value,uiText(label)])} onChange={v=>change(()=>setMode(v))}/></Field>
        <Button disabled={!receiver.trim()} onClick={()=>act(async()=>{setReport(await api('/api/sales/releases/preview',body()));setApproved(false);})}>{uiText("Review quantities")}</Button>
      </fieldset>:<p>{uiText("Select a submitted version below to review it.")}</p>}
      {!!months.length&&<Table headers={[uiText("Month"),uiText("Export quantity"),uiText("Open orders"),uiText("Still expected")]}>
        {months.map(r=><tr key={r.period+r.unit}><td>{r.period_label||r.period.slice(0,7)}</td><td>{number(r.quantity)} {r.unit}</td><td>{number(r.booked)}</td><td>{number(r.remaining)}</td></tr>)}
      </Table>}
      {!!months.length&&<details className="help-details"><summary>{uiText("Customer / product / month details")}</summary>
        <Table headers={[uiText("Customer"),uiText("SKU"),uiText("Month"),uiText("Calculated"),uiText("Open orders"),uiText("Still expected"),uiText("Export quantity")]}>
          {rows.slice(page*25,(page+1)*25).map(r=><tr key={r.customer+r.sku+r.period+r.unit}><td>{r.customer}</td><td>{r.sku}</td><td>{r.period_label||r.period.slice(0,7)}</td><td>{r.baseline==null?'—':number(r.baseline)}</td><td>{number(r.booked)}</td><td>{number(r.remaining)}</td><td>{number(outputMode==='remaining_forecast'?r.remaining:r.still_to_serve)} {r.unit}</td></tr>)}
        </Table>
        <div className="row-actions"><Button disabled={!page} onClick={()=>setPage(p=>p-1)}>{uiText("Previous")}</Button><small>{page*25+1}–{Math.min((page+1)*25,rows.length)}{' '}{uiText("of")}{' '}{rows.length}</small><Button disabled={(page+1)*25>=rows.length} onClick={()=>setPage(p=>p+1)}>{uiText("Next")}</Button></div>
      </details>}
      {!record&&report&&<>
        <small>{report.customers}{' '}{uiText("customers ·")}{' '}{report.rows}{' '}{uiText("customer/product/month rows. Delivered quantities excluded.")}</small>
        <label className="check-line"><input type="checkbox" disabled={busy} checked={approved} onChange={e=>setApproved(e.target.checked)}/>{uiText("I reviewed all customers, products, months and the receiving-system policy.")}</label>
        <div className="dialog-actions"><Button kind="primary" disabled={busy||!approved||!releaseReady(receiver,report,mode)} onClick={()=>act(async()=>{
          attempt.current ||= crypto.randomUUID();const saved=await api('/api/sales/releases',{...body(),reviewed:true,review_token:report.review_token,request_id:attempt.current});await load();await detail(saved.id);
        })}>{uiText("Submit for review")}</Button></div>
      </>}
      {record?.can_approve&&<>
        <label className="check-line"><input type="checkbox" disabled={busy} checked={approved} onChange={e=>setApproved(e.target.checked)}/>{record.demo_only?uiText("I reviewed this plan for a local demo, not company sign-off."):uiText("I reviewed the complete plan and receiving-system policy.")}</label>
        <div className="dialog-actions"><Button kind="primary" disabled={busy||!approved} onClick={()=>act(async()=>{
          await api('/api/sales/releases/'+record.id+'/approve',{reviewed:true,demo_confirmed:record.demo_only,review_token:record.report.review_token});await load();await detail(record.id);
        })}>{record.demo_only?uiText("Approve demo"):uiText("Approve release")}</Button></div>
      </>}
      {record?.state==='awaiting_review'&&!record.can_approve&&!record.blocked&&<small>{uiText("A different company reviewer must approve this version.")}</small>}
      {record?.can_export&&<div className="dialog-actions">{['xlsx','csv','json'].map(kind=><a key={kind} className={'btn '+(kind==='xlsx'?'primary':'secondary')} href={releaseDownload(record,kind)}>{kind==='xlsx'?uiText("Download approved Excel"):kind.toUpperCase()}</a>)}</div>}
      {record&&!releaseId&&<button className="home-text-link" disabled={busy} onClick={()=>{setRecord(null);setReport(null);setApproved(false);attempt.current=null;}}>{uiText("Back to releases")}</button>}
      {!!items.length&&<details className="help-details"><summary>{uiText("Saved releases (")}{items.length}) <Help text={uiText("Approved quantities are fixed. Newer orders, expired inputs or a replacement approval block old planning downloads.")}/></summary><Table headers={[uiText("Receiver"),uiText("Version"),uiText("Status"),'']}>
        {items.map(r=><tr key={r.id}><td>{r.contract.receiver}</td><td>{r.version}</td><td>{uiText(releaseLabel(r))}</td><td><Button disabled={busy} onClick={()=>act(()=>detail(r.id))}>{uiText("Review")}</Button></td></tr>)}
      </Table></details>}
    </>}
    </div>
  </Modal>;
}

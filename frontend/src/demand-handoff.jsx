import {apiLink} from './company-api.mjs';
import {t as uiText,unitLabel,i18n} from './localization.mjs';
import {useSmoothState} from './ui-motion.jsx';
import React,{useEffect,useRef,useState} from 'react';
import {releaseModes,releaseLabel,releaseDownload,releaseReady} from './demand-release-state.mjs';
import {Stack,Actions,Grid,DefinitionList,Disclosure,PageTabs,FieldGroup} from './ui-layout.jsx';

const number=v=>new Intl.NumberFormat(i18n.language,{maximumFractionDigits:2}).format(v);

export function DemandHandoff({open,onClose,snapshotId,runId,outlook,canEdit,api,ui,releaseId}){
  const {Button,Modal,Field,Pick,Table,ErrorBox,Help}=ui;
  const [tab,setTab]=useSmoothState('draft'),[mode,setMode]=useState('remaining_forecast');
  const [receiver,setReceiver]=useState(''),[report,setReport]=useState(null),[approved,setApproved]=useState(false);
  const [items,setItems]=useState([]),[record,setRecord]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [page,setPage]=useState(0);
  const attempt=useRef(null);
  async function act(work){setBusy(true);setError('');try{await work();}catch(e){setError(e);}finally{setBusy(false);}}
  async function load(){const data=await api('/api/sales/releases?run_id='+encodeURIComponent(runId));setItems(data.releases);}
  async function detail(id){setRecord(await api('/api/sales/releases/'+id));setApproved(false);setPage(0);}
  useEffect(()=>{if(open){setTab(releaseId?'planning':'draft');setReport(null);setRecord(null);setApproved(false);setError('');setPage(0);attempt.current=null;act(releaseId?()=>detail(releaseId):load);}},[open,snapshotId,runId,releaseId]);
  const body=()=>({snapshot_id:snapshotId,receiver:receiver.trim(),mode});
  function change(fn){fn();setReport(null);setApproved(false);setPage(0);attempt.current=null;}
  const months=record?.report.months||report?.months||[];
  const rows=record?.outlook.rows||outlook?.rows||[];
  const outputMode=record?.contract.mode||mode;
  return <Modal fixed open={open} title={releaseId?uiText("Review demand"):uiText("Export demand")} wide dismissible={!busy} onClose={onClose}>
    <Stack step={[tab,record?.id,record?.state].join(':')}>
    <ErrorBox error={error}/>
    {!releaseId&&<PageTabs value={tab} onChange={setTab} disabled={busy} label={uiText('Export stage')} items={[["draft","Draft download"],["planning","For planning"]]}/>}
    {releaseId&&!record&&!error&&<p role="status">{uiText("Loading demand review…")}</p>}
    {tab==='draft'?<>
      <Field title={uiText("Does the receiving system already have these orders?")}><Pick label={uiText("Draft export contents")} value={mode} options={releaseModes.map(([value,label])=>[value,uiText(label)])} onChange={v=>change(()=>setMode(v))}/></Field>
      <Help text={uiText("Draft only. Use For planning when the quantities need sign-off.")}/>
      <Actions>{['xlsx','csv','json'].map(kind=>outlook?.can_export?<a className={'btn '+(kind==='xlsx'?'primary':'secondary')} key={kind} href={apiLink(`/api/sales/inputs/${snapshotId}/export?mode=${mode}&kind=${kind}`)}>{kind==='xlsx'?uiText("Download Excel"):kind.toUpperCase()}</a>:<Button key={kind} disabled>{kind.toUpperCase()}</Button>)}</Actions>
      {!outlook?.can_export&&<p role="alert">{uiText("Resolve the flagged inputs before exporting.")}</p>}
    </>:<>
      {record?<>
        <DefinitionList rows={[[uiText('Receiver'),record.contract.receiver],[uiText('Version'),number(record.version)],[uiText('Status'),uiText(releaseLabel(record))]]}/>
        <p>{record.contract.mode==='remaining_forecast'?uiText("Expected demand only. The receiver already includes orders."):uiText("Open orders + expected demand. The receiver expects both.")}</p>
        <DefinitionList rows={[[uiText('Orders as of'),record.report.as_of],[uiText('Review again after'),record.report.valid_until]]}/>
        {record.blocked&&<p role="alert">{uiText(record.blocked)}</p>}
        {record.superseded&&<p role="status">{uiText("A newer approved version replaces this one.")}</p>}
      </>:canEdit?<FieldGroup disabled={busy}>
        <Grid>
        <Field title={uiText("Receiving system")}><input aria-label={uiText("Receiving planning system")} value={receiver} maxLength={120} onChange={e=>change(()=>setReceiver(e.target.value))}/></Field>
        <Field title={uiText("Does that system already have these orders?")}><Pick label={uiText("Planning release contents")} value={mode} options={releaseModes.map(([value,label])=>[value,uiText(label)])} onChange={v=>change(()=>setMode(v))}/></Field>
        </Grid>
        <Button disabled={!receiver.trim()} onClick={()=>act(async()=>{setReport(await api('/api/sales/releases/preview',body()));setApproved(false);})}>{uiText("Review quantities")}</Button>
      </FieldGroup>:<p>{uiText("Select a submitted version below to review it.")}</p>}
      {!!months.length&&<Table headers={[uiText("Month"),uiText("Export quantity"),uiText("Open orders"),uiText("Still expected")]}>
        {months.map(r=><tr key={r.period+r.unit}><td>{r.period_label||r.period.slice(0,7)}</td><td>{number(r.quantity)} {unitLabel(r.unit)}</td><td>{number(r.booked)}</td><td>{number(r.remaining)}</td></tr>)}
      </Table>}
      {!!months.length&&<Disclosure title={uiText("Customer / product / month details")}>
        <Table headers={[uiText("Customer"),uiText("SKU"),uiText("Month"),uiText("Calculated"),uiText("Open orders"),uiText("Still expected"),uiText("Export quantity")]}>
          {rows.slice(page*25,(page+1)*25).map(r=><tr key={r.customer+r.sku+r.period+r.unit}><td>{r.customer}</td><td>{r.sku}</td><td>{r.period_label||r.period.slice(0,7)}</td><td>{r.baseline==null?'—':number(r.baseline)}</td><td>{number(r.booked)}</td><td>{number(r.remaining)}</td><td>{number(outputMode==='remaining_forecast'?r.remaining:r.still_to_serve)} {unitLabel(r.unit)}</td></tr>)}
        </Table>
        <Actions><Button disabled={!page||busy} onClick={()=>setPage(p=>p-1)}>{uiText("Previous")}</Button><span>{number(page*25+1)}–{number(Math.min((page+1)*25,rows.length))}{' '}{uiText("of")}{' '}{number(rows.length)}</span><Button disabled={busy||(page+1)*25>=rows.length} onClick={()=>setPage(p=>p+1)}>{uiText("Next")}</Button></Actions>
      </Disclosure>}
      {!record&&report&&<>
        <DefinitionList rows={[[uiText('Customers'),number(report.customers)],[uiText('Customer/product/month rows'),number(report.rows)]]}/>
        <label className="ui-check"><input type="checkbox" disabled={busy} checked={approved} onChange={e=>setApproved(e.target.checked)}/>{uiText("I reviewed all customers, products, months and the receiving-system policy.")}</label>
        <Actions><Button kind="primary" disabled={busy||!approved||!releaseReady(receiver,report,mode)} onClick={()=>act(async()=>{
          attempt.current ||= crypto.randomUUID();const saved=await api('/api/sales/releases',{...body(),reviewed:true,review_token:report.review_token,request_id:attempt.current});await load();await detail(saved.id);
        })}>{uiText("Submit for review")}</Button></Actions>
      </>}
      {record?.can_approve&&<>
        <label className="ui-check"><input type="checkbox" disabled={busy} checked={approved} onChange={e=>setApproved(e.target.checked)}/>{record.demo_only?uiText("I reviewed this plan for a local demo, not company sign-off."):uiText("I reviewed the complete plan and receiving-system policy.")}</label>
        <Actions><Button kind="primary" disabled={busy||!approved} onClick={()=>act(async()=>{
          await api('/api/sales/releases/'+record.id+'/approve',{reviewed:true,demo_confirmed:record.demo_only,review_token:record.report.review_token});await load();await detail(record.id);
        })}>{record.demo_only?uiText("Approve demo"):uiText("Approve release")}</Button></Actions>
      </>}
      {record?.state==='awaiting_review'&&!record.can_approve&&!record.blocked&&<p>{uiText("A different company reviewer must approve this version.")}</p>}
      {record?.can_export&&<Actions>{['xlsx','csv','json'].map(kind=><a key={kind} className={'btn '+(kind==='xlsx'?'primary':'secondary')} href={apiLink(releaseDownload(record,kind))}>{kind==='xlsx'?uiText("Download approved Excel"):kind.toUpperCase()}</a>)}</Actions>}
      {record&&!releaseId&&<Button kind="ghost" disabled={busy} onClick={()=>{setRecord(null);setReport(null);setApproved(false);attempt.current=null;}}>{uiText("Back to releases")}</Button>}
      {!!items.length&&<Disclosure title={uiText('Saved releases ({{count}})',{count:number(items.length)})}><Help text={uiText("Approved quantities are fixed. Newer orders, expired inputs or a replacement approval block old planning downloads.")}/><Table headers={[uiText("Receiver"),uiText("Version"),uiText("Status"),'']}>
        {items.map(r=><tr key={r.id}><td>{r.contract.receiver}</td><td>{r.version}</td><td>{uiText(releaseLabel(r))}</td><td><Button disabled={busy} onClick={()=>act(()=>detail(r.id))}>{uiText("Review")}</Button></td></tr>)}
      </Table></Disclosure>}
    </>}
    </Stack>
  </Modal>;
}

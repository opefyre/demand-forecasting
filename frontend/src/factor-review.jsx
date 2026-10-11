import {t as uiText} from './localization.mjs';
import React,{useEffect,useRef,useState} from 'react';
import {Stack,Actions,DefinitionList,Disclosure} from './ui-layout.jsx';

export function FactorReview({run,api,ui,canEdit,onSaved,fmt,date}){
  const {Button,Table,Modal,ErrorBox}=ui;
  const [report,setReport]=useState(null),[error,setError]=useState(''),[open,setOpen]=useState(false),[busy,setBusy]=useState(false);
  const request=useRef(null),submitting=useRef(false);
  useEffect(()=>{let live=true;api(`/api/runs/${run.run_id}/factors`).then(r=>live&&setReport(r)).catch(e=>live&&setError(e.message));return()=>{live=false;};},[run.run_id]);
  async function compare(){
    if(submitting.current||!canEdit)return;
    submitting.current=true;setBusy(true);setError('');
    try{
      request.current ||= crypto.randomUUID();
      const saved=await api(`/api/runs/${run.run_id}/factor-comparison`,{reviewed:true,request_id:request.current});
      setOpen(false);await onSaved(saved);
    }catch(e){setError(e.message);}finally{submitting.current=false;setBusy(false);}
  }
  return <Disclosure title={uiText('Factors & source coverage')}><Stack>
    {!open&&<ErrorBox error={error}/>}
    {!report&&!error&&<p role="status">{uiText('Checking factor inputs…')}</p>}
    {report&&<>
      <DefinitionList rows={[[uiText('Historical file:'),`${date(report.history_start)} – ${date(report.history_end)}`],[uiText('Imported'),date(report.history_captured_at)],
        [uiText('Future inputs:'),`${date(report.forecast_start)} – ${date(report.forecast_end)}`]]}/>
      <Table headers={[uiText('Factor'),uiText('Blank source values'),uiText('Future values'),uiText('Location / unit')]}>
        {report.factors.map(f=><tr key={f.factor}>
          <td>{f.factor.replaceAll('_',' ')}<small className="muted">{f.source}</small></td>
          <td>{fmt(f.history_missing,0)} {uiText('of')} {fmt(f.history_rows,0)} {uiText('rows')}<small className="muted">{uiText('Last recorded:')} {f.latest_recorded_period?date(f.latest_recorded_period):uiText('Missing')}</small></td>
          <td>{fmt(f.future_provided,0)} {uiText('provided ·')} {fmt(f.future_filled,0)} {uiText('filled')}<small className="muted">{uiText({require:'No filling',carry:'Fill with last value',median:'Fill with typical value'}[f.future_policy]||'Missing')}</small></td>
          <td>{f.geography||uiText('Location not specified')}<small className="muted">{f.unit||uiText('Unit not specified')}</small></td>
        </tr>)}
      </Table>
      <Disclosure title={uiText('How are factors tested?')}>
        <p>{uiText(report.test_note)}</p><p>{uiText(report.availability_note)}</p><p>{uiText(report.future_note)}</p>
        {report.warnings.map((w,i)=><p key={i}>{uiText(w)}</p>)}
      </Disclosure>
      {report.comparison_blocker?<p role="status">{uiText(report.comparison_blocker)}</p>:<Actions><Button disabled={!canEdit||busy} onClick={()=>setOpen(true)}>{uiText('Compare without factors')}</Button></Actions>}
    </>}
  </Stack>
    <Modal title={uiText('Compare without extra factors')} open={open} onClose={()=>!busy&&setOpen(false)}><Stack>
      <ErrorBox error={error}/><p>{uiText('Keep the same sales history and calendar. Review customers and orders before calculating.')}</p>
      <Actions><Button disabled={busy} onClick={()=>setOpen(false)}>{uiText('Cancel')}</Button><Button kind="primary" disabled={busy||!canEdit} onClick={compare}>{uiText(busy?'Saving…':'Continue')}</Button></Actions>
    </Stack></Modal>
  </Disclosure>;
}

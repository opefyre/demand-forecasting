import {t as uiText} from './localization.mjs';
import React, {useEffect,useRef,useState} from 'react';

export function FactorReview({run,api,ui,canEdit,onSaved,fmt,date}) {
  const {Button,Table,Modal,ErrorBox}=ui;
  const [report,setReport]=useState(null),[error,setError]=useState(''),[open,setOpen]=useState(false),[busy,setBusy]=useState(false);
  const request=useRef(null);
  useEffect(()=>{let live=true;api(`/api/runs/${run.run_id}/factors`).then(r=>live&&setReport(r)).catch(e=>live&&setError(e.message));return()=>{live=false;};},[run.run_id]);
  async function compare(){
    setBusy(true);setError('');
    try{
      request.current ||= crypto.randomUUID();
      const saved=await api(`/api/runs/${run.run_id}/factor-comparison`,{reviewed:true,request_id:request.current});
      await onSaved(saved,request.current);setOpen(false);
    }catch(e){setError(e.message);}finally{setBusy(false);}
  }
  return <details className="surface disclosure factor-review">
    <summary>{uiText("Factors & source coverage")}</summary>
    <div className="detail-body">
      {!open&&<ErrorBox error={error}/>}
      {!report&&!error&&<p role="status">{uiText("Checking factor inputs…")}</p>}
      {report&&<>
        <p>{uiText("Historical file:")}{' '}{date(report.history_start)} – {date(report.history_end)}{uiText(". Imported")}{' '}{date(report.history_captured_at)}.</p>
        <Table headers={[uiText("Factor"),uiText("Blank source values"),uiText("Future values"),uiText("Location / unit")]}>
          {report.factors.map(f=><tr key={f.factor}>
            <td>{f.factor.replaceAll('_',' ')}<small className="muted">{f.source}</small></td>
            <td>{fmt(f.history_missing,0)}{' '}{uiText("of")}{' '}{fmt(f.history_rows,0)}{' '}{uiText("rows")}<small className="muted">{uiText("Last recorded:")}{' '}{f.latest_recorded_period?date(f.latest_recorded_period):uiText("Missing")}</small></td>
            <td>{fmt(f.future_provided,0)}{' '}{uiText("provided ·")}{' '}{fmt(f.future_filled,0)}{' '}{uiText("filled")}<small className="muted">{fmt(f.future_expected,0)}{' '}{uiText("item-period values ·")}{' '}{{require:'No filling',carry:'Fill with last value',median:'Fill with typical value'}[f.future_policy]}</small></td>
            <td>{f.geography||'Location not specified'}<small className="muted">{f.unit||'Unit not specified'}</small></td>
          </tr>)}
        </Table>
        <p className="muted">{uiText("Future inputs:")}{' '}{date(report.forecast_start)} – {date(report.forecast_end)} · {report.future_captured_at?`Imported ${date(report.future_captured_at)}`:uiText("No future file")}. {report.future_note}</p>
        <details className="help-details"><summary>{uiText("How are factors tested?")}</summary><p>{report.test_note}</p><p>{report.availability_note}</p>{report.warnings.map((w,i)=><p key={i}>{w}</p>)}</details>
        {report.comparison_blocker?<p role="status">{report.comparison_blocker}</p>:<div className="dialog-actions"><Button disabled={!canEdit||busy} onClick={()=>setOpen(true)}>{uiText("Compare without factors")}</Button></div>}
      </>}
    </div>
    <Modal title={uiText("Compare without extra factors")} open={open} onClose={()=>!busy&&setOpen(false)} description={uiText("Recalculate the same history, calendar and periods without extra factors. Automatic method selection, if chosen, runs again. Customer orders and the original forecast stay unchanged.")}>
      <ErrorBox error={error}/>
      <p>{uiText("This compares model estimates, not an order-adjusted plan. A lower past error does not guarantee future accuracy.")}</p>
      <div className="dialog-actions"><Button disabled={busy} onClick={()=>setOpen(false)}>{uiText("Cancel")}</Button><Button kind="primary" disabled={busy} onClick={compare}>{busy?uiText("Starting…"):uiText("Calculate comparison")}</Button></div>
    </Modal>
  </details>;
}

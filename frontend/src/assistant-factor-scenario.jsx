import {t as uiText,pluralSuffix} from './localization.mjs';
import React,{useState} from 'react';
import {planningMonth} from './planning-calendar.mjs';

export function AssistantFactorScenario({action,result,expired,busy,canEdit,onConfirm,ui,basis='gregorian'}) {
  const {Button,Table}=ui;
  const [approved,setApproved]=useState(false);
  const p=action.preview;
  return <section className="ai-proposal ai-factor-proposal">
    <h3>{uiText("Compare this factor scenario?")}</h3>
    <p>{p.scope} · {p.method.replace(/^model:/,'')}</p>
    <div className="ai-factor-sources">{p.factors.map((f,i)=><div key={i}><strong>{f.factor}</strong><small>{f.geography} · {f.unit} · {f.lag_months}{' '}{uiText("month")}{pluralSuffix(f.lag_months)}{' '}{uiText("earlier")}</small></div>)}</div>
    <details className="help-details"><summary>{uiText("Monthly inputs")}</summary>
      <Table headers={[uiText("Factor"),uiText("Month"),uiText("Value"),uiText("Source")]}>{p.future_rows.map((r,i)=><tr key={i}><td>{r.factor}</td><td>{planningMonth(r.sales_month,basis)}</td><td>{r.value??'Unknown'} {r.unit}</td><td>{r.treatment==='planning_assumption'?uiText("Your assumption"):uiText("Saved observation")}</td></tr>)}</Table>
    </details>
    {p.retrospective&&<p className="source-notice">{uiText("What-if comparison only. Downloaded history cannot prove improved accuracy.")}</p>}
    <details className="help-details"><summary>{uiText("Source timing & checks")}</summary><p>{p.policy}</p>{p.factors.map((f,i)=><p key={i}>{f.factor}: {f.policy}</p>)}{p.warnings.map((w,i)=><p key={i}>{typeof w==='string'?w:JSON.stringify(w)}</p>)}</details>
    {result?.job?<p role="status">{uiText("Comparison queued. Open it from the progress panel when ready. Orders have not been copied.")}</p>:expired?<p>{uiText("This proposal expired. Ask again to refresh it.")}</p>:<>
      <label className="check-line"><input type="checkbox" checked={approved} disabled={busy||!canEdit} onChange={e=>setApproved(e.target.checked)}/>{uiText("I reviewed the locations, timing, customer scope and future values.")}</label>
      <Button kind="primary" disabled={!approved||busy||!canEdit} onClick={onConfirm}>{busy?uiText("Starting…"):uiText("Confirm & calculate")}</Button>
    </>}
  </section>;
}

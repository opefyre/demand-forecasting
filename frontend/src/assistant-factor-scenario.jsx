import {t as uiText,i18n,unitLabel,pluralSuffix} from './localization.mjs';
import React,{useState} from 'react';
import {planningMonth} from './planning-calendar.mjs';
import {Panel,DefinitionList,Disclosure,Actions} from './ui-layout.jsx';
import {methodName} from './method-comparison.jsx';

export function AssistantFactorScenario({action,result,expired,busy,canEdit,onConfirm,ui,basis='gregorian'}) {
  const {Button,Table}=ui;
  const [approved,setApproved]=useState(false);
  const p=action.preview;
  const quantity=value=>value==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:3}).format(value);
  return <Panel title={uiText("Compare this factor scenario?")}>
    <p>{p.scope} · {methodName(p.method)}</p>
    <DefinitionList rows={p.factors.map(f=>[f.factor,<span>{f.geography} · {unitLabel(f.unit)} · {quantity(f.lag_months)} {uiText("month")}{pluralSuffix(f.lag_months)} {uiText("earlier")}</span>])}/>
    <Disclosure title={uiText("Monthly inputs")}>
      <Table headers={[uiText("Factor"),uiText("Month"),uiText("Value"),uiText("Source")]}>{p.future_rows.map((r,i)=><tr key={i}><td>{r.factor}</td><td>{planningMonth(r.sales_month,basis)}</td><td>{quantity(r.value)} {unitLabel(r.unit)}</td><td>{r.treatment==='planning_assumption'?uiText("Your assumption"):uiText("Saved observation")}</td></tr>)}</Table>
    </Disclosure>
    {p.retrospective&&<p className="source-notice">{uiText("What-if comparison only. Downloaded history cannot prove improved accuracy.")}</p>}
    <Disclosure title={uiText("Source timing & checks")}><p>{uiText(p.policy)}</p>{p.factors.map((f,i)=><p key={i}>{f.factor}: {uiText(f.policy)}</p>)}{p.warnings.map((w,i)=><p key={i}>{typeof w==='string'?uiText(w):JSON.stringify(w)}</p>)}</Disclosure>
    {result?.job?<p role="status">{uiText("Comparison queued. Open it from the progress panel when ready. Orders have not been copied.")}</p>:expired?<p>{uiText("This proposal expired. Ask again to refresh it.")}</p>:<>
      <label className="ui-check"><input type="checkbox" checked={approved} disabled={busy||!canEdit} onChange={e=>setApproved(e.target.checked)}/>{uiText("I reviewed the locations, timing, customer scope and future values.")}</label>
      <Actions><Button kind="primary" disabled={!approved||busy||!canEdit} onClick={onConfirm}>{busy?uiText("Starting…"):uiText("Confirm & calculate")}</Button></Actions>
    </>}
  </Panel>;
}

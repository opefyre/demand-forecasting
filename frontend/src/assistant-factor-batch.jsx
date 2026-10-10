import {t as uiText,i18n,unitLabel} from './localization.mjs';
import React,{useState,useEffect} from 'react';
import {BatchGroupTable} from './factor-batch.jsx';
import {planningMonth} from './planning-calendar.mjs';
import {Panel,Stack,Disclosure,Actions} from './ui-layout.jsx';

export function BatchJobReceipt({status,ui,onOpen}){
  const {Button}=ui;
  if(status.error)return <p role="alert">{uiText("Could not check this calculation. Open the progress panel or reopen this chat.")}</p>;
  if(status.state==='succeeded'&&status.run_id)return <><p>{uiText("Forecast ready. Review current orders next.")}</p><Button kind="primary" onClick={()=>onOpen?.(status.run_id)}>{uiText("Review demand & orders")}</Button></>;
  if(['failed','cancelled','interrupted'].includes(status.state))return <p role="status">{uiText("Calculation")}{' '}{uiText(({failed:'Failed',cancelled:'Cancelled',interrupted:'Interrupted'})[status.state])}{uiText(". No combined result was published. Check the progress panel before retrying.")}</p>;
  return <p role="status">{status.state==='queued'?uiText("Waiting to calculate…"):uiText("Calculating the groups…")}{' '}{uiText("Orders are unchanged.")}</p>;
}

function BatchProgress({api,turnId,index,ui,onOpen}){
  const [status,setStatus]=useState({state:'queued'});
  useEffect(()=>{
    let alive=true,timer;
    async function check(){try{const next=await api('/api/ai/turns/'+turnId+'/actions/'+index+'/progress');
      if(!alive)return;setStatus(next);
      if(!['succeeded','failed','cancelled','interrupted'].includes(next.state))timer=setTimeout(check,5000);
    }catch{if(alive)setStatus({error:true});}}
    check();return()=>{alive=false;clearTimeout(timer);};
  },[api,turnId,index]);
  return <BatchJobReceipt status={status} ui={ui} onOpen={onOpen}/>;
}

export function AssistantFactorBatchCard({action,result,expired,busy,canEdit,onConfirm,ui,basis='gregorian',api,turnId,index,onOpen}){
  const {Button,Table}=ui,[approved,setApproved]=useState(false),p=action.preview;
  const metadata=Object.fromEntries(p.groups.flatMap(g=>g.scope.map(s=>[s.id,s])));
  const groups=p.groups.map((g,i)=>({id:String(i),scenario_provenance:{alignment:{series_ids:g.scope.map(s=>s.id),method:g.method,factors:g.factors}}}));
  const quantity=value=>value==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:3}).format(value);
  return <Panel title={uiText("Run this monthly forecast?")}>
    <BatchGroupTable groups={groups} run={{metadata}} ui={ui}/>
    <p>{quantity(p.unchanged_series_ids.length)}{' '}{uiText("other products keep their baseline. Orders are reviewed afterwards.")}</p>
    <Disclosure title={uiText("Future values & source checks")}>
      {p.groups.map((g,i)=><Stack key={i}><strong>{g.scope.map(s=>s.customer+' · '+s.sku).join(', ')}</strong>
        <Table headers={[uiText("Factor"),uiText("Month"),uiText("Value"),uiText("Source")]}>{g.future_rows.map((r,j)=><tr key={j}><td>{r.factor}</td><td>{planningMonth(r.sales_month,basis)}</td><td>{quantity(r.value)} {unitLabel(r.unit)}</td><td>{r.treatment==='planning_assumption'?uiText("Your assumption"):uiText("Saved observation")}</td></tr>)}</Table>
        {g.factors.map((f,j)=><p key={j}>{f.factor} · {f.geography} · {quantity(f.lag_months)}{' '}{uiText("months earlier.")}{' '}{uiText(f.policy)}</p>)}
        {g.retrospective&&<p>{uiText("What-if only: downloaded history does not prove improved accuracy.")}</p>}
      </Stack>)}<p>{uiText(p.policy)}</p>
    </Disclosure>
    {result?.job?<BatchProgress api={api} turnId={turnId} index={index} ui={ui} onOpen={onOpen}/>:expired?<p>{uiText("This proposal expired. Ask again.")}</p>:<>
      <label className="ui-check"><input type="checkbox" disabled={busy||!canEdit} checked={approved} onChange={e=>setApproved(e.target.checked)}/>{uiText("I reviewed every group, source timing, location and future value.")}</label>
      <Actions><Button kind="primary" disabled={!approved||busy||!canEdit} onClick={onConfirm}>{busy?uiText("Starting…"):uiText("Confirm & calculate")}</Button></Actions>
    </>}
  </Panel>;
}

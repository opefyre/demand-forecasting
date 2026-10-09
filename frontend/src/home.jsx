import {localState} from './workspace-storage.mjs';
import {t as uiText} from './localization.mjs';
import React,{useState} from 'react';
import { ArrowRight, ChartLineUp, Play } from '@phosphor-icons/react';
import { workflowState, pendingImport } from './workflow-state.mjs';
import {RecurringForecasts} from './recurring-forecasts.jsx';

export function Home({run,runs,datasets,importNew,navigate,openRun,canEdit,canAdmin,ui,api,refresh,startUpdate,updates=[],resumeUpdate}) {
  const {Button} = ui;
  const [cycleUpdates,setCycleUpdates]=useState([]);
  const recentUpdates=updates.filter(u=>!cycleUpdates.includes(u.id));
  const draft = pendingImport(localState.getItem('demandlab.importDraft'));
  const state = workflowState({run,runs,datasets,hasDraft:draft.exists});
  const next = {
    start: {eyebrow:'Start here',title:'Turn sales data into your next forecast.',body:'Bring your sales history. We’ll help you turn it into demand by customer, product and month.',action:'Add sales history',onClick:importNew},
    import: {eyebrow:draft.sample?'Sample workspace':'Continue where you left off',title:draft.sample?'Finish exploring the sample.':'Your import is waiting for you.',body:'Finish checking your columns and settings. Nothing is calculated until you confirm.',action:draft.sample?'Continue sample import':'Continue import',onClick:importNew},
    calculate: {eyebrow:'Your next step',title:'Your data is ready. Create a forecast.',body:'Open your saved sales data, check the period you want to forecast, and start the calculation.',action:'Open sales data',onClick:()=>navigate('data')},
    review: {eyebrow:'Your forecasting workspace',title:'Review your sales forecast.',body:'Update orders, check demand by customer and product, then export your plan.',action:'Open forecast',onClick:()=>openRun(state.current.run_id,'demand')},
  }[state.stage];
  return <div className="home-page">
    <div className="home-title"><h1>{uiText("Home")}</h1><span>{uiText("Sales & demand planning")}</span></div>
    <section className="home-hero">
      <div className="home-eyebrow">{uiText(canEdit ? next.eyebrow : 'Your workspace')}</div>
      <h2>{uiText(canEdit ? next.title : 'Review your team’s demand forecast.')}</h2>
      <p>{uiText(canEdit ? next.body : 'Open a saved forecast to inspect demand. A planner manages data and calculations.')}</p>
      <div className="home-hero-actions">
        {canEdit ? <Button kind="primary" onClick={next.onClick}>{uiText(next.action)}<ArrowRight size={18}/></Button> : state.current && <Button kind="primary" onClick={()=>openRun(state.current.run_id,'demand')}>{uiText("Open forecast")}<ArrowRight size={18}/></Button>}
        {state.sample && <Button kind="ghost" onClick={()=>openRun(state.sample.run_id,'demand')}><Play size={18}/>{uiText("Explore sample")}</Button>}
        {canEdit&&state.stage==='review'&&startUpdate&&<Button kind="ghost" onClick={()=>startUpdate(state.current.run_id)}>{uiText("Update forecast")}</Button>}
      </div>
    </section>
    <button className="home-text-link" onClick={()=>navigate('help')}>{uiText("New here? See how it works")}<ArrowRight size={16}/></button>
    {api&&<RecurringForecasts api={api} ui={ui} run={run} runs={runs} datasets={datasets} canAdmin={canAdmin} resumeUpdate={resumeUpdate} refresh={refresh} navigate={navigate} onCycles={setCycleUpdates}/>}
    {canEdit&&recentUpdates.length>0&&<section className="home-recent"><div className="home-section-heading"><h2>{uiText("Recent forecast updates")}</h2></div>{recentUpdates.slice(0,3).map(value=><button className="home-recent-row" key={value.id} onClick={()=>resumeUpdate(value.id)}><ChartLineUp size={22}/><span><strong>{value.name}</strong><small>{value.classification==='synthetic_sample'?'Sample · ':''}{value.stage==='ready'?uiText("Review & export"):'Next: '+({history:'sales history',forecast:'calculation',calculating:'calculation result',factors:'external factors',factor_calculating:'factor comparison',orders:'customer orders',review:'changes'})[value.stage]}</small></span><ArrowRight size={18}/></button>)}</section>}
    {!!state.realRuns.length&&<section className="home-recent"><div className="home-section-heading"><h2>{uiText("Continue an existing forecast")}</h2></div>{state.realRuns.slice(0,3).map(r=><button className="home-recent-row" key={r.run_id} onClick={()=>openRun(r.run_id,'demand')}><ChartLineUp size={22}/><span><strong>{r.name||'Sales forecast'}</strong><small>{r.created_at?new Date(r.created_at*1000).toLocaleDateString('en',{month:'short',day:'numeric',year:'numeric'}):uiText("Saved forecast")}</small></span><ArrowRight size={18}/></button>)}</section>}
  </div>;
}

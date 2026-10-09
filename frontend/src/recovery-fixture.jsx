// Development-only acceptance fixture: no real API, provider, credentials or business writes.
// Not imported by the production entry point or added to application navigation.
import React from 'react';
import {createRoot} from 'react-dom/client';
import {SalesDemand} from './sales-demand.jsx';
import {MonthlyRefresh} from './monthly-refresh.jsx';
import {LiveSources} from './live-sources.jsx';
import {RequestRecovery} from './request-recovery.jsx';
import {responseFailure} from './request-errors.mjs';
import {changeInterfaceLanguage,applyInterfaceLanguage} from './localization.mjs';
import "./design-system.css";
const run={run_id:'recovery-demo',dataset_name:'Synthetic recovery demo',source_classification:'synthetic_sample',
  input_manifest:{settings:{month_basis:'gregorian'}},run_settings:{frequency:'monthly'},forecast:[]};
const outlook={fresh:true,can_export:true,warnings:[],as_of:'2026-10-07',valid_until:'2026-11-07',orders:[],
  rows:[{customer:'Customer Home',sku:'0001',period:'2026-11-01',unit:'tonnes',baseline:10,booked:3,fulfilled:0,remaining:7,total:10,status:'partial'}]};
const ui={
  Button:({children,kind='secondary',...props})=><button className={'btn '+kind} {...props}>{children}</button>,
  Pick:({label,options,value,onChange,disabled})=><select aria-label={label} value={value} disabled={disabled} onChange={e=>onChange?.(e.target.value)}>{options.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>,
  ErrorBox:RequestRecovery,Modal:()=>null,Help:()=>null,
  Table:({headers,children})=><table><thead><tr>{headers.map((h,i)=><th key={i}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table>,
  Field:({title,children})=><label>{title}{children}</label>,
};
function Fixture(){
  const [mode,setMode]=React.useState('inputs'),[revision,setRevision]=React.useState(0),[language,setLanguage]=React.useState('en');
  const [counts,setCounts]=React.useState({reads:0,writes:0});
  const attempts=React.useRef({});
  const reset=next=>{attempts.current={};setCounts({reads:0,writes:0});setMode(next);setRevision(v=>v+1);};
  const api=React.useCallback(async(url,body)=>{
    setCounts(c=>({...c,[body?'writes':'reads']:c[body?'writes':'reads']+1}));
    if(body)throw Error('Fixture prohibits all writes');
    const n=(attempts.current[url]||0)+1;attempts.current[url]=n;
    const failing=(mode==='inputs'||mode==='permission')&&url.endsWith('/inputs')||mode==='outlook'&&url.endsWith('/outlook')||mode==='monthly'&&url.startsWith('/api/forecast-updates/')||mode==='sources'&&url==='/api/live-sources';
    if(failing&&(mode==='permission'||n===1)){const error=responseFailure(mode==='permission'?403:503,{detail:'Synthetic temporary failure · Customer Home · 0001'});error.operation='read';throw error;}
    if(url.endsWith('/inputs'))return {snapshots:[{id:'synthetic-orders',name:'Demo orders',as_of:'2026-10-07'}]};
    if(url.endsWith('/outlook'))return structuredClone(outlook);
    if(url.endsWith('/views'))return {views:[]};
    if(url==='/api/live-sources')return {sources:[]};
    if(url.startsWith('/api/forecast-updates/'))return {id:'synthetic-update',stage:'history',revision:1,base_run_id:'recovery-demo',base_dataset_id:'synthetic-history',classification:'synthetic_sample',name:'Synthetic monthly update'};
    if(url.startsWith('/api/runs/'))return run;
    throw Error('Unexpected fixture read: '+url);
  },[mode,revision]);
  return <div className="recovery-fixture">
    <h1>Synthetic recovery test · not client data</h1>
    <div className="row-actions recovery-fixture-actions">{[['inputs','Demand read failure'],['outlook','Order version read failure'],['monthly','Monthly update read failure'],['sources','Live source read failure'],['permission','Reader access failure']].map(([v,l])=><button key={v} className="btn secondary" onClick={()=>reset(v)}>{l}</button>)}
      <button className="btn secondary" onClick={async()=>{const next=language==='en'?'fa':'en';await changeInterfaceLanguage(next);applyInterfaceLanguage(document,next);setLanguage(next);}}>English / فارسی</button>
    </div><p role="status" aria-label="Fixture request counts">Reads: {counts.reads} · Writes: {counts.writes}</p>
    {mode==='monthly'?<MonthlyRefresh key={revision} id="synthetic-update" api={api} ui={ui} datasets={[{id:'synthetic-history',name:'Synthetic history',settings:{},review:{summary:{end:'2026-09-01'}}}]} canEdit={true} onClose={()=>reset('inputs')}/>:
      mode==='sources'?<LiveSources key={revision} api={api} ui={ui} canAdmin={false}/>:
      <SalesDemand key={revision} api={api} ui={ui} run={run} runs={[]} canEdit={mode!=='permission'} navigate={()=>{}}/>}
  </div>;
}
createRoot(document.getElementById('root')).render(<Fixture/>);

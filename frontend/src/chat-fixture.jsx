import {localState} from './workspace-storage.mjs';
// Development-only UI acceptance fixture. No network requests, provider calls or real data.
// This entry point is not imported or built into the production app.
import React,{useState,useRef,useMemo} from 'react';
import {createRoot} from 'react-dom/client';
import * as Dialog from '@radix-ui/react-dialog';
import * as Tooltip from '@radix-ui/react-tooltip';
import {House,Database,ChartLineUp,Question,GearSix} from '@phosphor-icons/react';
import {AssistantWorkspace} from './assistant-workspace.jsx';
import {AppSidebar,readSidebarPreference,saveSidebarPreference} from './ui-sidebar.jsx';
import {MotionPresence} from './ui-motion.jsx';
import {changeInterfaceLanguage,applyInterfaceLanguage,t as uiText} from './localization.mjs';
import './design-system.css';

const ui={
  Button:({kind='secondary',children,...props})=><button className={'btn '+kind} {...props}>{children}</button>,
  ErrorBox:({error})=>error?<p role="alert">{error}</p>:null,
  Modal:({open,onClose,title,description,children})=><Dialog.Root open={open} onOpenChange={value=>{if(!value)onClose();}}><Dialog.Portal><Dialog.Overlay className="modal-overlay"/><Dialog.Content className="modal"><Dialog.Title>{title}</Dialog.Title><Dialog.Description>{description||title}</Dialog.Description>{children}<button type="button" className="btn" onClick={onClose}>Close</button></Dialog.Content></Dialog.Portal></Dialog.Root>,
};
const datasets=[{id:'synthetic-chat-history',name:'Synthetic sales history',settings:{month_basis:'gregorian'},sources:{history:'synthetic-file'}},
  {id:'synthetic-alternate-history',name:'Synthetic alternate history',settings:{month_basis:'gregorian'},sources:{history:'synthetic-alternate-file'}}];
function initialChats(){
  const turns=[];
  for(let i=0;i<12;i++)turns.push({id:'synthetic-saved-'+i,question:i?'Synthetic follow-up '+i:'Synthetic monthly forecast',answer:'Synthetic saved conversation — no forecast was calculated. Message '+(i+1),actions:[],previous_turn_id:i?'synthetic-saved-'+(i-1):null,run_id:null,snapshot_id:null,dataset_id:'synthetic-chat-history',chat_id:'synthetic-saved-0'});
  turns.push({id:'synthetic-alternate',question:'Synthetic alternate customer',answer:'Synthetic alternate history — this chat keeps its own data selection.',actions:[],run_id:null,snapshot_id:null,dataset_id:'synthetic-alternate-history',chat_id:'synthetic-alternate'});
  return turns;
}
function Fixture(){
  const [language,setLanguage]=useState('en'),[destination,setDestination]=useState(''),[dataView,setDataView]=useState(''),[sent,setSent]=useState(0);
  const [collapsed,setCollapsed]=useState(()=>readSidebarPreference(localState));
  const [toast,setToast]=useState('');
  const fail=useRef(false),saved=useRef(initialChats()),counter=useRef(0),lastContext=useRef('');
  function chain(head){const turns=[];while(head){const turn=saved.current.find(t=>t.id===head);if(!turn)throw Error('Synthetic chat not found');turns.unshift(turn);head=turn.previous_turn_id;}return turns;}
  const api=useMemo(()=>async(url,payload)=>{
    if(url==='/api/ai/status')return {ready:true,consent_id:'0'.repeat(64),provider_label:'Synthetic local fixture (no network)'};
    if(url.startsWith('/api/ai/conversations?')){const groups=new Map();for(const turn of saved.current){const first=saved.current.find(t=>t.id===turn.chat_id);groups.set(turn.chat_id,{id:turn.chat_id,head_id:turn.id,title:first.question});}return {chats:[...groups.values()].reverse(),next_offset:null};}
    if(url.startsWith('/api/ai/conversations/')){const head=url.split('/').at(-1),turns=chain(head),last=turns.at(-1);return {turns:structuredClone(turns),head_id:head,context:{run_id:last.run_id,snapshot_id:last.snapshot_id,dataset_id:last.dataset_id}};}
    if(url==='/api/ai/chat'){
      await new Promise(resolve=>setTimeout(resolve,800));
      if(fail.current){fail.current=false;throw Error('Synthetic reply failed. Your message is kept for retry.');}
      lastContext.current=payload.dataset_id||'no dataset';
      const parent=saved.current.find(t=>t.id===payload.previous_turn_id),id='synthetic-turn-'+(++counter.current);
      const turn={id,question:payload.question,run_id:payload.run_id,snapshot_id:payload.snapshot_id,dataset_id:payload.dataset_id||null,previous_turn_id:payload.previous_turn_id,chat_id:parent?.chat_id||id,
        answer:payload.question.toLowerCase().includes('long')
          ?'Synthetic UI test only — no forecast was calculated.\n\n'+Array(8).fill('This paragraph checks that long replies scroll while the input stays at the bottom.').join('\n\n')
          :'Synthetic UI preview — no forecast was calculated.\n\nI can help you review sales history, customer orders and selected factors before running a forecast.',actions:[]};
      saved.current.push(turn);setSent(value=>value+1);return turn;
    }
    throw Error('Unexpected fixture request: '+url);
  },[]);
  return <Tooltip.Provider><div className="app-shell" data-sidebar-collapsed={collapsed}><AppSidebar collapsed={collapsed} onToggle={()=>setCollapsed(value=>{saveSidebarPreference(localState,!value);return !value;})}
    page="today" onNavigate={page=>{if(page==='today')setDestination('');else setDestination(page);}}
    items={[["today","Home",House],["demand","Forecast",ChartLineUp],["data","Data",Database]]} secondary={[["help","Help",Question],["settings","Settings",GearSix]]}/><div className="main">
    <header className="topbar"><span className="site-name">Synthetic chat test · no real AI</span><button className="text-btn" onClick={()=>setToast('Synthetic notification')}>Preview toast</button><button className="text-btn" onClick={()=>setToast('')}>Dismiss toast</button><button className="text-btn" onClick={async()=>{const next=language==='en'?'fa':'en';await changeInterfaceLanguage(next);applyInterfaceLanguage(document,next);setLanguage(next);}}>English / فارسی</button></header>
    <main id="workspace" data-native-motion={typeof document.startViewTransition==='function'}>{destination?<section className="ui-panel"><h2 className="ui-panel-title">{destination} {dataView}</h2><button className="btn" onClick={()=>setDestination('')}>Back to chat</button></section>:<AssistantWorkspace api={api} ui={ui} canEdit datasets={datasets} home refresh={async()=>{}}
      renderImport={({onCancel})=><section className="ui-panel"><h2 className="ui-panel-title">Synthetic import</h2><button className="btn" onClick={onCancel}>Back to chat</button></section>}
      navigate={setDestination} setDataView={setDataView} onNewForecast={()=>setDestination('Unified forecast wizard')}/>}
    </main><footer className="app-footer"><span role="status" aria-label="Fixture requests">Synthetic replies: {sent} · {lastContext.current}</span><button className="text-btn" onClick={()=>{fail.current=true;}}>Fail next reply</button><button className="text-btn" onClick={()=>{
      for(const node of document.querySelectorAll('.ui-mascot'))for(const animation of node.getAnimations({subtree:true})){
        animation.pause();animation.currentTime=animation.animationName==='mascot-eyes'?3150:0;
      }
    }}>Preview eye morph</button><span>{uiText('Sales forecast')}</span></footer>
  </div></div><MotionPresence present={!!toast}><div className="toast" role="status">{toast}</div></MotionPresence></Tooltip.Provider>;
}
applyInterfaceLanguage(document,'en');
createRoot(document.getElementById('root')).render(<Fixture/>);

import React from 'react';
import * as Tooltip from '@radix-ui/react-tooltip';
import {ChartLineUp,SidebarSimple} from '@phosphor-icons/react';
import {t as uiText} from './localization.mjs';

export const SIDEBAR_KEY='demandlab.sidebar.collapsed';
export function readSidebarPreference(storage){try{return storage.getItem(SIDEBAR_KEY)==='true';}catch{return false;}}
export function saveSidebarPreference(storage,collapsed){try{storage.setItem(SIDEBAR_KEY,String(collapsed));}catch{}}

export function AppSidebar({collapsed,onToggle,items,secondary=[],page,onNavigate}){
  function links(entries){return entries.map(([id,label,Icon])=>{
    const active=page===id||(id==='demand'&&page==='forecast');
    return <Tooltip.Root key={id}><Tooltip.Trigger asChild><button type="button" className={'nav-link '+(active?'active':'')}
      aria-label={uiText(label)} aria-current={active?'page':undefined} onClick={()=>onNavigate(id)}>
      <Icon aria-hidden="true"/><span>{uiText(label)}</span>
    </button></Tooltip.Trigger>{collapsed&&<Tooltip.Portal><Tooltip.Content className="ui-sidebar-tooltip" side="right" sideOffset={8}>{uiText(label)}</Tooltip.Content></Tooltip.Portal>}</Tooltip.Root>;
  });}
  return <aside className="sidebar" aria-label={uiText('Main navigation')}>
    <div className="ui-sidebar-header"><a className="brand" href="/today" aria-label="DemandLab" onClick={event=>{event.preventDefault();onNavigate('today');}}><ChartLineUp weight="bold" aria-hidden="true"/><span>DemandLab</span></a>
      <button type="button" className="ui-sidebar-toggle" aria-expanded={!collapsed} aria-controls="app-sidebar-links" onClick={onToggle}
        aria-label={uiText(collapsed?'Expand sidebar':'Collapse sidebar')} title={uiText(collapsed?'Expand sidebar':'Collapse sidebar')}><SidebarSimple aria-hidden="true"/></button>
    </div>
    <nav id="app-sidebar-links" aria-label={uiText('Main navigation')}>{links(items)}</nav>
    <div className="sidebar-secondary">{links(secondary)}</div>
  </aside>;
}

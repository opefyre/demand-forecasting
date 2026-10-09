import React,{useRef,useState} from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {DotsThree,NotePencil,Archive,ArrowCounterClockwise,ClockCounterClockwise} from '@phosphor-icons/react';
import {t as uiText,interfaceDirection,i18n} from './localization.mjs';
import {Actions,Stack,useMenuHandoff} from './ui-layout.jsx';

// Inputs and forecasts use the same menu, fixed dialog and revision table.
export function ResourceMenu({api,ui,kind,id,name,archived=false,canEdit,onChanged,onOpenRevision,onCreateRevision,sources=[],allowVersions=true}){
  const {Button,Field,Modal,Table,ErrorBox}=ui;
  const trigger=useRef(null),handoff=useMenuHandoff();
  const [dialog,setDialog]=useState(null),[record,setRecord]=useState(null),[draft,setDraft]=useState('');
  const [rows,setRows]=useState([]),[error,setError]=useState(null),[busy,setBusy]=useState(false);
  const [files,setFiles]=useState([]);
  const base='/api/v1/'+kind+'/'+encodeURIComponent(id);
  async function open(action){
    setDialog(action);setBusy(true);setError(null);setRecord(null);setRows([]);
    try{const r=await api(base+'/metadata');setRecord(r);setDraft(r.name||name);
      if(action==='versions'){
        setRows((await api(base+'/revisions')).revisions);
        setFiles(await Promise.all(sources.map(s=>api('/api/v1/sources/'+s.id+'/metadata'))));
      }
    }catch(e){setError(e);}finally{setBusy(false);}
  }
  async function save(action){
    if(!record||busy)return;setBusy(true);setError(null);
    try{const archived=record.lifecycle.archived;
      await api(base+(action==='rename'?'/metadata':archived?'/restore':'/archive'),
        {version:record.lifecycle.version,...(action==='rename'?{name:draft.trim()}:{})},action==='rename'?'PATCH':'POST');
      await onChanged?.();setDialog(null);
    }catch(e){setError(e);}finally{setBusy(false);}
  }
  const items=[...(canEdit?[['rename','Rename',NotePencil],['archive',archived?'Restore':'Archive',archived?ArrowCounterClockwise:Archive]]:[]),
    ...(allowVersions?[['versions','Versions',ClockCounterClockwise]]:[])];
  return <>
    <DropdownMenu.Root modal={false} dir={interfaceDirection()}>
      <DropdownMenu.Trigger asChild><button ref={trigger} type="button" className="btn secondary" aria-label={uiText('Item options for {{name}}',{name})} title={uiText('Item options')}><DotsThree aria-hidden="true"/></button></DropdownMenu.Trigger>
      <DropdownMenu.Portal><DropdownMenu.Content className="ui-menu" align="end" collisionPadding={12} onCloseAutoFocus={handoff.close}>
        {items.map(([action,label,Icon])=><DropdownMenu.Item key={action} className="ui-menu-item" onSelect={()=>handoff.select(trigger.current,()=>open(action))}><Icon aria-hidden="true"/>{uiText(label)}</DropdownMenu.Item>)}
        {canEdit&&onCreateRevision&&<DropdownMenu.Item className="ui-menu-item" onSelect={()=>handoff.select(trigger.current,onCreateRevision)}><ArrowCounterClockwise aria-hidden="true"/>{uiText('Create revision')}</DropdownMenu.Item>}
      </DropdownMenu.Content></DropdownMenu.Portal>
    </DropdownMenu.Root>
    <Modal open={!!dialog} fixed wide={dialog==='versions'} title={uiText(dialog==='rename'?'Rename':dialog==='archive'?(record?.lifecycle.archived?'Restore':'Archive'):'Versions')} onClose={()=>!busy&&setDialog(null)}>
      <Stack><ErrorBox error={error}/>{busy&&!record&&<p role="status">{uiText('Loading…')}</p>}
        {record&&dialog==='rename'&&<form onSubmit={e=>{e.preventDefault();save('rename');}}><Stack><Field title={uiText('Name')}><input aria-label={uiText('Name')} value={draft} maxLength={160} onChange={e=>setDraft(e.target.value)}/></Field><Actions><Button disabled={busy} onClick={()=>setDialog(null)} type="button">{uiText('Cancel')}</Button><Button kind="primary" disabled={busy||!draft.trim()} type="submit">{uiText('Save')}</Button></Actions></Stack></form>}
        {record&&dialog==='archive'&&<><p>{record.name}</p><Actions><Button disabled={busy} onClick={()=>setDialog(null)}>{uiText('Cancel')}</Button><Button kind="primary" disabled={busy} onClick={()=>save('archive')}>{uiText(record.lifecycle.archived?'Restore':'Archive')}</Button></Actions></>}
        {record&&dialog==='versions'&&<><Table headers={[uiText('Name'),uiText('Created'),uiText('Status'),'']} empty={!rows.length&&uiText('No versions found.')}>
          {rows.map(row=><tr key={row.id}>
            <td><strong>{row.name}</strong>{row.id===record.id&&<span className="ui-record-meta">{uiText('Current version')}</span>}</td>
            <td>{row.created_at?new Intl.DateTimeFormat(i18n.language,{dateStyle:'medium',timeStyle:'short'}).format(new Date(typeof row.created_at==='number'?row.created_at*1000:row.created_at)):'—'}</td>
            <td>{uiText(row.lifecycle.archived?'Archived':'Active')}</td>
            <td><Actions>{onOpenRevision&&<Button disabled={busy} onClick={async()=>{
              setBusy(true);
              try{await onOpenRevision(row);setDialog(null);}catch(e){setError(e);}finally{setBusy(false);}
            }}>{uiText('Open')}</Button>}
            {canEdit&&<ResourceMenu api={api} ui={ui} kind={row.kind} id={row.id} name={row.name} archived={row.lifecycle.archived} canEdit allowVersions={false}
              onChanged={async()=>{await onChanged?.();setRows((await api(base+'/revisions')).revisions);}}/>}</Actions></td>
          </tr>)}
        </Table>{files.length>0&&<Table headers={[uiText('Files'),uiText('Status'),'']}>
            {files.map(source=><tr key={source.id}><td>{source.name}</td><td>{uiText(source.lifecycle.archived?'Archived':'Active')}</td><td>{canEdit&&<ResourceMenu api={api} ui={ui} kind="sources" id={source.id} name={source.name} archived={source.lifecycle.archived} canEdit allowVersions={false} onChanged={async()=>{await onChanged?.();setFiles(await Promise.all(sources.map(s=>api('/api/v1/sources/'+s.id+'/metadata'))));}}/>}</td></tr>)}
        </Table>}</>}
      </Stack>
    </Modal>
  </>;
}

import React,{useEffect,useState} from 'react';
import {CloudArrowDown,Plus} from '@phosphor-icons/react';
import {Collection,SearchControl,ConnectionRecord,Disclosure,Actions,Grid,Stack,PageTabs} from './ui-layout.jsx';
import {t as uiText,i18n} from './localization.mjs';
import {LiveSources} from './live-sources.jsx';

const ROOT='/api/v1/connections/inputs';
const empty=()=>({name:'',provider:'http',role:'history',filename:'sales.csv',url:'',host:'',port:22,
  username:'',path:'',host_key:'',credential:'',template_dataset_id:'',confirmed_read_access:false});

export function InputConnections({api,ui,datasets,canAdmin,canEdit,onReview}){
  const {Button,Field,Pick,Table,Modal,ErrorBox}=ui;
  const [rows,setRows]=useState([]),[search,setSearch]=useState(''),[archived,setArchived]=useState(false);
  const [editing,setEditing]=useState(null),[busy,setBusy]=useState(''),[error,setError]=useState(null),[loading,setLoading]=useState(true);
  const refresh=()=>api(ROOT+'?include_archived=true').then(r=>setRows(r.connections));
  useEffect(()=>{let active=true;refresh().catch(e=>active&&setError(e)).finally(()=>active&&setLoading(false));return()=>{active=false;};},[api]);
  async function act(key,fn){setBusy(key);setError(null);try{await fn();await refresh();}catch(e){setError(e);await refresh().catch(()=>{});}finally{setBusy('');}}
  async function save(event){event.preventDefault();await act('save',async()=>{
    const {id,version,credential,...config}=editing;
    await api(id?ROOT+'/'+id:ROOT,{...config,port:Number(config.port),template_dataset_id:config.template_dataset_id||null,
      ...(credential?{credential}:{}),...(id?{version}:{})},id?'PUT':'POST');setEditing(null);
  });}
  const visible=rows.filter(row=>(archived||!row.archived)&&[row.name,row.provider].join(' ').toLowerCase().includes(search.toLowerCase()));
  function edit(row){const form=empty();for(const key of Object.keys(form))if(key!=='credential'&&row[key]!==undefined)form[key]=row[key]??'';setError(null);setEditing({...form,id:row.id,version:row.version,confirmed_read_access:false});}
  const change=(key,value)=>setEditing(form=>({...form,[key]:value}));
  const date=value=>new Date(value*1000).toLocaleString(i18n.language==='fa'?'fa-IR':'en-GB');
  return <>
    <Collection label={uiText('Sales data connections')} controls={<><SearchControl label={uiText('Search connections')} value={search} onChange={setSearch}/><label className="ui-check"><input type="checkbox" checked={archived} onChange={e=>setArchived(e.target.checked)}/>{uiText('Show archived')}</label></>}
      actions={canAdmin&&<Button kind="primary" disabled={!!busy} onClick={()=>{setError(null);setEditing(empty());}}><Plus/>{uiText('Add connection')}</Button>}>
      {!editing&&<ErrorBox error={error}/>}
      <Table headers={[uiText('Name'),uiText('Source'),uiText('Status'),'']} empty={loading?uiText('Loading connections…'):!visible.length&&uiText('No matching connections.')}>
        {visible.map(row=>{const latest=row.pulls[0];return <ConnectionRecord key={row.id} name={row.name} icon={CloudArrowDown} provider={row.provider==='sftp'?'SFTP':'HTTPS'}
          category={uiText(row.role==='history'?'Sales history':'Future factors')} tone={row.archived?undefined:latest?.state==='failed'?'warning':latest?.state==='ready'?'success':undefined}
          status={uiText(row.archived?'Archived':latest?.state==='failed'?'Fetch failed':latest?.accepted_dataset_id?'Inputs ready':latest?.message||'Not checked yet')} meta={latest&&date(latest.started)}
          actions={<>
            {canEdit&&!row.archived&&<Button disabled={!!busy} onClick={()=>act(row.id,async()=>{const result=await api(ROOT+'/'+row.id+'/fetch',{request_id:crypto.randomUUID()});if(result.state==='failed')throw Error(result.message);})}>{uiText(busy===row.id?'Fetching inputs…':'Fetch inputs')}</Button>}
            {canEdit&&latest?.candidate_id&&<Button disabled={!!busy} onClick={()=>act('review',()=>onReview(latest.candidate_id))}>{uiText(latest.accepted_dataset_id?'View saved data':'Review inputs')}</Button>}
            <Disclosure title={uiText('Details')}><Stack><span>{row.filename}</span>
              {canAdmin&&!row.archived&&<Button disabled={!!busy} onClick={()=>edit(row)}>{uiText('Edit')}</Button>}
              {canAdmin&&<Button disabled={!!busy} onClick={()=>act(row.id,()=>api(ROOT+'/'+row.id+(row.archived?'/restore':''),{version:row.version},row.archived?'POST':'DELETE'))}>{uiText(row.archived?'Restore':'Archive')}</Button>}
              {row.pulls.map(pull=><span key={pull.id}>{date(pull.started)} · {uiText(pull.message)}{canEdit&&pull.candidate_id&&<Button disabled={!!busy} onClick={()=>act('review',()=>onReview(pull.candidate_id))}>{uiText('Review inputs')}</Button>}</span>)}
            </Stack></Disclosure>
          </>}/>;})}
      </Table>
    </Collection>
    <Modal title={uiText(editing?.id?'Edit connection':'Add connection')} open={!!editing} onClose={()=>!busy&&setEditing(null)} fixed>
      {editing&&<form className="ui-stack" onSubmit={save}><ErrorBox error={error}/>
        <Field title={uiText('Connection name')}><input required maxLength={120} value={editing.name} onChange={e=>change('name',e.target.value)}/></Field>
        <Grid><Field title={uiText('Source')}><Pick label={uiText('Source')} disabled={!!editing.id} value={editing.provider} onChange={provider=>setEditing(form=>({...empty(),name:form.name,role:form.role,provider,template_dataset_id:form.template_dataset_id}))} options={[["http","HTTPS API"],["sftp","SFTP"]]}/></Field>
          <Field title={uiText('Input type')}><Pick label={uiText('Input type')} value={editing.role} onChange={value=>change('role',value)} options={[["history",uiText('Sales history')],["future",uiText('Future factors')]]}/></Field></Grid>
        {editing.provider==='http'?<Field title={uiText('Export endpoint')} help={uiText('Use a complete HTTPS export. Enter a token below, never in the address.')}><input required type="url" value={editing.url} onChange={e=>change('url',e.target.value)}/></Field>:<>
          <Grid><Field title={uiText('SFTP host')}><input required value={editing.host} onChange={e=>change('host',e.target.value)}/></Field><Field title={uiText('Port')}><input type="number" required min={1} max={65535} value={editing.port} onChange={e=>change('port',e.target.value)}/></Field></Grid>
          <Field title={uiText('Username')}><input required autoComplete="off" value={editing.username} onChange={e=>change('username',e.target.value)}/></Field>
          <Field title={uiText('Remote file path')}><input required value={editing.path} onChange={e=>change('path',e.target.value)}/></Field>
          <Field title={uiText('SSH host key')} help={uiText('Ask the source administrator for the public host key. Unknown or changed keys are rejected.')}><textarea required rows={2} value={editing.host_key} onChange={e=>change('host_key',e.target.value)}/></Field>
        </>}
        <Field title={uiText(editing.provider==='http'?'Access token (optional)':'SFTP password')} help={editing.id?uiText('Leave blank to keep the current credential. A changed destination needs a new credential.'):undefined}><input type="password" autoComplete="new-password" required={!editing.id&&editing.provider==='sftp'} value={editing.credential} onChange={e=>change('credential',e.target.value)}/></Field>
        <Field title={uiText('Export filename')}><input required value={editing.filename} onChange={e=>change('filename',e.target.value)}/></Field>
        <Field title={uiText('Use reviewed mapping')} help={editing.role==='future'?uiText('Select the sales data these future factors belong to.'):undefined}><Pick label={uiText('Use reviewed mapping')} value={editing.template_dataset_id} onChange={value=>change('template_dataset_id',value)} options={[["",uiText('Map after fetching')],...datasets.filter(d=>d.sources.history&&!d.sources.operations).map(d=>[d.id,d.name])]}/></Field>
        <label className="ui-check"><input type="checkbox" required checked={editing.confirmed_read_access} onChange={e=>change('confirmed_read_access',e.target.checked)}/>{uiText('I have permission to read this source.')}</label>
        <Actions><Button type="button" disabled={!!busy} onClick={()=>setEditing(null)}>{uiText('Cancel')}</Button><Button kind="primary" type="submit" disabled={!!busy}>{uiText(busy?'Saving…':'Save connection')}</Button></Actions>
      </form>}
    </Modal>
  </>;
}

export function BusinessConnections(props){
  const [view,setView]=useState('sales');
  return <Stack><PageTabs value={view} onChange={setView} label={uiText('Connection types')} items={[["sales",uiText('Sales data')],["factors",uiText('External factors')]]}/>
    {view==='sales'?<InputConnections {...props}/>:<LiveSources api={props.api} ui={props.ui} canAdmin={props.canAdmin}/>}</Stack>;
}

import React,{useEffect,useState} from 'react';
import {CloudArrowDown,Plus} from '@phosphor-icons/react';
import {Collection,SearchControl,ConnectionRecord,Actions,Grid,Stack,PageTabs} from './ui-layout.jsx';
import {t as uiText,i18n} from './localization.mjs';
import {LiveSources} from './live-sources.jsx';
import {ConnectionRowReview} from './connection-review.jsx';

const ROOT='/api/v1/connections/inputs';
const empty=()=>({name:'',provider:'http',role:'history',filename:'sales.csv',url:'',host:'',port:22,
  username:'',path:'',host_key:'',credential:'',template_dataset_id:'',confirmed_read_access:false,
  spreadsheet_id:'',sheet_range:'',database:'',odoo_company_id:1,timezone:'Asia/Tehran'});
const roleName={history:'Sales history',future:'Future factors',sales_customers:'Customers',sales_orders:'Orders'};
const providerName={http:'HTTPS',sftp:'SFTP',sheets:'Google Sheets',odoo18:'Odoo 18',odoo19:'Odoo 19'};

export function InputConnections({api,ui,datasets,canAdmin,canEdit,onReview,onViewRole}){
  const {Button,Field,Pick,Table,Modal,ErrorBox}=ui;
  const [rows,setRows]=useState([]),[search,setSearch]=useState(''),[archived,setArchived]=useState(false);
  const [editing,setEditing]=useState(null),[busy,setBusy]=useState(''),[error,setError]=useState(null),[loading,setLoading]=useState(true);
  const [reviewing,setReviewing]=useState(null),[schedule,setSchedule]=useState(null);
  const [details,setDetails]=useState(null);
  const detail=rows.find(row=>row.id===details);
  const refresh=()=>api(ROOT+'?include_archived=true').then(r=>setRows(r.connections));
  useEffect(()=>{let active=true;refresh().catch(e=>active&&setError(e)).finally(()=>active&&setLoading(false));return()=>{active=false;};},[api]);
  async function act(key,fn){setBusy(key);setError(null);try{await fn();await refresh();}catch(e){setError(e);await refresh().catch(()=>{});}finally{setBusy('');}}
  async function save(event){event.preventDefault();await act('save',async()=>{
    const {id,version,credential,...config}=editing;
    await api(id?ROOT+'/'+id:ROOT,{...config,port:Number(config.port),template_dataset_id:config.template_dataset_id||null,
      ...(credential?{credential}:{}),...(id?{version}:{})},id?'PUT':'POST');setEditing(null);
  });}
  const visible=rows.filter(row=>(archived||!row.archived)&&[row.name,row.provider].join(' ').toLowerCase().includes(search.toLowerCase()));
  async function review(id){const candidate=await api('/api/v1/connections/imports/'+id);
    if(candidate.role.startsWith('sales_')){if(candidate.accepted_resource)return;setReviewing(candidate);}else await onReview(id);}
  function edit(row){const form=empty();for(const key of Object.keys(form))if(key!=='credential'&&row[key]!==undefined)form[key]=row[key]??'';setError(null);setEditing({...form,id:row.id,version:row.version,confirmed_read_access:false});}
  const change=(key,value)=>setEditing(form=>({...form,[key]:value}));
  const date=value=>new Date(value*1000).toLocaleString(i18n.language==='fa'?'fa-IR':'en-GB');
  return <>
    <Collection label={uiText('Sales data connections')} controls={<><SearchControl label={uiText('Search connections')} value={search} onChange={setSearch}/><label className="ui-check"><input type="checkbox" checked={archived} onChange={e=>setArchived(e.target.checked)}/>{uiText('Show archived')}</label></>}
      actions={canAdmin&&<Button kind="primary" disabled={!!busy} onClick={()=>{setError(null);setEditing(empty());}}><Plus/>{uiText('Add connection')}</Button>}>
      {!editing&&!schedule&&<ErrorBox error={error}/>}
      <Table headers={[uiText('Name'),uiText('Source'),uiText('Status'),'']} empty={loading?uiText('Loading connections…'):!visible.length&&uiText('No matching connections.')}>
        {visible.map(row=>{const latest=row.pulls[0];return <ConnectionRecord key={row.id} name={row.name} icon={CloudArrowDown} provider={providerName[row.provider]}
          category={uiText(roleName[row.role])} tone={row.archived?undefined:latest?.state==='failed'?'warning':latest?.state==='ready'?'success':undefined}
          status={uiText(row.archived?'Archived':latest?.state==='failed'?'Fetch failed':latest?.accepted_dataset_id||latest?.accepted_resource?'Inputs ready':latest?.message||'Not checked yet')} meta={latest&&date(latest.started)}
          actions={<>
            {canEdit&&!row.archived&&<Button disabled={!!busy} onClick={()=>act(row.id,async()=>{const result=await api(ROOT+'/'+row.id+'/fetch',{request_id:crypto.randomUUID()});if(result.state==='failed')throw Error(result.message);})}>{uiText(busy===row.id?'Fetching inputs…':'Fetch inputs')}</Button>}
            {canEdit&&latest?.candidate_id&&!latest?.accepted_resource&&<Button disabled={!!busy} onClick={()=>act('review',()=>review(latest.candidate_id))}>{uiText(latest.accepted_dataset_id?'View saved data':'Review inputs')}</Button>}
            {latest?.accepted_resource&&onViewRole&&<Button onClick={()=>onViewRole(latest.accepted_resource.kind,latest.accepted_resource.dataset_id)}>{uiText(latest.accepted_resource.kind==='customers'?'View customers':'View orders')}</Button>}
            <Button disabled={!!busy} onClick={()=>setDetails(row.id)}>{uiText('Details')}</Button>
          </>}/>;})}
      </Table>
    </Collection>
    <Modal title={detail?.name||uiText('Details')} open={!!detail} onClose={()=>!busy&&setDetails(null)} fixed>
      {detail&&<Stack>
        <Field title={uiText('Export filename')}><span>{detail.filename}</span></Field>
        {detail.schedule&&<Field title={uiText('Refresh schedule')}><span>{uiText(detail.schedule.enabled?'Scheduled':'Paused')} · {uiText(detail.schedule.last_status)}</span>
          {detail.schedule.enabled&&<span>{uiText('Next fetch')} · {date(detail.schedule.next_due)}</span>}</Field>}
        <Actions>
          {canAdmin&&!detail.archived&&<Button disabled={!!busy} onClick={()=>{setDetails(null);edit(detail);}}>{uiText('Edit')}</Button>}
          {canAdmin&&!detail.archived&&<Button disabled={!!busy} onClick={()=>{setDetails(null);setSchedule({row:detail,minutes:detail.schedule?.minutes||1440,enabled:detail.schedule?.enabled||false,confirmed:false});}}>{uiText('Refresh schedule')}</Button>}
          {canAdmin&&<Button disabled={!!busy} onClick={()=>act(detail.id,async()=>{await api(ROOT+'/'+detail.id+(detail.archived?'/restore':''),{version:detail.version},detail.archived?'POST':'DELETE');setDetails(null);})}>{uiText(detail.archived?'Restore':'Archive')}</Button>}
        </Actions>
        <Table headers={[uiText('Date'),uiText('Status'),'']}>
          {detail.pulls.map(pull=><tr key={pull.id}><td>{date(pull.started)}</td><td>{uiText(pull.accepted_dataset_id||pull.accepted_resource?'Inputs ready':pull.message)}</td><td>{canEdit&&pull.candidate_id&&!pull.accepted_resource&&<Button disabled={!!busy} onClick={()=>{setDetails(null);act('review',()=>review(pull.candidate_id));}}>{uiText('Review inputs')}</Button>}</td></tr>)}
        </Table>
      </Stack>}
    </Modal>
    <Modal title={uiText(editing?.id?'Edit connection':'Add connection')} open={!!editing} onClose={()=>!busy&&setEditing(null)} fixed>
      {editing&&<form className="ui-stack" onSubmit={save}><ErrorBox error={error}/>
        <Field title={uiText('Connection name')}><input required maxLength={120} value={editing.name} onChange={e=>change('name',e.target.value)}/></Field>
        <Grid><Field title={uiText('Source')}><Pick label={uiText('Source')} disabled={!!editing.id} value={editing.provider} onChange={provider=>setEditing(form=>({...empty(),name:form.name,role:provider.startsWith('odoo')?'sales_customers':form.role,provider,filename:provider.startsWith('odoo')?'sales.json':'sales.csv',template_dataset_id:form.template_dataset_id}))} options={Object.entries(providerName)}/></Field>
          <Field title={uiText('Input type')}><Pick label={uiText('Input type')} value={editing.role} onChange={role=>setEditing(f=>({...f,role,...(role==='sales_customers'?{template_dataset_id:''}:{})}))} options={Object.entries(roleName).filter(([key])=>!editing.provider.startsWith('odoo')||key.startsWith('sales_')).map(([key,label])=>[key,uiText(label)])}/></Field></Grid>
        {editing.provider==='http'?<Field title={uiText('Export endpoint')} help={uiText('Use a complete HTTPS export. Enter a token below, never in the address.')}><input required type="url" value={editing.url} onChange={e=>change('url',e.target.value)}/></Field>:editing.provider==='sheets'?<>
          <Field title={uiText('Spreadsheet ID')}><input required value={editing.spreadsheet_id} onChange={e=>change('spreadsheet_id',e.target.value)}/></Field>
          <Field title={uiText('Worksheet')} help={uiText('Read the whole worksheet. Share it with the service account as a viewer.')}><input required value={editing.sheet_range} onChange={e=>change('sheet_range',e.target.value)}/></Field>
        </>:editing.provider.startsWith('odoo')?<>
          <Field title={uiText('Odoo address')}><input required type="url" value={editing.url} onChange={e=>change('url',e.target.value)}/></Field>
          <Grid><Field title={uiText('Database')}><input required value={editing.database} onChange={e=>change('database',e.target.value)}/></Field>
            <Field title={uiText('Company ID in Odoo')}><input type="number" min={1} required value={editing.odoo_company_id} onChange={e=>change('odoo_company_id',Number(e.target.value))}/></Field></Grid>
          {editing.provider==='odoo18'&&<Field title={uiText('Username')}><input required value={editing.username} onChange={e=>change('username',e.target.value)}/></Field>}
          {editing.role==='sales_orders'&&<Field title={uiText('Delivery-date timezone')} help={uiText('Odoo stores times in UTC. Convert to the customer delivery timezone, for example Asia/Tehran.')}><input required value={editing.timezone} onChange={e=>change('timezone',e.target.value)}/></Field>}
        </>:<>
          <Grid><Field title={uiText('SFTP host')}><input required value={editing.host} onChange={e=>change('host',e.target.value)}/></Field><Field title={uiText('Port')}><input type="number" required min={1} max={65535} value={editing.port} onChange={e=>change('port',e.target.value)}/></Field></Grid>
          <Field title={uiText('Username')}><input required autoComplete="off" value={editing.username} onChange={e=>change('username',e.target.value)}/></Field>
          <Field title={uiText('Remote file path')}><input required value={editing.path} onChange={e=>change('path',e.target.value)}/></Field>
          <Field title={uiText('SSH host key')} help={uiText('Ask the source administrator for the public host key. Unknown or changed keys are rejected.')}><textarea required rows={2} value={editing.host_key} onChange={e=>change('host_key',e.target.value)}/></Field>
        </>}
        <Field title={uiText(editing.provider==='http'?'Access token (optional)':editing.provider==='sftp'?'SFTP password':editing.provider==='sheets'?'Google service-account JSON':'Odoo API key')} help={editing.id?uiText('Leave blank to keep the current credential. A changed destination needs a new credential.'):undefined}><input type="password" autoComplete="new-password" required={!editing.id&&editing.provider!=='http'} value={editing.credential} onChange={e=>change('credential',e.target.value)}/></Field>
        <Field title={uiText('Export filename')}><input required value={editing.filename} onChange={e=>change('filename',e.target.value)}/></Field>
        {editing.role!=='sales_customers'&&<Field title={uiText(editing.role==='history'?'Use reviewed mapping':'Sales data')} help={editing.role==='future'?uiText('Select the sales data these future factors belong to.'):undefined}><Pick label={uiText('Sales data')} value={editing.template_dataset_id} onChange={value=>change('template_dataset_id',value)} options={[["",uiText(editing.role==='history'?'Map after fetching':'Choose sales data')],...datasets.filter(d=>d.sources.history&&!d.sources.operations).map(d=>[d.id,d.name])]}/></Field>}
        <label className="ui-check"><input type="checkbox" required checked={editing.confirmed_read_access} onChange={e=>change('confirmed_read_access',e.target.checked)}/>{uiText('I have permission to read this source.')}</label>
        <Actions><Button type="button" disabled={!!busy} onClick={()=>setEditing(null)}>{uiText('Cancel')}</Button><Button kind="primary" type="submit" disabled={!!busy||(['future','sales_orders'].includes(editing.role)&&!editing.template_dataset_id)}>{uiText(busy?'Saving…':'Save connection')}</Button></Actions>
      </form>}
    </Modal>
    {reviewing&&<ConnectionRowReview candidate={reviewing} api={api} ui={ui} onClose={()=>setReviewing(null)} onSaved={refresh}/>}
    <Modal title={uiText('Refresh schedule')} open={!!schedule} onClose={()=>!busy&&setSchedule(null)} fixed>
      {schedule&&<form className="ui-stack" onSubmit={e=>{e.preventDefault();act('schedule',async()=>{await api(ROOT+'/'+schedule.row.id+'/schedule',{
        version:schedule.row.schedule?.version||0,connection_version:schedule.row.version,minutes:schedule.minutes,enabled:schedule.enabled,confirmed:schedule.confirmed},'PUT');setSchedule(null);});}}><ErrorBox error={error}/>
        <Field title={uiText('Fetch every')}><Pick label={uiText('Fetch every')} value={String(schedule.minutes)} onChange={v=>setSchedule(s=>({...s,minutes:Number(v)}))} options={[["60",uiText('Hour')],["360",uiText('6 hours')],["1440",uiText('Day')]]}/></Field>
        <label className="ui-check"><input type="checkbox" checked={schedule.enabled} onChange={e=>setSchedule(s=>({...s,enabled:e.target.checked}))}/>{uiText('Enabled')}</label>
        <label className="ui-check"><input type="checkbox" required checked={schedule.confirmed} onChange={e=>setSchedule(s=>({...s,confirmed:e.target.checked}))}/>{uiText('Fetch automatically. Review changes before using them.')}</label>
        <Actions><Button type="button" disabled={!!busy} onClick={()=>setSchedule(null)}>{uiText('Cancel')}</Button><Button kind="primary" type="submit" disabled={!!busy}>{uiText('Save')}</Button></Actions>
      </form>}
    </Modal>
  </>;
}

export function BusinessConnections(props){
  const [view,setView]=useState('sales');
  return <Stack><PageTabs value={view} onChange={setView} label={uiText('Connection types')} items={[["sales",uiText('Sales data')],["factors",uiText('External factors')]]}/>
    {view==='sales'?<InputConnections {...props}/>:<LiveSources api={props.api} ui={props.ui} canAdmin={props.canAdmin}/>}</Stack>;
}

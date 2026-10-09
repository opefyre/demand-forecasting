import React,{useEffect,useState} from 'react';
import {Bell,Plus,ArrowClockwise} from '@phosphor-icons/react';
import {Collection,SearchControl,ConnectionRecord,Actions,ActionMenu,Grid,Stack,PageTabs,DefinitionList,FieldGroup} from './ui-layout.jsx';
import {t,i18n} from './localization.mjs';

const ROOT='/api/v1/notifications';
export const providers={slack:'Slack',teams:'Teams Workflows',telegram:'Telegram',whatsapp:'WhatsApp'};
export const notificationEvents={forecast_ready:'Forecast ready',forecast_failed:'Forecast needs attention',forecast_approved:'Forecast approved',inputs_ready:'New inputs to review',import_failed:'Connection needs attention'};
export const deliveryStates={queued:'Waiting to send',sending:'Sending',accepted:'Accepted by provider',rejected:'Not accepted',unknown:'Uncertain',cancelled:'Cancelled'};
const fields=['name','provider','destination','language','events','enabled','confirmed','template','template_language','eligible'];
const empty=()=>({name:'',provider:'slack',destination:'',language:i18n.language==='fa'?'fa':'en',events:[],enabled:false,confirmed:false,
  webhook:'',token:'',recipient:'',sender_id:'',template:'',template_language:'en_US',eligible:false});
export function notificationPayload(form){
  return Object.fromEntries([...fields,...['webhook','token','recipient','sender_id'].filter(k=>form[k]),...(form.id?['version']:[])].map(k=>[k,form[k]]));
}

export function NotificationSettings({api,ui}){
  const {Button,Field,Pick,Table,Modal,ErrorBox}=ui;
  const [view,setView]=useState('destinations'),[rows,setRows]=useState([]),[history,setHistory]=useState({deliveries:[],total:0}),[offset,setOffset]=useState(0);
  const [search,setSearch]=useState(''),[archived,setArchived]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState(null),[busy,setBusy]=useState(false);
  const [editing,setEditing]=useState(null),[action,setAction]=useState(null),[confirmed,setConfirmed]=useState(false),[duplicates,setDuplicates]=useState(false),[detail,setDetail]=useState(null);
  const date=value=>value?new Intl.DateTimeFormat(i18n.language,{dateStyle:'medium',timeStyle:'short'}).format(new Date(value*1000)):'—';
  async function refresh(page=offset){
    const [destinations,deliveries]=await Promise.all([api(ROOT+'/destinations?include_archived=true'),api(ROOT+'/deliveries?limit=50&offset='+page)]);
    setRows(destinations.destinations);setHistory(deliveries);
  }
  useEffect(()=>{let active=true;setLoading(true);setError(null);
    Promise.all([api(ROOT+'/destinations?include_archived=true'),api(ROOT+'/deliveries?limit=50&offset='+offset)])
      .then(([destinations,deliveries])=>{if(active){setRows(destinations.destinations);setHistory(deliveries);}})
      .catch(e=>active&&setError(e)).finally(()=>active&&setLoading(false));return()=>{active=false;};},[api,offset]);
  function open(kind,row){setError(null);setConfirmed(false);setDuplicates(false);
    if(kind==='edit')setEditing({...empty(),...row,confirmed:false});
    else setAction({kind,row,request_id:crypto.randomUUID()});
  }
  async function act(fn){if(busy)return;setBusy(true);setError(null);try{await fn();await refresh();}catch(e){setError(e);}finally{setBusy(false);}}
  const visible=rows.filter(r=>(archived||!r.archived)&&[r.name,r.destination,providers[r.provider]].join(' ').toLowerCase().includes(search.toLowerCase()));
  const update=(key,value)=>setEditing(f=>({...f,[key]:value}));
  const current=action&&(action.kind==='retry'?rows.find(r=>r.id===action.row.destination_id):action.row);
  async function sendAction(){await act(async()=>{
    if(action.kind==='archive'||action.kind==='restore'){
      await api(ROOT+'/destinations/'+current.id+(action.kind==='restore'?'/restore':''),{version:current.version},action.kind==='restore'?'POST':'DELETE');
    }else{
      const path=action.kind==='retry'?'/deliveries/'+action.row.id+'/retry':'/destinations/'+current.id+'/test';
      const receipt=await api(ROOT+path,{version:current.version,confirmed,duplicate_confirmed:duplicates,request_id:action.request_id});
      setDetail(receipt);setView('history');
    }setAction(null);
  });}
  return <Stack>
    <PageTabs label={t('Notification sections')} value={view} onChange={setView} items={[["destinations","Destinations"],["history","Delivery history"]]}/>
    {view==='destinations'?<Collection label={t('Notifications')} controls={<><SearchControl label={t('Search destinations')} value={search} onChange={setSearch}/><label className="ui-check"><input type="checkbox" checked={archived} onChange={e=>setArchived(e.target.checked)}/>{t('Show archived')}</label></>}
      actions={<Button kind="primary" disabled={busy} onClick={()=>{setError(null);setEditing(empty());}}><Plus aria-hidden="true"/>{t('Add destination')}</Button>}>
      {!editing&&!action&&<ErrorBox error={error}/>}
      <Table headers={[t('Name'),t('Destination'),t('Status'),'']} empty={loading?t('Loading…'):!visible.length&&t('No matching destinations.')}>
        {visible.map(row=><ConnectionRecord key={row.id} name={row.name} icon={Bell} provider={providers[row.provider]} category={row.destination}
          status={t(row.archived?'Archived':row.enabled?'Enabled':'Paused')} tone={row.enabled&&!row.archived?'success':undefined}
          actions={<ActionMenu name={row.name} disabled={busy} items={row.archived?[["Restore",()=>open('restore',row)]]:[["Edit",()=>open('edit',row)],["Send test",()=>open('test',row)],["Archive",()=>open('archive',row)]]}/>}/>)}
      </Table>
    </Collection>:<Collection label={t('Delivery history')} controls={<span>{t('{{count}} notifications',{count:history.total})}</span>}
      actions={<Button disabled={busy||loading} onClick={()=>act(()=>api(ROOT+'/check',{}))}><ArrowClockwise aria-hidden="true"/>{t('Check now')}</Button>}>
      {!action&&!detail&&<ErrorBox error={error}/>}
      <Table headers={[t('Date'),t('Destination'),t('Event'),t('Status'),'']} empty={loading?t('Loading…'):!history.deliveries.length&&t('No notifications yet.')}>
        {history.deliveries.map(row=><tr key={row.id}><td>{date(row.created_at)}</td><td><strong>{row.name}</strong><span className="ui-record-meta">{row.destination}</span></td>
          <td>{t(notificationEvents[row.event]||'Connection test')}</td><td><span className="ui-record-state" data-tone={row.state==='accepted'?'success':['rejected','unknown'].includes(row.state)?'warning':undefined}>{t(deliveryStates[row.state]||row.state)}</span></td>
          <td><Actions><Button onClick={()=>{setError(null);setDetail(row);}}>{t('Details')}</Button></Actions></td></tr>)}
      </Table>
      {history.total>50&&<Actions><Button disabled={loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-50))}>{t('Previous')}</Button><Button disabled={loading||offset+50>=history.total} onClick={()=>setOffset(offset+50)}>{t('Next')}</Button></Actions>}
    </Collection>}
    <Modal open={!!editing} title={t(editing?.id?'Edit destination':'Add destination')} fixed onClose={()=>!busy&&setEditing(null)}>
      {editing&&<Stack as="form" onSubmit={e=>{e.preventDefault();act(async()=>{await api(ROOT+'/destinations'+(editing.id?'/'+editing.id:''),notificationPayload(editing),editing.id?'PUT':'POST');setEditing(null);});}}>
        <ErrorBox error={error}/>
        <Grid><Field title={t('Name')}><input aria-label={t('Name')} required maxLength={120} value={editing.name} onChange={e=>update('name',e.target.value)}/></Field>
          <Field title={t('Source')}><Pick label={t('Source')} disabled={!!editing.id} value={editing.provider} options={Object.entries(providers)} onChange={provider=>setEditing({...empty(),name:editing.name,destination:editing.destination,provider})}/></Field></Grid>
        <Field title={t('Destination label')} help={t('Name the channel or recipient so everyone knows where alerts go.')}><input aria-label={t('Destination label')} required maxLength={120} value={editing.destination} onChange={e=>update('destination',e.target.value)}/></Field>
        {['slack','teams'].includes(editing.provider)?<Field title={t(editing.provider==='slack'?'Slack webhook':'Teams Workflows webhook')} help={editing.id?t('Leave blank to keep the current credential.'):undefined}><input aria-label={t('Webhook')} type="password" autoComplete="new-password" required={!editing.id} value={editing.webhook} onChange={e=>update('webhook',e.target.value)}/></Field>:<>
          <Field title={t(editing.provider==='telegram'?'Bot token':'Access token')} help={editing.id?t('Leave blank to keep the current credential.'):undefined}><input aria-label={t(editing.provider==='telegram'?'Bot token':'Access token')} type="password" autoComplete="new-password" required={!editing.id} value={editing.token} onChange={e=>update('token',e.target.value)}/></Field>
          <Field title={t(editing.provider==='telegram'?'Chat ID':'Recipient phone')}><input aria-label={t(editing.provider==='telegram'?'Chat ID':'Recipient phone')} type="password" autoComplete="off" required={!editing.id} value={editing.recipient} onChange={e=>update('recipient',e.target.value)}/></Field>
        </>}
        {editing.provider==='whatsapp'&&<>
          <Field title={t('Sender phone ID')}><input aria-label={t('Sender phone ID')} type="password" autoComplete="off" required={!editing.id} value={editing.sender_id} onChange={e=>update('sender_id',e.target.value)}/></Field>
          <Grid><Field title={t('Approved template')} help={t('Use an approved body template with one text variable, {{1}}.')}><input aria-label={t('Approved template')} required value={editing.template} onChange={e=>update('template',e.target.value)}/></Field>
            <Field title={t('Template language')}><input aria-label={t('Template language')} required value={editing.template_language} onChange={e=>update('template_language',e.target.value)}/></Field></Grid>
          <label className="ui-check"><input type="checkbox" required checked={editing.eligible} onChange={e=>update('eligible',e.target.checked)}/>{t('This account is eligible and the recipient agreed to WhatsApp messages.')}</label>
        </>}
        <Field title={t('Message language')}><Pick label={t('Message language')} value={editing.language} onChange={v=>update('language',v)} options={[["en","English"],["fa","فارسی"]]}/></Field>
        <FieldGroup title={t('Notify me about')}>{Object.entries(notificationEvents).map(([key,label])=><label key={key} className="ui-check"><input type="checkbox" checked={editing.events.includes(key)} onChange={e=>update('events',e.target.checked?[...editing.events,key]:editing.events.filter(v=>v!==key))}/>{t(label)}</label>)}</FieldGroup>
        <label className="ui-check"><input type="checkbox" checked={editing.enabled} onChange={e=>update('enabled',e.target.checked)}/>{t('Enable automatic notifications')}</label>
        <label className="ui-check"><input type="checkbox" required checked={editing.confirmed} onChange={e=>update('confirmed',e.target.checked)}/>{t('I authorize brief status messages and sign-in-required links to this destination.')}</label>
        <Actions><Button type="button" disabled={busy} onClick={()=>setEditing(null)}>{t('Cancel')}</Button><Button kind="primary" type="submit" disabled={busy||!editing.confirmed||(editing.enabled&&!editing.events.length)}>{t(busy?'Saving…':'Save')}</Button></Actions>
      </Stack>}
    </Modal>
    <Modal open={!!action} title={t(action?.kind==='test'?'Send test':action?.kind==='retry'?'Retry notification':action?.kind==='archive'?'Archive':'Restore')} fixed onClose={()=>!busy&&setAction(null)}>
      {action&&<Stack><ErrorBox error={error}/><DefinitionList rows={[[t('Name'),current?.name],[t('Destination'),current?.destination],[t('Source'),providers[current?.provider]]]}/>
        {['test','retry'].includes(action.kind)&&<>
          <p>{action.kind==='test'?t('A brief connection test will be sent. No sales data or files are included.'):action.row.text}</p>
          <label className="ui-check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>{t('Send this notification to the destination above.')}</label>
          {action.row.state==='unknown'&&<label className="ui-check"><input type="checkbox" checked={duplicates} onChange={e=>setDuplicates(e.target.checked)}/>{t('I checked the destination. I understand a duplicate is possible.')}</label>}
        </>}
        {action.kind==='restore'&&<p>{t('Restored connections stay paused until you enable them again.')}</p>}
        <Actions><Button disabled={busy} onClick={()=>setAction(null)}>{t('Cancel')}</Button><Button kind="primary" disabled={busy||!current||(['test','retry'].includes(action.kind)&&(!confirmed||(action.row.state==='unknown'&&!duplicates)))} onClick={sendAction}>{t(busy?'Working…':action.kind==='archive'?'Archive':action.kind==='restore'?'Restore':'Send')}</Button></Actions>
      </Stack>}
    </Modal>
    <Modal open={!!detail} title={t('Notification details')} fixed onClose={()=>!busy&&setDetail(null)}>
      {detail&&<Stack><ErrorBox error={error}/><DefinitionList rows={[[t('Destination'),detail.destination],[t('Source'),providers[detail.provider]],[t('Event'),t(notificationEvents[detail.event]||'Connection test')],[t('Status'),t(deliveryStates[detail.state])],[t('Date'),date(detail.created_at)]]}/>
        <p>{t(detail.message)}</p><p>{detail.text}</p>
        <Actions><Button onClick={()=>{setDetail(null);setView('destinations');}}>{t('Destinations')}</Button>
          {detail.retry_of&&<Button disabled={busy} onClick={()=>act(async()=>setDetail(await api(ROOT+'/deliveries/'+detail.retry_of)))}>{t('Previous attempt')}</Button>}
          {['rejected','unknown','cancelled'].includes(detail.state)&&rows.some(r=>r.id===detail.destination_id&&!r.archived)&&<Button disabled={busy} onClick={()=>{const row=detail;setDetail(null);open('retry',row);}}>{t('Retry notification')}</Button>}</Actions>
      </Stack>}
    </Modal>
  </Stack>;
}

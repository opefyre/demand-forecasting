import {apiLink} from './company-api.mjs';
import {chartTheme} from './chart-theme.mjs';
import {t as uiText,i18n} from './localization.mjs';
import React, {useEffect, useState} from 'react';
import {ArrowClockwise, Pause, Play, Plug, ArrowSquareOut, CurrencyDollar, ChartLine, Drop, GlobeHemisphereWest, Boat, Factory, Bank} from '@phosphor-icons/react';
import {LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer} from 'recharts';
import {sourceChart} from './source-chart.mjs';
import {sourceCaption,sourceRefreshState} from './live-source-presentation.mjs';
import {Collection,SearchControl,ConnectionRecord} from './ui-layout.jsx';

const sourceAppearance={servix:[CurrencyDollar,'Exchange-rate quotes'],iran_cpi:[ChartLine,'Monthly price index'],commodities:[Drop,'Monthly market data'],supply:[GlobeHemisphereWest,'Monthly market data'],hormuz:[Boat,'Daily ship traffic'],inflation:[Bank,'Annual context'],industry:[Factory,'Annual context']};

const time = value => value ? new Date(value).toLocaleString(i18n.language==='fa'?'fa-IR-u-ca-gregory-nu-latn':'en-GB', {dateStyle:'medium', timeStyle:'short'}) : uiText('Not checked yet');
export function LiveSources({api, ui, canAdmin, supplemental=[]}) {
  const {Button, Modal, Field, Pick, ErrorBox, Table, Help} = ui;
  const [data,setData]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState('');
  const [loadError,setLoadError]=useState(''),[detailError,setDetailError]=useState(''),[reloading,setReloading]=useState(false);
  const [selected,setSelected]=useState(null), [factor,setFactor]=useState(''), [observations,setObservations]=useState(null);
  const [connect,setConnect]=useState(false), [key,setKey]=useState('');
  const [permission,setPermission]=useState(false), [reference,setReference]=useState('');
  const [search,setSearch]=useState('');
  const [extra,setExtra]=useState(null);
  async function load(){setData(await api('/api/live-sources'));setLoadError('');}
  async function reloadSaved(){if(reloading)return;setReloading(true);try{await load();}catch(e){setLoadError(e);}finally{setReloading(false);}}
  async function loadObservations(){try{const response=await api('/api/factors');setObservations(response.snapshots);setDetailError('');}catch(e){setDetailError(e);}}
  useEffect(()=>{load().catch(e=>setLoadError(e));},[]);
  const checking = data?.sources.some(row=>['queued','refreshing'].includes(row.status));
  useEffect(()=>{const timer=setInterval(()=>load().catch(e=>setLoadError(e)),checking?3000:60000);return()=>clearInterval(timer);},[checking]);
  async function action(id, job){
    setError('');setBusy(id);
    try{await job();await load();}catch(e){setError(e);await load().catch(()=>{});}finally{setBusy('');}
  }
  async function details(source){
    setSelected(source.id);setFactor(source.series[0]?.id||'');setObservations(null);setDetailError('');setPermission(false);setReference('');
    if(source.series.length)await loadObservations();
  }
  const source=data?.sources.find(row=>row.id===selected);
  const snapshot=observations?.find(row=>row.id===factor);
  const chart=sourceChart(snapshot);
  async function saveKey(event){
    event.preventDefault();setBusy('servix');setError('');
    try{await api('/api/live-sources/servix/credential',{key},'PUT');setKey('');setConnect(false);await load();}
    catch(e){setError(e.message);}finally{setBusy('');}
  }
  function renderSource(row){
      const {hasData,working,cooling,needsPermission,status}=sourceRefreshState(row);
      const [Icon,category]=sourceAppearance[row.id]||[Plug,''];
      const tone=needsPermission||row.status==='failed'||row.refresh_overdue||row.data_behind?'warning':hasData&&row.enabled&&!working?'success':undefined;
      return <ConnectionRecord key={row.id} name={sourceCaption(row,uiText)} icon={Icon} provider={row.provider} category={uiText(category)} status={uiText(status)} tone={tone}
        meta={cooling?uiText('Retry after {{date}}',{date:time(row.cooldown_until)}):row.last_success?uiText('Checked {{date}}',{date:time(row.last_success)}):hasData?uiText("A saved source version is available"):uiText("No data fetched")}
        actions={<>
          {needsPermission&&canAdmin?<Button onClick={()=>details(row)}>{uiText("Review access")}</Button>:row.key_required&&!row.credential_configured&&canAdmin?<Button onClick={()=>{setError('');setConnect(true);}}><Plug size={18}/>{uiText("Connect")}</Button>:canAdmin&&<>
            <Button disabled={!!busy||working||cooling} onClick={()=>action(row.id,async()=>{await api(`/api/live-sources/${row.id}`,{enabled:true},'PUT');await api(`/api/live-sources/${row.id}/refresh`,{});})} title={cooling?uiText('Retry after {{date}}. Open Details for the last failure.',{date:time(row.cooldown_until)}):uiText("Fetch the latest available source data and enable automatic refresh")}><ArrowClockwise size={18}/>{busy===row.id||working?uiText("Checking…"):hasData?uiText("Refresh"):uiText("Connect")}</Button>
            {row.enabled&&<Button disabled={!!busy} title={uiText("Pause automatic refresh")} aria-label={uiText('Pause {{name}}',{name:sourceCaption(row,uiText)})} onClick={()=>action(row.id,()=>api(`/api/live-sources/${row.id}`,{enabled:false},'PUT'))}><Pause size={18}/></Button>}
            {!row.enabled&&hasData&&<Button disabled={!!busy} title={uiText("Resume automatic refresh")} aria-label={uiText('Resume {{name}}',{name:sourceCaption(row,uiText)})} onClick={()=>action(row.id,()=>api(`/api/live-sources/${row.id}`,{enabled:true},'PUT'))}><Play size={18}/></Button>}
          </>}
          {(!needsPermission||!canAdmin)&&<Button onClick={()=>details(row)}>{uiText("Details")}</Button>}
        </>}/>;
  }
  const priorities={servix:0,iran_cpi:1,commodities:2,supply:3,hormuz:4};
  const matching=data?.sources.filter(row=>[sourceCaption(row,uiText),row.provider].join(' ').toLowerCase().includes(search.toLowerCase()))||[];
  const records=matching.sort((a,b)=>(priorities[a.id]??5)-(priorities[b.id]??5));
  const extras=supplemental.filter(row=>[row.name,row.provider,row.category].join(' ').toLowerCase().includes(search.toLowerCase()));
  const extraSource=supplemental.find(row=>row.id===extra);
  const headers=[uiText('Factor'),uiText('Source'),uiText('Status'),''];
  return <>
    <Collection label={uiText('Factors')} controls={<SearchControl label={uiText('Search factors')} value={search} onChange={setSearch}/>} actions={<Help text={uiText("These feeds receive no sales or customer data. Refreshes save a new source version; they never overwrite your forecast. A relevant factor needs a fair historical test and future assumptions before use.")}/>}>
    {!connect&&<ErrorBox error={error}/>}
    <ErrorBox error={loadError} onReload={reloadSaved} busy={reloading}/>
    <Table headers={headers} empty={!data?uiText('Loading connections…'):!records.length&&!extras.length&&uiText('No matching factors.')}>
      {records.map(renderSource)}
      {data&&extras.map(row=><ConnectionRecord key={row.id} {...row} actions={<Button onClick={()=>setExtra(row.id)}>{uiText('Details')}</Button>}/>)}
    </Table>
    </Collection>
    <Modal title={extraSource?.name||uiText('Source details')} open={!!extraSource} onClose={()=>setExtra(null)} wide>{extraSource?.content}</Modal>
    <Modal title={uiText("Connect Iran exchange rates")} open={connect} onClose={()=>{if(!busy){setConnect(false);setKey('');setError('');}}} dismissible={!busy}>
      <form onSubmit={saveKey} className="ui-stack">
        <p>{uiText("Create a free Servix account, verify your email, then copy its API key.")}</p>
        <a href="https://servix.cc/auth/register" target="_blank" rel="noreferrer">{uiText("Open Servix signup")}{' '}<ArrowSquareOut size={16}/></a>
        <Field title={uiText("Servix API key")}><input type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} maxLength={2048} required spellCheck={false}/></Field>
        <p className="footnote">{uiText("Kept in macOS Keychain, outside project files. Never sent to AI.")}</p>
        <ErrorBox error={error}/>
        <Button kind="primary" disabled={!!busy||!key.trim()}>{busy?uiText("Verifying…"):uiText("Verify & save key")}</Button>
      </form>
    </Modal>
    <Modal title={source?sourceCaption(source,uiText):uiText('Source details')} open={!!selected} onClose={()=>setSelected(null)} wide>
      {source&&<div className="ui-stack">
        <p>{uiText(source.description)}</p><a href={apiLink(source.url)} target="_blank" rel="noreferrer">{source.provider}{' '}{uiText("documentation")}{' '}<ArrowSquareOut size={16}/></a>
        {source.permission_required&&<details className="help-details" open={!source.permission_confirmed}><summary>{uiText("Commercial data access")}</summary>
          <p>{uiText("IMF asks for permission for commercial reuse. Request permission at")}{' '}<a href="mailto:copyright@imf.org">copyright@imf.org</a>{' '}{uiText("covering this app’s automated data fetches and forecast use. A free account alone is not permission.")}{' '}<a href={apiLink(source.terms_url)} target="_blank" rel="noreferrer">{uiText("Read terms")}</a>.</p>
          {source.permission_confirmed?<><p className="footnote">{uiText("Permission recorded by your administrator; not independently verified. Reference:")}{' '}{source.permission_reference}</p>{canAdmin&&<button className="text-button" disabled={!!busy} onClick={()=>action(source.id,()=>api(`/api/live-sources/${source.id}/permission`,{confirmed:false,reference:''},'PUT'))}>{uiText("Withdraw permission & pause")}</button>}</>:canAdmin&&<form className="ui-stack" onSubmit={e=>{e.preventDefault();action(source.id,()=>api(`/api/live-sources/${source.id}/permission`,{confirmed:true,reference},'PUT'));}}>
            <Field title={uiText("Permission reference")}><input value={reference} onChange={e=>setReference(e.target.value)} minLength={8} maxLength={300} required placeholder={uiText("Permission email date or agreement reference")}/></Field>
            <label className="ui-check"><input type="checkbox" checked={permission} onChange={e=>setPermission(e.target.checked)}/>{uiText("I have permission covering automated commercial use.")}</label>
            <Button disabled={!!busy||!permission||reference.trim().length<8}>{uiText("Record permission")}</Button>
          </form>}
        </details>}
        <ErrorBox error={source.error||error}/>
        {source.cooldown_until&&source.status==='failed'&&<p className="footnote">{uiText("Next retry after")}{' '}{time(source.cooldown_until)}.</p>}
        <dl className="review-list"><div><dt>{uiText("Last successful fetch")}</dt><dd>{time(source.last_success)}</dd></div>
          <div><dt>{uiText("Checks")}</dt><dd>{source.hours===24?uiText("Daily"):source.hours===168?uiText("Weekly"):uiText('Every {{count}} hours',{count:source.hours})}{' '}{uiText("when auto-refresh is on")}</dd></div></dl>
        {source.series.length>1&&<Field title={uiText("Price series")}><Pick label={uiText("Price series")} value={factor} onChange={setFactor} options={source.series.map(r=>[r.id,`${r.name} · ${r.unit}`])}/></Field>}
        <ErrorBox error={detailError} onReload={loadObservations}/>
        {!!source.series.length&&!snapshot&&!detailError&&<p role="status">{uiText("Loading saved data…")}</p>}
        {snapshot&&<>
          <p>{uiText(snapshot.geography)} · {snapshot.unit}</p>
          {chart.length>0&&<div role="img" aria-label={uiText('{{name}}: recent source observations. Gaps mean missing data.',{name:snapshot.name})} className="ui-chart-preview"><ResponsiveContainer width="100%" height="100%"><LineChart data={chart} margin={chartTheme.margin}>
            <XAxis dataKey="period" tickFormatter={v=>snapshot.frequency==='daily'?v.slice(5):v.slice(0,7)} minTickGap={32} axisLine={false} tickLine={false} tick={chartTheme.ticks}/>
            <YAxis width={60} axisLine={false} tickLine={false} tick={chartTheme.ticks} tickFormatter={v=>new Intl.NumberFormat(undefined,{notation:'compact'}).format(v)}/>
            <Tooltip formatter={v=>[new Intl.NumberFormat(undefined,{maximumFractionDigits:3}).format(v),snapshot.unit]}/><Line dataKey="value" stroke="var(--chart-forecast)" strokeWidth={2} dot={false} connectNulls={false} isAnimationActive={false}/>
          </LineChart></ResponsiveContainer></div>}
          <p className="footnote">{snapshot.frequency==='quotes'?uiText("Quote observations; gaps are not filled. Rial values are not toman."):uiText("History is shown in the source’s own periods.")}{' '}{uiText("Latest period:")}{' '}{snapshot.points.at(-1)?.period}.</p>
          <details className="help-details"><summary>{uiText("How is this used in forecasting?")}</summary>
            <p>{['supply','servix','commodities','hormuz','iran_cpi'].includes(source.id)?uiText('New forecast → Factors. Choose this source and review future assumptions. Missing history is never filled.'):uiText("Annual figures are background information. They are not repeated into monthly forecast inputs.")}</p>
            {['hormuz','iran_cpi'].includes(source.id)&&<p>{snapshot.limitation}</p>}
          </details>
          {source.id==='hormuz'&&<p className="footnote">{snapshot.monthly?.length||0}{' '}{uiText("complete source months. Incomplete days and months are excluded from forecast inputs. Counts miss ships without AIS; earlier tracking was reconstructed.")}{' '}<a href="https://hormuz.now/data" target="_blank" rel="noreferrer">Source: hormuz.now · CC BY 4.0</a></p>}
          <details className="help-details"><summary>{uiText("Recent observations")}</summary><Table headers={[snapshot.frequency==='quotes'?uiText("Quote date"):uiText("Period"),snapshot.unit]}>
            {[...snapshot.points].reverse().slice(0,36).map((p,i)=><tr key={`${p.period}-${i}`}><td>{p.quote_time?time(p.quote_time):p.period}</td><td>{new Intl.NumberFormat(undefined,{maximumFractionDigits:3}).format(p.value)}</td></tr>)}
          </Table></details>
        </>}
        {!source.series.length&&<p className="footnote">{uiText("Connect this source to see the available history.")}</p>}
        {source.key_required&&source.credential_configured&&canAdmin&&<button className="text-button" onClick={()=>{setSelected(null);setConnect(true);setError('');}}>{uiText("Replace private key")}</button>}
      </div>}
    </Modal>
  </>;
}

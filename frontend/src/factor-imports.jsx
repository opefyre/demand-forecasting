import {t as uiText,pluralSuffix} from './localization.mjs';
import {useSmoothState} from './ui-motion.jsx';
import React, { useEffect, useRef, useState } from 'react';
import {suggestFactorMapping, factorMappingReady, factorUnit, factorTypeDefaults, factorSourceReady} from './factor-import-flow.mjs';
import {FactorFolder} from './factor-folder.jsx';
import {FactorLink} from './factor-links.jsx';
import {PanelHeader,Actions} from './ui-layout.jsx';

const defaults = { name: '', unit: '', geography: '', provider: '', frequency: 'monthly',
  classification: 'user_provided', mapping: {}, header_row: 1, sheet: '', calendar:'gregorian', publication_timezone:'UTC' };
const fields = [['period', 'Period end'], ['value', 'Value'], ['available_at', 'Publication date']];

export function FactorImports({ api, ui, onEditingChange, canAdmin, canEdit, run, onDraft }) {
  const { Button, Field, Pick, Table, ErrorBox, Help } = ui;
  const [items, setItems] = useState([]), [editing, setEditing] = useState(false);
  const [step, setStep] = useSmoothState(0);
  const fileInput = useRef(null), panel = useRef(null);
  const [config, setConfig] = useState(defaults), [table, setTable] = useState(null);
  const [fileName, setFileName] = useState('');
  const [review, setReview] = useState(null), [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [detail, setDetail] = useState(null), [cutoff, setCutoff] = useState(new Date().toISOString().slice(0, 10));
  const [available, setAvailable] = useState(null);
  const attempt = useRef(null);
  const [connectedReview,setConnectedReview]=useState(null),[readyFactor,setReadyFactor]=useState(null);
  const load = () => api('/api/factors').then(data => setItems(data.snapshots.filter(row => row.kind === 'imported_observations')));
  useEffect(() => { load().catch(e => setError(e.message)); }, []);
  useEffect(() => { onEditingChange?.(editing); }, [editing, onEditingChange]);
  useEffect(() => { if(editing) panel.current?.scrollIntoView({block:'start'}); }, [step,editing]);
  async function act(work) { setBusy(true); setError(''); try { await work(); } catch(e) { setError(e.message); } finally { setBusy(false); } }
  function change(patch) { setConfig(old => ({ ...old, ...patch })); setReview(null); setConfirmed(false); attempt.current = null; }
  function detailChange(patch){change({factor_details:{...config.factor_details,...patch}});}
  function start(item) { setConfig(item ? { ...item.import_config, source_id: null, parent_id: item.id } : defaults);
    setConnectedReview(null);setTable(null); setFileName(''); setReview(null); setConfirmed(false); setError(''); setStep(0); setEditing(true); attempt.current = null; }
  function connected(value){setConnectedReview(value);setConfig(value.review.config);setReview(value.review);setConfirmed(false);setError('');setStep(2);setEditing(true);}
  async function accepted(saved){await load();setReadyFactor(saved);setEditing(false);setConnectedReview(null);}
  async function upload(event) {
    const file = event.target.files?.[0]; if (!file) return;
    await act(async () => { const body = new FormData(); body.append('file', file); body.append('role', 'factor_observations');
      const source = await api('/api/sources', body);
      const next = { ...config, source_id: source.id, sheet: source.sheet || '' };
      const preview = await api('/api/factor-imports/table', next);
      change({ source_id: source.id, sheet: source.sheet || '', mapping: config.parent_id ? config.mapping : suggestFactorMapping(preview.columns) }); setTable(preview); setFileName(source.name);
    }); event.target.value = '';
  }
  if (editing) return <section ref={panel} className="ui-stack">
    <PanelHeader title={connectedReview?uiText('Review factor update'):config.parent_id?uiText('Update factor file'):uiText('Import a factor')} actions={<Button disabled={busy} onClick={()=>setEditing(false)}>{uiText('Cancel')}</Button>}/>
    <ErrorBox error={error}/>
    {!connectedReview&&<ol className="factor-import-steps" aria-label={uiText("Factor import progress")}>{['File & columns','Source details','Review'].map((label,i)=><li key={label} aria-current={step===i?'step':undefined}><span>{i+1}</span><b>{label}</b></li>)}</ol>}
    <p className="muted">{connectedReview?uiText("Save a new version. Your forecasts stay unchanged."):config.parent_id ? uiText("Upload the complete updated history. Previous versions are kept.") : uiText("One factor per file. Importing does not change your forecast.")}</p>
    <fieldset className="ui-stack" disabled={busy}>
      {step===0&&<>
      <input ref={fileInput} hidden type="file" accept=".xlsx,.xlsm,.csv,.tsv,.json" onChange={upload}/>
      <Button onClick={()=>fileInput.current?.click()}>{fileName?uiText("Replace factor file"):uiText("Choose factor file")}</Button>
      {fileName && <p className="muted">{uiText("Uploaded:")}{' '}{fileName}</p>}
      {table && <>
        <div className="ui-grid ui-grid-two">
          {!!table.sheets.length && <Field title={uiText("Worksheet")}><Pick value={config.sheet} options={table.sheets.map(s => [s,s])} onChange={sheet => { act(async () => {const next=await api('/api/factor-imports/table', {...config,sheet});change({sheet,mapping:{}});setTable(next);}); }}/></Field>}
          <Field title={uiText("Heading row")}><input type="number" min="1" max="200" value={config.header_row} onChange={e => change({header_row: Number(e.target.value), mapping: {}})}/></Field>
          <Button onClick={() => act(async () => { setTable(await api('/api/factor-imports/table', config)); setReview(null); setConfirmed(false); })}>{uiText("Read headings")}</Button>
        </div>
        <Table headers={table.columns.map(c => `${c.id} · ${c.label}`)} empty={!table.rows.length && 'No rows found.'}>
          {table.rows.slice(0,3).map(row => <tr key={row.source_row}>{table.columns.map(col => <td key={col.id}>{String(row.values[col.id] ?? '')}</td>)}</tr>)}
        </Table>
        <div className="ui-grid ui-grid-two">
          <Field title={uiText("Dates in the file")} help={uiText("Persian months retain their actual start/end dates. They are not converted into Gregorian monthly averages.")}><Pick label={uiText("Dates in the factor file")} disabled={!!config.parent_id} value={config.calendar||'gregorian'} options={[['gregorian',uiText("Gregorian")],['jalali',uiText("Persian (Jalali)")]]} onChange={calendar=>change({calendar,publication_timezone:calendar==='jalali'?'Asia/Tehran':'UTC'})}/></Field>
          <Field title={uiText("Publication dates use")} help={uiText("Values become available at the end of the publication day in this timezone.")}><Pick label={uiText("Factor publication timezone")} disabled={!!config.parent_id} value={config.publication_timezone||'UTC'} options={[['UTC',uiText("UTC")],['Asia/Tehran',uiText("Tehran time")]]} onChange={publication_timezone=>change({publication_timezone})}/></Field>
        </div>
        <h3 className="ui-panel-title">{uiText("Match columns")}</h3>
        <div className="ui-grid ui-grid-two">{fields.map(([key,label]) => <Field title={label} key={key} help={key === 'value' ? uiText("Persian and Arabic digits are accepted. Currency conversion is selected in Source details.") : key === 'available_at' ? uiText("The date this value was published, not downloaded. Use YYYY-MM-DD in the selected calendar.") : uiText("Use the last day of the observation period in the selected calendar, as YYYY-MM-DD.")}>
          <Pick value={config.mapping[key] || ''} options={[["",uiText("Choose column")], ...table.columns.map(c => [c.id,`${c.id} · ${c.label}`])]} onChange={value => change({mapping: {...config.mapping,[key]:value}})}/>
        </Field>)}</div>
        <Button kind="primary" disabled={!factorMappingReady(config.mapping,table.columns)} onClick={()=>{setError('');setStep(1);}}>{uiText("Continue")}</Button>
      </>}
      </>}
      {step===1&&<>
        <h3 className="ui-panel-title">{uiText("Identify the source")}</h3>
        <Field title={uiText("Data kind")}><Pick label={uiText("Factor data kind")} disabled={!!config.parent_id} value={config.factor_details?.kind||'other'} options={[['other',uiText("Other factor")],['inflation',uiText("Inflation / price index")],['exchange_rate',uiText("Exchange rate")]]} onChange={kind=>change({factor_details:factorTypeDefaults(kind),unit:''})}/></Field>
        <div className="ui-grid ui-grid-two">{[['name','Factor name','e.g. Exchange rate'],...(!config.factor_details?[['unit','Unit','e.g. Index points']]:[]),['geography','Location / coverage','e.g. Iran · national or Tehran'],['provider','Source','Provider and series reference']].map(([key,label,placeholder]) => <Field title={label} key={key}><input value={config[key]} maxLength={200} placeholder={placeholder} disabled={!!config.parent_id} onChange={e => change({[key]:e.target.value})}/></Field>)}
          <Field title={uiText("Frequency")}><Pick disabled={!!config.parent_id} value={config.frequency} options={['daily','monthly','annual'].map(v => [v,v[0].toUpperCase()+v.slice(1)])} onChange={frequency => change({frequency})}/></Field>
          <Field title={uiText("Data type")}><Pick disabled={!!config.parent_id} value={config.classification} options={[["user_provided",uiText("Real data")],["synthetic_sample",uiText("Demo sample")]]} onChange={classification => change({classification})}/></Field>
        </div>
        {config.factor_details?.kind==='exchange_rate'&&<div className="ui-grid ui-grid-two">
          <Field title={uiText("Foreign currency")} help={uiText("Quote must be rial/toman paid for this currency—not the inverse rate.")}><input aria-label={uiText("FX foreign currency")} value={config.factor_details.currency} maxLength={3} disabled={!!config.parent_id} onChange={e=>detailChange({currency:e.target.value.toUpperCase()})}/></Field>
          <Field title={uiText("Market")}><Pick label={uiText("FX market")} disabled={!!config.parent_id} value={config.factor_details.market} options={[['',uiText("Choose market")],['settlement',uiText("Factory settlement")],['free_market',uiText("Free market")],['official',uiText("Official")],['commercial',uiText("Commercial market")],['other',uiText("Other — identify in source")]]} onChange={market=>detailChange({market})}/></Field>
          <Field title={uiText("Quote basis")}><Pick label={uiText("FX quote basis")} disabled={!!config.parent_id} value={config.factor_details.side} options={[['',uiText("Choose basis")],['buy',uiText("Buy")],['sell',uiText("Sell")],['mid',uiText("Midpoint")],['settlement',uiText("Actual settlement")]]} onChange={side=>detailChange({side})}/></Field>
          <Field title={uiText("Values are in")}><Pick label={uiText("FX source amount unit")} disabled={!!config.parent_id} value={config.factor_details.amount_unit} options={[['',uiText("Choose unit")],['rial',uiText("Rial")],['toman',uiText("Toman (10 rials)")]]} onChange={amount_unit=>detailChange({amount_unit})}/></Field>
          <Field title={uiText("Quoted per")} help={uiText("For a rate quoted per 100 yen, enter 100. Saved rates are always rials per one foreign currency unit.")}><input aria-label={uiText("FX quote quantity")} inputMode="decimal" value={config.factor_details.quote_quantity} disabled={!!config.parent_id} onChange={e=>detailChange({quote_quantity:e.target.value})}/></Field>
        </div>}
        {config.factor_details?.kind==='inflation'&&<div className="ui-grid ui-grid-two">
          <Field title={uiText("Measure")} help={uiText("A 40% annual inflation rate is not a 40% monthly increase or a CPI index value.")}><Pick label={uiText("Inflation measure")} disabled={!!config.parent_id} value={config.factor_details.measure} options={[['',uiText("Choose measure")],['cpi_index',uiText("CPI price index")],['monthly_change',uiText("Change from previous month (%)")],['year_on_year',uiText("Change from same month last year (%)")],['annual_average',uiText("Annual-average inflation (%)")]]} onChange={measure=>change({factor_details:{kind:'inflation',measure,...(measure==='cpi_index'?{base_year:''}:{})}})}/></Field>
          {config.factor_details.measure==='cpi_index'&&<Field title={uiText("Index base year")} help={uiText("Copy the base year from the source. Different base years must be separate series.")}><input aria-label={uiText("CPI base year")} value={config.factor_details.base_year} inputMode="numeric" maxLength={4} disabled={!!config.parent_id} onChange={e=>detailChange({base_year:e.target.value})}/></Field>}
        </div>}
        {config.factor_details&&<small>{uiText("Saved unit:")}{' '}{factorUnit(config)||'Choose the measure above'}</small>}
        <div className="ui-actions"><Button onClick={()=>{setError('');setStep(0);}}>{uiText("Back")}</Button><Button kind="primary" disabled={!factorSourceReady(config)} onClick={() => act(async () => { setReview(await api('/api/factor-imports/preview',config)); setConfirmed(false);setStep(2); })}>{uiText("Review observations")}</Button></div>
      </>}
      {step===2&&review && <div className="ui-field-group ui-stack">
        <h3 className="ui-panel-title">{config.name}</h3>
        <p>{config.geography} · {review.config.unit} · {config.classification==='synthetic_sample'?uiText("Demo sample"):uiText("Real data")}</p>
        <details className="help-details"><summary>{uiText("Dates and units")}</summary><p>{review.normalization.period_rule}{' '}{uiText("Releases use")}{' '}{review.normalization.publication_timezone}. {review.normalization.value_rule}.</p>
          {review.normalization.factor_details.kind==='exchange_rate'&&<p>{review.normalization.factor_details.market.replaceAll('_',' ')} · {review.normalization.factor_details.side} · {review.normalization.original_amount_unit}{' '}{uiText("per")}{' '}{review.normalization.factor_details.quote_quantity} {review.normalization.factor_details.currency} → {review.config.unit}</p>}
        </details>
        <p>{review.summary.observations}{' '}{uiText("periods ·")}{' '}{review.summary.revisions}{' '}{uiText("revision")}{pluralSuffix(review.summary.revisions)} · {review.summary.gap_count}{' '}{uiText("missing")}{' '}{review.summary.gap_count===1?uiText("period"):uiText("periods")}</p>
        {review.changes&&<p>{review.changes.new_releases}{' '}{uiText("new releases ·")}{' '}{review.changes.changed_values}{' '}{uiText("changed values ·")}{' '}{review.changes.removed_releases}{' '}{uiText("removed releases")}</p>}
        {!!review.removed_releases?.length&&<details><summary>{uiText("Removed releases")}</summary><Table headers={[uiText("Period end"),uiText("Available from")]}>{review.removed_releases.map(p=><tr key={p.period+p.available_at}><td>{p.period}</td><td>{p.available_at}</td></tr>)}</Table></details>}
        {review.summary.last_period && <p className="muted">{uiText("Latest period:")}{' '}{review.summary.last_period} ({review.summary.days_since_last_period}{' '}{uiText("days before this review).")}</p>}
        {!!review.summary.gap_count && <p className="muted">{uiText("Missing:")}{' '}{review.summary.gaps.join(', ')}{review.summary.gap_count > 24 ? '…' : ''}{uiText(". Gaps remain empty, not zero.")}</p>}
        {!!review.issue_count && <div role="alert"><p>{uiText("Fix")}{' '}{review.issue_count}{' '}{uiText("row errors in your file, then upload again.")}</p><ul>{review.issues.map((issue,i) => <li key={i}>{uiText("Row")}{' '}{issue.row ?? '—'}: {issue.message}</li>)}</ul></div>}
        <details><summary>{uiText("View checked values")}</summary><Table headers={[uiText("Original period"),uiText("Period end"),uiText("Original value"),...(connectedReview?[uiText("Previously saved")]:[]),uiText("Saved value"),uiText("Published")]} empty={!review.points.length && 'No valid observations.'}>{review.points.map(p => <tr key={`${p.period}-${p.publication_date}`}><td>{p.original_period}</td><td>{p.period}</td><td>{p.original_value}</td>{connectedReview&&<td>{p.previous_value??'—'}</td>}<td>{p.value}</td><td>{p.publication_date}</td></tr>)}</Table></details>
        <small className="muted">{connectedReview?uiText("Changes shown first; up to 30 values. All rows checked."):uiText("Up to 30 values in the preview; all rows checked.")}{' '}{uiText("Publication dates are supplied by you, not independently verified.")}</small>
        <label className="ui-check"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)}/>{' '}{uiText("I checked the source, units, location, dates and gaps.")}</label>
        <div className="ui-actions">{!connectedReview&&<Button onClick={()=>{setConfirmed(false);setError('');setStep(1);}}>{uiText("Back")}</Button>}<Button kind="primary" disabled={!confirmed || !!review.issue_count} onClick={() => act(async () => {
          let saved;
          if(connectedReview)saved=await api(connectedReview.endpoint+'/accept',{candidate_id:connectedReview.candidate_id,reviewed:true,review_token:review.review_token});
          else{attempt.current ||= crypto.randomUUID();saved=await api('/api/factor-imports', {...config,reviewed:true,review_token:review.review_token,request_id:attempt.current});}
          await accepted(saved);
        })}>{uiText("Save factor")}</Button></div>
      </div>}
    </fieldset>
  </section>;
  const latest = items.filter((row,index) => items.findIndex(other => other.factor_id === row.factor_id) === index);
  return <section className="ui-stack">
    <Actions><Button onClick={()=>start()}>{uiText('Import factor')}</Button><Help text={uiText('Keep dated inflation, exchange-rate or other observations here. Importing does not automatically add them to a forecast.')}/></Actions>
    <ErrorBox error={error}/>
    {readyFactor&&run&&!run.scenario_name&&run.dataset_id&&onDraft&&<div className="ui-actions"><span>{readyFactor.name}{' '}{uiText("saved")}</span><FactorLink run={run} api={api} ui={ui} canEdit={canEdit} initialSnapshot={readyFactor.id} buttonLabel="Prepare forecast draft" onSaved={async(...args)=>{await onDraft(...args);setReadyFactor(null);}}/></div>}
    <Table headers={[uiText('Name'),uiText('Location / coverage'),uiText('Latest:'),'']} empty={!latest.length&&uiText('No factor files yet.')}>
      {latest.map(item=><tr key={item.id}><td><button className="text-button" onClick={()=>{setDetail(item);setAvailable(null);}}>{item.name}</button></td><td>{item.geography} · {item.unit}</td><td>{item.summary.last_period}{item.summary.gap_count>0&&<span className="ui-record-meta">{item.summary.gap_count} {uiText('missing periods')}</span>}{item.freshness?.status==='behind'&&<Help text={item.freshness.rule}/>}</td><td><div className="ui-record-actions"><Button onClick={()=>start(item)}>{uiText('Update file')}</Button>{canAdmin&&<FactorFolder snapshot={item} api={api} ui={ui} onReview={connected} onAccepted={accepted}/>}</div></td></tr>)}
    </Table>
    {detail && <div className="ui-field-group ui-stack"><div className="ui-panel-header"><h3 className="ui-panel-title">{detail.name}</h3><Button disabled={busy} onClick={() => setDetail(null)}>{uiText("Close")}</Button></div>
      {items.filter(row => row.factor_id === detail.factor_id).length > 1 && <Field title={uiText("Saved version")}><Pick value={detail.id} options={items.filter(row => row.factor_id === detail.factor_id).map(row => [row.id, new Date(row.captured_at).toLocaleString()])} onChange={id => { setDetail(items.find(row => row.id === id)); setAvailable(null); }}/></Field>}
      <p>{detail.provider} · {detail.frequency} · {detail.summary.first_period}{' '}{uiText("to")}{' '}{detail.summary.last_period}</p>
      <p className="muted">{detail.limitation}</p>
      {detail.normalization&&<details className="help-details"><summary>{uiText("Dates and units")}</summary><p>{detail.normalization.period_rule} {detail.normalization.value_rule} → {detail.unit}{uiText(". Release dates use")}{' '}{detail.normalization.publication_timezone}.</p>{detail.normalization.factor_details.kind==='exchange_rate'&&<p>{detail.normalization.factor_details.market.replaceAll('_',' ')} · {detail.normalization.factor_details.side}</p>}</details>}
      <div className="ui-grid ui-grid-two"><Field title={uiText("Available by")} help={uiText("Uses the latest revision published by the end of this day (UTC).")}><input type="date" disabled={busy} value={cutoff} onInput={e => {setCutoff(e.currentTarget.value);setAvailable(null);}} onChange={e => {setCutoff(e.target.value);setAvailable(null);}}/></Field>
        <Button disabled={busy || !cutoff} onClick={() => act(async () => setAvailable(await api(`/api/factor-imports/${detail.id}/available?cutoff=${encodeURIComponent(cutoff)}`)))}>{uiText("Check dates")}</Button></div>
      {available && <><p>{available.count}{' '}{uiText("periods available by")}{' '}{available.cutoff}{' '}{uiText("· first 100 shown")}</p><Table headers={[uiText("Period end"),uiText("Value"),uiText("Published")]} empty={!available.points.length && 'No observations available by this date.'}>{available.points.map(p => <tr key={p.period}><td>{p.period}</td><td>{p.value}</td><td>{p.publication_date}</td></tr>)}</Table></>}
    </div>}
  </section>;
}

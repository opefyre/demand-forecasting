import {t as uiText,i18n} from './localization.mjs';
import React,{useEffect,useState} from 'react';
import {Page,Collection,Disclosure} from './ui-layout.jsx';
import {DemandHandoff} from './demand-handoff';
import {releaseLabel,visibleReleases} from './demand-release-state.mjs';

export function DemandReviews({api,ui,canEdit,runs,legacy}){
  const {Button,Table,ErrorBox}=ui;
  const [items,setItems]=useState([]);
  const [selected,setSelected]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
  async function load(){setLoading(true);setError('');try{setItems((await api('/api/sales/releases')).releases);}catch(e){setError(e.message);}finally{setLoading(false);}}
  useEffect(()=>{load();},[]);
  const rows=visibleReleases(items,true);
  return <Page title={uiText('Approvals')}>
    <ErrorBox error={error}/>
    <Collection label={uiText('Approvals')}>
      {loading?<p role="status">{uiText("Loading reviews…")}</p>:<Table headers={[uiText("Receiving system"),uiText("Forecast"),uiText("Status"),'']} empty={!rows.length&&uiText("No demand reviews yet. Submit one from Forecast → Export demand → For planning.")}>
        {rows.map(r=><tr key={r.id}><td><strong>{r.contract.receiver}</strong><span className="ui-record-meta">{uiText('Version')}{' '}{new Intl.NumberFormat(i18n.language).format(r.version)}</span></td><td>{runs.find(run=>run.run_id===r.run_id)?.name||uiText('Saved forecast')}</td><td>{uiText(releaseLabel(r))}</td><td><Button onClick={()=>setSelected(r)}>{uiText("Review")}</Button></td></tr>)}
      </Table>}
    </Collection>
    {legacy&&<Disclosure title={uiText("Earlier model-only reviews")}><p>{uiText("These do not include customer orders and are not approved demand exports.")}</p>{legacy}</Disclosure>}
    <DemandHandoff open={!!selected} releaseId={selected?.id} runId={selected?.run_id} snapshotId={selected?.snapshot_id} api={api} ui={ui} canEdit={canEdit} onClose={()=>{setSelected(null);load();}}/>
  </Page>;
}

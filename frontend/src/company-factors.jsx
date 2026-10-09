import React,{useEffect,useState} from 'react';
import {Collection,SearchControl} from './ui-layout.jsx';
import {t as uiText} from './localization.mjs';

export function CompanyFactors({api,ui,onConnections}){
  const {Table,Button,ErrorBox}=ui;
  const [rows,setRows]=useState([]),[error,setError]=useState(null),[search,setSearch]=useState('');
  useEffect(()=>{let active=true;api('/api/factors').then(data=>{if(active)setRows(data.snapshots);}).catch(e=>active&&setError(e));return()=>{active=false;};},[api]);
  const visible=rows.filter(row=>[row.name,row.provider,row.geography].join(' ').toLowerCase().includes(search.toLowerCase()));
  return <Collection label={uiText('Factors')} controls={<SearchControl label={uiText('Search factors')} value={search} onChange={setSearch}/>} actions={<Button onClick={onConnections}>{uiText('Connections')}</Button>}>
    <ErrorBox error={error}/>
    <Table headers={[uiText('Factor'),uiText('Source'),uiText('Location'),uiText('Frequency')]} empty={!visible.length&&uiText('No factors yet.')}>
      {visible.map(row=><tr key={row.id}><td><strong>{row.name}</strong></td><td>{row.provider}</td><td>{row.geography}</td><td>{uiText(row.frequency)}</td></tr>)}
    </Table>
  </Collection>;
}

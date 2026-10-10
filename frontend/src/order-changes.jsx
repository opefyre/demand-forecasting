import React,{useState} from 'react';
import {Actions,Disclosure} from './ui-layout.jsx';
import {t as uiText,unitLabel,i18n} from './localization.mjs';

export function OrderChanges({changes=[],ui}){
  const [page,setPage]=useState(0);
  if(!changes.length)return null;
  const {Table,Button}=ui;
  const fields={due_date:'Due date',ordered:'Ordered',fulfilled:'Already fulfilled',cancelled:'Cancelled',status:'Status'};
  function value(row,field){
    if(!row)return '—';
    if(field==='due_date')return <bdi>{row[field]}</bdi>;
    if(field==='status')return uiText({confirmed:'Confirmed',unconfirmed:'Unconfirmed',cancelled:'Cancelled'}[row[field]]||row[field]);
    return new Intl.NumberFormat(i18n.language,{maximumFractionDigits:3}).format(row[field])+' '+unitLabel(row.unit);
  }
  return <Disclosure title={uiText('{{count}} order lines changed',{count:changes.length})}>
    <Table headers={['Order line','Changed field','Before','After'].map(label=>uiText(label))}>
      {changes.slice(page*25,(page+1)*25).flatMap(change=>Object.keys(fields).filter(field=>change.before?.[field]!==change.after?.[field]).map(field=><tr key={change.reference+'/'+field}>
        <td><bdi>{change.reference}</bdi><span className="ui-record-meta">{(change.after||change.before).customer} · {(change.after||change.before).sku}</span></td><td>{uiText(fields[field])}</td><td>{value(change.before,field)}</td><td>{value(change.after,field)}</td>
      </tr>))}
    </Table>
    {changes.length>25&&<Actions><Button disabled={!page} onClick={()=>setPage(p=>p-1)}>{uiText('Previous')}</Button><Button disabled={(page+1)*25>=changes.length} onClick={()=>setPage(p=>p+1)}>{uiText('Next')}</Button></Actions>}
  </Disclosure>;
}

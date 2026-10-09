import React from 'react';
import {Collection,SearchControl} from './ui-layout.jsx';
import {t as uiText} from './localization.mjs';
import {ResourceMenu} from './resource-lifecycle.jsx';

export function SalesFiles({datasets,search,onSearch,actions,onReview,ui,date,fmt,api,canEdit,onChanged,showArchived,onArchived}) {
  const {Table,Button}=ui;
  return <Collection label={uiText('Your files')} controls={<><SearchControl label={uiText('Search sales history')} value={search} onChange={onSearch}/>{api&&<label className="ui-check"><input type="checkbox" checked={showArchived} onChange={e=>onArchived(e.target.checked)}/>{uiText('Show archived')}</label>}</>} actions={actions}>
    <Table headers={[uiText('Name'),uiText('Period'),uiText('Products'),'']} empty={!datasets.length&&(search?uiText('No matching files.'):uiText('Start with your historical data'))}>
      {datasets.map(d=><tr key={d.id}>
        <td><strong>{d.name}</strong>{d.lifecycle?.archived&&<span className="ui-record-meta">{uiText('Archived')}</span>}</td>
        <td>{date(d.review.summary.start)} – {date(d.review.summary.end)}</td><td>{fmt(d.review.summary.series,0)}</td>
        <td><div className="ui-record-actions"><Button onClick={()=>onReview(d)}>{uiText('Review data')}</Button>
          {api&&<ResourceMenu api={api} ui={ui} kind="datasets" id={d.id} name={d.name} archived={!!d.lifecycle?.archived} canEdit={canEdit} onChanged={onChanged}
            onOpenRevision={async row=>onReview(await api('/api/v1/datasets/'+row.id))}
            sources={Object.entries(d.sources||{}).map(([role,id])=>({id,name:uiText(role==='history'?'Sales history':'Future factors')}))}/>}
        </div></td>
      </tr>)}
    </Table>
  </Collection>;
}

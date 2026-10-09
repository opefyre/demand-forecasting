import React from 'react';
import {Collection,SearchControl} from './ui-layout.jsx';
import {t as uiText} from './localization.mjs';

export function SalesFiles({datasets,search,onSearch,actions,onReview,ui,date,fmt}) {
  const {Table,Button}=ui;
  return <Collection label={uiText('Your files')} controls={<SearchControl label={uiText('Search sales history')} value={search} onChange={onSearch}/>} actions={actions}>
    <Table headers={[uiText('Name'),uiText('Period'),uiText('Products'),'']} empty={!datasets.length&&(search?uiText('No matching files.'):uiText('Start with your historical data'))}>
      {datasets.map(d=><tr key={d.id}><td><strong>{d.name}</strong></td><td>{date(d.review.summary.start)} – {date(d.review.summary.end)}</td><td>{fmt(d.review.summary.series,0)}</td><td><div className="ui-record-actions"><Button onClick={()=>onReview(d)}>{uiText('Review data')}</Button></div></td></tr>)}
    </Table>
  </Collection>;
}

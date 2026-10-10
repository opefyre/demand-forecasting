import {t as uiText,i18n,unitLabel} from './localization.mjs';
import React from 'react';
import {Panel,Disclosure,Actions} from './ui-layout.jsx';

const labels={date_col:'Sales date',target_col:'Sales quantity',item_col:'Customer–SKU series',customer_col:'Customer',sku_col:'SKU',future_date_col:'Factor date',future_item_col:'Factor series'};
const quantity=v=>v==null?uiText('Unknown'):new Intl.NumberFormat(i18n.language,{maximumFractionDigits:3}).format(v);

export function InputMappingProposal({action,result,expired,busy,canEdit,onConfirm,ui,onUse}){
  const {Button,Table}=ui;
  return <Panel title={uiText("Review input mappings")}>
    <p>{action.reason}</p>
    <Table headers={[uiText("Field"),uiText("Before"),uiText("After")]}>{action.diff.map(d=><tr key={d.field}><td>{uiText(labels[d.field]||d.field)}</td><td>{d.before||uiText('Not mapped')}</td><td>{d.after}</td></tr>)}</Table>
    <p>{uiText("Source quantity total:")}{' '}<bdi>{quantity(action.before_total)} → {quantity(action.after_total)}</bdi> {unitLabel(action.unit)}</p>
    <p>{uiText("History used after date grouping and gap treatment:")}{' '}<bdi>{quantity(action.before_prepared_total)} → {quantity(action.after_prepared_total)}</bdi> {unitLabel(action.unit)}</p>
    {!!action.warnings?.length&&<Disclosure open title={uiText('Checks to review')}><ul>{action.warnings.map((w,i)=><li key={i}>{uiText(w)}</li>)}</ul></Disclosure>}
    <p>{uiText("Original files, orders and forecasts stay unchanged.")}</p>
    {result?.dataset_id?<><p role="status">{uiText("Saved “")}{result.dataset_name}”.</p><Actions>{onUse?<Button disabled={busy} onClick={onUse}>{uiText("Use these inputs")}</Button>:<a className="btn secondary" href="/data">{uiText("Open Data")}</a>}</Actions></>:expired?<p role="status">{uiText("This proposal expired. Ask again to refresh it.")}</p>:<Actions><Button disabled={!canEdit||busy} kind="primary" onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Approve & save new input version")}</Button></Actions>}
  </Panel>;
}

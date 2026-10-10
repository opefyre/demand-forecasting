import {apiLink} from './company-api.mjs';
import {t as uiText,i18n} from './localization.mjs';
import React from 'react';
import {Panel,DefinitionList,Actions} from './ui-layout.jsx';
import {OrderComparisonReport} from './order-comparison.jsx';

export function AssistantComparison({action,result,expired,busy,canEdit,onConfirm,onOpen,ui}) {
  const {Button}=ui, preview=action.preview;
  const count=value=>new Intl.NumberFormat(i18n.language).format(value);
  return <Panel title={uiText("Save a separate scenario draft?")}>
    <strong>{action.name}</strong>
    <DefinitionList rows={[[uiText('Customers'),count(preview.customer_count)],[uiText('SKUs'),count(preview.sku_count)]]}/>
    <OrderComparisonReport rows={preview.months} basis={action.month_basis} warnings={preview.warnings} ui={ui}/>
    <p className="table-note">{uiText("Orders stay unchanged. Totals include deliveries; exports exclude them. This saves all customers and SKUs, not just a filtered preview.")}</p>
    {result?.snapshot_id?<><p role="status">{uiText("Separate draft saved. The original is unchanged.")}</p><Actions>
      <Button disabled={busy} onClick={onOpen}>{uiText("Open forecast")}</Button>
      <a className="btn secondary" href={apiLink(`/api/sales/inputs/${encodeURIComponent(result.snapshot_id)}/export?mode=combined_demand&kind=xlsx`)}>{uiText("Full scenario · Excel")}</a>
      <a className="btn secondary" href={apiLink(`/api/sales/inputs/${encodeURIComponent(result.snapshot_id)}/export?mode=remaining_forecast&kind=csv`)}>{uiText("Remaining forecast · CSV")}</a>
    </Actions></>:expired?<p role="status">{uiText("This proposal expired. Ask again to refresh it.")}</p>:<Actions><Button kind="primary" disabled={!canEdit||busy||preview.can_save===false} onClick={onConfirm}>{busy?uiText("Saving…"):uiText("Approve & save draft")}</Button></Actions>}
  </Panel>;
}

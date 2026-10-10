import React,{useState} from 'react';
import {ForecastOrders} from './forecast-orders.jsx';
import {Panel} from './ui-layout.jsx';
import {t as uiText} from './localization.mjs';

export function OrderUpdate({api,ui,run,initial,canEdit,onClose,onSaved}){
  const [busy,setBusy]=useState(false);
  return <ui.Modal open fixed wide title={uiText('Update orders')} dismissible={!busy} onClose={onClose}>
    <Panel title={uiText('Customers & orders')}>
      <ForecastOrders api={api} ui={ui} targetRun={run} initial={initial} canEdit={canEdit} onWorkingChange={setBusy}
        onReady={async id=>{if(id)await onSaved({id});}}/>
    </Panel>
  </ui.Modal>;
}

import React from 'react';
import {Grid} from './ui-layout.jsx';
import {t as uiText} from './localization.mjs';
import {FORECAST_CHOICES} from './forecast-start.mjs';

export const inputMethodChoices=dataset=>dataset?.settings?.drivers?.length||dataset?.settings?.evidence_policy==='reviewed_what_if'
  ?FORECAST_CHOICES.filter(([id])=>['model:Ridge + drivers','model:Elastic Net + drivers','model:Histogram gradient boosting'].includes(id))
  :FORECAST_CHOICES;

export function ForecastMethods({choices=FORECAST_CHOICES,methods,onChange,disabled=false,ui}) {
  return <Grid>{choices.map(([id,title,description])=><div className="ui-choice" key={id}>
    <label className="ui-check"><input type="checkbox" disabled={disabled} checked={methods.includes(id)}
      onChange={e=>onChange(e.target.checked?[...methods,id]:methods.filter(m=>m!==id))}/><strong>{uiText(title)}</strong></label>
    <ui.Help text={uiText(description)}/>
  </div>)}</Grid>;
}

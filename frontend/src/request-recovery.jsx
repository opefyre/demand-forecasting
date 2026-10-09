import React from 'react';
import {WarningCircle,ArrowClockwise} from '@phosphor-icons/react';
import {t as uiText,i18n} from './localization.mjs';
import {recoveryPresentation} from './request-errors.mjs';

// onReload must only read saved state, never repeat a mutation.
export function RequestRecovery({error,onReload,busy=false}) {
  const [now,setNow]=React.useState(Date.now());
  React.useEffect(()=>{
    if(!error?.retryAt||error.retryAt<=Date.now())return;
    const timer=setTimeout(()=>setNow(Date.now()),Math.min(error.retryAt-Date.now()+25,2147483647));
    return()=>clearTimeout(timer);
  },[error,now]);
  const view=recoveryPresentation(error,now);
  if(!view)return null;
  return <div role="alert" className="error-box request-recovery">
    <WarningCircle size={20} aria-hidden="true"/>
    <div className="request-recovery-copy">
      {view.plain?<span>{uiText(view.message)}</span>:<>
        <strong>{uiText(view.title)}</strong><p>{uiText(view.next)}</p>
        {view.fields.length>0?<ul>{view.fields.map((field,index)=><li key={index}>{field.field&&<bdi>{field.field}: </bdi>}{field.message}</li>)}</ul>:view.inlineDetails?<p className="request-original">{view.details}</p>:
          <details><summary>{uiText('Details')}</summary><p className="request-original">{view.details}</p></details>}
        {view.retryAt>now&&<p>{uiText('Retry after {{date}}',{date:new Date(view.retryAt).toLocaleString(i18n.language==='fa'?'fa-IR-u-ca-gregory-nu-latn':'en-GB')})}</p>}
      </>}
      {onReload&&view.canReload&&<button className="text-button request-reload" disabled={busy} onClick={onReload}><ArrowClockwise size={16}/>{uiText(busy?'Loading saved data…':'Reload saved data')}</button>}
    </div>
  </div>;
}

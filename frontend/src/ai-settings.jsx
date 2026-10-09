import {t as uiText} from './localization.mjs';
import React,{useState,useEffect} from 'react';
import {Panel,Stack,DefinitionList} from './ui-layout.jsx';

export function AISettings({api,ui,expanded=false}) {
  const {ErrorBox,Help}=ui;
  const [status,setStatus]=useState(null),[error,setError]=useState('');
  async function load() {
    setError('');
    try{setStatus(await api('/api/ai/status'));}catch(e){setError(e.message);}
  }
  useEffect(()=>{if(expanded)load();},[expanded]);
  const content=<Stack>
      <ErrorBox error={error}/>
      {status&&<>
        <p>{status.provider_label||'AI'} · {status.ready?uiText("Configured"):uiText(status.message)}</p>
        {status.models&&<DefinitionList rows={Object.entries(status.models).map(([role,model])=>[uiText(({query:'Questions',review:'Data review',decision:'Forecast decisions',title:'Chat names'})[role]||role),model])}/>}
        {status.limits&&<>
          <p>{uiText("Calls today:")}{' '}{status.usage_today?.workspace_calls??0} / {status.limits.daily_calls}<Help text={uiText("Each model request counts as one call. A reply may need several calls. Failed attempts also count. Resets at midnight UTC. This is not a money limit.")}/></p>
          <p className="ui-panel-description">{uiText('Up to {{count}} steps per request. Limits are managed on the server.',{count:status.limits.request_calls})}</p>
        </>}
      </>}
    </Stack>;
  return expanded?<Panel title={uiText('AI settings')}>{content}</Panel>:<details className="surface disclosure" onToggle={e=>{if(e.currentTarget.open)load();}}><summary>{uiText('AI settings')}</summary>{content}</details>;
}

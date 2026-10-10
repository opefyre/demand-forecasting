// Local visual fixture only; not imported by the production bundle. No auth,
// mail, credentials, codes or provider requests are submitted by this fixture.
import React,{useState,useMemo} from 'react';
import {createRoot} from 'react-dom/client';
import {ChartLineUp} from '@phosphor-icons/react';
import {IdentityLogin} from './identity-login.jsx';
import {EntrySurface,Actions} from './ui-layout.jsx';
import {changeInterfaceLanguage,applyInterfaceLanguage} from './localization.mjs';
import './design-system.css';
function Fixture(){
  const [language,setLanguage]=useState('en'),[mode,setMode]=useState('signin');
  const api=useMemo(()=>async()=>({google:true}),[]);
  return <><header className="topbar"><Actions>
    <button className="text-button" onClick={()=>setMode(mode==='signin'?'factor':'signin')}>Sign in / MFA</button>
    <button className="text-button" onClick={async()=>{const next=language==='en'?'fa':'en';await changeInterfaceLanguage(next);applyInterfaceLanguage(document,next);setLanguage(next);}}>English / فارسی</button>
  </Actions></header><EntrySurface brand="DemandLab" icon={ChartLineUp}>
    <IdentityLogin key={mode} api={api} user={mode==='factor'?{mfa_required:true,mfa_enabled:true}:null}/>
  </EntrySurface></>;
}
applyInterfaceLanguage(document,'en');
createRoot(document.getElementById('root')).render(<Fixture/>);

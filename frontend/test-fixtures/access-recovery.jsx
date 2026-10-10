// Disposable local browser fixture. Never imported by the production entry.
import React,{Suspense,lazy} from 'react';
import {createRoot} from 'react-dom/client';
import {ChartLineUp} from '@phosphor-icons/react';
import {EntrySurface} from '../src/ui-layout.jsx';
import {AccessBoundary} from '../src/access.jsx';
import {changeInterfaceLanguage,applyInterfaceLanguage} from '../src/localization.mjs';
import '../src/design-system.css';
const Fault=lazy(()=>Promise.reject(new TypeError('Synthetic unavailable sign-in chunk')));
const language=new URLSearchParams(location.search).get('lang')==='fa'?'fa':'en';
await changeInterfaceLanguage(language);applyInterfaceLanguage(document);
createRoot(document.getElementById('root')).render(
  <EntrySurface brand="DemandLab" icon={ChartLineUp}><AccessBoundary>
    <Suspense fallback={null}><Fault/></Suspense>
  </AccessBoundary></EntrySurface>
);

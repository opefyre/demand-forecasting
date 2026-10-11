import React,{useEffect,useRef,useState} from 'react';
import {downloadSession} from './cloud-transport.mjs';
import {saveDownload} from './downloads.mjs';
import {t as uiText} from './localization.mjs';

// Shared download control; dialogs own their errors, not the obscured page behind.
export function DownloadLink({href,primary=false,children,onError,onStart}){
  const [busy,setBusy]=useState(false),pending=useRef(false),live=useRef(true);
  useEffect(()=>{live.current=true;return()=>{live.current=false;};},[]);
  async function download(event){
    if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    event.preventDefault();if(pending.current)return;
    pending.current=true;setBusy(true);const session=downloadSession();
    try{onStart?.();await saveDownload(href,{isCurrent:()=>live.current});}
    catch(error){if(live.current&&session===downloadSession())onError?.(error);}
    finally{pending.current=false;if(live.current)setBusy(false);}
  }
  return <a className={'btn '+(primary?'primary':'secondary')} href={href} aria-disabled={busy||undefined} aria-busy={busy||undefined} onClick={download}>{busy?uiText('Preparing download…'):children}</a>;
}

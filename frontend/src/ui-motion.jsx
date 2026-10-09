import React,{useCallback,useRef,useState} from 'react';
import {flushSync} from 'react-dom';
import {Presence} from '@radix-ui/react-presence';
import {createMotionController} from './motion.mjs';

const update=createMotionController({
  host:typeof document==='undefined'?null:document,
  // Native snapshots briefly intercept clicks on rapidly changing pages. Shared
  // CSS region transitions keep navigation immediate and dialog overlays stable.
  nativeSnapshots:false,
  // Do not return an async action's promise: transitions must not wait for network requests.
  commit:change=>{flushSync(()=>{change();});},
  reveal:()=>{
    const dialog=document.querySelector('[role="dialog"][data-state="open"]');
    const region=dialog?.querySelector('.ui-dialog-body')||dialog||document.querySelector('#workspace');
    if(region)region.dataset.motionPhase=region.dataset.motionPhase==='one'?'two':'one';
  },
});

export function smoothUpdate(change){update(change);}

/** Keep the last content through its CSS exit; Radix removes it after the animation. */
export function MotionPresence({present,children}){
  const last=useRef(children);
  if(present)last.current=children;
  return <Presence present={present}>{React.cloneElement(last.current,{
    'data-state':present?'open':'closed','aria-hidden':!present,
  })}</Presence>;
}

/** For explicit visual changes only, not typing, polling or calculation state. */
export function useSmoothState(initial){
  const [value,setValue]=useState(initial);
  const latest=useRef(value);
  latest.current=value;
  const setSmooth=useCallback(next=>{
    if(typeof next!=='function'&&Object.is(next,latest.current))return;
    if(typeof next!=='function')latest.current=next;
    smoothUpdate(()=>setValue(next));
  },[]);
  return [value,setSmooth];
}

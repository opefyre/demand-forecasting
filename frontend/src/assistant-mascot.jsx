import React, {useEffect, useId, useRef} from 'react';

// Stable phase variation between instances, without timers or inline styling.
export function mascotRhythm(id){return [...id].reduce((hash,letter)=>(hash*31+letter.charCodeAt(0))%997,0)%3;}

/** Native vector motion: no video, frame swapping, timers or image downloads. */
export function AssistantMascot() {
  const id=useId().replace(/[^a-zA-Z0-9_-]/g,''), root=useRef(null);
  useEffect(()=>{
    const node=root.current;
    let visible=true;
    const update=()=>{node.dataset.motion=visible&&!document.hidden?'running':'paused';};
    const observer=typeof IntersectionObserver==='undefined'?null:new IntersectionObserver(([entry])=>{
      visible=entry.isIntersecting;update();
    });
    observer?.observe(node);document.addEventListener('visibilitychange',update);update();
    return ()=>{observer?.disconnect();document.removeEventListener('visibilitychange',update);};
  },[]);
  return <svg ref={root} className="ui-mascot" data-rhythm={mascotRhythm(id)} viewBox="0 0 100 100" aria-hidden="true" focusable="false">
    <defs>
      <radialGradient id={`${id}-body`} cx="34%" cy="27%" r="78%">
        <stop className="ui-mascot-light" offset="0"/>
        <stop className="ui-mascot-green" offset="0.6"/>
        <stop className="ui-mascot-shade" offset="1"/>
      </radialGradient>
      <linearGradient id={`${id}-limb`} x1="0" y1="0" x2="0.8" y2="1">
        <stop className="ui-mascot-green" offset="0"/>
        <stop className="ui-mascot-shade" offset="1"/>
      </linearGradient>
    </defs>
    <g className="ui-mascot-breathe">
      <g className="ui-mascot-feet" fill={`url(#${id}-limb)`}>
        <path d="M29 80 C24 85 24 93 32 93 C41 94 47 90 44 84 Z"/>
        <path d="M58 83 C54 88 59 94 68 93 C78 93 78 85 70 80 Z"/>
      </g>
      <path className="ui-mascot-hand-rest" fill={`url(#${id}-limb)`} d="M22 55 C17 58 9 66 10 73 C11 80 19 80 24 72 L29 61 Z"/>
      <path className="ui-mascot-hand-wave" fill={`url(#${id}-limb)`} d="M71 60 C80 56 81 48 83 43 C86 37 93 40 93 46 C94 57 87 66 76 70 Z"/>
      <path className="ui-mascot-body" fill={`url(#${id}-body)`} d="M35 9 C25 6 17 16 19 22 C21 27 28 24 29 20 C31 17 35 18 34 23 C33 27 30 29 27 33 C20 43 16 58 19 73 C21 86 35 89 53 88 C71 88 81 80 80 65 C79 42 71 31 57 23 C47 18 46 12 35 9 Z"/>
      <g className="ui-mascot-face">
        <g className="ui-mascot-eyes">
        <path className="ui-mascot-eye" d="M35 53 C36 50 38 49 40 49 C42 49 44 50 45 53 C45 55 43 55 42 53 C40 51 38 51 37 54 Z"/>
        <path className="ui-mascot-eye" transform="translate(20 -2)" d="M35 53 C36 50 38 49 40 49 C42 49 44 50 45 53 C45 55 43 55 42 53 C40 51 38 51 37 54 Z"/>
        </g>
        <path className="ui-mascot-smile" d="M45 60 C48 64 53 64 56 59"/>
      </g>
    </g>
  </svg>;
}

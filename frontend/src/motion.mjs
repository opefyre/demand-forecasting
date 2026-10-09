/** Progressive enhancement only. Every update runs once, even without browser motion support. */
export function createMotionController({host,commit,reveal=()=>{},nativeSnapshots=true}) {
  let active;
  return function update(change) {
    const canAnimate=host?.visibilityState==='visible' &&
      !host.defaultView?.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    // Browser snapshots render above all portals. Never snapshot the workspace
    // while a dialog is open: keep the overlay stable and animate its body only.
    if (!nativeSnapshots || !host?.startViewTransition || !canAnimate || host.querySelector?.('[role="dialog"][data-state="open"]')) {
      commit(change);
      if(canAnimate)reveal();
      return;
    }
    // Commit an older queued change before the newer one. Browser callbacks can
    // otherwise arrive out of order when users navigate rapidly.
    if(active){active.apply();active.transition.skipTransition();}
    let committed=false;
    const apply=()=>{if(!committed){committed=true;commit(change);}};
    try {
      const transition=host.startViewTransition(apply);
      const current={transition,apply};
      active=current;
      // A skipped or unsupported snapshot must never drop an operation or leak a rejection.
      transition.ready.catch(()=>{});
      transition.updateCallbackDone.catch(()=>{});
      transition.finished.catch(()=>{}).finally(()=>{if(active===current)active=null;});
    } catch(error) {
      if(committed)throw error;
      apply();
      reveal();
    }
  };
}

// Personal browser preferences/drafts must never carry into another company/user.
let prefix='';
export function workspaceContextKey(access){
  const user=access?.user;
  return JSON.stringify([access?.mode,user?.issuer,user?.company_id,user?.subject,user?.role,
    [...(user?.permissions||[])].sort()]);
}
export function configureWorkspaceStorage(access){
  prefix=access?.mode==='better_auth'
    ? 'demandlab:company:'+encodeURIComponent(JSON.stringify([access.user?.issuer,access.user?.company_id,access.user?.subject]))+':'
    : '';
}
export function scopedStorage(storage,namespace=''){
  return {getItem:key=>storage.getItem(namespace+key),setItem:(key,value)=>storage.setItem(namespace+key,value),
    removeItem:key=>storage.removeItem(namespace+key)};
}
function storage(kind){return {getItem:key=>globalThis[kind]?.getItem(prefix+key)??null,
  setItem:(key,value)=>globalThis[kind]?.setItem(prefix+key,value),removeItem:key=>globalThis[kind]?.removeItem(prefix+key)};}
export const localState=storage('localStorage');
export const sessionState=storage('sessionStorage');

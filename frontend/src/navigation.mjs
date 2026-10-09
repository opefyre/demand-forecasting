const pages=new Set(['today','demand','forecast','data','plans','settings','customers','help']);
const aliases=new Set(['new','assistant']);
export function workspacePage(value){
  if(value==='new')return 'demand';
  if(value==='assistant')return 'today';
  return pages.has(value)?value:'today';
}
export function workspaceRequest({pathname='/',hash=''}){
  const legacy=hash.slice(1);
  if(pages.has(legacy)||aliases.has(legacy))return legacy;
  return pathname.replace(/^\/+|\/+$/g,'');
}
export function workspacePath(value){return '/'+workspacePage(value);}
export function writeWorkspaceLocation(history,location,value,{replace=false,preserveSearch=false}={}){
  const path=workspacePath(value)+(preserveSearch?location.search||'':'');
  if(replace)history.replaceState(null,'',path);
  else if(location.pathname!==workspacePath(value)||location.hash||location.search)history.pushState(null,'',path);
}
